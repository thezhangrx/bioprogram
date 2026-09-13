"""Training / Runtime Adapter 接口。

只做编排: TrainingConfig(仅训练系统现有参数) -> Validate -> Preflight -> Submit
-> 状态监控 (training_status.json 落盘, GUI 关闭任务继续) -> Cancel/Resume。
绝不 import/修改训练代码; 科学执行 = 子进程调用现有 CLI:
    data_digging.py  (已测数据 Training Scope 网格挖掘)
    predict.py       (mixed 十折 CV + 目标预测)
HPC: 本包不实现 Slurm/CUDA; HpcAdapter 生成可提交的启动脚本/命令,
     状态由 job 侧回写 training_status.json 或 run 日志解析 (GUI 不绑定任务进程)。
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config, store

# 与现有 CLI choices 一致的参数面 (仅展示/校验现有支持项)
MODELS = ["linear", "xgboost", "mlp", "transformer", "cnn"]
CELL_LINES = ["hct116", "hek293t", "hela", "hl60"]
SPLITS = ["single", "all", "mixed"]
KERNELS = [3, 5, 7]
MIXED_SEEDS = [42, 43, 44, 45]

STATUS_FILE = "training_status.json"
DONE_FILE = "done.rc"


@dataclass
class TrainingConfig:
    """Training 配置 (与 data_digging/predict CLI 一一对应, 不发明新超参)。"""

    kind: str = "dig"            # dig | predict
    models: List[str] = field(default_factory=lambda: ["linear", "xgboost"])
    cell_lines: List[str] = field(default_factory=lambda: CELL_LINES)
    split_types: List[str] = field(default_factory=lambda: ["single"])
    environments: Optional[List[str]] = None       # 显式组合
    training_scope_epis: Optional[List[str]] = None  # 或由向导选项2自动展开
    mixed_seeds: List[int] = field(default_factory=lambda: MIXED_SEEDS)
    cnn_kernels: List[int] = field(default_factory=lambda: KERNELS)

    # 超参 (与训练 CLI 默认一致; 改动会改变结果, 仅在用户明确要偏离基准时设置)
    epochs: int = 100
    batch_size: int = 64
    learning_rate: float = 1e-3
    dropout: float = 0.2
    weight_decay: float = 0.0
    patience: int = 20
    min_delta: float = 1e-6
    hidden_dim1: int = 128
    hidden_dim2: int = 64
    conv_channels1: int = 32
    conv_channels2: int = 64
    train_ratio: float = 0.70
    valid_ratio: float = 0.15
    test_ratio: float = 0.15
    use_scaler: bool = False

    # 目录/批次 (跨平台: 由后端解析为绝对路径, 前端只传相对/逻辑值)
    data_dir: str = ""
    results_dir: str = ""
    model_dir: str = ""
    logs_dir: str = ""
    batch_name: str = ""

    # Runtime
    runtime: str = "local_cpu"     # local_cpu | local_gpu | hpc
    device: Optional[str] = None
    workers: int = 1
    in_process: bool = True
    threads_per_worker: int = 0
    cuda_visible: Optional[str] = None   # 由 Runtime 管理, 非前端硬编码

    # predict (kind=predict) 专用
    target_input: str = ""
    target_epigenetics: Optional[List[str]] = None
    ultimate_cv_folds: int = 10
    ultimate_epochs: int = 15
    ultimate_seed: int = 42
    candidate_top_k: int = 20

    # 工具选项
    dry_run: bool = False          # 只生成计划/命令, 不真正启动 (冒烟/预检用)

    def default_dirs(self) -> None:
        repo = config.repo_root()
        if not self.data_dir:
            self.data_dir = str(repo / "data" / "proceeded_data")
        if not self.results_dir:
            self.results_dir = str(repo / "results")
        if not self.model_dir:
            self.model_dir = str(repo / "models")
        if not self.logs_dir:
            self.logs_dir = str(repo / "logs")

    @classmethod
    def from_dict(cls, d: Dict) -> "TrainingConfig":
        from dataclasses import fields
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        return cls(**kw)

    # ---- 校验 ------------------------------------------------------------
    def validate(self) -> List[str]:
        errs = []
        if not self.models or not all(m in MODELS for m in self.models):
            errs.append(f"models 须属于 {MODELS}")
        if not self.cell_lines or not all(c in CELL_LINES for c in self.cell_lines):
            errs.append(f"cell_lines 须属于 {CELL_LINES}")
        if not self.split_types or not all(s in SPLITS for s in self.split_types):
            errs.append(f"split_types 须属于 {SPLITS}")
        if self.runtime not in ("local_cpu", "local_gpu", "hpc"):
            errs.append("runtime 须为 local_cpu/local_gpu/hpc")
        if self.kind == "predict":
            if self.target_input and not Path(self.target_input).exists():
                errs.append(f"target_input 不存在: {self.target_input}")
        return errs

    # ---- CLI 构建 (唯一允许的“控制训练”通道) -------------------------------
    def build_command(self) -> List[str]:
        self.default_dirs()
        if self.kind == "predict":
            return self._predict_command()
        return self._dig_command()

    def _base(self, script: str) -> List[str]:
        return [sys.executable, str(config.repo_root() / script)]

    def _dig_command(self) -> List[str]:
        cmd = self._base("data_digging.py")
        cmd += ["--batch-name", self.batch_name]
        cmd += ["--data-dir", self.data_dir, "--model-dir", self.model_dir,
                "--results-dir", self.results_dir, "--logs-dir", self.logs_dir]
        cmd += ["--models", *self.models]
        cmd += ["--cell-lines", *self.cell_lines]
        cmd += ["--split-types", *self.split_types]
        if self.training_scope_epis:
            cmd += ["--training-scope-epis", *self.training_scope_epis]
        elif self.environments:
            cmd += ["--environments", *self.environments]
        cmd += ["--epochs", str(self.epochs), "--batch-size", str(self.batch_size),
                "--learning-rate", str(self.learning_rate), "--dropout", str(self.dropout),
                "--weight-decay", str(self.weight_decay), "--patience", str(self.patience),
                "--min-delta", str(self.min_delta),
                "--hidden-dim1", str(self.hidden_dim1), "--hidden-dim2", str(self.hidden_dim2),
                "--conv-channels1", str(self.conv_channels1), "--conv-channels2", str(self.conv_channels2)]
        if self.use_scaler:
            cmd.append("--use-scaler")
        if self.in_process:
            cmd.append("--in-process")
        if self.workers > 1:
            cmd += ["--workers", str(self.workers)]
            if self.threads_per_worker > 0:
                cmd += ["--threads-per-worker", str(self.threads_per_worker)]
        if self.device:
            cmd += ["--device", self.device]
        if self.dry_run:
            cmd.append("--dry-run")
        return cmd

    def _predict_command(self) -> List[str]:
        cmd = self._base("predict.py")
        cmd += ["--data-dir", self.data_dir, "--results-dir", self.results_dir,
                "--batch-name", self.batch_name]
        cmd += ["--models", *self.models]
        cmd += ["--cell-lines", *self.cell_lines]
        cmd += ["--ultimate-cv-folds", str(self.ultimate_cv_folds),
                "--ultimate-epochs", str(self.ultimate_epochs),
                "--ultimate-seed", str(self.ultimate_seed),
                "--candidate-top-k", str(self.candidate_top_k)]
        if self.target_input:
            cmd += ["--target-input", self.target_input]
        if self.target_epigenetics:
            cmd += ["--target-epigenetics", *self.target_epigenetics]
        if self.device:
            cmd += ["--device", self.device]
        if self.dry_run:
            cmd.append("--dry-run")
        return cmd


def preflight(cfg: TrainingConfig) -> Dict:
    """运行前检查: 数据集/QC/输出可写/runtime 可用/配置有效。"""
    checks: List[Dict] = []
    ok = True

    def add(name: str, passed: bool, msg: str) -> None:
        nonlocal ok
        if not passed:
            ok = False
        checks.append({"check": name, "ok": passed, "message": msg})

    cfg.default_dirs()
    data = Path(cfg.data_dir)
    add("Dataset exists", data.exists() and (data / "feature_schema.json").exists()
        or any(data.glob("*_features_*.npy")),
        f"data_dir={cfg.data_dir}")
    for d, label in ((cfg.results_dir, "results"), (cfg.model_dir, "models"),
                     (cfg.logs_dir, "logs")):
        p = Path(d)
        writable = False
        try:
            p.mkdir(parents=True, exist_ok=True)
            writable = os.access(p, os.W_OK)
        except OSError:
            writable = False
        add(f"Output writable ({label})", writable, f"{d}")
    errs = cfg.validate()
    add("Training configuration valid", not errs, "; ".join(errs) or "ok")
    add("Runtime available", True, cfg.runtime)  # 真实可用性由 Runtime Adapter 探测
    if cfg.kind == "predict" and cfg.target_input:
        add("Target input exists", Path(cfg.target_input).exists(), cfg.target_input)
    return {"ok": ok, "checks": checks}


# ---------------------------------------------------------------------------
# Device 策略 (前端只显示 cpu / gpu, 不暴露 hpc)
# ---------------------------------------------------------------------------
CPU_ONLY_MODELS = {"linear", "xgboost"}          # 仅 CPU 可跑 (树/线性实现)
GPU_CAPABLE_MODELS = {"mlp", "cnn", "transformer"}  # 支持 GPU


def device_policy(models: Optional[List[str]]) -> Dict[str, Any]:
    """按勾选模型给出可用 Device 列表。

    规则（与前端联动，后端同样校验）：
      * 只勾 LR/XGBoost, 不勾深度模型      -> 只能 cpu
      * 只勾深度模型, 不勾 LR/XGBoost      -> cpu 或 gpu
      * 两类都勾（混杂）                   -> cpu 或 cpu/gpu（同一批次按模型分别落设备）
    """
    ms = {str(m).lower() for m in (models or [])}
    only_cpu = bool(ms) and ms <= CPU_ONLY_MODELS
    only_gpu_capable = bool(ms) and ms <= GPU_CAPABLE_MODELS
    if only_cpu:
        return {"allowed": ["cpu"], "locked": True, "cpu_only": True,
                "note": "所选模型（线性/树模型）仅在 CPU 上实现，Device 锁定为 cpu。"}
    if only_gpu_capable:
        return {"allowed": ["cpu", "gpu"], "locked": False, "cpu_only": False,
                "note": "所选深度模型支持 GPU 加速；也可选择 cpu 强制不使用 GPU。"}
    return {"allowed": ["cpu", "cpu/gpu"], "locked": False, "cpu_only": False,
            "note": "混合模型：cpu 表示全部用 CPU；cpu/gpu 表示深度模型用 GPU、树/线性模型用 CPU。"}


def resolve_device(device: Optional[str], models: Optional[List[str]]) -> Dict[str, Any]:
    """校验并归一化 device 选择；返回 {device, cuda_visible, cpu_only, note}。"""
    pol = device_policy(models)
    dev = (device or "").strip().lower()
    if not dev:
        dev = pol["allowed"][0]
    if dev not in pol["allowed"]:
        raise ValueError(f"device={dev!r} 不被允许（可选: {', '.join(pol['allowed'])}）; {pol['note']}")
    cpu_only = dev == "cpu"
    return {"device": dev, "cpu_only": cpu_only,
            "cuda_visible": "" if cpu_only else None,   # "" -> 强制无 GPU
            "note": pol["note"]}


# ---------------------------------------------------------------------------
# Runtime Adapter (Local / HPC)
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_id(kind: str) -> str:
    return datetime.now().strftime(f"{kind}_%Y%m%d_%H%M%S")


def _process_alive(pid: int) -> bool:
    """进程是否仍在运行。

    修复要点：子进程结束但父进程未 wait() 时会成为**僵尸**，此时 ``os.kill(pid, 0)``
    仍然成功，导致运行状态永远停留在 running。这里额外检查 /proc/<pid>/stat 的状态位
    （Z = 僵尸 → 视为已退出），非 Linux 平台回退为 kill(0) 的结果。
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        state = stat.rsplit(")", 1)[1].split()[0]
        return state != "Z"
    except (OSError, IndexError):
        return True


def _write_done_file(done: Path, rc: int) -> None:
    try:
        done.write_text(str(rc), encoding="utf-8")
    except OSError:
        pass


class LocalRuntime:
    """本地 (CPU/GPU) 执行: 独立子进程, 与 GUI 生命周期解耦。"""

    def __init__(self, workspace_root: Path):
        self.runs_dir = workspace_root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, cfg: TrainingConfig) -> Dict:
        cfg.default_dirs()
        return self.submit_raw(
            cmd=cfg.build_command(), kind=cfg.kind, batch_name=cfg.batch_name,
            runtime=cfg.runtime, device=cfg.device, dry_run=cfg.dry_run,
            extra={"config": asdict(cfg)},
            plan_payload=asdict(cfg) if cfg.dry_run else None,
            cuda_visible=cfg.cuda_visible)

    def submit_raw(self, cmd: List[str], kind: str, batch_name: str = "",
                   runtime: str = "local_cpu", device: Optional[str] = None,
                   dry_run: bool = False, extra: Optional[Dict] = None,
                   plan_payload: Optional[Dict] = None,
                   cuda_visible: Optional[str] = None,
                   run_id: Optional[str] = None) -> Dict:
        """通用提交：任意子进程命令复用同一 run 目录/状态/日志/cancel 机制。

        训练与流程步骤（feature_engineering / collect_results / analyse.pipeline ...）共用，
        因此 ``/api/runs``、``/api/runs/<id>/log``、cancel、resume 对所有步骤一致可用。
        """
        rid = run_id or _run_id(kind)
        rdir = self.runs_dir / rid
        rdir.mkdir(parents=True, exist_ok=True)
        st = {
            "run_id": rid,
            "kind": kind,
            "schema": "training.status/1",
            "status": "dry-run" if dry_run else "running",
            "runtime": runtime,
            "device": device,
            "batch_name": batch_name,
            "started_at": _now(),
            "command": " ".join(cmd),
            "cwd": str(config.repo_root()),
            "pid": None,
            "job_id": None,
            "progress": {"done": 0, "total": None, "ratio": None},
            "log_path": str(rdir / "run.log"),
            "done_file": str(rdir / DONE_FILE),
        }
        if extra:
            st.update(extra)
        store.write_json(rdir / STATUS_FILE, st)
        if dry_run:
            (rdir / "plan.json").write_text(
                json.dumps(plan_payload or {"command": cmd}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            return st
        env = os.environ.copy()
        if cuda_visible:
            env["CUDA_VISIBLE_DEVICES"] = cuda_visible
        logf = open(rdir / "run.log", "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(config.repo_root()), env=env,
                                stdout=logf, stderr=subprocess.STDOUT,
                                start_new_session=True)
        st["pid"] = proc.pid
        logf.close()
        store.write_json(rdir / STATUS_FILE, st)

        done_file = rdir / DONE_FILE

        def _reap() -> None:
            rc = proc.wait()
            _write_done_file(done_file, rc)

        threading.Thread(target=_reap, name=f"reap-{rid}", daemon=True).start()
        return st

    def status(self, rid: str) -> Dict:
        rdir = self.runs_dir / rid
        st = store.read_json(rdir / STATUS_FILE)
        if st is None:
            raise FileNotFoundError(f"run not found: {rid}")
        self._update_status(rdir, st)
        return st

    def _update_status(self, rdir: Path, st: Dict) -> None:
        done = rdir / DONE_FILE
        log_path = rdir / "run.log"
        if done.exists():
            rc = int(done.read_text().strip() or "0")
            st["status"] = "completed" if rc == 0 else "failed"
            st["returncode"] = rc
            st["ended_at"] = _now()
        elif st.get("pid"):
            if not _process_alive(int(st["pid"])):
                # 进程已退出但无 done 标记 (如服务重启): 由日志兜底判定
                st["status"] = self._guess_from_log(log_path)
        self._progress_from_log(log_path, st)
        store.write_json(rdir / STATUS_FILE, st)

    def _guess_from_log(self, log_path: Path) -> str:
        if not log_path.exists():
            return "running"
        text = log_path.read_text(encoding="utf-8", errors="replace")
        if "[✓] All batch experiments executed." in text or "赛道二_results.csv" in text:
            return "completed"
        return "failed"

    @staticmethod
    def _progress_from_log(log_path: Path, st: Dict) -> None:
        if not log_path.exists():
            return
        text = log_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"Total:\s*(\d+)", text)
        m2 = re.findall(r"Experiment\s+(\d+)/(\d+)\] Starting", text)
        total = int(m.group(1)) if m else None
        done = 0
        if m2:
            done = max(int(a) for a, _ in m2)
            if total is None:
                total = max(int(b) for _, b in m2)
        st["progress"] = {"done": done, "total": total,
                          "ratio": (done / total) if total else None}

    def cancel(self, rid: str) -> Dict:
        rdir = self.runs_dir / rid
        st = store.read_json(rdir / STATUS_FILE)
        if st is None:
            raise FileNotFoundError(f"run not found: {rid}")
        pid = st.get("pid")
        if pid:
            try:
                os.killpg(int(pid), signal.SIGTERM)  # 由 Adapter 处理, 不直接 kill 任意进程
            except (OSError, ProcessLookupError):
                pass
        st["status"] = "cancelled"
        st["cancelled_at"] = _now()
        store.write_json(rdir / STATUS_FILE, st)
        return st

    def resume(self, rid: str) -> Dict:
        """Resume = 以相同命令重跑 (data_digging 自带断点续跑 completed 判定)。"""
        rdir = self.runs_dir / rid
        st = store.read_json(rdir / STATUS_FILE)
        if st is None:
            raise FileNotFoundError(f"run not found: {rid}")
        if (rdir / DONE_FILE).exists():
            (rdir / DONE_FILE).unlink()
        cfg = TrainingConfig(**json.loads((rdir / "config.json").read_text(encoding="utf-8")))
        return self.submit(cfg)


class HpcRuntime:
    """HPC Adapter: 不实现 Slurm/CUDA。生成可提交脚本 + 记录 job 回写约定。

    状态来源 (按优先级): training_status.json (job 侧回写) -> 用户提交后置
    'submitted_external'; GUI 关闭不影响任务。
    """

    def __init__(self, workspace_root: Path):
        self.runs_dir = workspace_root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, cfg: TrainingConfig) -> Dict:
        cfg.default_dirs()
        rid = _run_id(cfg.kind)
        rdir = self.runs_dir / rid
        rdir.mkdir(parents=True, exist_ok=True)
        cmd = cfg.build_command()
        # 保存配置供 resume / 回写
        (rdir / "config.json").write_text(
            json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
        launcher = rdir / "submit.sh"
        lines = ["#!/usr/bin/env bash",
                 "# 由 HPC Runtime Adapter 生成 (可编辑: 分区/卡号/作业名)",
                 "set -euo pipefail",
                 "# 示例: 单卡执行; 8 卡分片请按 docs/HPC_EXPERIMENT_PROTOCOL.md",
                 f"export CUDA_VISIBLE_DEVICES=${{CUDA_VISIBLE_DEVICES:-0}}",
                 "cd " + str(config.repo_root()),
                 " ".join(cmd) + " > " + str(rdir / "run.log") + " 2>&1",
                 f"echo $? > {rdir / DONE_FILE}",
                 ]
        launcher.write_text("\n".join(lines) + "\n", encoding="utf-8")
        st = {
            "run_id": rid,
            "kind": cfg.kind,
            "schema": "training.status/1",
            "status": "submitted_external",
            "runtime": "hpc",
            "started_at": _now(),
            "command": " ".join(cmd),
            "launcher": str(launcher),
            "job_id": None,
            "progress": {"done": 0, "total": None, "ratio": None},
            "log_path": str(rdir / "run.log"),
            "done_file": str(rdir / DONE_FILE),
            "note": "GUI 不直接管理 HPC 作业; 请按平台提交 launcher 或 sbatch 后把 job_id "
                    "填入, 进度由 job 侧回写 training_status.json",
        }
        store.write_json(rdir / STATUS_FILE, st)
        return st

    def status(self, rid: str) -> Dict:
        rdir = self.runs_dir / rid
        st = store.read_json(rdir / STATUS_FILE)
        if st is None:
            raise FileNotFoundError(f"run not found: {rid}")
        if (rdir / DONE_FILE).exists():
            st["status"] = "completed"
            st["ended_at"] = _now()
        LocalRuntime._progress_from_log(rdir / "run.log", st)
        store.write_json(rdir / STATUS_FILE, st)
        return st

    def cancel(self, rid: str) -> Dict:
        st = store.read_json(self.runs_dir / rid / STATUS_FILE) or {}
        st["status"] = "cancelled"
        st["note"] = "取消需在 HPC 侧执行 scancel (GUI 不做); 状态已标记"
        store.write_json(self.runs_dir / rid / STATUS_FILE, st)
        return st

    def resume(self, rid: str) -> Dict:
        rdir = self.runs_dir / rid
        st = store.read_json(rdir / STATUS_FILE) or {}
        if (rdir / DONE_FILE).exists():
            (rdir / DONE_FILE).unlink()
        st["status"] = "submitted_external"
        st["resumed_at"] = _now()
        store.write_json(rdir / STATUS_FILE, st)
        return st


def adapter_for(runtime: str, workspace_root: Path):
    if runtime == "hpc":
        return HpcRuntime(workspace_root)
    return LocalRuntime(workspace_root)


def submit(cfg: TrainingConfig, workspace_root: Optional[Path] = None,
           save_config: bool = True) -> Dict:
    """统一提交入口 (Runtime Adapter 路由)。"""
    wr = workspace_root or config.default_workspace_root()
    errs = cfg.validate()
    if errs:
        raise ValueError("; ".join(errs))
    dev = resolve_device(getattr(cfg, "device", None), cfg.models)
    cfg.device = dev["device"]
    if dev["cpu_only"]:
        cfg.cuda_visible = ""            # 用户选择 cpu -> 强制不使用 GPU
    st = adapter_for(cfg.runtime, wr).submit(cfg)
    if save_config:
        rdir = wr / "runs" / st["run_id"]
        (rdir / "config.json").write_text(
            json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    return st


def submit_command(cmd: List[str], kind: str, workspace_root: Optional[Path] = None,
                   output_dir: str = "", dry_run: bool = False,
                   extra: Optional[Dict] = None, run_id: Optional[str] = None,
                   device: Optional[str] = None,
                   cuda_visible: Optional[str] = None,
                   batch_name: Optional[str] = None) -> Dict:
    """通用子进程提交入口（供 pipeline 服务使用；与训练共用 run 存储）。

    * ``output_dir``：用户选择的绝对输出目录（前端路径）。
    * ``batch_name``：**仅调试用**的批次子目录名；前端不传，manifest 中为空字符串。
    * ``cuda_visible=""``：强制不使用 GPU（Device=cpu 时由调用方设置）。
    """
    if not cmd:
        raise ValueError("empty command")
    wr = workspace_root or config.default_workspace_root()
    extra = dict(extra or {})
    extra.setdefault("output_dir", output_dir)
    return LocalRuntime(wr).submit_raw(cmd=cmd, kind=kind, batch_name=(batch_name or ""),
                                       dry_run=dry_run, extra=extra, run_id=run_id,
                                       device=device, cuda_visible=cuda_visible)


def status(run_id: str, workspace_root: Optional[Path] = None) -> Dict:
    wr = workspace_root or config.default_workspace_root()
    manifest = store.read_json(wr / "runs" / run_id / STATUS_FILE)
    if manifest is None:
        raise FileNotFoundError(f"run not found: {run_id}")
    return adapter_for(manifest["runtime"], wr).status(run_id)


def cancel(run_id: str, workspace_root: Optional[Path] = None) -> Dict:
    wr = workspace_root or config.default_workspace_root()
    manifest = store.read_json(wr / "runs" / run_id / STATUS_FILE)
    if manifest is None:
        raise FileNotFoundError(f"run not found: {run_id}")
    return adapter_for(manifest["runtime"], wr).cancel(run_id)


def resume(run_id: str, workspace_root: Optional[Path] = None) -> Dict:
    wr = workspace_root or config.default_workspace_root()
    manifest = store.read_json(wr / "runs" / run_id / STATUS_FILE)
    if manifest is None:
        raise FileNotFoundError(f"run not found: {run_id}")
    return adapter_for(manifest["runtime"], wr).resume(run_id)


def list_runs(workspace_root: Optional[Path] = None) -> List[Dict]:
    wr = workspace_root or config.default_workspace_root()
    base = wr / "runs"
    out = []
    if base.exists():
        for d in sorted(base.iterdir()):
            m = store.read_json(d / STATUS_FILE)
            if m:
                out.append(m)
    return out
