# crispr_workspace (本地后端, 零依赖)

CRISPR Scientific Workspace 的本地 Workflow API 服务 (纯 Python 标准库)。
科学计算一律通过现有引擎子进程/只读产物执行; 本包不 import 训练模型代码。

## 运行

```bash
# 默认工作根 = <仓库>/workspace; 可用环境变量覆盖
CRISPR_WORKSPACE_ROOT=/path/to/root python -m crispr_workspace.server --port 8765
python -m crispr_workspace.server --root /path/to/root --port 8765   # 等价

# 前端开发代理指向 http://127.0.0.1:8765
```

## 接口
见 `/api/health` 与仓库根 `docs/frontend_architecture.md` §4 接口表。

## 测试
```bash
cd backend
PYTHONPATH=. python3 -m unittest tests.test_workspace -v
```
