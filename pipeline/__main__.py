"""python -m pipeline：共享编排层的只读调试入口（等价于 pipeline.steps CLI）。"""
from .steps import _main

if __name__ == '__main__':
    raise SystemExit(_main())
