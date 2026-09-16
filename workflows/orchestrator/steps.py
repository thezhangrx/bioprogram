"""共享编排层：把平台的全部可执行步骤定义为一个可复用的注册表。

设计约定（本轮修订）
--------------------
1. **前端不暴露 batch**：用户在前端选择的是一个**绝对输出目录** ``output_dir``，
   训练与分析的产物固定落在::

       <output_dir>/results/     ← 实验目录、summary（含分析引擎全部产物）
       <output_dir>/models/      ← 模型权重
       <output_dir>/logs/        ← 训练日志

   ``batch_name`` 仅作为**命令行/调试参数**保留（默认空 = 直接使用 results 目录本身），
   Web 端永不传该参数。
2. **一切以绝对路径为准**：所有传给子进程的路径参数（脚本、数据、输出、配置、目标文件、
   计划文件……）都由本模块解析为绝对路径；Web 侧不做任何路径字符串拼接。
3. 本模块**只描述与拼装命令**，不执行、不训练、不写结果。

调试::

    python -m pipeline list | check | order | command --step train_grid
"""
from __future__ import annotations


# --- 项目根引导: 保证从任意工作目录运行/被导入都能解析 core、analysis、workflows ---
import sys as _sys
from pathlib import Path as _Path
_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA = "pipeline.step/2"

CATEGORY_DATA = "data"
CATEGORY_TRAIN = "train"
CATEGORY_ANALYSIS = "analysis"
CATEGORY_DELIVERABLE = "deliverable"

DEFAULT_OUTPUT_DIRNAME = "output"


def _abs(p: Path | str, base: Optional[Path] = None) -> Path:
    """解析为绝对路径（相对路径一律相对 base，默认仓库根）。"""
    path = Path(p).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


@dataclass
class PipelineContext:
    """一次流程运行所需的**绝对**路径与选项。"""

    repo_root: Path
    output_dir: Optional[str] = None          # 用户选择的绝对输出根
    batch_name: Optional[str] = None          # 仅 CLI/调试：批次子目录名（前端不使用）
    data_set: Optional[str] = None            # 数据集名称（如 DeepCRISPR/Hiranniramol/Labuhn）
    data_dir: Optional[str] = None            # 特征数据目录（绝对，与 data_set 二选一）
    raw_data_dir: Optional[str] = None        # 原始数据目录（绝对）
    feature_config: Optional[str] = None      # 特征/Mapping 配置（绝对）
    python: str = field(default_factory=lambda: sys.executable)
    options: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.repo_root = _abs(self.repo_root)

    # ---------------- 派生绝对路径 ----------------
    @property
    def output_root(self) -> Path:
        return _abs(self.output_dir or (self.repo_root / DEFAULT_OUTPUT_DIRNAME), self.repo_root)

    @property
    def results_base(self) -> Path:
        """训练结果的根目录（绝对）：<output_dir>/results/batches（与仓库级约定一致）。"""
        return self.output_root / "results" / "batches"

    @property
    def results_path(self) -> Path:
        """实际使用的 results 目录：有 batch_name 时为其子目录（调试用），否则即 results 根。"""
        name = (self.batch_name or "").strip()
        return (self.results_base / name) if name else self.results_base

    @property
    def models_path(self) -> Path:
        return self.output_root / "models" / "weights"

    @property
    def logs_path(self) -> Path:
        return self.output_root / "results" / "logs"

    @property
    def data_path(self) -> Path:
        """已处理数据目录。

        优先 ``data_set``（按名称解析到 data/processed/<名称>）；
        其次 ``data_dir``（绝对路径）；都没有时取**第一个可用数据集**
        （数据驱动，不再固定回退到 data/processed——那里现在只是根目录）。
        """
        if self.data_set:
            from core.common.paths import resolve_dataset
            return resolve_dataset(self.data_set)
        if self.data_dir:
            return _abs(self.data_dir, self.repo_root)
        from core.common.paths import available_datasets
        names = available_datasets()
        if names:
            return self.repo_root / "data" / "processed" / names[0]
        return self.repo_root / "data" / "processed"

    @property
    def raw_data_path(self) -> Path:
        """原始数据目录：与所选数据集同名时用 data/raw/<名称>，否则用 data/raw 根。"""
        if self.raw_data_dir:
            return _abs(self.raw_data_dir, self.repo_root)
        base = self.repo_root / "data" / "raw"
        if self.data_set and (base / self.data_set).is_dir():
            return base / self.data_set
        return base

    @property
    def feature_config_path(self) -> Path:
        return _abs(self.feature_config or (self.repo_root / "data" / "feature_config.json"),
                    self.repo_root)

    @property
    def script_root(self) -> Path:
        return self.repo_root

    @property
    def batch_dir(self) -> Path:
        """兼容别名：无 batch 概念后即 results 目录。"""
        return self.results_path

    def opt(self, key: str, default: Any = None) -> Any:
        v = self.options.get(key, default)
        return default if v in (None, "", [], ()) else v

    def validate(self) -> None:
        """强制绝对路径约定。"""
        if self.batch_name and (("/" in self.batch_name) or ("\\" in self.batch_name)):
            raise ValueError(f"batch_name 不能包含路径分隔符: {self.batch_name!r}")
        for name, value in (("output_dir", self.output_dir), ("data_dir", self.data_dir),
                            ("raw_data_dir", self.raw_data_dir),
                            ("feature_config", self.feature_config)):
            if value and not Path(value).expanduser().is_absolute():
                raise ValueError(f"{name} 必须是绝对路径（收到: {value!r}）")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "output_dir": str(self.output_root),
            "results_dir": str(self.results_path),
            "results_base": str(self.results_base),
            "batch_name": self.batch_name or "",
            "model_dir": str(self.models_path),
            "logs_dir": str(self.logs_path),
            "data_set": self.data_set or "",
            "data_dir": str(self.data_path),
            "raw_data_dir": str(self.raw_data_path),
            "feature_config": str(self.feature_config_path),
            "options": dict(self.options),
        }

    @classmethod
    def from_dict(cls, repo_root: Path, d: Dict[str, Any] | None = None) -> "PipelineContext":
        d = dict(d or {})
        options = d.pop("options", {}) or {}
        known = {k: (v if v != "" else None)
                 for k, v in d.items() if k in cls.__dataclass_fields__ and k != "repo_root"}
        return cls(repo_root=repo_root, options=options, **known)


# --------------------------------------------------------------------------- #
# 助手
# --------------------------------------------------------------------------- #
def _script(ctx: PipelineContext, rel: str) -> str:
    return str(_abs(ctx.script_root / rel))


def _opt_path(ctx: PipelineContext, value: str) -> str:
    return str(_abs(value, ctx.repo_root))


def _append(cmd: List[str], flag: str, values: Optional[Iterable[Any]]) -> None:
    if values:
        cmd += [flag, *[str(v) for v in values]]


# --------------------------------------------------------------------------- #
# 步骤定义
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StepSpec:
    step_id: str
    title: str
    category: str
    heavy: bool
    requires: Tuple[str, ...]
    artifacts: Tuple[str, ...]           # "@repo:"/"@data:" 前缀；其余 = 输出 results 目录相对
    description: str
    kind: str = "subprocess"
    cli_script: Optional[str] = None
    cli_flags: Tuple[str, ...] = ()

    def build_command(self, ctx: PipelineContext) -> List[str]:
        if self.kind == "internal":
            return []
        return _BUILDERS[self.step_id](ctx)

    def artifact_paths(self, ctx: PipelineContext) -> List[Path]:
        """解析产物路径。

        前缀约定：
          ``@repo:``   仓库根相对
          ``@data:``   特征数据目录相对
          ``@output:`` 输出根目录相对（如 analysis/…）
          ``@glob:``   results 目录下的 glob（命中任意一个即视为完成，用于训练这类一次产生多份产物的步骤）
          其他          results 目录相对
        """
        out: List[Path] = []
        for rel in self.artifacts:
            if rel.startswith("@repo:"):
                out.append(ctx.repo_root / rel[len("@repo:"):])
            elif rel.startswith("@data:"):
                out.append(ctx.data_path / rel[len("@data:"):])
            elif rel.startswith("@output:"):
                out.append(ctx.output_root / rel[len("@output:"):])
            elif rel.startswith("@glob:"):
                pattern = rel[len("@glob:"):]
                matches = sorted(ctx.results_path.glob(pattern))
                if matches:
                    out.extend(matches[:5])
                else:                       # 未命中：返回模式本身（用于展示/诊断）
                    out.append(ctx.results_path / pattern.lstrip("*/"))
            elif Path(rel).is_absolute():
                out.append(Path(rel))
            else:
                out.append(ctx.results_path / rel)
        return out

    def preview(self, ctx: PipelineContext) -> str:
        cmd = self.build_command(ctx)
        return " ".join(cmd) if cmd else "(内部检查步骤，无子进程命令)"

    def as_dict(self, ctx: PipelineContext) -> Dict[str, Any]:
        arts = []
        for rel, p in zip(self.artifacts, self.artifact_paths(ctx)):
            try:
                exists, size = p.exists(), (p.stat().st_size if p.is_file() else 0)
            except OSError:
                exists, size = False, 0
            arts.append({"rel": rel, "path": str(p), "exists": exists, "size": size})
        return {
            "schema": SCHEMA, "step_id": self.step_id, "title": self.title,
            "category": self.category, "heavy": self.heavy, "requires": list(self.requires),
            "description": self.description, "kind": self.kind,
            "artifacts": arts, "command": self.preview(ctx),
        }


# ---- 命令构造（全绝对路径、无 batch 名） ---------------------------------- #
def _cmd_feature_engineering(ctx: PipelineContext) -> List[str]:
    return [ctx.python, _script(ctx, "core/features/engineering/feature_engineering.py"),
            "--source-dir", str(ctx.raw_data_path),
            "--output-dir", str(ctx.data_path),
            "--config", str(ctx.feature_config_path)]


def _cmd_train_grid(ctx: PipelineContext) -> List[str]:
    cmd = [ctx.python, _script(ctx, "workflows/training/data_digging.py"),
           "--data-dir", str(ctx.data_path),
           "--model-dir", str(ctx.models_path),
           "--results-dir", str(ctx.results_base),
           "--logs-dir", str(ctx.logs_path)]
    if ctx.batch_name:
        cmd += ["--batch-name", str(ctx.batch_name)]
    _append(cmd, "--models", ctx.opt("models"))
    _append(cmd, "--cell-lines", ctx.opt("cell_lines"))
    _append(cmd, "--split-types", ctx.opt("split_types"))
    _append(cmd, "--environments", ctx.opt("environments"))
    _append(cmd, "--training-scope-epis", ctx.opt("training_scope_epis"))
    if ctx.opt("epochs") is not None:
        cmd += ["--epochs", str(ctx.opt("epochs"))]
    if ctx.opt("device"):
        cmd += ["--device", str(ctx.opt("device"))]
    if ctx.opt("dry_run", False):
        cmd.append("--dry-run")
    return cmd


def _cmd_generate_candidates(ctx: PipelineContext) -> List[str]:
    cmd = [ctx.python, _script(ctx, "workflows/prediction/predict.py"), "--generate-candidates",
           "--data-dir", str(ctx.data_path),
           "--results-dir", str(ctx.results_base)]
    if ctx.batch_name:
        cmd += ["--batch-name", str(ctx.batch_name)]
    _append(cmd, "--models", ctx.opt("models"))
    _append(cmd, "--cell-lines", ctx.opt("cell_lines"))
    if ctx.opt("candidate_top_k") is not None:
        cmd += ["--candidate-top-k", str(ctx.opt("candidate_top_k"))]
    if ctx.opt("target_input"):
        cmd += ["--target-input", _opt_path(ctx, str(ctx.opt("target_input")))]
    _append(cmd, "--target-epigenetics", ctx.opt("target_epigenetics"))
    if ctx.opt("ultimate_dir"):
        cmd += ["--ultimate-dir", _opt_path(ctx, str(ctx.opt("ultimate_dir")))]
    for flag, key in (("--ultimate-cv-folds", "cv_folds"), ("--ultimate-epochs", "epochs"),
                      ("--ultimate-seed", "seed")):
        if ctx.opt(key) is not None:
            cmd += [flag, str(ctx.opt(key))]
    if ctx.opt("device"):
        cmd += ["--device", str(ctx.opt("device"))]
    if ctx.opt("dry_run", False):
        cmd.append("--dry-run")
    return cmd


def _cmd_collect_results(ctx: PipelineContext) -> List[str]:
    cmd = [ctx.python, _script(ctx, "analysis/collect_results.py"),
           "--batch-dir", str(ctx.results_path)]
    _append(cmd, "--split-types", ctx.opt("split_types"))
    return cmd


def _cmd_anomaly_treatment(ctx: PipelineContext) -> List[str]:
    return [ctx.python, _script(ctx, "analysis/anomaly_treatment.py"),
            "--batch-dir", str(ctx.results_path)]


def _cmd_importance_extraction(ctx: PipelineContext) -> List[str]:
    return [ctx.python, _script(ctx, "analysis/importance_extraction.py"),
            "--batch_dir", str(ctx.results_path)]


def _cmd_legacy_visualization(ctx: PipelineContext) -> List[str]:
    cmd = [ctx.python, _script(ctx, "analysis/panorama.py"),
           "--batch-dir", str(ctx.results_path)]
    cmd += ["--output-dir", str(_abs(ctx.opt("plots_dir") or (ctx.results_path / "summary" / "plots"),
                                     ctx.repo_root))]
    return cmd


def _cmd_analysis_engine(ctx: PipelineContext) -> List[str]:
    cmd = [ctx.python, "-m", "analysis.pipeline", "--batch-dir", str(ctx.results_path),
           "--output", str(ctx.output_root / "analysis")]
    if ctx.opt("analysis_plan"):
        cmd += ["--analysis-plan", _opt_path(ctx, str(ctx.opt("analysis_plan")))]
    return cmd


_BUILDERS = {
    "feature_engineering": _cmd_feature_engineering,
    "train_grid": _cmd_train_grid,
    "generate_candidates": _cmd_generate_candidates,
    "collect_results": _cmd_collect_results,
    "anomaly_treatment": _cmd_anomaly_treatment,
    "importance_extraction": _cmd_importance_extraction,
    "legacy_visualization": _cmd_legacy_visualization,
    "analysis_engine": _cmd_analysis_engine,
}

STEPS: Tuple[StepSpec, ...] = (
    StepSpec(step_id="feature_engineering", title="特征工程（序列+表观张量 + schema）",
             category=CATEGORY_DATA, heavy=False, requires=(),
             artifacts=("@data:feature_schema.json",),
             description="按用户 Mapping 配置由原始 CSV 生成 (23×通道) 张量与 feature_schema.json；"
                    "通道数由所选表观特征决定（纯序列 = 23×4 / 92 维）。",
             cli_script="core/features/engineering/feature_engineering.py"),
    StepSpec(step_id="train_grid", title="受控网格训练（data_digging.py）",
             category=CATEGORY_TRAIN, heavy=True, requires=("feature_engineering",),
             artifacts=("@glob:*/*_metrics.json",),
             description="多模型 × 多环境 × 多划分 × 多种子受控实验；权重写入 <输出目录>/models/weights，日志写入 <输出目录>/results/logs。",
             cli_script="workflows/training/data_digging.py"),
    StepSpec(step_id="generate_candidates", title="候选生成与优先级排序（predict.py）",
             category=CATEGORY_TRAIN, heavy=True, requires=("feature_engineering",),
             artifacts=("summary/赛道二_results.csv",),
             description="mixed 十折 CV + 候选打分排序，输出官方候选清单。",
             cli_script="workflows/prediction/predict.py"),
    StepSpec(step_id="collect_results", title="指标汇总（collect_results.py）",
             category=CATEGORY_ANALYSIS, heavy=False, requires=("train_grid",),
             artifacts=("summary/metrics_tables/all_experiments.csv",),
             description="扫描实验目录生成统一指标表。",
             cli_script="analysis/collect_results.py"),
    StepSpec(step_id="anomaly_treatment", title="异常实验检测（anomaly_treatment.py）",
             category=CATEGORY_ANALYSIS, heavy=False, requires=("train_grid",),
             artifacts=("summary/anomaly_report.md",),
             description="两级异常检测与治疗报告（标记而不删除）。",
             cli_script="analysis/anomaly_treatment.py"),
    StepSpec(step_id="importance_extraction", title="关键调控特征库（importance_extraction.py）",
             category=CATEGORY_DELIVERABLE, heavy=False, requires=("train_grid",),
             artifacts=("summary/feature_importance/key_regulatory_biomarkers.csv",
                        "summary/feature_importance"),
             description="各模型重要性/稳健性报告与 key_regulatory_biomarkers.csv（官方交付物）。",
             cli_script="analysis/importance_extraction.py"),
    StepSpec(step_id="legacy_visualization", title="全景图（panorama.py）",
             category=CATEGORY_ANALYSIS, heavy=False, requires=("train_grid",),
             artifacts=("summary/plots",),
             description="23 nt 位置热图、环境增量树、表观因子对比等全景图。",
             cli_script="analysis/panorama.py"),
    StepSpec(step_id="analysis_engine", title="分析引擎（analysis.pipeline：统计/证据/报告/图表）",
             category=CATEGORY_ANALYSIS, heavy=False, requires=("train_grid",),
             artifacts=("summary/analysis_status.json", "summary/reports", "summary/figures"),
             description="配对 bootstrap、置换、BH-FDR、区组 ANOVA、motif 发现、证据整合与报告。",
             cli_script="analysis/pipeline.py"),
    StepSpec(step_id="deliverables_check", title="交付物核对",
             category=CATEGORY_DELIVERABLE, heavy=False,
             requires=("importance_extraction", "generate_candidates"),
             artifacts=("summary/赛道二_results.csv",
                        "summary/feature_importance/key_regulatory_biomarkers.csv"),
             description="核对官方交付物是否齐全（只读检查）。", kind="internal"),
)

STEP_INDEX: Dict[str, StepSpec] = {s.step_id: s for s in STEPS}


def get_step(step_id: str) -> StepSpec:
    try:
        return STEP_INDEX[step_id]
    except KeyError as exc:  # pragma: no cover
        raise KeyError(f"unknown pipeline step: {step_id} (known: {', '.join(STEP_INDEX)})") from exc


def list_steps(ctx: PipelineContext) -> List[Dict[str, Any]]:
    return [s.as_dict(ctx) for s in STEPS]


def resolve_order(step_ids: Sequence[str]) -> List[str]:
    wanted: List[str] = []

    def visit(sid: str) -> None:
        if sid in wanted:
            return
        for dep in get_step(sid).requires:
            visit(dep)
        wanted.append(sid)

    for sid in step_ids:
        visit(sid)
    return wanted


def step_status(spec: StepSpec, ctx: PipelineContext) -> Dict[str, Any]:
    arts = [{"rel": rel, "path": str(p), "exists": p.exists()}
            for rel, p in zip(spec.artifacts, spec.artifact_paths(ctx))]
    n_ok = sum(1 for a in arts if a["exists"])
    status = "completed" if arts and n_ok == len(arts) else ("partial" if n_ok else "pending")
    return {"step_id": spec.step_id, "status": status, "artifacts": arts}


def build_command(step_id: str, ctx: PipelineContext) -> List[str]:
    ctx.validate()
    return get_step(step_id).build_command(ctx)


# --------------------------------------------------------------------------- #
# 调试用 CLI
# --------------------------------------------------------------------------- #
def _main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="共享编排层：步骤注册表（只读，不执行）")
    ap.add_argument("action", choices=["list", "command", "order", "check", "context"])
    ap.add_argument("--step", action="append", default=[])
    ap.add_argument("--repo-root", default=str(_PROJECT_ROOT))
    ap.add_argument("--output-dir", default="")
    ap.add_argument("--batch-name", default="", help="仅调试：批次子目录名（Web 前端不使用）")
    ap.add_argument("--data-set", "--data_set", "--dataset", dest="data_set", default="",
                    help="数据集名称，如 DeepCRISPR / Hiranniramol / Labuhn")
    ap.add_argument("--data-dir", default="")
    a = ap.parse_args(argv)
    ctx = PipelineContext(repo_root=Path(a.repo_root),
                          output_dir=a.output_dir or None,
                          batch_name=a.batch_name or None,
                          data_set=a.data_set or None,
                          data_dir=a.data_dir or None)
    if a.action == "context":
        print(json.dumps(ctx.as_dict(), ensure_ascii=False, indent=2)); return 0
    if a.action == "list":
        for s in list_steps(ctx):
            print(f"{s['step_id']:<22} [{s['category']:<11} {'heavy' if s['heavy'] else 'light':<5}] {s['title']}")
        return 0
    if a.action == "order":
        for sid in resolve_order(a.step or [s.step_id for s in STEPS]):
            print(sid)
        return 0
    if a.action == "command":
        if not a.step:
            print("--step required", file=sys.stderr); return 2
        for sid in a.step:
            print(json.dumps({"step_id": sid, "command": get_step(sid).build_command(ctx)},
                             ensure_ascii=False))
        return 0
    for s in STEPS:
        st = step_status(s, ctx)
        print(f"{st['step_id']:<22} {st['status']:<10} "
              + ", ".join(("✓" if x["exists"] else "✗") + Path(x["path"]).name for x in st["artifacts"]))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
