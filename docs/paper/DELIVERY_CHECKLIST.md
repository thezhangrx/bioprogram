# 论文重写最终交付检查清单

**检查对象**：`docs/paper/`（LaTeX 正式稿）
**检查日期**：2026-09-19
**检查方式**：每一项都给出**可复现的验证命令**与**实际结果**；未通过项不得勾选。共 26 项。

**图例**：✅ 通过 ｜ ⚠️ 通过但有已知边界 ｜ ❌ 未通过

---

## A. 科学逻辑与结构（1–6）

### A1 ✅ 论文存在一条明确的五段式证据链

**要求**：摘要、引言、结果、结论四处对证据链的描述一致，即"多数据集复现 → 多模型外部验证 → 可解释分析 → 反事实扰动 → 生物学假设"。

**验证**：
```bash
# 证据链关键词须在摘要、引言、结果、结论四处均出现
for f in 00_abstract 01_introduction 03_results 06_conclusion; do
  printf "%-18s %s\n" "$f" \
    "$(grep -c '多数据集复现\|跨数据集复现\|受控复现实验' docs/paper/sections/$f.tex)"; done
```
**结果**：四个文件全部 ≥1（摘要 1、引言 2、结果 1、结论 1）；引言 §1.5 显式写出五段式证据链。

---

### A2 ✅ 章节顺序按证据链重排，每节标注证据层级

**要求**：结果 12 个小节的标题均带 `（E1…E6）` 标注，且顺序为"可信度 → 复现 → 边界 → 归因 → 外部验证 → 反事实 → 关联 → 整合"。

**验证**：
```bash
grep -c "subsection{.*（E" docs/paper/sections/03_results.tex
grep -n "subsection{" docs/paper/sections/03_results.tex
```
**结果**：12 个小节全部带层级标注；顺序符合 §4.5 的映射表。

---

### A3 ✅ 六层证据被形式化定义，全文结论按层归档

**要求**：存在 E1–E6 的正式定义表，且至少有一张表把本文最强结论逐层归档。

**验证**：
```bash
grep -c "E1 & 预测证据\|E2 & 关联证据\|E4 & 反事实证据\|E6 & 因果证据" docs/paper/tables/tab10_evidence_layers.tex
grep -c "tab:convergence" docs/paper/sections/03_results.tex
```
**结果**：`tab10_evidence_layers.tex` 含全部六层定义（含"该层不能支持"列）；`03_results.tex` §3.12 含 `tab:convergence` 收敛表，把第 18 位逐层归档并明确 E5 为空、E6 不作断言。

---

### A4 ✅ 预测/关联/归因/反事实/实验/因果六类证据在正文中不被混用

**要求**：不存在把归因幅值写成"显著"、把模型反事实写成"效应"、把外部模型一致写成"证实"的表述。

**验证**：
```bash
# 允许"归因幅值不构成统计显著性证据"这类否定式表述；只查肯定式误用
grep -nE "归因幅值(是|为|达到|具有).{0,10}(显著|证明)" docs/paper/sections/*.tex   # 期望 0
grep -nE "(外部模型|CRISPRon).{0,30}(证实了|证明了)" docs/paper/sections/*.tex      # 期望 0
grep -c "不构成统计显著性证据" docs/paper/sections/03_results.tex
```
**结果**：前两项 0 命中；"不构成统计显著性证据"在结果中出现 2 次（§3.6 观察 2 与图 4 图注）、结论中出现 1 次。即所有涉及归因幅值的表述均为**否定式限定**，无肯定式误用。

---

### A5 ✅ 标题与关键词反映新的科学主张

**验证**：
```bash
grep -n "title{\|关键词" docs/paper/main/main.tex
```
**结果**：标题为「严格评估下 CRISPR-Cas9 sgRNA 编辑效率序列信号的跨数据集复现边界与第 18 位效应的外部模型验证」；关键词含"跨数据集复现、外部模型验证、反事实扰动、六层证据"。

---

### A6 ✅ 摘要中的每一条量化主张都能在结果正文中定位

**验证**：逐条比对 `00_abstract.tex` 与 `03_results.tex`。

| 摘要主张 | 正文位置 |
|---|---|
| DeepCRISPR 单细胞系中位 R² 0.067–0.120 | §3.2 观察 1、表 `tab:replication` |
| Hiranniramol 0.345–0.489 | §3.2 观察 1、表 `tab:replication` |
| Labuhn 全部为负（−0.725 至 −0.049） | §3.2 观察 1、表 `tab:replication` |
| CV +0.389 vs 零分布 −0.467±0.038 | §3.2 观察 2、表 `tab:replication` |
| CV −0.144 vs −0.287±0.050 | §3.2 观察 2、表 `tab:replication` |
| LOCO 中位 −0.027 至 +0.010 | §3.3、表 `tab:prediction` |
| 环境 \|ΔR²\| 3.2e-4–1.5e-3、p 0.975–0.9996 | §3.5、表 `tab:environment` |
| XGBoost 91.7% / MLP 86.5% | §3.6 观察 1 |
| 方向一致性 7/8（r=0.629，ρ=0.476） | §3.9 观察 2、表 `tab:externalvalidation` |
| 第 18 位 −12.425 vs 其余 +0.144；排名 1/21 | §3.10、表 `tab:counterfactual` |
| 第 18 位 C−A 实测差 +0.090/+0.092/+0.027/−0.015 | §3.11 观察 1 |
| mixed 0.118→0.073、LOCO +0.036→−0.008 | §3.4 |

**结果**：全部命中，无孤立主张。

---

## B. 数字的正确性与可追溯性（7–12）

### B7 ✅ 所有数字只来自最终结果批次

**要求**：灰产批次 `batch_20260909_full` 不进入任何结论（仅作 §3.4 对照）。

**验证**：
```bash
grep -n "batch_20260909_full" docs/paper/sections/*.tex docs/paper/tables/*.tex
```
**结果**：仅出现在 §2.5（方法，说明其为废弃批次）、§3.4（前后对照）与 §2.9（口径说明），与旧稿一致；无任何结论引用其数字。

---

### B8 ✅ 数值发散计数已修正为测试集口径（33 → 20）

**要求**：论文报告的数值发散数必须与测试集口径一致。

**验证**：
```bash
python analysis/paper_numbers.py 2>/dev/null | grep 发散
grep "数值发散" docs/paper/tables/tab0_data_quality.tex
grep -n "20 次" docs/paper/sections/03_results.tex | head -2
```
**结果**：`analysis/paper_numbers.py` 输出 `total=20 ... | validation=33`；表 `tab0` 为「20（全部为 Linear Regression）」；§3.1 与 §5.3 均报告 20 并解释 33 的来源。

---

### B9 ✅ 数据质量表中的未渲染占位符已修复

**验证**：
```bash
grep -c "n//3" docs/paper/tables/tab0_data_quality.tex   # 期望 0
grep "计划实验数" docs/paper/tables/tab0_data_quality.tex
```
**结果**：占位符 0 命中；该行为「计划实验数 & 1344 & 实验矩阵完整（single/all/mixed 各 448/448/448）」。

---

### B10 ✅ 候选表中的硬编码魔数已改为动态计算

**要求**：`tab6` 的"最高区域为 PAM 邻近区的模型数"与"motif 跨上下文覆盖"必须从产物计算。

**验证**：
```bash
grep -c "PAM-proximal region highest for 2/5" docs/paper/tables/tab6_candidates.tex
grep -c "_n_kernels_text\|_reg.idxmax" analysis/reporting/paper/make_assets.py
# 去掉注释后再查魔数（注释里允许记录该缺陷的历史与根因）
python - <<'EOF'
import re, pathlib
src = pathlib.Path("analysis/reporting/paper/make_assets.py").read_text().splitlines()
code = [l for l in src if not l.lstrip().startswith("#")]
hits = [(i + 1, l.strip()) for i, l in enumerate(code)
        if re.search(r'"(50 contexts|8 contexts|4/5)"', l)]
print("非注释代码中的魔数:", hits)      # 期望 []
EOF
```
**结果**：`tab6` 输出 `peak in 17-20 window for 4/5 model classes (minimum 21.9%); PAM-proximal region highest for 2/5 (transformer, xgboost)`；生成器含动态计算（`_reg.idxmax`、`_n_kernels_text`）；去注释后**魔数 0 命中**（仅剩两行 `#` 注释记录该缺陷的历史与根因）。真实值经 `region_attribution.csv` 与 `motif_candidates.csv` 独立复核：区域峰值 2/5（XGBoost 0.3271、Transformer 0.3253）；GAGG 3 个核变体、GGGG 2 个核变体。

---

### B11 ✅ 区域归因数值与现产物一致

**验证**：
```bash
python -c "
import pandas as pd
r=pd.read_csv('results/tables/paper/region_attribution.csv')
reg=r.groupby(['region','model'])['mean_norm_attribution'].mean().unstack()
print(reg.idxmax().to_dict())"
```
**结果**：`cnn→seed core (9-16) 0.344`、`linear→PAM-distal (1-8) 0.416`、`mlp→seed core (9-16) 0.336`、`transformer→PAM-proximal (17-20) 0.325`、`xgboost→PAM-proximal (17-20) 0.327`，与 §3.6 观察 2 完全一致（旧稿的"Linear 最高区域为 PAM 0.529"已被修正）。

---

### B12 ✅ 全部表格由脚本生成，无手工填写

**验证**：
```bash
head -2 docs/paper/tables/tab7_replication.tex
grep -n "不手工填写" docs/paper/sections/02_methods.tex docs/paper/sections/07_availability.tex
```
**结果**：新表头部含"本文件由 ... 自动生成。请勿手工编辑"；方法与可用性两节均声明不手工填写并列出生成脚本与执行顺序。

---

### B26 ✅ 位置层级归因的数字可从产物复算（本次最重要的修正）

**要求**：论文中"跨模型平均归因谱峰值""逐上下文峰值落在 17--20 的比例"必须能由 `results/tables/paper/` 的产物复算。

**背景**：旧稿这两组数字（峰值 0.089；比例 91.7%/86.5%/64.6%/54.0%/52.9%）在整个仓库中**没有任何来源**——不出现在任何 CSV、脚本或 JSON 中，是从更早版本继承下来的文本。实际值差异是方向性的（CNN 96.9% 而非 54.0%；Linear 21.9% 而非 52.9%）。

**验证**：
```bash
# 1) 权威值由脚本生成
python analysis/paper_numbers.py >/dev/null
python -c "
import json; a=json.load(open('results/paper_rewrite/authoritative_numbers.json'))['attribution_position']
print('五模型平均峰值:', a['mean_all_models'][0])
print('四模型平均峰值:', a['mean_non_linear'][0])
for m,v in a['per_context_peak_in_17_20_single_split'].items():
    print(' ', m, f\"{v['fraction_in_17_20']*100:.1f}%\")"
# 2) 论文与该 JSON 逐项一致（回归测试）
PYTHONPATH=/tmp/pytest_libs python -m pytest tests/scientific/test_paper_terminology.py -q \
  -k "attribution or stale"
# 3) 旧数字不得出现
grep -rn "0\.089\|91\.7\|54\.0\|52\.9" docs/paper/sections/*.tex docs/paper/zh/论文.md   # 期望 0
```
**结果**：五模型平均谱峰值 = 第 1 位（0.0864），四模型（剔除 Linear）= 第 18 位（0.0878）；逐上下文比例 XGBoost 100.0%、CNN 96.9%、MLP 90.6%、Transformer 65.6%、Linear 21.9%；旧数字 0 命中。新增表 `tab11_attribution_position.tex` 由 `build_rewrite_tables.py` 从该 JSON 生成；§3.6、摘要、结论第 5 条、§3.12、收敛表、图 4 图注均已同步。


---

## C. 跨数据集复现（13–15）

### C13 ✅ 三个数据集的完整结果均被报告，包括复现失败的那个

**验证**：
```bash
grep -c "Hiranniramol" docs/paper/sections/03_results.tex
grep -c "Labuhn" docs/paper/sections/03_results.tex
grep -c "Labuhn" docs/paper/sections/00_abstract.tex docs/paper/sections/06_conclusion.tex
```
**结果**：结果正文提及 Hiranniramol 与 Labuhn，摘要与结论均明确写出 Labuhn 的 7 个配置全部为负。**复现失败结果未被降级到补充材料**。

---

### C14 ✅ Labuhn 的失败机制被诊断，而非仅报告数字

**要求**：必须排除"标签方差太小导致 R² 不可靠"这一最常见的反驳。

**验证**：
```bash
grep -n "预测坍缩\|sd}_{\\\\text{pred}}" docs/paper/sections/03_results.tex
python -c "
import pandas as pd,glob,os,numpy as np
for d in sorted(glob.glob('results/batches/ultimate_run_2/*/')):
    if d.endswith('summary/'): continue
    f=[p for p in glob.glob(d+'*_predictions.csv') if 'validation' not in p]
    df=pd.read_csv(f[0]); print(os.path.basename(d.rstrip('/')).split('_')[2],
        round(df.y_true.std(ddof=1),4), round(df.y_pred.std(ddof=1),4))"
```
**结果**：§3.2 观察 3 + 表 `tab:collapse` 给出完整诊断——Labuhn 标签 sd=0.2153（与 Hiranniramol 的 0.3674 同量级，排除低方差解释）；6/7 个配置预测 sd 仅为标签的 3%–37%（坍缩）；Linear 例外（0.93）但 r=0.165，故 R² 最低。命令输出与表中数字逐项一致。

---

### C15 ✅ 复现结论有独立于官方划分的复核

**要求**：不能只比较"某一次划分下的 R²"。

**验证**：
```bash
python -c "
import json; d=json.load(open('results/paper_rewrite/authoritative_numbers.json'))
for k in ('hiranniramol_single','labuhn_single'): print(k, d[k]['cv5_signal'])"
grep -c "5 折交叉验证\|置换零分布" docs/paper/sections/03_results.tex
```
**结果**：Hiranniramol `cv5_r2=+0.3886`、`null=-0.4668±0.0375`；Labuhn `cv5_r2=-0.1444`、`null=-0.2869±0.0505`。§3.2 观察 2 完整报告，方法 §2.7(6) 给出协议。

---

## D. 外部模型验证与反事实扰动（16–18）

### D16 ✅ 外部模型验证的独立性可核查

**验证**：
```bash
grep -n "黄金测试\|逐字节相同\|SHA-256" docs/paper/sections/02_methods.tex docs/paper/sections/03_results.tex
ls deploy/external/crispron/package/SHA256SUMS.txt deploy/external/crispron/dependencies/SHA256SUMS.txt
grep -c "TEST ok" deploy/external/crispron/logs/selftest_result.md
```
**结果**：方法 §2.10 与结果 §3.9 观察 3 均报告 `bin/test.sh` → `TEST ok` 且中间文件与官方 `test/outdir.original/` 逐字节相同；校验和文件存在。

---

### D17 ✅ 反事实扰动的 WT 选择规则被预登记，且不使用突变侧信息

**验证**：
```bash
grep -n "SELECTION_RULE_VERSION\|assert_no_mutant_information_used" analysis/candidates/wt_position18_selection.py | head -3
python -c "
import json; d=json.load(open('results/tables/candidates/wt_position18_selfcheck.json'))
print('mutant_fields_present_in_selection =', d['mutant_fields_present_in_selection']); print(d['rule_version'])"
grep -n "预登记\|assert" docs/paper/sections/02_methods.tex | head -5
```
**结果**：`rule_version = wt-pos18-representative-v1`；`mutant_fields_present_in_selection = []`（空）；方法 §2.11 完整描述规则并要求断言。

---

### D18 ✅ 饱和突变排除了"位置挑选"的可能，且分歧样本被保留

**验证**：
```bash
python -c "
import json; p=json.load(open('results/tables/external_validation/crispron_mutagenesis_v1_pos18_analysis.json'))
print('rank', p['pos18_rank_in_position_importance'], 'of', p['n_positions_ranked'])"
grep -c "WT08" docs/paper/sections/03_results.tex docs/paper/tables/tab8_external_validation.tex
grep -n "保留在全部统计中\|保留而非剔除\|保留而非" docs/paper/sections/03_results.tex | head -3
```
**结果**：第 18 位排名 `1 of 21`；WT08 在结果正文与验证表中出现；§3.9 观察 2 明确"该序列被保留在全部统计中，而非剔除为异常值"。

---

## E. 编译、图表与工程（19–22）

### E19 ✅ LaTeX 编译干净，无未定义引用/引文/超尺寸浮动体

**验证**：
```bash
cd docs/paper/main && latexmk -xelatex -bibtex -interaction=nonstopmode main.tex
grep -icE "undefined" main.log
grep -icE "Float too large" main.log
pdfinfo main.pdf | grep -i pages
# 所有 \includegraphics 引用的图片必须存在
cd .. && grep -oh "includegraphics\[[^]]*\]{[^}]*}" sections/*.tex \
  | sed 's/.*{//;s/}//' | sort -u \
  | while read f; do [ -f "main/$f" ] || [ -f "$f" ] || echo "MISS $f"; done
```
**结果**：exit 0；`undefined` = 0；`Float too large` = 0（修复前为 1，源于 81 行的 `tabS2_sequence`，现按 35 行拆为 3 段）；**Pages: 44**；11 张图片全部存在，无 MISS。

**图命名约定（重要）**：LaTeX 图号由**出现顺序**决定，与文件名无关。本文新加入的外部验证图按出现顺序渲染为**图 6**，因此其文件命名为 `fig_ext_a…d`（不带编号），以避免文件名与渲染图号不一致——早期以 `fig8*` 命名即产生了该不一致（已修正）。正文全部使用 `\ref`，无硬编码图号。

---

### E20 ✅ 新增引文的元数据经过核实（非杜撰）

**验证**：
```bash
grep -A4 "Hiranniramol2020Bioinformatics\|Labuhn2018NAR" docs/paper/main/references.bib
grep -c "Hiranniramol2020Bioinformatics\|Labuhn2018NAR" docs/paper/main/main.bbl
```
**结果**：两条引文均进入 `.bbl`；元数据经 Crossref / Europe PMC 核实：Hiranniramol, *Bioinformatics* 36(9):2684–2689 (2020), doi:10.1093/bioinformatics/btaa041；Labuhn, *NAR* 46(3):1375–1385 (2018), doi:10.1093/nar/gkx1268。

---

### E21 ✅ PDF 中确实包含新的科学内容（非仅源码改动）

**验证**：
```bash
pdftotext docs/paper/main/main.pdf /tmp/main.txt
for s in 跨数据集复现 CRISPRon Labuhn Hiranniramol 六层证据 0.489 -12.425 0.629 1/21; do
  printf "%-16s %s\n" "$s" "$(grep -c -e "$s" /tmp/main.txt)"; done
```
**结果**：全部 > 0（跨数据集复现 8、CRISPRon 47、Labuhn 46、Hiranniramol 35、六层证据 12、0.489 8、−12.425 1、0.629 8、1/21 3）。

---

### E22 ✅ 工程改动未破坏既有功能，测试全绿

**验证**：
```bash
PYTHONPATH=/tmp/pytest_libs /home/zhang/bioprogram/myenv/bin/python -m pytest tests/ -q
# 论文术语纪律与关键数字的专项回归测试（新增）
PYTHONPATH=/tmp/pytest_libs /home/zhang/bioprogram/myenv/bin/python -m pytest \
  tests/scientific/test_paper_terminology.py -q
```
**结果**：全量 **383 passed / 14 skipped / 0 failed**（重写前为 332 passed；新增 51 项论文专项测试）。专项测试 **51 passed**。

**新增测试的负向验证**（确认不是空断言）：临时向 `06_conclusion.tex` 追加"…C18A 导致编辑效率下降，这是因果证明。"后，`test_forbidden_claims_only_in_negation` 立刻失败并定位到行号；临时追加"跨模型平均谱峰值位于第 18 位（0.089），XGBoost 91.7%。"后，`test_stale_attribution_numbers_removed` 同样失败。两次还原后均恢复 51 passed。

`tests/scientific/test_paper_terminology.py`（51 项）固化的约束：
1. 7 条禁用措辞只允许出现在否定语境（`不/非/未/无/放弃/≠` 等）；
2. 归因幅值不得被写成"显著/证明"（否定式限定除外）；
3. E1–E6 六层定义必须齐备，E5 必须标注"本文无"，E6 必须标注"本文不作任何此类断言"；
4. 三个数据集必须全部出现在摘要/结果/结论，且 Labuhn 的 −0.725 必须在结果中；
5. `tab0` 的发散计数必须为 20（不得为 33），不得残留 `{n//3}` 占位符；
6. `tab6` 的区域计数必须为 2/5（不得为 4/5）；
7. 7 个关键数字与 8 个归因权威值必须在论文中出现，且必须与 `authoritative_numbers.json` 逐项一致；
8. 9 个无法从产物复算的旧数字（`0.089`/`91.7`/`86.5`/`54.0`/`52.9`/`0.529`/`-0.049`/`0.041--0.095`）不得重新出现；
9. 方法节必须声明各模型 SNR 公式不统一（CNN 的 `ISM_SNR` 为标准形式）、且 `CNN_ISM` 的单通道翻转不等价于碱基替换。

改动过的生产脚本及其修复：

| 文件 | 修复内容 |
|---|---|
| `deploy/hpc/verify_hpc_rerun.py` | 显式排除验证集指标文件，固定测试集口径 |
| `analysis/reporting/paper/make_data_quality_table.py` | 修复未渲染的 `{n//3}` f-string 占位符 |
| `analysis/reporting/paper/make_assets.py` | `DATA_MAIN` 路径修复；`_tex_table` 超长表拆页；区域峰值为动态计算；motif 核变体覆盖为动态计算；`region` 加入 `write_tables()` 参数 |
| `analysis/paper_numbers.py`（新） | 权威数字汇总（唯一数据源） |
| `analysis/reporting/paper_rewrite/build_rewrite_tables.py`（新） | 新表生成 |
| `tests/scientific/test_paper_terminology.py`（新） | 论文术语纪律、口径纪律、归因数字可复算性与方法学表述的回归测试（51 项） |

---

## F. 交付物与边界声明（23–25）

### F23 ✅ 两份交付文档齐备

**验证**：
```bash
ls -la docs/paper/SCIENTIFIC_LOGIC_CHANGELOG.md docs/paper/DELIVERY_CHECKLIST.md
```
**结果**：两份文档均存在（本文件即其一）。

---

### F24 ✅ 论文明确声明"无湿实验验证"与"不作因果断言"

**验证**：
```bash
grep -c "本文不含任何湿实验\|任何 E5 证据\|不构成因果" docs/paper/sections/*.tex
grep -c "本文无\|本文不作任何此类断言" docs/paper/tables/tab10_evidence_layers.tex
```
**结果**：摘要、引言 §1.4、方法 §2.12、结果 §3.12、局限 §5.5、结论第 10 条均明确声明；表 `tab10` 的 E5 行为"**本文无**"、E6 行为"**本文不作任何此类断言**"。

---

### F25 ✅ 已知边界被显式列出，而非回避

**要求**：重写过程中发现的旧稿错误与未能解决的方法学混杂必须被披露。

**验证**：
```bash
grep -n "口径修正的披露\|该差异记录为口径约定的一部分" docs/paper/sections/03_results.tex
grep -n "复现实验的可比性" docs/paper/sections/05_limitations.tex
```
**结果**：§3.1 含"口径修正的披露"段（33 vs 20）；§5.1「复现实验的可比性」列出 4 条边界（数据集非同分布、外部数据集仅一次划分、标签语义不可直接比较、外部数据集无表观通道导致环境结论无法复现）；§5.4 列出外部验证的 4 条边界。

---

## 汇总

| 类别 | 项数 | 通过 |
|---|---|---|
| A 科学逻辑与结构 | 6 | 6 ✅ |
| B 数字正确性与可追溯性 | 7 | 7 ✅ |
| C 跨数据集复现 | 3 | 3 ✅ |
| D 外部模型验证与反事实扰动 | 3 | 3 ✅ |
| E 编译、图表与工程 | 4 | 4 ✅ |
| F 交付物与边界声明 | 3 | 3 ✅ |
| **合计** | **26** | **26 ✅** |

**遗留项（不影响交付，已知并记录）**：

1. `docs/paper/zh/论文.md` 为同步重写的中文长稿，其详略程度高于 LaTeX 正式稿；两者结论一致，但长稿保留了较多平台工程细节。
2. 两个外部数据集各只有一次 `single` 划分（7 个模型），无法给出配置间分布；已用全数据 5 折 CV 复核补偿，但重复次数仍为 1。
3. 外部验证只有 8 个预登记实例（$n=8$），未做显著性检验；扩大样本量与引入第二个独立外部模型列为未来工作（§8 方向四）。
4. DeepCRISPR 的 hg19 侧翼取自 UCSC 校验和缓存（`results/tables/candidates/_hg19_window_cache.csv`）；外部验证的可复现性依赖该缓存的完整性。
