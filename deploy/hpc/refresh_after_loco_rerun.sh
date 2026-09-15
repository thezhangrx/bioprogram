#!/usr/bin/env bash
# LOCO 重跑完成后的自动刷新与核对：
#   1) 等训练进程退出
#   2) 重建 summary/metrics_tables（collect_results）
#   3) 重跑 analyse 引擎，沿用原 analysis_plan.json（ANOVA 等开关保持一致）
#   4) 核对：448 个 all run 的划分形状、失败数、all 与 single 是否仍逐位相同、LOCO R² 统计
#   5) 产出 results/analysis/loco_after_fix_summary.{md,csv}
set -u
cd "$(dirname "$0")/../.."          # 切到项目根
PY="${PY:-python3}"
BATCH=results/batches/batch_20260909_full
LOG=results/logs/loco_refresh.log
PLAN=$BATCH/summary/analysis_plan.json
exec > >(tee -a "$LOG") 2>&1

echo "=== [$(date +%F' '%T)] 等待 LOCO 训练结束 ==="
while pgrep -f "data_digging.py --batch-name batch_20260909_full" >/dev/null 2>&1; do sleep 60; done
echo "=== [$(date +%F' '%T)] 训练进程已退出 ==="
echo "all_ 目录数: $(ls $BATCH | grep -c '^all_') / 448"
echo "日志中的失败计数: $(grep -c 'Failed\|failed' logs/loco_rerun_20260913.log)"
tail -4 logs/loco_rerun_20260913.log

echo "=== [$(date +%F' '%T)] 1/3 重建 summary/metrics_tables ==="
$PY -m analysis.collect_results --results-dir results --batch-name batch_20260909_full \
    --split-types single all mixed

echo "=== [$(date +%F' '%T)] 2/3 重跑 analyse 引擎 (沿用 analysis_plan.json) ==="
if [ -f "$PLAN" ]; then
  $PY -m analysis.pipeline --batch-dir "$BATCH" --analysis-plan "$PLAN"
else
  $PY -m analysis.pipeline --batch-dir "$BATCH"
fi

echo "=== [$(date +%F' '%T)] 3/3 核对与产出 ==="
$PY - <<'PY'
import re, glob, os
import numpy as np
import pandas as pd

BATCH = "results/batch_20260909_full"
OUT_MD = "results/analysis/loco_after_fix_summary.md"
OUT_CSV = "results/analysis/loco_after_fix_summary.csv"
lines = []

# ---- A. 448 个 all run 的划分形状核对 ----
expect = {"hct116": 4239, "hek293t": 2333, "hela": 8101, "hl60": 2076}
total = sum(expect.values())
rows, bad = [], []
dirs = sorted(d for d in glob.glob(f"{BATCH}/all_*") if os.path.isdir(d))
for d in dirs:
    info = glob.glob(os.path.join(d, "*_info.txt"))
    if not info:
        bad.append((os.path.basename(d), "缺少 info 文件")); continue
    txt = open(info[0], encoding="utf-8", errors="ignore").read()
    def grab(key, _t=txt):
        m = re.search(rf"^{key}:\s*(.+)$", _t, re.M)
        return m.group(1).strip() if m else None
    cells = grab("cell_lines")
    shp = {k: grab(f"input_shape_{k}") for k in ("train", "valid", "test")}
    held = next((c for c in expect if f"heldout_{c}" in os.path.basename(d)), None)
    n_train = int(re.findall(r"\d+", shp["train"])[0]) if shp["train"] else -1
    n_valid = int(re.findall(r"\d+", shp["valid"])[0]) if shp["valid"] else -1
    n_test = int(re.findall(r"\d+", shp["test"])[0]) if shp["test"] else -1
    exp_test = expect.get(held, -1)
    exp_train = int(np.floor((total - exp_test) * 0.85))
    exp_valid = (total - exp_test) - exp_train
    ok = (cells is not None and cells.count(",") == 3
          and n_test == exp_test and n_train == exp_train and n_valid == exp_valid)
    rows.append({"run": os.path.basename(d), "heldout": held, "cell_lines": cells,
                 "n_train": n_train, "n_valid": n_valid, "n_test": n_test,
                 "expected_train": exp_train, "expected_valid": exp_valid,
                 "expected_test": exp_test, "layout_ok": ok})
    if not ok:
        bad.append((os.path.basename(d), f"cells={cells} shapes={n_train}/{n_valid}/{n_test}"))

shape = pd.DataFrame(rows)
n_ok = int(shape.layout_ok.sum()) if len(shape) else 0
lines.append("## A. 运行与划分核对\n")
lines.append(f"- `all_*` 目录数：**{len(dirs)} / 448**")
lines.append(f"- 划分形状正确（4 个细胞系、train/valid = 85/15 of 另外三个、test = 留出系全量）：**{n_ok} / {len(dirs)}**")
lines.append(f"- 形状异常：{len(bad)} 个" + (f"（示例 {bad[:3]}）" if bad else ""))

# ---- B. all 与 single 是否仍逐位相同 ----
a = pd.read_csv(f"{BATCH}/summary/metrics_tables/all_experiments.csv", low_memory=False)
key = ["model", "environment", "cell_line", "random_seed"]
metrics = ["R2", "RMSE", "MAE", "Pearson", "Spearman"]
s = a[a.split_type == "single"][key + metrics].add_suffix("_single").rename(
    columns={f"{k}_single": k for k in key})
l = a[a.split_type == "all"][key + metrics].add_suffix("_all").rename(
    columns={f"{k}_all": k for k in key})
m = s.merge(l, on=key)
ident = np.ones(len(m), dtype=bool)
for c in metrics:
    ident &= (m[f"{c}_single"] - m[f"{c}_all"]).abs() < 1e-12
lines.append("\n## B. `all` 与 `single` 是否仍然重复\n")
lines.append(f"- 可配对实验：**{len(m)}**")
lines.append(f"- 五个指标全部逐位相同：**{int(ident.sum())} / {len(m)}**（修复前为 448/448）")

# ---- C. LOCO R² 统计 ----
loco = a[a.split_type == "all"].copy()
sing = a[a.split_type == "single"].copy()
per_model = (loco.groupby("model")["R2"].agg(["median", "mean", "count"])
             .join(sing.groupby("model")["R2"].median().rename("single_median_R2"))
             .sort_values("median"))
per_cell = loco.groupby("cell_line")["R2"].agg(["median", "mean", "count"])
lines.append("\n## C. LOCO 泛化性能（修复后，test = 留出细胞系）\n")
lines.append("### 按模型（7 个配置，跨 16 环境 × 4 留出细胞系）\n")
lines.append("| model | n | LOCO R² 中位 | LOCO R² 均值 | 同细胞系 single R² 中位 |")
lines.append("| :--- | ---: | ---: | ---: | ---: |")
for mdl, r in per_model.iterrows():
    lines.append(f"| {mdl} | {int(r['count'])} | {r['median']:.4f} | {r['mean']:.4f} | "
                 f"{r['single_median_R2']:.4f} |")
lines.append("\n### 按留出细胞系（跨 7 模型 × 16 环境）\n")
lines.append("| 留出细胞系 | n | LOCO R² 中位 | LOCO R² 均值 |")
lines.append("| :--- | ---: | ---: | ---: |")
for cl, r in per_cell.iterrows():
    lines.append(f"| {cl} | {int(r['count'])} | {r['median']:.4f} | {r['mean']:.4f} |")
lines.append(f"\n- 全体 LOCO：中位 R² = **{loco.R2.median():.4f}**，均值 = **{loco.R2.mean():.4f}**，"
             f"n = {len(loco)}；同批 `single`（域内）中位 = {sing.R2.median():.4f}")

os.makedirs("results/analysis", exist_ok=True)
shape.to_csv(OUT_CSV, index=False)
header = ("# `all`（LOCO）修复后的核对结果\n\n"
          f"- 生成时间：{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}\n"
          "- 修复内容：`data_digging.py` 为 `all` 补发 `--cell-lines <全部细胞系>`；"
          "`cell_line_division.py` 新增 `create_train_valid_indices` 供留一分支使用（85/15）。\n"
          "- 旧退化产物备份：`_backup_degenerate_all/{results,models,logs}/`（各 448 个目录）\n")
open(OUT_MD, "w", encoding="utf-8").write(header + "\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\n[write] {OUT_MD}\n[write] {OUT_CSV}")
PY

echo "=== [$(date +%F' '%T)] 全部完成 ==="
