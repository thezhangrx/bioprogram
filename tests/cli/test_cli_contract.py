"""CLI 契约测试：命令行接口必须真的接受它声称接受的参数。

保护的是"README/文档写了某个 flag，但脚本其实不认"以及"必需参数没被真正强制"
这两类问题——它们都会让用户的第一步就失败，而静态读代码看不出来。

做法：对每个入口实际执行 ``--help``，从输出中提取 option 字符串，再与期望集合比对；
对必需参数，实际执行一次不带参数的调用，断言退出码为 2（argparse 用法错误）。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY] + args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
    )


def _options(script: str) -> set[str]:
    """从 --help 输出中提取全部 option 字符串（如 --batch-name）。"""
    p = _run([script, "--help"])
    assert p.returncode == 0, f"{script} --help 失败（exit={p.returncode}）：\n{p.stderr[:500]}"
    return set(re.findall(r"(?<![\w-])--[A-Za-z][\w-]*", p.stdout))


ENTRIES = {
    "feature_engineering": "core/features/engineering/feature_engineering.py",
    "train": "workflows/training/train.py",
    "data_digging": "workflows/training/data_digging.py",
    "predict": "workflows/prediction/predict.py",
    "design": "workflows/design/design.py",
    "screen": "workflows/screening/screen.py",
    "validate_schema": "core/features/engineering/validate_feature_schema.py",
    "panorama": "analysis/panorama.py",
    "importance_extraction": "analysis/importance_extraction.py",
    "anomaly_treatment": "analysis/anomaly_treatment.py",
    # 桌面 GUI：--help/--version 必须**立即返回**（历史上无参数解析，--help 被忽略
    # 并直接启动 GUI，在无显示机器上挂死）
    "main_wizard": "app/desktop/main_wizard.py",
}


@pytest.mark.parametrize("name,script", sorted(ENTRIES.items()))
def test_help_available(name: str, script: str) -> None:
    """每个用户入口都必须支持 --help 且退出码为 0。"""
    p = _run([script, "--help"])
    assert p.returncode == 0, f"{name} ({script}) --help 退出码 {p.returncode}"
    assert "usage:" in p.stdout.lower() or "usage:" in p.stderr.lower(), (
        f"{name}: --help 输出里没有 usage 段"
    )


@pytest.mark.parametrize("name,script", sorted(ENTRIES.items()))
def test_help_has_descriptions(name: str, script: str) -> None:
    """--help 不能只有参数名堆叠：至少要有 help 文本。"""
    p = _run([script, "--help"])
    out = p.stdout or p.stderr
    body = [ln for ln in out.splitlines() if ln.strip().startswith("-")]
    with_help = [ln for ln in body if len(ln.split()) > 2]
    assert with_help, f"{name}: --help 没有任何带说明的参数行"


def test_feature_engineering_requires_three_paths() -> None:
    """--raw-data / --output-dir / --config 三路径必填：缺一即用法错误。"""
    p = _run(["core/features/engineering/feature_engineering.py"])
    assert p.returncode == 2, "缺参数时应以退出码 2 失败（argparse 用法错误）"
    for flag in ("--raw-data", "--output-dir", "--config"):
        assert flag in (p.stderr + p.stdout), f"错误信息里未提示必填 {flag}"


def test_train_requires_dataset_and_model() -> None:
    """训练必须强制 --data-set/--data-dir 与 --model，不能回退到任何默认数据集。"""
    p = _run(["workflows/training/train.py"])
    assert p.returncode == 2
    msg = p.stderr + p.stdout
    assert "--model" in msg
    assert "--data-set" in msg or "--data-dir" in msg


def test_predict_requires_dataset() -> None:
    """预测必须强制指定数据集（README 曾漏掉该参数导致命令失败）。"""
    p = _run(["workflows/prediction/predict.py"])
    assert p.returncode == 2
    msg = p.stderr + p.stdout
    assert "--data-set" in msg or "--data-dir" in msg


def test_data_digging_requires_dataset() -> None:
    p = _run(["workflows/training/data_digging.py"])
    assert p.returncode == 2
    msg = p.stderr + p.stdout
    assert "--data-set" in msg or "--data-dir" in msg


def test_collect_results_missing_batch_exits_nonzero() -> None:
    """批次不存在必须返回非零退出码（否则 shell && 链会静默继续）。"""
    p = _run(["-m", "analysis.collect_results", "--batch-name", "__no_such_batch__"])
    assert p.returncode != 0, "批次缺失时退出码为 0 —— 脚本化陷阱"
    assert "does not exist" in (p.stdout + p.stderr)


def test_train_exposes_documented_hyperparameters() -> None:
    """README §7.2 表格里列出的参数必须真实存在于 train.py。"""
    opts = _options("workflows/training/train.py")
    for flag in ("--model", "--split-type", "--cell-line", "--cell-lines",
                 "--environment", "--data-set", "--data-dir",
                 "--train-ratio", "--valid-ratio", "--test-ratio", "--seed",
                 "--epochs", "--batch-size", "--learning-rate", "--dropout",
                 "--weight-decay", "--patience", "--min-delta",
                 "--hidden-dim1", "--hidden-dim2", "--conv-channels1",
                 "--conv-channels2", "--sequence-kernel", "--environment-kernel",
                 "--device", "--use-scaler", "--batch-name", "--run-name",
                 "--model-dir", "--results-dir", "--logs-dir",
                 # 优化/调度/激活/并行/GPU 绑定（README §7.2）
                 "--optimizer", "--scheduler", "--activation",
                 "--num-workers", "--gpu-id"):
        assert flag in opts, f"train.py 缺少 README 中记录的参数 {flag}"


def test_data_digging_exposes_documented_options() -> None:
    opts = _options("workflows/training/data_digging.py")
    for flag in ("--data-set", "--data-dir", "--training-scope-epis", "--environments",
                 "--models", "--cell-lines", "--split-types", "--mixed-seeds",
                 "--cnn-kernels", "--batch-name", "--results-dir", "--model-dir",
                 "--logs-dir", "--workers", "--gpus", "--dry-run"):
        assert flag in opts, f"data_digging.py 缺少 README 中记录的参数 {flag}"


def test_predict_exposes_documented_options() -> None:
    opts = _options("workflows/prediction/predict.py")
    for flag in ("--data-set", "--data-dir", "--batch-name", "--models",
                 "--target-input", "--target-epigenetics", "--candidate-top-k",
                 "--ultimate-dir", "--results-dir", "--device", "--dry-run"):
        assert flag in opts, f"predict.py 缺少 README 中记录的参数 {flag}"


def test_orchestrator_commands_are_non_empty_or_explained() -> None:
    """非 internal 步骤必须给出非空命令；internal 步骤必须给出解释与产物。"""
    import json

    p = _run(["-m", "workflows.orchestrator", "list"])
    assert p.returncode == 0
    steps = [ln.split()[0] for ln in p.stdout.splitlines() if ln.strip()]

    for sid in steps:
        q = _run(["-m", "workflows.orchestrator", "command", "--step", sid,
                  "--data-set", "DeepCRISPR"])
        assert q.returncode == 0, f"orchestrator command --step {sid} 失败"
        payload = json.loads(q.stdout.strip().splitlines()[-1])
        if payload["command"]:
            continue
        # 空命令必须是 internal，且带 note + artifacts
        assert payload.get("kind") == "internal", (
            f"{sid}: 命令为空但不是 internal 步骤 —— 用户会以为生成失败"
        )
        assert payload.get("note"), f"{sid}: internal 步骤缺少 note 解释"
        assert payload.get("artifacts"), f"{sid}: internal 步骤缺少 artifacts"


def test_orchestrator_feature_engineering_config_exists() -> None:
    """orchestrator 生成的 feature_engineering 命令，其 --config 必须真实存在。

    历史缺陷：默认指向不存在的 data/feature_config.json，导致生成的命令必然失败；
    且对无表观通道的数据集错用 8 通道配置。
    """
    import json

    for ds, expect in (("DeepCRISPR", "feature_config.json"),
                       ("Hiranniramol", "feature_config_sequence_only.json"),
                       ("Labuhn", "feature_config_sequence_only.json")):
        p = _run(["-m", "workflows.orchestrator", "command",
                  "--step", "feature_engineering", "--data-set", ds])
        assert p.returncode == 0
        cmd = json.loads(p.stdout.strip().splitlines()[-1])["command"]
        assert cmd, f"{ds}: feature_engineering 命令为空"
        cfg = cmd[cmd.index("--config") + 1]
        assert Path(cfg).is_file(), f"{ds}: --config 指向不存在的文件 {cfg}"
        assert cfg.endswith(expect), f"{ds}: 期望 config {expect}，实际 {cfg}"
        # 输入目录必须与数据集匹配（不能把全部 raw 目录混在一起）
        raw = cmd[cmd.index("--source-dir") + 1] if "--source-dir" in cmd \
            else cmd[cmd.index("--raw-data") + 1]
        assert raw.endswith(ds), f"{ds}: --raw-data 应为该数据集目录，实际 {raw}"


def test_orchestrator_default_output_is_repo_root() -> None:
    """默认输出根必须是项目根，使 results/ 与 models/ 落在 README 约定的位置。"""
    import json

    p = _run(["-m", "workflows.orchestrator", "context", "--data-set", "DeepCRISPR"])
    assert p.returncode == 0
    ctx = json.loads(p.stdout)
    assert Path(ctx["output_dir"]).resolve() == ROOT.resolve(), (
        f"默认输出根 {ctx['output_dir']} != 项目根 {ROOT}；"
        "会凭空造出一棵 README 从未提到的目录树"
    )
    assert ctx["results_dir"].endswith("results/batches")
    assert ctx["model_dir"].endswith("models/weights")
    assert ctx["logs_dir"].endswith("results/logs")


def test_gui_entry_help_returns_quickly() -> None:
    """GUI 入口的 --help 必须立即返回，不能启动窗口并阻塞。"""
    import time

    t0 = time.time()
    p = _run(["app/desktop/main_wizard.py", "--help"], timeout=30)
    elapsed = time.time() - t0
    assert p.returncode == 0, f"--help 退出码 {p.returncode}"
    assert elapsed < 25, f"--help 耗时 {elapsed:.1f}s，疑似启动了 GUI 并阻塞"
    assert "usage:" in p.stdout.lower()


def test_gui_entry_version_returns_quickly() -> None:
    p = _run(["app/desktop/main_wizard.py", "--version"], timeout=30)
    assert p.returncode == 0
