"""路径完整性守卫（回归测试）。

背景
----
2026-09 的目录重构把 ``analyse/`` → ``analysis/``、``src/`` → ``core/``、
``results/<batch>`` → ``results/batches/<batch>``、``models/<batch>`` → ``models/weights/<batch>``。
重构过程中有 11 个入口脚本的项目根推导少了一层 ``parents``（例如 ``core/common/paths.py``
用 ``parents[1]`` 得到 ``<root>/core``），结果所有默认路径静默指向不存在的目录。

本测试把"路径不能悄悄失效"变成可执行断言，覆盖三类漂移：

1. ``core.common.paths`` 的全部常量必须真实存在；
2. 任何脚本里赋值给 ``PROJECT_ROOT`` / ``ROOT`` / ``_PROJECT_ROOT`` / ``_REPO_ROOT`` 的
   路径推导表达式，结果必须等于仓库根；
3. 文档里 ``python <script>.py`` 形式、以及脚本里 ``--xxx default=<路径>`` 形式的
   可执行目标，必须真实存在（允许显式白名单）。

失败时的修法：先修 ``core/common/paths.py``，再让脚本 ``from core.common.paths import ...``，
不要在入口脚本里重新手写 ``parents[N]``。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 从 core.common.paths 导入的常量名 -> 期望相对路径
EXPECTED_PATH_CONSTANTS = {
    "PROJECT_ROOT": ".",
    "DATA_DIR": "data",
    "DATA_PROCESSED": "data/processed",
    "DATA_RAW": "data/raw",
    "DATA_CANDIDATE": "data/candidate",
    "DATA_METADATA": "data/metadata",
    "RESULTS_DIR": "results",
    "RESULTS_BATCHES": "results/batches",
    "RESULTS_TABLES": "results/tables",
    "LOGS_DIR": "results/logs",
    "MODELS_DIR": "models",
    "MODELS_WEIGHTS": "models/weights",
}

#: 允许 ROOT 不等于仓库根的脚本 —— 必须写明理由，否则测试会拦住你
ROOT_DERIVATION_ALLOWLIST = {
    # analysis/visualization/__init__.py 里的 _LEGACY_VIZ_FILE 指向 analysis/panorama.py，不是项目根
    "analysis/visualization/__init__.py",
}

#: 只写不读的输出目录允许尚不存在（运行时才创建）
OUTPUT_PATH_ALLOWLIST = {
    "results/tables/audit/env_equivalence",
    "results/tables/audit/hpc_verify",
}

#: 已不在仓库中的一次性开发脚本；文档里的命令仅作历史存档
MISSING_TOOL_ALLOWLIST = {"profile_experiment.py", "regression_compare.py"}

SKIP_DIR_PARTS = {
    "node_modules", ".venv", "__pycache__", "workspace", ".git", "build", "dist",
    # HPC 上传包：由 deploy/hpc/make_upload_dir.sh 生成的派生副本，
    # 它自带一份 core/workflows，其中的 parents[N] 相对包根解析，
    # 不是仓库根的路径漂移。源码在仓库里有唯一权威副本。
    "upload",
}


def _iter_files(suffix: str):
    for p in REPO_ROOT.rglob(f"*{suffix}"):
        if any(part in SKIP_DIR_PARTS for part in p.relative_to(REPO_ROOT).parts):
            continue
        yield p


# --------------------------------------------------------------------------- #
# 1. 唯一路径权威
# --------------------------------------------------------------------------- #
def test_paths_module_constants_exist():
    """core/common/paths.py 必须把项目根算对，且每个常量都指向真实目录。"""
    from core.common import paths as P

    assert P.PROJECT_ROOT == REPO_ROOT, (
        f"core/common/paths.py 的 PROJECT_ROOT 解析为 {P.PROJECT_ROOT}，应为 {REPO_ROOT}；"
        "本文件位于 core/common/ 下，parents[2] 才是项目根"
    )

    missing = []
    for name, rel in EXPECTED_PATH_CONSTANTS.items():
        value = getattr(P, name, None)
        assert value is not None, f"core/common/paths.py 缺少常量 {name}"
        expected = (REPO_ROOT / rel).resolve()
        assert Path(value).resolve() == expected, f"{name} = {value}，应为 {expected}"
        if not Path(value).exists():
            missing.append(f"{name} -> {rel}")
    assert not missing, "以下权威路径不存在：\n  " + "\n  ".join(missing)


def test_processed_datasets_are_addressable_by_name():
    """data/processed 下的每个数据集都必须能被 --data-set 解析到，并与 raw 对齐。"""
    from core.common.paths import DATA_PROCESSED, DATA_RAW, available_datasets, resolve_dataset

    names = available_datasets()
    assert names, f"{DATA_PROCESSED} 下没有任何已处理数据集（缺少 feature_schema.json）"

    raw_names = sorted(d.name for d in DATA_RAW.iterdir() if d.is_dir()) if DATA_RAW.is_dir() else []
    assert names == raw_names, f"processed={names} 与 raw={raw_names} 不一致"

    for name in names:
        resolved = resolve_dataset(name)
        assert resolved.is_dir() and (resolved / "feature_schema.json").is_file()
        # 大小写不敏感
        assert resolve_dataset(name.lower()) == resolved
        # 每个数据集都得能被细胞系发现逻辑解析出至少一个数据集
        import sys as _sys
        _sys.path.insert(0, str(REPO_ROOT))
        from core.data.splitting.cell_line_division import (
            discover_available_cell_lines, load_feature_schema,
        )
        schema = load_feature_schema(str(resolved))
        cells = discover_available_cell_lines(str(resolved))
        assert cells, f"{name} 下没有可发现的细胞系/数据集"
        # 每通道 23 个位置、文件名维度与 schema 一致
        n_ch, n_ft = int(schema["channel_count"]), int(schema["feature_count"])
        assert n_ft == 23 * n_ch, f"{name}: feature_count={n_ft} != 23*{n_ch}"
        for cell in cells:
            assert (resolved / f"{cell}_features_23x{n_ch}.npy").is_file(), f"{name}/{cell} 缺 23x{n_ch}"
            assert (resolved / f"{cell}_features_{n_ft}.npy").is_file(), f"{name}/{cell} 缺 {n_ft}"


def test_string_helpers_match_path_constants():
    """STR_* 字符串形式必须与 Path 常量一致（argparse default 用的是字符串）。"""
    from core.common import paths as P

    assert P.STR_DATA_PROCESSED == str(P.DATA_PROCESSED)
    assert P.STR_RESULTS_BATCHES == str(P.RESULTS_BATCHES)
    assert P.STR_MODELS_WEIGHTS == str(P.MODELS_WEIGHTS)
    assert P.STR_LOGS == str(P.LOGS_DIR)


# --------------------------------------------------------------------------- #
# 2. 入口脚本的项目根推导
# --------------------------------------------------------------------------- #
_ROOT_ASSIGN_RE = re.compile(
    r"^(?P<name>_PROJECT_ROOT|PROJECT_ROOT|_REPO_ROOT|ROOT)"
    r"(?:\s*:\s*[A-Za-z_][\w.\[\]]*)?"      # 可选类型注解，例如 `PROJECT_ROOT: Path = ...`
    r"\s*[:=]\s*(?P<expr>[^\n#]+)",
    re.MULTILINE,
)


def test_entry_scripts_derive_project_root_correctly():
    """所有 PROJECT_ROOT/ROOT 推导都必须落在仓库根（路径推导漂移守卫）。"""
    offenders = []
    for path in _iter_files(".py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ROOT_DERIVATION_ALLOWLIST or rel.startswith("tests/"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in _ROOT_ASSIGN_RE.finditer(text):
            expr = m.group("expr").strip()
            if "parents[" not in expr and ".parent" not in expr:
                continue
            # 只校验自包含表达式，跳过 `ROOT = _PROJECT_ROOT` 这类转发
            if not expr.startswith("Path(__file__)"):
                continue
            try:
                value = eval(  # noqa: S307 - 受控表达式，仅 Path 推导
                    expr.replace("__file__", repr(str(path))).replace("_Path", "Path"),
                    {"Path": Path},
                )
            except Exception as exc:  # pragma: no cover - 表达式不可求值时给出可读失败
                offenders.append(f"{rel}: {expr}  <无法求值: {exc}>")
                continue
            if Path(value).resolve() != REPO_ROOT:
                offenders.append(
                    f"{rel}: {expr} -> {value}  (应为 {REPO_ROOT})"
                )
    assert not offenders, (
        "以下脚本的项目根推导错误，会让默认路径静默指向不存在的目录：\n  "
        + "\n  ".join(sorted(set(offenders)))
        + "\n\n修法：改为 `from core.common.paths import PROJECT_ROOT`，不要手写 parents[N]。"
    )


# --------------------------------------------------------------------------- #
# 3. 可执行目标与默认路径必须真实存在
# --------------------------------------------------------------------------- #
def test_documented_commands_point_at_existing_files():
    """文档里 `python <script>.py` 形式的命令，目标必须存在。"""
    cmd_re = re.compile(r"(?:python3?|bash|sh|pytest)\s+([^\s`'\"]+\.(?:py|sh))")
    offenders = []
    for path in _iter_files(".md"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if "/recon/" in rel:  # 历史勘察快照，显式记录了重构前结构
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            for m in cmd_re.finditer(line):
                target = m.group(1)
                if target.startswith("-") or "$" in target or "<" in target:
                    continue
                if Path(target).name in MISSING_TOOL_ALLOWLIST:
                    continue
                candidates = [
                    REPO_ROOT / target,
                    REPO_ROOT / "deploy" / target,
                    REPO_ROOT / "analysis" / target,
                    REPO_ROOT / "workflows" / target,
                ]
                if not any(c.exists() for c in candidates):
                    offenders.append(f"{rel}:{lineno} -> {target}")
    assert not offenders, "文档引用了不存在的脚本：\n  " + "\n  ".join(offenders)


def test_script_path_defaults_exist():
    """脚本里 `default=<路径字面量>` 形式的默认值，必须指向真实存在的路径（输出目录除外）。"""
    literal_re = re.compile(
        r"""default\s*=\s*['"]([^'"]*(?:data|results|models|logs|docs|weights|batches)[^'"]*)['"]"""
    )
    offenders = []
    for path in _iter_files(".py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if "add_argument" not in line:
                continue
            for m in literal_re.finditer(line):
                value = m.group(1)
                if value.strip() in OUTPUT_PATH_ALLOWLIST:
                    continue
                if not re.search(r"[/\\]|^(data|results|models|logs|docs)$", value):
                    continue
                if not (REPO_ROOT / value).exists():
                    offenders.append(f"{rel}:{lineno} -> {value}")
    assert not offenders, "脚本默认路径不存在：\n  " + "\n  ".join(offenders)


def test_batch_resolution_accepts_batches_subdir():
    """importance_extraction 的批次解析必须能同时接受新写法和旧写法。"""
    import importlib

    mod = importlib.import_module("analysis.importance_extraction")
    from core.common.paths import RESULTS_BATCHES

    assert RESULTS_BATCHES.name == "batches"

    # 旧写法 --results_dir results 必须被自动补成 results/batches
    legacy = mod._resolve_batch_paths(str(REPO_ROOT / "results"), "ultimate_run", "", False, False)
    assert legacy == [(RESULTS_BATCHES / "ultimate_run").resolve()]

    new = mod._resolve_batch_paths(str(RESULTS_BATCHES), "ultimate_run", "", False, False)
    assert new == [(RESULTS_BATCHES / "ultimate_run").resolve()]

    with pytest.raises(SystemExit):
        mod._resolve_batch_paths(str(RESULTS_BATCHES), "definitely_not_a_batch", "", False, False)
