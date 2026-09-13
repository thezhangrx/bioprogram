"""静态守卫: Workflow 后端绝不 import 训练/引擎科学模块 (红线 P0)。

允许: 标准库 / crispr_workspace 自身 / 以子进程字符串引用现有 CLI 路径 /
仅以"路径字符串"或 analyse.registry 任务目录读取 (registry 只列任务, 不算科学计算)。
禁止模式: from src..., import src..., from train, import train, from predict,
from data_digging (会直接把训练代码拉进后端进程)。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "crispr_workspace"

FORBIDDEN = [
    re.compile(r"^\s*(from|import)\s+src\b"),
    re.compile(r"^\s*(from|import)\s+train\b"),
    re.compile(r"^\s*(from|import)\s+predict\b"),
    re.compile(r"^\s*(from|import)\s+data_digging\b"),
    re.compile(r"^\s*import\s+analyse\b"),          # 顶层整包 import 禁止
]


class TestNoTrainingDependency(unittest.TestCase):
    def test_package_never_imports_training_science(self):
        offenders = []
        for f in sorted(PKG.glob("*.py")):
            text = f.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), 1):
                if line.strip().startswith("#") or line.strip().startswith('"""'):
                    continue
                for rx in FORBIDDEN:
                    if rx.search(line):
                        offenders.append(f"{f.name}:{line_no}: {line.strip()}")
        self.assertEqual([], offenders,
                         "backend must not import training/scientific modules:\n" +
                         "\n".join(offenders))


if __name__ == "__main__":
    unittest.main(verbosity=2)
