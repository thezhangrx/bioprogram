"""流程步骤服务：共享编排层 ``pipeline.steps`` 的只读列表 + 受控执行。

设计要点
--------
* **唯一定义源**：步骤、命令、依赖、产物全部来自 ``pipeline/steps.py``（向导与网页共用），
  本模块不复制任何命令拼装逻辑。
* **复用 Runtime**：执行走 ``training.submit_command``，因此流程步骤与训练共享同一 run 存储，
  ``/api/runs``、``/api/runs/<id>/log``（实时 print 文本）、cancel、resume 全部一致可用。
* **重任务标注**：``heavy=True`` 的步骤（网格训练、候选生成）会写入 models/results/logs，
  前端需二次确认；支持 ``dry_run`` 预览。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, training

_REPO = config.repo_root()
if str(_REPO) not in sys.path:          # 共享层位于仓库根目录的 pipeline/
    sys.path.insert(0, str(_REPO))

from pipeline import (  # noqa: E402  (路径注入后再导入)
    STEPS, PipelineContext, get_step, list_steps, resolve_order, step_status,
)

SCHEMA = "pipeline.run/1"

#: 允许前端覆盖的上下文字段（其余一律用服务端默认值）。
#: 注意：不再有 batch_name —— 用户选择的是一个**绝对输出目录** output_dir，
#: results/models/logs 由共享编排层在该目录下派生。
_CONTEXT_FIELDS = ("output_dir", "data_dir", "raw_data_dir", "feature_config", "batch_name")
# 注：batch_name 仅供命令行/调试与既有交付结果复核；Web 前端不提供该输入。
#: 允许透传的选项（键必须属于此白名单）
_OPTION_KEYS = ("models", "cell_lines", "split_types", "environments", "training_scope_epis",
                "epochs", "candidate_top_k", "target_input", "target_epigenetics",
                "ultimate_dir", "cv_folds", "seed", "device", "plots_dir", "analysis_plan")


def build_context(payload: Optional[Dict[str, Any]] = None) -> PipelineContext:
    """由请求载荷构造上下文；只接受白名单字段，路径一律要求绝对。"""
    payload = dict(payload or {})
    ctx_fields = {k: str(v) for k, v in payload.items() if k in _CONTEXT_FIELDS and v}
    for key in ("output_dir", "data_dir", "raw_data_dir", "feature_config"):
        val = ctx_fields.get(key)
        if val and not Path(val).expanduser().is_absolute():
            raise ValueError(f"{key} 必须是绝对路径（Web 端不做路径拼接）: {val!r}")
    options = {k: v for k, v in (payload.get("options") or {}).items() if k in _OPTION_KEYS}
    ctx = PipelineContext(repo_root=_REPO, options=options, **ctx_fields)
    ctx.validate()
    return ctx


def steps_payload(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """步骤清单 + 产物状态 + 拓扑顺序（只读，不执行任何命令）。"""
    ctx = build_context(payload)
    steps: List[Dict[str, Any]] = []
    for spec in STEPS:
        item = spec.as_dict(ctx)
        item.update(step_status(spec, ctx))
        item["ready"] = all(
            step_status(get_step(dep), ctx)["status"] == "completed" for dep in spec.requires)
        steps.append(item)
    return {
        "schema": SCHEMA,
        "context": ctx.as_dict(),
        "results_dir": str(ctx.results_path),
        "output_dir": str(ctx.output_root),
        "order": resolve_order([s.step_id for s in STEPS]),
        "steps": steps,
    }


def run(step_id: str, payload: Optional[Dict[str, Any]] = None,
        workspace_root: Optional[Path] = None) -> Dict[str, Any]:
    """执行一个步骤。

    * ``kind == "subprocess"`` → 通过 Runtime 提交子进程（返回 run manifest，含 run_id）
    * ``kind == "internal"``   → 进程内只读检查（无子进程、无 run_id）
    """
    payload = dict(payload or {})
    ctx = build_context(payload)
    spec = get_step(step_id)
    dry_run = bool(payload.get("dry_run"))

    if spec.kind == "internal":
        checks = [{"artifact": a["rel"], "path": a["path"], "exists": a["exists"]}
                  for a in spec.as_dict(ctx)["artifacts"]]
        ok = all(c["exists"] for c in checks) if checks else True
        return {"schema": SCHEMA, "step_id": step_id, "kind": "internal", "run_id": None,
                "status": "completed" if ok else "failed", "checks": checks,
                "message": "交付物齐全" if ok else "存在缺失交付物"}

    # ---- Device 策略：cpu 强制禁用 GPU；gpu -> cuda；cpu/gpu -> 交给脚本按模型自动选择 ----
    device_note = None
    cuda_visible = None
    if step_id in ("train_grid", "generate_candidates"):
        wanted = ctx.opt("device")
        if wanted:
            dev = training.resolve_device(wanted, ctx.opt("models"))
            device_note = dev["note"]
            if dev["cpu_only"]:
                cuda_visible = ""                       # CUDA_VISIBLE_DEVICES=""
                ctx.options["device"] = "cpu"
            elif dev["device"] == "gpu":
                ctx.options["device"] = "cuda"
            else:                                        # cpu/gpu：按模型自动
                ctx.options.pop("device", None)

    cmd = spec.build_command(ctx)
    manifest = training.submit_command(
        cmd, kind=f"pipeline_{step_id}", workspace_root=workspace_root,
        output_dir=str(ctx.output_root), dry_run=dry_run,
        extra={"schema": SCHEMA, "step_id": step_id, "step_title": spec.title,
               "heavy": spec.heavy, "category": spec.category,
               "device": ctx.opt("device") or "auto", "device_note": device_note,
               "context": ctx.as_dict()},
        device=ctx.opt("device"), cuda_visible=cuda_visible,
        batch_name=ctx.batch_name)
    return manifest
