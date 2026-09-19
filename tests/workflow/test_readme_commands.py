"""README 命令可执行性测试：文档里的命令必须真的能跑。

这一层直接对应"新用户只依赖 Bash + README 就能完成全流程"这一目标。它拦截的是
**文档与代码漂移**：README 写了 ``--source-dir`` 而脚本改名为 ``--raw-data``、
README 漏了必填的 ``--data-set``、README 引用不存在的文件——这些都会让用户第一步就失败。

检查方式（不真正训练，只做静态可执行性核查，因此很快）：

1. 抽取 README 中所有 ```bash / ``` 代码块里的 Python 命令；
2. ``python <script.py>``  → 脚本文件必须存在；命令中出现的每个 ``--flag`` 必须被该脚本接受；
3. ``python -m <mod>``    → 模块必须可导入（``find_spec``）；
4. 命令中出现的相对路径，若位于 ``data/`` / ``core/`` / ``workflows/`` / ``analysis/`` 等
   仓库自有目录下，则必须存在（排除输出路径与占位符）。

真正的端到端执行由 ``tests/workflow/clean_user_test.sh`` 负责（从 README 逐字提取命令并执行，含负向路径）。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
PY = sys.executable


def _readme() -> str:
    assert README.is_file(), "README.md 不存在"
    return README.read_text(encoding="utf-8")


def _bash_blocks() -> list[str]:
    blocks = re.findall(r"```(?:bash|sh)\n(.*?)```", _readme(), re.S)
    assert blocks, "README 中没有 ```bash 代码块 —— 用户无法复制命令"
    return blocks


def _commands() -> list[str]:
    """把代码块拆成逻辑命令行（处理行尾反斜杠续行与注释）。"""
    out: list[str] = []
    for block in _bash_blocks():
        buf = ""
        for raw in block.splitlines():
            line = raw.split("#", 1)[0].rstrip() if raw.lstrip().startswith("#") else raw
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.endswith("\\"):
                buf += stripped[:-1] + " "
                continue
            buf += stripped
            out.append(buf.strip())
            buf = ""
        if buf.strip():
            out.append(buf.strip())
    return out


COMMANDS = _commands()
PYTHON_CMDS = [c for c in COMMANDS if re.match(r"^(python|py)\b", c)]


def _tokens(cmd: str) -> list[str]:
    # 去掉可能的 python 前缀的可执行名差异
    return cmd.replace("python3", "python").split()


def _script_of(tokens: list[str]) -> str | None:
    if len(tokens) < 2:
        return None
    if tokens[1] == "-m":
        return None
    if tokens[1].endswith(".py"):
        return tokens[1]
    return None


def _module_of(tokens: list[str]) -> str | None:
    if len(tokens) >= 3 and tokens[1] == "-m":
        return tokens[2]
    return None


def _flags(tokens: list[str]) -> list[str]:
    return [t for t in tokens[2:] if t.startswith("--") and t != "--"]


_HELP_CACHE: dict[str, set[str]] = {}


def _accepted_flags(script: str) -> set[str]:
    if script not in _HELP_CACHE:
        p = subprocess.run([PY, script, "--help"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=180)
        assert p.returncode == 0, f"{script} --help 失败：{p.stderr[:300]}"
        _HELP_CACHE[script] = set(re.findall(r"(?<![\w-])--[A-Za-z][\w-]*", p.stdout))
    return _HELP_CACHE[script]


def test_readme_has_python_commands() -> None:
    assert PYTHON_CMDS, "README 中没有可执行的 python 命令"


@pytest.mark.parametrize("cmd", PYTHON_CMDS)
def test_python_command_targets_exist(cmd: str) -> None:
    """每个 python 命令的目标（脚本或 -m 模块）必须存在。"""
    tokens = _tokens(cmd)
    script = _script_of(tokens)
    module = _module_of(tokens)
    if script:
        assert (ROOT / script).is_file(), f"README 命令引用了不存在的脚本：{script}\n  {cmd}"
        return
    if module:
        try:
            spec = importlib.util.find_spec(module)
        except (ImportError, ModuleNotFoundError, ValueError) as e:
            pytest.fail(f"README 命令的模块 {module} 无法解析：{e}\n  {cmd}")
        assert spec is not None, f"README 命令引用了不存在的模块：{module}\n  {cmd}"
        return
    pytest.fail(f"README 中有无法识别的 python 命令形式：{cmd}")


@pytest.mark.parametrize("cmd", PYTHON_CMDS)
def test_python_command_flags_are_accepted(cmd: str) -> None:
    """README 命令里出现的每个 --flag 都必须被目标脚本接受。

    这是最有价值的一条：它能捕获"文档写了 --source-dir 但脚本已改名 --raw-data"
    这类漂移。
    """
    tokens = _tokens(cmd)
    script = _script_of(tokens)
    if not script:
        pytest.skip("模块命令，参数不在本测试范围（模块参数由各自 --help 覆盖）")
    accepted = _accepted_flags(script)
    used = _flags(tokens)
    unknown = [f for f in used if f not in accepted]
    assert not unknown, (
        f"README 命令对 {script} 使用了它不接受的参数 {unknown}\n  {cmd}\n"
        f"  该脚本接受的参数：{sorted(accepted)}"
    )


def test_required_flags_present_in_readme_commands() -> None:
    """README 中每个脚本的**第一条**命令必须包含该脚本的必填参数。

    历史缺陷：README 的 predict 命令漏了必填 --data-set/--data-dir，
    特征工程命令漏了必填 --config。
    """
    required = {
        "core/features/engineering/feature_engineering.py":
            ("--raw-data", "--output-dir", "--config"),
        "workflows/training/train.py": ("--model", "--environment"),
        "workflows/prediction/predict.py": (),      # --data-set/--data-dir 二选一
        "workflows/training/data_digging.py": (),
    }
    seen: dict[str, int] = {}
    for cmd in PYTHON_CMDS:
        tokens = _tokens(cmd)
        script = _script_of(tokens)
        if not script or script not in required:
            continue
        idx = seen.get(script, 0)
        seen[script] = idx + 1
        if idx != 0:
            continue                      # 只校验第一条（通常是 Quick Start 的主命令）
        used = set(_flags(tokens))
        missing = [f for f in required[script] if f not in used]
        assert not missing, (
            f"README 中 {script} 的第一条命令缺少必填参数 {missing}\n  {cmd}"
        )
        if script == "workflows/training/train.py":
            assert "--data-set" in used or "--data-dir" in used, (
                f"README 训练命令缺少 --data-set/--data-dir（必填）\n  {cmd}"
            )
        if script == "workflows/prediction/predict.py":
            assert "--data-set" in used or "--data-dir" in used, (
                f"README 预测命令缺少 --data-set/--data-dir（必填）\n  {cmd}"
            )


REPO_DIRS = ("data/", "core/", "workflows/", "analysis/", "docs/",
             "deploy/", "tests/", "app/", "configs/")


def test_readme_referenced_paths_exist() -> None:
    """README 里引用的仓库自有路径必须存在（避免死链）。"""
    text = _readme()
    # 抽出形如 data/xxx/yyy.json 的路径
    cands = set(re.findall(
        r"(?<![\w/])(" + "|".join(re.escape(d) for d in REPO_DIRS) + r"[\w./\-]+)", text))
    missing = []
    for c in sorted(cands):
        c = c.rstrip(".,)%`")
        if any(x in c for x in ("<", ">", "*", "...", "{}")):
            continue                      # 占位符/通配
        p = ROOT / c
        if p.exists():
            continue
        # 允许"数据集名占位"的形式
        if c.startswith("data/raw/") or c.startswith("data/processed/"):
            continue
        missing.append(c)
    assert not missing, "README 引用了不存在的路径：\n  " + "\n  ".join(missing)


def test_readme_documents_all_core_steps() -> None:
    """README 必须覆盖十个核心步骤的关键词（用户按目录找得到）。"""
    text = _readme()
    for kw in ("Quick Start", "数据集", "Feature schema", "预处理", "训练",
               "评估", "数据挖掘", "预测", "结果汇总", "可视化",
               "输出结构", "可复现性", "用户应该改哪里"):
        assert kw in text, f"README 缺少章节/关键词：{kw}"
