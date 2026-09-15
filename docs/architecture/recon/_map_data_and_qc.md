# 数据链路地图：原始数据 → 特征工程 → schema → QC → 数据划分

> ⚠️ **历史勘察快照（重构前）**：本文记录 2026-09-14 目录重构**之前**的结构，其中的路径名（`src/`、`analyse/`、`data/proceeded_data/`、`results/<batch>`）均为旧路径。
> 当前权威结构见 `README.md` 与 `docs/architecture/`；科学定义见 `docs/science/`。


> 只读勘察报告。范围：`data/source_data/*.csv` → `data/proceeded_data/*` → `train.py`/`data_digging.py` → `results/` → `analyse/` 消费端。
> 证据一律给 `file:line` 或产物路径。所有行号以仓库根副本为准；根目录另有一份**未跟踪的逐字节镜像 `./Submit/`**（`git ls-files Submit` 为空），引用时请去重。
> 本报告不修改任何已有文件。

---

## 0. 链路总览（谁产生、谁消费）

| 阶段 | 入口 | 关键产物 |
| :--- | :--- | :--- |
| 原始数据 | `data/source_data/{hct116,hek293t,hela,hl60}.csv` | 10 列表（见 §1.1） |
| 特征工程 | `src/feature_engineering.py`（CLI `--source-dir/--output-dir/--config`，`:1967-2029`） | `data/proceeded_data/{cl}_features_23x8.npy`、`{cl}_features_184.npy`、`{cl}_labels.npy`、`{cl}_metadata.csv`、`feature_schema.json`、`feature_engineering_summary.csv` |
| schema | `data/proceeded_data/feature_schema.json`（唯一权威；**`data/feature_schema.json` 不存在**） | `channel_names`、`feature_names`、`channel_count=8`、`feature_count=184` |
| 划分 | `src/input_control/cell_line_division.py::divide_data`（`:324-363`） | `split_type/cell_line/random_seed/train_data/valid_data/test_data` + `schema`/fractions |
| 环境子集 | `src/input_control/cell_environment_combination.py::prepare_train_valid_test`（`:1357-1480`） | 模型输入（2D 184 或 3D (N,23,8)，**mask 置零不降维**） |
| 单实验 | `train.py::run_one_experiment`（`:441-592`） | `*_info.txt` / `*_metrics.json` / 权重 / 重要性 CSV |
| 网格 | `data_digging.py`（`:457-541`） | `results/<batch>/<run_name>/` |
| 汇总 | `analyse/collect_results.py` | `summary/metrics_tables/all_experiments.csv`（1344×78） |
| 分析 | `analyse/pipeline.py`（`-m analyse.pipeline`） | `summary/tables|summary|figures` |
| 独立 QC | `analyse/data_QC.py`（经 `backend/crispr_workspace/qc_service.py:24` 子进程调用） | `workspace/qc_sessions/qc_*/qc_summary.json`、`quality_report.md`、2 张 KDE |

⚠ **QC 不在训练链路上**：`data_digging.py`/`train.py`/`src/feature_engineering.py` 都不调用 `analyse/data_QC.py`（grep 无引用，除 `backend` 与测试）。`data_QC` 是"训练前独立体检"。

---

## 1. 变量空间：本项目实际建立了什么

### 1.1 原始数据与 metadata 表头

原始 4 个 CSV 的表头完全一致（实读 `head -1`）：

```
Chromosome,Start,End,Strand,sgRNA,CTCF,Dnase,H3K4me3,RRBS,Normalized efficacy
```

`data/source_data/hct116.csv`(4239) / `hek293t.csv`(4566) / `hela.csv`(8101) / `hl60.csv`(2076)，合计 **18982** 行。

产物 metadata 表头（`src/feature_engineering.py:136-143` 定义，`save_metadata :1504-1525` 写出）：

```
Cell line,Chromosome,Start,End,Strand,sgRNA,Normalized efficacy
```

| 文件 | 行数 |
| :--- | ---: |
| `data/proceeded_data/hct116_metadata.csv` | 4239 |
| `data/proceeded_data/hek293t_metadata.csv` | 2333 |
| `data/proceeded_data/hela_metadata.csv` | 8101 |
| `data/proceeded_data/hl60_metadata.csv` | 2076 |
| 合计 | **16749** |

> ⚠ metadata **不含**表观轨道（CTCF/…）列，也不含位置信息。环境轨道只存在于 `*_features_23x8.npy` 的第 4–7 通道；下游若想按"该样本的 CTCF 轨道"分层，必须回读 `.npy`，metadata 不够。

### 1.2 `sequence`（23nt × 4 通道）

- 长度常量 `SEQUENCE_LENGTH = 23`：`src/feature_engineering.py:132`；通道定义 `DEFAULT_SEQUENCE_CHANNELS=["A","C","G","T"]`：`:147-152`；`data/feature_config.json:2-7` 亦写 `["A","C","G","T"]`。
- 编码一 hot：`encode_sgrna` `:358-429`，`encoded[position, channel_index]=1.0`；遇到 `A/C/G/T` 之外的字符**直接 raise**（`:411-418`）。
- 展平顺序：**position-major、channel-minor**（`engineer_dataframe :1295-1301` 用 `reshape(N, 23*C)`，等价于 `for p in 1..23: for ch in channels:`）→ `feature_names` 为 `pos1_A,pos1_C,pos1_G,pos1_T,pos1_CTCF,...,pos23_RRBS`（`generate_vector_feature_names :919-951`；实读 `data/proceeded_data/feature_schema.json`）。
- 长度校验 `validate_sequence :332-355` 只查 `len==23`（strip+upper 后）。
- **PAM 未编码为一个变量**：代码不校验/不特征化 21–23 位是否 `NGG`；仅在可视化里硬编码标注（`analyse/visualization.py:508-518` "1 to 20: Protospacer / 21 to 23: PAM"）。数据事实：4 个源文件 pos22–23 100% 为 `GG`（`hek293t` 等实测 `PAM last2==GG` = 全部行；`docs/paper_analysis/position18_ism_audit.py:322` 亦用 `sg.str[21:23].eq("GG")` 交叉校验）。`analyse/config.py:145-146` 明确 `region_ranges=()` 表示"schema 未定义 seed/PAM → 不假设"。

### 1.3 `environment`（CTCF/Dnase/H3K4me3/RRBS，per-position binary）

`data/feature_config.json:8-47` 定义 4 个特征，每个都是：

```json
{"name":"CTCF","column":"CTCF","type":"per_position_binary",
 "encoding":{"A":1,"N":0},"enabled":true}
```

编码规则（`encode_per_position_binary :436-487`）：把该样本的 23 字符串逐位映射为 23×1，**`A→1.0`、`N→0.0`**，其它字符 raise（`:471-478`）。语义：**"该位置是否被该表观轨道标注为可用/阳性区域"的指示（indicator），不是 CTCF 结合强度、不是 DNase 信号值、不是甲基化率**。这从两方面可证：

1. 配置文件只有字符映射 `A/N`（`type` 名即 `per_position_binary`），没有任何强度/连续值字段；
2. `src/feature_engineering.py:36-54` 注释把 `per_position_binary` 与 `per_position_numeric`（23 个连续值）并列为两类，后者当前**没有任何启用的实例**（`feature_config.json` 4 项全是 binary）。

框架还预留了 `per_position_numeric`（`:494-626`）与 `global_numeric`（广播到 23 位，`:633-691`），但 `data/feature_config.json` 未启用；`get_channel_specs :757-806` 会把启用项追加到 sequence 通道之后。

**实际数据的退化（QC 未覆盖）**：

| 细胞系 | CTCF | Dnase | H3K4me3 | RRBS |
| :--- | :--- | :--- | :--- | :--- |
| hct116 | A 86.6% / N 13.4% | A 95.1% | A 84.0% | A 0.9% / N 99.1%，pos23 恒 N |
| hek293t | A 67.0% | **A 100%（全轨恒 1）** | A 79.7% | A 0.6%，pos23 恒 N |
| hela | A 99.0% | **A 100%（全轨恒 1）** | A 97.2% | A 1.0%，pos23 恒 N |
| hl60 | A 38.4% | A 97.4% | A 81.5% | A 1.2%，pos23 恒 N |

（实读 4 个 CSV 统计；`all-A rows` 见勘察脚本输出。）⇒ hek293t/heLa 的 Dnase 通道是**零方差常数列**，`RRBS` 近 99% 为 0 且 pos23 恒定。`data_QC.py` 只对 **sgRNA 序列**做单态位点检测（`:617-653`，实测只报 `pos22=G,pos23=G`），**不检查表观轨道是否方差为 0**。这直接解释了 §2 里线性模型秩亏与"死列"。

### 1.4 `position`：1-based / 0-based 分布

**唯一权威约定：张量轴 0 索引，用户可见命名 1-based。** 但中间产物里两套并存：

| 位置 | 约定 | 证据 |
| :--- | :--- | :--- |
| schema `feature_names` | **1-based** `pos{p}_{ch}` | `data/proceeded_data/feature_schema.json` |
| 数组轴 | 0-based（`encoded[position, ...]`） | `src/feature_engineering.py:406-427` |
| `predict.py` plan | **1-based** | `predict.py:134` `[f"pos{p}_{ch}" for p in range(1,seq_len+1) ...]` |
| `train.py::build_feature_names`（2D 模型） | **1-based** | `train.py:311-320` |
| LR/XGB/MLP 保存的权重/重要性 CSV | **1-based** `pos{p}_{ch}`（LR 无 T，161 列） | 实测 `linear_regression_weights.csv`、`xgboost_feature_importance.csv` |
| CNN/Transformer 重要性 CSV：`Feature` 名 | **0-based** `{ch}_pos_{l}` | `src/cnn/cnn.py:373`；`src/transformer/transformer.py:377` |
| CNN/Transformer 重要性 CSV：`Position` 列 | **0-based 0..22** | `src/cnn/cnn.py:376`；实测 `cnn_feature_importance.csv` 首行 `T_pos_20,20,T` |
| `analyse/attribution/extractors.py::_parse_position_channel` | 归一化为 **1-based** | `:31,38` |
| `analyse/importance_extraction.py::extract_feature_position` | **不归一化**（CNN 行落 0-based） | `:84-95` |
| `analyse/importance_extraction.py::get_canonical_feature_id` | 归一化为 **1-based** | `:653-667` |
| `analyse/visualization.py::parse_feature_position_channel`（legacy） | 对所有 ≤22 的值 **+1**，对 1-based 名**误加** | `:177-180` |
| `analyse/data_QC.py` 行号 | 1-based（含表头） | `:482,634` |
| signed-ISM | 1-based 18 ↔ 张量 index 17 | `docs/paper_analysis/position18_signed_substitution_ism.py:55-56` |
| ISM audit | 内部 0-based 17 → 输出 1-based 18 | `docs/paper_analysis/position18_ism_audit.py:32-33,85` |

实测三个解析器（本会话直接调用）：

```
feature          legacy viz   attribution   get_canonical   extract_feature_position
pos1_A                2            1             1                1
pos20_G              21           20            20               20
T_pos_20             21           21            21               20
CTCF_pos_9           10           10            10                9
pos9_CTCF            10            9             9                9
```

### 1.5 `cell line`

- 不是预测输入。原始 CSV 没有该列；`load_source_csv :1229-1233` 由**文件名**注入（`df.insert(0,"Cell line",cell_line)`，`cell_line` 来自 `os.path.splitext(os.path.basename(csv_file))[0]`，`:1573-1577`）。
- 它是**分层/划分变量**：`metadata_train/valid/test` 保留 `Cell line`（`cell_line_division.py:202-208`），`mixed` 合并后 `cell_line` 被统一写成 `"none"`（`collect_results.py:124-127`、`analyse/data/loaders.py:105`、`analyse/importance_extraction.py:45-51`）。
- 细胞系集合动态发现：`discover_available_cell_lines :55-72`（扫 `*_metadata.csv` 与 `*_features_*.npy`）；**目录空时仍硬编码回退** `["hct116","hek293t","hela","hl60"]`（`:72`）。
- ⚠ 产物 metadata 里 `Cell line` 一列是划分/分层的唯一依据；`environment` 轨道内容不随之携带（见 §1.1）。

### 1.6 `label`（Normalized efficacy）

- 列名常量：`TARGET_COLUMN = "Normalized efficacy"`（`src/feature_engineering.py:134`），也是 `get_required_columns :1030-1060` 的必需列 → 缺失值会在 `load_source_csv :1187-1212` 被拒。
- **来源**：仓库内**无归一化实现**。`README.md:334-337` 说明数据来自公开基准 **DeepCRISPR**（Chuai et al. 2018）；`docs/statistics_and_parameters_zh.md:312` 明确写"归一化算法：仓库内无实现（README 称来自 DeepCRISPR）"。
- 范围（实读源 CSV）：hct116 `[0.0003, 0.9459]`；hek293t `[0.0369, 0.5903]`；hela `[0.0000, 1.0000]`；hl60 `[0.0278, 0.6927]`；无 NaN。**代码没有任何 `[0,1]` 硬门禁**；唯一的越界提示是 `data_QC.py:358-361` 的离群归因 hint（`y<0 or y>1 → extreme_target_y`），只写进报告，不拦截。
- 目标待测集 `data/todo_data.CSV` 表头 `sgRNA,Efficacy`，180512 行，`Efficacy∈{0,1}`——与训练标签不同名、不同语义，仅用于 `predict.py`。

### 1.7 哪些量可直接作为 biological factor 解释，哪些只是模型输入

| 量 | 能否作 biological factor | 理由（证据） |
| :--- | :--- | :--- |
| `sequence` 每个 (position, base) 的 one-hot 系数/归因 | **可以**（有明确生物学含义：该位点该碱基） | `pos{p}_{ch}` 命名与张量轴一一对应（`train.py:311-320`、`cnn.py:373`）；线性系数有符号（`linear_regression.py:465-488`） |
| `environment` 的 per-position binary 通道系数/归因 | **谨慎可解释**：解释为"该位点是否落在 CTCF/DNase/H3K4me3/RRBS 标注区域内"的边际效应 | 编码只有 A/N→1/0（`feature_config.json:8-47`），**不是结合强度** |
| 单通道整体重要性（如 "RRBS 是 Tier 1"） | 可以，但等价于"整条 23 位指示轨道" | 通道级聚合见 `analyse/evidence/integration.py:132-292` |
| `cell line` | **不能作为预测因子进入模型**；只能作分层/异质性变量 | 从不进入 X（`cell_environment_combination.py` 只切通道）；`mixed` 下被写成 `"none"`（`collectors`/`loaders` 多处） |
| `Normalized efficacy` | 目标 y | `engineer_dataframe :1303-1307` |
| `Chromosome/Start/End/Strand` | **未进入模型**，只保留在 metadata | `METADATA_COLUMNS :136-143` 进 metadata，`build_feature_matrix :813-912` 只读 `sgRNA` + 环境列 |
| `feature_count=184`（23×8） | 只是输入维度 | `feature_schema.json` |

### 1.8 schema/config 实际字段（逐字）

`data/feature_config.json`（输入配置，仅定义通道与编码）：

```json
{"sequence_channels":["A","C","G","T"],
 "environment_features":[
   {"name":"CTCF","column":"CTCF","type":"per_position_binary","encoding":{"A":1,"N":0},"enabled":true},
   {"name":"Dnase", ... }, {"name":"H3K4me3", ... }, {"name":"RRBS", ... }]}
```

`data/proceeded_data/feature_schema.json`（产物，`generate_feature_schema :958-1023`）：

```
sequence_length: 23
sequence_channels: ["A","C","G","T"]
environment_features: [同上 4 项]
channel_count: 8
feature_count: 184
channel_names: ["A","C","G","T","CTCF","Dnase","H3K4me3","RRBS"]
feature_names: ["pos1_A","pos1_C","pos1_G","pos1_T","pos1_CTCF","pos1_Dnase","pos1_H3K4me3","pos1_RRBS",
                "pos2_A", ..., "pos23_RRBS"]   # 184 项，position-major
```

产物汇总 `data/proceeded_data/feature_engineering_summary.csv`：

```
cell_line,original_samples,duplicate_rows,final_samples,channel_count,feature_count
hct116,4239,0,4239,8,184
hek293t,4566,2233,2333,8,184
hela,8101,0,8101,8,184
hl60,2076,0,2076,8,184
```

> 注：`data/feature_config.user.json` 被 `README.md:430` 提到，但**仓库内不存在**（`ls data/*.json` 只有 `feature_config.json`）。`backend` 向导在用户改写映射时会生成它，但本仓库没有该文件。

---

## 2. schema 如何保证跨分析位置一致

### 2.1 `feature_names` 的构造

- 特征工程侧：`generate_vector_feature_names :919-951` —— `for position in range(1, 24): for channel in channel_specs: f"pos{position}_{channel['name']}"`；`channel_specs = sequence_channels + enabled environment_features`（`get_channel_specs :757-806`）。
- 训练侧：`train.py::build_feature_names :306-322` 对 2D 输入重建**同一顺序**（schema `channel_names` × 1..23）；对 3D 输入只返回 `channel_names`（8 个通道名，无位置），由 CNN/Transformer 内部再展开成 `{ch}_pos_{l}`。
- 落盘一致性校验：`save_vector_csv :1391-1447` 断言 `features_2d.shape[1] == len(feature_names)`。

### 2.2 `build_channel_plan` 的 keep/seq 索引与展平顺序

`predict.py:101-136`（Ultimate / 目标预测路径）：

- `seq_idx = [i for i,ch in enumerate(channel_names) if ch in SEQ_LETTERS]`（`:112`）；`epi_all` = 其余（`:115`）；`chosen_epi` 按 schema 序保序（`:122`）。
- `keep = sorted(seq_idx + [channel_names.index(c) for c in chosen_epi])`（`:124`）—— **保持 schema 顺序**，sequence 通道恒选。
- `plan["feature_names"] = [f"pos{p}_{ch}" for p in range(1, seq_len+1) for ch in kept]`（`:134`）。
- `subset_arrays_3d :139-142`：`X3[:, :, plan["keep"]]` 再 `reshape(len,-1)` → **丢列压缩**。

### 2.3 线性模型剔 `_T` 参照列（161 / 69）

`src/linear_regression/linear_regression.py::select_non_t_reference_features :465-488`：丢弃所有 `endswith("_T")` 的列（`REFERENCE_T_SUFFIX="_T" :465`），保留 `keep_indices`；调用点 `:734-744`。
- 184 → **161**（23 位点 × (A,C,G + 4 表观) = 7 列/位点）。
- 92（纯序列 4 通道）→ **69**（23 × 3）。
- 实测：`results/batch_20260909_full/single_hct116_linear_sequence/linear_regression_weights.csv` 有 161 特征 + `Bias`。
- ⚠ 网格里**无论选哪个 environment**，`feature_count` 都是 161（`linear_regression_info.txt` 实测 `sequence` / `sequence_ctcf` / `all` 均为 161），因为 `apply_environment_combination` 只把未选表观通道**置零**而不删列；被置零的通道成为数值死列（实测 H3K4me3/RRBS 系数 ≈1e-16），因此 `sequence` 配置下 161 列里有 92 列恒 0，`Numerical rank` 只有 60–69（实测 hct116 `sequence` rank=60、`all` rank=149）。
- ⚠ 日志口径错误：`:744` 把"保留列数 161"写成"已剔除 161 个 `_T` 参照特征"（应为剔除 23）。

### 2.4 CNN 的 `sequence_channels=4` 内部切片

`src/cnn/cnn.py:563-637`：

- `sequence_channels = sum(1 for c in schema_channels if c.upper() in {A,C,G,T})`（`:570-572`）→ 当前批次为 **4**（实测 `all_experiments.csv` 的 `sequence_channels` 列恒为 4）。
- 输入恒 `(N,23,8)`（`apply_environment_combination` 置零，`prepare_model_input :1295-1350`）。
- `selected_env == []` → `X = X[:,:,:4]`（`:590-594`）；非空 → `concat(seq_part, X[:,:,env_indices_abs])`（`:596-616`）。
- `forward :186-193`：`seq_x = x[:,:,:self.sequence_channels].unsqueeze(1)`；`env_x = x[:,:,self.sequence_channels:]`。
- legacy else 分支 `sequence_channels=3`、`seq_names=["A","G","C"]`（`:579,624`）在当前 schema 下不可达。
- ⚠ **Transformer 没有切片**：`input_dim=8`，恒用 (N,23,8)（实测 `input_shape_train=[N,23,8]`）；`transformer.py:572` 有一个硬编码 7 通道 fallback `["A","G","C","CTCF","Dnase","H3K4me3","RRBS"]`（缺 T），仅当 `feature_names` 长度≠8 时触发，正常路径传 8 个通道名故不可达——潜在雷。

### 2.5 `_parse_position_channel` 的 +1 约定

`analyse/attribution/extractors.py:24-38`：

```python
m = re.search(r"pos_?(\d+)", fn, re.IGNORECASE)
one_based = m.start() == 0 and fn.lower().startswith("pos")
return (pos0 if one_based else pos0 + 1), ch
```

- `pos20_G` → `(20,'G')`（名字自带 1-based）；`T_pos_20`/`CTCF_pos_9` → `(21,'T')`/`(10,'CTCF')`（0-based +1）。
- 通道取 `pos` 片段之外按 `[_\-.]` 切分的首个非数字 token（`:32-37`）。
- 已知缺陷：`pos_20_delta_G` 会把通道解析成 **`delta`** 而非 `G`（实测）。

### 2.6 attribution / ISM / SHAP / IG / ANOVA / environment factorial 各自靠什么对齐

| 分析 | 位置/通道从哪来 | 对齐机制 | 证据 |
| :--- | :--- | :--- | :--- |
| attribution extraction + summary | 只读训练产出的 importance CSV 的 `Feature` 串，调 `_parse_position_channel` | 两种命名风格都被归一化为 1-based；`Bias/intercept` 被丢弃 | `extractors.py:53-139`（`:101-103` 跳 Bias，`:117` 解析）；契约 `analyse/docs/interface_contract.md:71` 明确 "position 1-based" |
| key_regulatory_biomarkers | 同一批 CSV，但用 `get_canonical_feature_id` | 独立实现的 0→1 归一化（`^pos(\d+)_` 当 1-based；`pos_(\d+)`/尾部数字 +1） | `importance_extraction.py:623-676`、`:746`；实测产物 `pos9_CTCF` 等 1-based |
| importance_extraction 的 per-model `.md` 排序 | `extract_feature_position` | **不归一化** → CNN/Transformer 行按 0-based 排序 | `:84-95`，调用点 `:337,397,457,528,591` |
| 环境合法性过滤 | `is_feature_valid_for_env` + `get_active_channels` | 按 `environment` 串判断通道是否激活（A/C/G/T 恒激活） | `importance_extraction.py:54-63,98-102` |
| SHAP / IG / attention / CNN-ISM | 各模型训练内生成 | 特征名由 `train.py:311-320`（2D，1-based）或 `cnn.py:373`/`transformer.py:377`（3D，0-based）注入；`src/xai_importance.py:76-122` 只做列白名单/重命名，不产生特征名 | `mlp.py:301`；`cnn.py:370-381`；`transformer.py:372-385`；`xai_importance.py` 无 23/4/8/161/184 字面量 |
| signed substitution ISM | 自建 `plan=build_channel_plan(schema,None)`，断言 23×4==92，`POS_1B=18`、`L=17` | schema 驱动 + 元数据/PAM 交叉校验（`check_numbering :73-85`） | `docs/paper_analysis/position18_signed_substitution_ism.py:55-69` |
| ISM audit | 读 CNN 原始 CSV 的 0-based `Position`，输出 1-based `position` 与 0-based `position_raw` 双列 | 显式声明 +1 | `position18_ism_audit.py:32-33,317-322` |
| ANOVA | `experiment_table.csv`（只按 model/split/cell/environment 列） | 零 position/channel 解析；因子名由 `ALL_ENVIRONMENTS` 固定 | `analyse/stats/tasks.py:436`；`analyse/config.py:90-101` |
| environment factorial（条件/主效应/交互） | `all_experiments.csv` 的 `environment` 组合名 | `parse_environment_set`：`sequence→∅`、`all→4因子`，其余按 `_` 切分并与 `ALL_ENVIRONMENTS` 取交 | `analyse/environment/incremental_effect.py:16-31,51-90,109-172` |
| bootstrap / permutation | `*_predictions.csv`（逐样本） | 分组键 `(split_type, cell_line, model, random_seed)`，**不跨 seed 配对** | `analyse/stats/tasks.py:105-108,357-358`；`analyse/data/validation.py:36-40` |
| motif discovery | attribution_summary 的 (position, channel) | 假定 **1-based**：`mat[int(pos)-1, j]` | `analyse/sequence/motif/core.py:129-136,146-158` |

**实测对齐结论**：`results/batch_20260909_full/summary/tables/attribution_summary.csv` 里 5 个模型的 `position` 全为 **1..23**；linear 行 161 特征（无 T），cnn 行 184（含 T）；`T_pos_20 → position 21`。`key_regulatory_biomarkers.csv` 亦为 1-based。

**已确认不对齐的三处**：

1. `analyse/visualization.py::parse_feature_position_channel :155-182`（legacy，但仍是 live Step：`pipeline/steps.py:292-297,314,350`）对所有 `0<=pos<=22` 加 1 → 对 1-based 的 **LR/XGB/MLP 全体 +1 错位**，对 0-based 的 CNN/Transformer 正确。实测 `load_raw_feature_records` 输出：linear/xgboost/mlp 的 position 集合 = `2..23`（**没有 1**），cnn/transformer = `1..23`。后果：`_draw_single_heatmap :454-461` 补 `range(1,24)` 让 position 1 恒 0，且 pos22/pos23 都映射到列 23 被 `mean` 合并 → `results/batch_20260909_full/summary/plots/01_position_heatmaps/*_{linear,xgboost,mlp}_heatmap.png` 存在一位错位。
2. `importance_extraction.py` 内部两套归一化器冲突：`extract_feature_position:84`（0-based）vs `get_canonical_feature_id:661`（+1）。同一 `pos_17_c` 在 `extractors.py:31` 判定为 17、在 `importance_extraction.py:661` 判定为 18。
3. `analyse/visualization/attribution_plots.py:23-24,28`：先 `channel.str.upper()` 再与 TitleCase 白名单 `CHANNEL_ORDER`（`:12`）比对 → `Dnase→DNASE`、`H3K4me3→H3K4ME3` 不匹配，**静默丢弃 2 个表观通道**。

### 2.7 两套环境子集策略（同一 combination 名 = 两个特征空间）

| 路径 | 机制 | 维度 |
| :--- | :--- | :--- |
| 网格训练 `train.py` → `cell_environment_combination.py` | `create_channel_mask :1063-1144` → `apply_environment_combination :1151-1236` **乘 mask 置零**；`prepare_model_input :1295-1350`；2D 模型 `flatten_features :1243-1261` | 恒 `(N,184)` / `(N,23,8)`；LR 后 161 |
| Ultimate `predict.py` | `build_channel_plan` + `subset_arrays_3d :139-142` **丢列** | `23*K`（纯序列 92；LR 后 69） |

`predict.py` 反复断言 `23*plan["n_channels"] == len(feature_names)`（`:789`）；训练路径则靠 `schema.channel_count` 与 mask 长度对齐（`cell_environment_combination.py:1197-1208` 强制 `X_3d.shape[1:]==(23,8)`）。两者**不能互喂**。

其它环境选择语义差异：
- `resolve_environment_selection :952-957`：`provided_count==0` → 返回**全部环境**；而 `predict.py:105,117-122` 把 None/空当**纯序列**。
- 显式 `selected_environments` 路径**保留用户顺序**（`:478-482`）且**大小写敏感**（`:469-476`），而 `predict.py:117`/`cnn.py:591` 都做 lowercase。
- `incremental_effect.parse_environment_set :21-31` 只认 `"sequence"`/`"all"`，**静默丢弃未知 token**；`importance_extraction.get_active_channels:58` 却认 `all/all_features/full`。

---

## 3. QC 清单：检查什么 → 失败会污染哪个分析

### 3.1 实际存在的检查

| # | 检查项 | 代码位置 | 检查内容 | 失败后污染链 |
| ---: | :--- | :--- | :--- | :--- |
| 1 | 文件/列存在性（data validity） | `src/feature_engineering.py:1153-1181` | 文件非空；`get_required_columns :1030-1060` 的 6+ 列齐全 | 列缺失 → raise，训练不启动（无污染，但是硬失败） |
| 2 | 缺失值（data/label validity） | `:1187-1212` | `required_columns`（含 `Normalized efficacy`、4 个环境列、`sgRNA`）任一 NaN → raise | 若放行 → 标签/特征 NaN → 线性解析解奇异、CNN/MLP 梯度 NaN → 指标 NaN → bootstrap/permutation 无法配对 → evidence matrix 缺行 |
| 3 | 去重（duplicate handling） | `remove_duplicate_rows :1067-1126`，在 `load_source_csv :1214-1223` 调用（**在插入 `Cell line` 之前**） | **整行完全相同**（含 4 环境列 + 标签 + 位点列）用 `df.duplicated(keep="first")` 删重复，**逐文件（逐细胞系）执行** | 见 §3.2/§3.3：单细胞系内重复 → 该细胞系 single 划分的 train/test 泄漏；跨细胞系重复**未被此规则覆盖** |
| 4 | 长度一致性 | `validate_sequence :332-355`（特征工程，强制 `len==23`）；`data_QC.py:717-744`（报告型，众数长度 + 异常行） | 23nt | 长度异常 → `encode_sgrna` 数组维度错位或 raise；若静默截断 → 所有 `pos{p}` 语义整体偏移 |
| 5 | 非 ACGT（sequence validity） | `encode_sgrna :411-418` raise；`data_QC.py:582-612` 统计 IUPAC/N 并给 `iupac_hint` | 只允许 A/C/G/T（特征工程），data_QC 允许并报告 | 若放行 → one-hot 该行全 0 或错位 → 该 (position,base) 归因/线性系数被污染 |
| 6 | 特征形状（feature validity） | `build_feature_matrix :904-910`、`engineer_dataframe :1321-1337`、`apply_environment_combination :1197-1208`、`save_vector_csv :1407-1417` | `(23, C)` / `(N,23*C)` / `X_3d.shape[1:]==(23,channel_count)` / feature_names 数 == 列数 | 形状错位 → 所有 `pos{p}_{ch}` 与张量轴错配 → 全部分析连锁错位 |
| 7 | NaN/Inf（feature validity） | `parse_position_numeric_values :593-599`、`encode_global_numeric :675-682`、`apply_environment_combination :1210-1216`（**所有模型输入必经**）、`linear_regression.py:146-149,272`、`xgboost.py:192` | X 或 y 非有限 → raise | 若放行 → 解析解爆炸/梯度 NaN → 发散实验（实测 linear 21/64 发散，`README.md:313`） |
| 8 | 模型输入维度 | `train.py::validate_model_input_shape :329-343`（只查 ndim）；`cell_environment_combination.py:1197-1208`（查 `(23,8)`） | 2D vs 3D | ndim 错 → raise |
| 9 | 划分样本数一致 | `cell_line_division.validate_cell_line_dataset :98-110`；`train.py::validate_split_result :259-284` | `len(X_3d)==len(X_2d)==len(y)==len(metadata)`；ndim | 若错位 → 标签与特征错配 → 全部指标无效（**这是最致命的静默错误**） |
| 10 | 比例和为 1 | `cell_line_division.validate_split_fractions :89-95`；`train.py:223-225` | 三段比例均 >0 且和为 1 | 下游划分形状异常 |
| 11 | 序列单态位点（zero-variance） | `data_QC.py:617-653` | 23 位点上 100% 单一碱基 → 列出，并给 `biological_risk_note`（零方差列 → 线性模型奇异/不满秩） | 实测只报 `pos22=G,pos23=G`。若不处理 → 线性设计矩阵秩亏（实测 hct116 sequence rank=60 < 161） |
| 12 | 表观完整度 70% 门禁 | `data_QC.py:1026-1094` | 逐细胞系逐通道"严格完整率"<70% → `blocked_channels` | ⚠ **无消费方**（见 §3.4） |
| 13 | 序列×表观长度对齐 | `data_QC.py:809-935` | 位置型通道位数 == 众数长度 L | 不对齐 → 该通道逐位点语义偏移 |
| 14 | 零标注诊断 | `data_QC.py:940-1021` | 单通道整轨空白 / 全局纯空白 | 纯空白样本 → 该样本表观信息全 0 → 表观 ΔR² 被稀释 |
| 15 | 离群检测 | `data_QC.py:1099-1202` | IsolationForest(contamination=0.01, seed=42)，向量 = 4 碱基 one-hot(23×4) + 各表观轨道(23 each) | 实测 hct116: 43/4239 (1.01%) |
| 16 | 指标一致性（result validity） | `analyse/data/validation.py:14-63`；入口 `analyse/pipeline.py:98` | 同 `(split,cell,model,seed)` 下 ΔR² 与 ΔRMSE **同号** → 标记（不删） | 同号 = 理论上矛盾 → 该实验的可信度存疑，但产物 `01_data_quality.md` 实测为 `_无_` |
| 17 | 指标发散过滤 | `analyse/collect_results.py:176-179`、`analyse/config.py:38` | `|R²|>10` 或 `MAE>10` 或 `RMSE>10` → 从结果表中剔除 | 若放行 → 极端值主导均值（`README.md:313` linear 21/64 发散即靠此过滤） |
| 18 | 实验级异常 | `analyse/anomaly_treatment.py:144-208` | ΔR²/ΔRMSE 同向（相对 sequence 基线，按 `(split,cell,model)` 聚合，**不含 seed**） | 见 §3.4 的口径差异 |
| 19 | 数据级异常 | `analyse/anomaly_treatment.py:215-278` | `|Linear Weight| > 10` → 病态矩阵标记 | 提示线性解读不可信 |
| 20 | 非线性模型不得带 t/p/FDR | `src/xai_importance.py:116-121`（残留则 raise）；`importance_extraction.py:759-761` | 学术红线 | 防把归因当统计显著 |

### 3.2 去重 18982 → 16749 的确切规则

- 规则：`df.duplicated(keep="first")` 对**整行**（读入 CSV 的全部 10 列）判重，`keep="first"` 保留首次出现的行，删掉后续重复（`:1080-1098`）。
- 执行粒度：**每个源文件独立执行**（`load_source_csv :1218-1223`，此时尚未插入 `Cell line`；插入在 `:1229-1233`）。
- 计数：`feature_engineering_summary.csv` 实测 hek293t 唯一有重复 —— `original=4566, duplicate_rows=2233, final=2333`；其余 3 个细胞系 0。总计 **18982 − 2233 = 16749**。
- 实测 hek293t 的 2233 组重复：`dup_row == dup_sgrna_only == dup_ignore_locus == 2233`，即这些重复在 (sgRNA, 4 环境列, 标签) 上完全一致，且每个重复 sgRNA 只有 1 种 (env,label) 组合（`dup groups with >1 distinct (env+label) combo = 0`）。所以本批的整行去重**等价于**按 sgRNA 去重，但**规则本身是整行**。
- ⚠ **跨细胞系重复未被覆盖**：hct116 与 hela 有 **2506 行在全部 6 个内容列（sgRNA + 4 环境 + `Normalized efficacy`）上完全相同**（实测 inner-merge 结果；locus+sgRNA 相同的有 4181 行）；hct116↔hl60 27 行；hela↔hl60 34 行。因为去重是逐文件的，这些全部保留，最终 16749 条里仍有大量跨细胞系孪生行。

### 3.3 重复/泄漏对下游的污染链（含实测）

**single（单细胞系内）划分**：因为逐文件整行去重已清掉文件内重复，实测 4 个细胞系的 test 中 `(sgRNA, label)` 与 train 的交集、`(Chromosome,Start,End,Strand,sgRNA)` 交集**均为 0**。

**mixed（4 细胞系合并后随机 70/15/15）划分**：实测跨细胞系孪生行导致**严重 train/test 泄漏**（复现 `divide_data(data_dir,"mixed",random_seed=seed)`）：

| seed | n_train | n_valid | n_test | test 中 `(sgRNA,label)` 亦在 **train** 的样本 | test 中亦在 **valid** 的样本 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 11724 | 2512 | 2513 | **528 (21.0%)** | 121 (4.8%) |
| 43 | 11724 | 2512 | 2513 | 524 (20.9%) | 118 (4.7%) |
| 44 | 11724 | 2512 | 2513 | 533 (21.2%) | 108 (4.3%) |
| 45 | 11724 | 2512 | 2513 | 535 (21.3%) | 108 (4.3%) |

污染链：**跨细胞系重复序列未被去重 → mixed 划分 train/test 信息泄漏（约 21% 测试样本的精确副本在训练集）→ mixed 的 test R²/RMSE 被高估 → `prediction_summary.csv`(mixed 均值) → 环境 ΔR²（mixed 的 ΔR² 在泄漏基线上计算）→ bootstrap CI 偏窄 → permutation p 偏小 → BH-FDR → Evidence Tier（mixed 行的 Tier 判定）→ 论文"跨细胞系泛化/环境增量"结论**。

**当前批次实际状态**：`all` 退化为 single（§4.3），所以 `single` 与 `all` 无泄漏；只有 `mixed` 的 448 个 run 受影响。

### 3.4 明确"未实现/未找到"的 QC

| 声称/应有的检查 | 状态 | 证据 |
| :--- | :--- | :--- |
| **PAM/NGG 校验** | **未实现** | 全仓库 grep `NGG`/`PAM` 在 `analyse/data_QC.py`、`analyse/data/validation.py`、`analyse/anomaly_treatment.py`、`src/feature_engineering.py` 内 **0 命中**；只有可视化硬编码标注（`analyse/visualization.py:508-518`）与 ISM 脚本的交叉校验（`position18_ism_audit.py:322`）。数据事实成立（实读 4 个源 CSV：pos22–23 100% `GG`；pos21 `G` 仅 12.6%–21.1% → NGG），但**没有任何代码门禁**；`README.md:11,315` 的"由数据验证"指的是这个事后核对，不是 QC |
| **标签范围门禁**（`Normalized efficacy∈[0,1]`） | **未实现为门禁** | 只有 `data_QC.py:358-361` 的离群归因 hint；无 raise、无过滤 |
| **序列级去重**（按 sgRNA 去重） | **未实现**（只有整行去重） | `remove_duplicate_rows:1080` 是 `df.duplicated(keep="first")`，无 `subset=` |
| **跨细胞系重复/泄漏检测** | **未实现** | 无任何跨文件判重；实测 mixed 泄漏 21% 无告警 |
| **表观通道零方差检测** | **未实现** | `data_QC.py:617-653` 只扫 `sgRNA`；hek293t/heLa 的 Dnase 100% 恒 1 未被报告 |
| **shape vs schema 校验** | **部分实现** | `cell_line_division.validate_cell_line_dataset:98-110` 读了 `sequence_length/channel_count/feature_count` 但**从不使用**（只查 ndim 与样本数）；`train.py::validate_model_input_shape:329-343` 只查 ndim |
| **n_train/n_valid/n_test 落入分析层** | **断路** | `all_experiments.csv` 只有 `input_shape_*`，无 `n_train`；`analyse/data/loaders.py:67-86` 造出 `n_train` 列但全为 NA → `ExperimentRecord.n_train=0`（实测 `experiment_table.csv` 的 n_train/n_valid/n_test 全空）。样本量分层因此不可用 |
| **70% 门禁的强制禁用行为** | **未实现** | `data_QC.py:1084-1087,1428-1431` 承诺"特征工程阶段强制禁用该通道或 Zero-Masking"；但 `blocked_channels` 无任何消费方（`src/feature_engineering.py`/`cell_environment_combination.py`/`train.py` 均不读 QC 结果），代码里也无 Zero-Masking 实现 |
| **QC 结果进入训练链路** | **未接线** | `data_digging.py`/`train.py` 不引用 `analyse/data_QC.py` |
| **实际 QC 运行范围** | 只跑了部分数据 | `workspace/qc_sessions/qc_20260912_203603/qc_summary.json`：`n_files=1`、`per_cell_line={'hct116':4239}`、`qc_pass=true`、`issues=[]`、monomorphic=`pos22=G,pos23=G`、gating blocked=`[]`、outliers=43/4239。**不是 4 个细胞系合并的 QC** |

---

## 4. 划分与可支持的结论类型

### 4.1 single / all / mixed 的数据组织

`src/input_control/cell_line_division.py::divide_data :324-363` 统一入口；`schema` 来自 `load_feature_schema`（读 `data_dir/feature_schema.json`，**缺文件/0 字节/JSON 损坏时会自动写盘**，`:26-52`）。

| split | 函数 | 数据组织 | seed | 比例 |
| :--- | :--- | :--- | :--- | :--- |
| `single` | `split_single_cell_line :222-234` | 单细胞系样本内随机划分 | 42 | CLI 默认 0.70/0.15/0.15（`DEFAULT_* :21-23`） |
| `all` | `split_all_cell_lines :237-282` | **设计**：`test_cell_line` 留出细胞系 100% 作 test；其余细胞系**合并**后按 **0.85/0.15 硬编码**切 train/valid（`:253-254`，用 `create_train_valid_indices :175-199`）。**退化路径**：`len(datasets)==1 or len(cell_lines)<=1` → 直接 `split_single_cell_line`（`:241-244`） | 42 | LOCO 分支 **0.85/0.15**；退化分支 0.70/0.15/0.15 |
| `mixed` | `split_mixed_cell_lines :285-302` | 4 细胞系**先合并**再随机划分 | 42/43/44/45（`data_digging.py:59 MIXED_SEEDS`） | 0.70/0.15/0.15 |

- 划分实现：`create_split_indices :154-172` —— `np.random.default_rng(seed).shuffle(np.arange(N))`，`train=int(floor(N*0.70))`、`valid=int(floor(N*0.15))`、`test=剩余`；**非分层**（全仓库无 `StratifiedKFold`）。
- seed 注入：`data_digging.py:287 random_seed = seed if split_type=="mixed" else 42`，`build_command :307` 传 `--seed`。
- LOCO 修复（2026-09-13 落地，本批产物未重跑）：`build_command :324-331` 在 `split_type=="all"` 时追加 `--cell-lines <loco_cells>`；`loco_cells` 由 `:509` 取 `args.cell_lines or CELL_LINES`；`create_train_valid_indices :175-199` 显式绕过 `validate_split_fractions` 的 ">0" 校验（旧代码用 `create_split_indices(...,test_fraction=0.0)` 必然抛错）。
- `mixed` 合并规模实测：11724 + 2512 + 2513 = 16749（先合并 4 个细胞系再划分）。

### 4.2 当前批次 `all` 的实际状态：**已退化为 single（确认）**

证据（全部本会话实测）：

1. `results/batch_20260909_full/summary/metrics_tables/all_experiments.csv` 共 1344 行；`split_type` 分布 `single=448, all=448, mixed=448`。
2. `split_type=='all'` 的 448 行，`cell_lines` 字段**全部长度为 1**（`{"['hct116']":112, "['hek293t']":112, "['hela']":112, "['hl60']":112}`）。
3. 同细胞系的 `all` 与 `single` 的 `input_shape_train/valid/test` **完全相同**（hct116 `[2967]`/`[635]`/`[637]`；hek293t `[1633]`/`[349]`/`[351]`；hela `[5670]`/`[1215]`/`[1216]`；hl60 `[1453]`/`[311]`/`[312]`）。以 hct116 为例 `2967+635+637 = 4239 =` hct116 自身样本数，而非"其余 3 系合并池"（应为 16749−4239 = 12510）。
4. 448 个 `all` run 与同 `(model/kernel, environment, cell_line, sequence_kernel)` 的 `single` run，`R2/RMSE/MAE/Pearson/Spearman` **448/448 逐位相同，max|Δ| = 0.000e+00**（实算）。
5. 单实验 `results/batch_20260909_full/all_linear_sequence_heldout_hct116/linear_regression_info.txt` 明写 `split_type: all`、`cell_lines: ['hct116']`、`input_shape_train: [2967, 184]`。
6. 原因链：本批运行于 2026-09-09/10，早于 2026-09-13 的 LOCO 修复；旧版 `data_digging.py` 不传 `--cell-lines` → `train.py:663-664` 把 `cell_lines` 补成 `[cell_line]` → `divide_data:340-342` 只加载 1 个数据集 → `split_all_cell_lines:241-244` 退化保护改走 `split_single_cell_line`。

**下游后果**：`results/batch_20260909_full/summary/tables/loco_performance.csv`（28 行）把**细胞系内的 test 指标**当作"LOCO 跨细胞系泛化"，`analyse/prediction.py:24-35` 仅按 `split_type=='all'` 分组、**不做退化检测**。`prediction_summary.csv` 里 `split=all` 与 `split=single` 的均值应完全一致。

### 4.3 每种 split 能支持 / 不能支持的结论

| split | 当前批次可支持 | 当前批次**不能**支持 |
| :--- | :--- | :--- |
| `single` | 单细胞系内、同分布样本级泛化性能；单细胞系内的 (position,channel) 归因与线性系数；细胞系内环境通道的边际 ΔR²（同 cohort 配对） | 跨细胞系泛化；细胞系异质性（需多系结果对比，可做但只能比较各系**内部**性能） |
| `all`（**已退化**） | 与 `single` 完全等价的结论（重复实验） | **任何 LOCO / 留一细胞系 / 跨宿主迁移**结论。`loco_performance.csv`、论文"留一细胞系泛化"表述**无支撑**；且这 448 次运行与 `single` 重复（1/3 算力空耗） |
| `mixed`（合并随机划分） | 4 细胞系合并分布的**插值**预测能力；跨模型/跨 seed 稳健性（42–45）；环境因子在混合队列上的条件/主效应 | **跨细胞系泛化**（test 含训练过的细胞系，不是留出系）；**任何未去重孪生行导致的泄漏敏感结论**——mixed 的 R²/RMSE 绝对值、环境 ΔR² 的绝对幅度、由之派生的 bootstrap CI 与 permutation p/FDR 都受 §3.3 的 21% 泄漏影响。mixed 可支持的是"排序/方向一致性"这类相对结论，不能支持绝对泛化性能 |
| 科学上本应支持的 LOCO | 需在修好代码后重跑 `all`（`python data_digging.py --batch-name <b> --split-types all --workers N` + `bash scripts/refresh_after_loco_rerun.sh`，见 `docs/statistics_and_parameters_zh.md:276-281`） | — |

---

## 5. 落到产物的 split metadata 与下游读取

### 5.1 `summary/metrics_tables/all_experiments.csv`（1344 行 × 78 列）

可用于 robustness / heterogeneity 分层的列（逐字来自表头）：

| 列 | 用途 | 实测取值 |
| :--- | :--- | :--- |
| `run_name` | 实验唯一键 → 定位 predictions/权重 | 如 `all_linear_sequence_heldout_hct116` |
| `split_type` | **分层主键** | `single`/`all`/`mixed` 各 448 |
| `cell_line` | **分层主键**（mixed 为 `none`） | hct116/hek293t/hela/hl60/none |
| `cell_lines` | **退化检测唯一的直接证据** | `all` 全为长度 1 的列表 |
| `model` | 模型族（CNN 已含核大小） | `linear,xgboost,mlp,cnn(3\|3),cnn(5\|3),cnn(7\|3),transformer` |
| `sequence_kernel` / `environment_kernel` | CNN 架构分层 | cnn: 3/5/7 与恒 3；其它模型恒 3 |
| `random_seed` | **配对/多种子稳健性** | single/all=42；mixed=42/43/44/45 |
| `environment` | **环境分层主键** | 16 种（`sequence` + 15 非空子集，含 `all`） |
| `environment_count` | 环境因子数 | 0/1/2/3/4 |
| `selected_environments` | 环境列表（⚠ 大小写不一致，如 `['CTCF']` 与 `['ctcf']` 并存） | — |
| `channel_names` | 输入通道定义 | 恒 `['A','C','G','T','CTCF','Dnase','H3K4me3','RRBS']` |
| `channel_count` / `sequence_length` | 维度断言 | 8 / 23 |
| `input_shape_train/valid/test` | **划分形状（可用于退化检测、样本量估计）** | 见 §4.2 |
| `train_ratio/validation_ratio/test_ratio` | 比例 | 0.7/0.15/0.15（LOCO 真跑时应为 0.85/0.15/0） |
| `sequence_channels` / `environment_channels` | 模型实际通道数 | cnn: 4 + 0/1/2/3 |
| `Numerical rank` / `Condition number` / `pinv_rcond` | 线性病态分层 | 实测 rank 60–154，condition 16–566 |
| `R2/RMSE/MAE/Pearson/Spearman` + `validation_*` | 指标 | — |
| `conv_channels1/conv_channels2` | **无效列**（见 §6） | 恒 32/64 |

### 5.2 下游实际读了哪些

| 下游 | 读取路径 | 读到的分层列 | 证据 |
| :--- | :--- | :--- | :--- |
| `analyse/data/loaders.py::load_experiment_table :38-87` | 优先 `summary/metrics_tables/all_experiments.csv` | **只保留** `model, split_type, cell_line, environment, random_seed, n_train, n_valid, n_test, R2, MAE, RMSE, Pearson, Spearman, MSE, source_table, run_name`（`:84-86`）→ **`cell_lines`、`input_shape_*`、`sequence_kernel`、`selected_environments`、`environment_count` 全部被丢弃** | 实测 loader 输出 16 列；`architecture` 恒 None（`sequence_kernel` 已丢，`:141`） |
| `analyse/prediction.py::loco_performance :24-35` | 上表 | `split_type=='all'` + `(model,cell_line)` 均值；**不检查退化** | 产物 `loco_performance.csv` 28 行 |
| `analyse/environment/incremental_effect.py:16-18` | 上表 | `GROUP_COLS=["split_type","cell_line","model","random_seed"]` → 同 seed 配对 | 产物 `environment_conditional_delta_r2.csv`(2016 行)、`environment_main_effects.csv` |
| `analyse/stats/tasks.py:105-108,357-358` | 上表 + `*_predictions.csv` | 分组键含 `random_seed`（**逐 seed 一行 CI，不跨 seed 平均**） | `bootstrap_results.csv` |
| `analyse/data/validation.py:29-63` | 上表 | key 含 `random_seed`（**同 seed 配对**） | `metric_inconsistency.csv`（实测空） |
| `analyse/anomaly_treatment.py::aggregate_metrics:120-137` | 直接读 `all_experiments.csv`（`:92-117`） | 按 `(split_type,cell_line,model,environment)` 求均值 → **丢 seed**；`normalize_cell_line:79-85` 把 mixed 置 `none` | `summary/anomaly_report.md` |
| `analyse/collect_results.py::calculate_delta_R2:217-244` | 收集阶段 | 基线 key `(split_type,cell_line,model)` —— **不含 seed** | 与 §2.6 的"同 seed 配对"原则不一致（`docs/statistics_and_parameters_zh.md:288-289` 已记录） |
| `analyse/importance_extraction.py::collect_all_model_features:679-784` | **直接扫实验目录**（不走 loader） | `split_type/cell_line/environment/model_key`；**不用 seed 分层**（mixed 跨 seed 平均，`:807-825`） | `key_regulatory_biomarkers.csv`（92489 行） |
| `analyse/cellline/consistency.py` + `cellline_effects.csv` | 上表（经 `incremental_effect`） | 按 `(split_type, model, factor)` 比较 4 个细胞系 | `cellline_effects.csv` |
| `analyse/stats/tasks.py::run_factorial_anova` | `experiment_table.csv` | blocked 设计用 `model/cell_line/split_type` 作区组 | `anova_results.csv`（94 行，无 FDR） |

**结论**：`all_experiments.csv` 保留了完整的分层信息（尤其是 `cell_lines` 与 `input_shape_*`，足以检测当前批次 `all` 退化），但**分析引擎的 loader 把它们丢掉了**；因此退化检测能力存在于原始表、不存在于分析链。

---

## 6. 文档与代码/产物不一致清单

> 分三类：**(A) 文档落后于已修复的代码**、**(B) 文档与产物不符**、**(C) 项目内其它已核实的不一致**。每条给 doc 与 code/artifact 双方证据。

### A. 文档仍描述"修复前"的代码（stale）

| # | 文档说法 | 实际代码/产物 |
| ---: | :--- | :--- |
| A1 | `docs/project_pipeline_and_code_documentation.md:11,952,1055,1076,3094-3096`：LOCO "真正的 LOCO 分支因 `test_fraction=0.0` 触发 `validate_split_fractions` 的 `>0` 校验而抛错、**当前不可达**"；`docs/_recon_parameters.md:183`、`docs/statistics_and_parameters_zh.md:247` 同（引 `cell_line_division.py:225`） | **已修复**：`cell_line_division.py:253-254` 调用新增的 `create_train_valid_indices(...,0.85,0.15)`（定义 `:175-199`），该函数显式**不走** `validate_split_fractions`，也**没有 `test_fraction` 参数**。且 `logs/loco_rerun_20260913.log:17,32` 记录本地真跑 `Train shape (10633,161)/Test shape (4239,161) ... R2 0.1142` |
| A2 | `docs/project_pipeline_and_code_documentation.md:926,3085`、`docs/_recon_parameters.md:210-211`、`docs/statistics_and_parameters_zh.md:50`：`data_digging.py` "只传 `--cell-line`，**从不传 `--cell-lines`**" | **已修复**：`data_digging.py:324-331` 在 `split_type=='all'` 时追加 `--cell-lines <loco_cells>`；`:509` 提供 `loco_cells`。（`docs/statistics_and_parameters_zh.md:260` 已写"已修复"，与同文件 `:50` 自相矛盾，也与 A1 的其它文档互相矛盾） |
| A3 | `docs/project_pipeline_and_code_documentation.md:668,808,1057,1067,1075`：QC 离群 one-hot 是 **23×3（A/G/C，丢 T）** → `feature_dim=161` | **已改为 4 碱基**：`analyse/data_QC.py:1106-1107` `seq_bases=["A","C","G","T"]`，注释明写"旧版仅 A/G/C 丢弃 T"。产物 `workspace/qc_sessions/qc_20260912_203603/qc_summary.json` 的 `outliers.feature_dim=184` |
| A4 | `docs/project_pipeline_and_code_documentation.md:1044`：`cell_line_division` 的 `.get("channel_count", 7)` 回退默认值是 7，会去找 `*_features_23x7.npy` | **实际是 8**：`cell_line_division.py:78` 与 `:100` 均为 `schema.get("channel_count", 8)`；`get_feature_file_paths:82` 用 `sequence_length x channel_count` |
| A5 | `docs/project_pipeline_and_code_documentation.md:921-922,926,3054,3085`（`cell_line_division` 行号 `:195-207/:210-253/:219-236/:313-314`；"all=留一细胞系"无退化注记）、`docs/_recon_parameters.md:189`（种子的行使 `data_digging.py:275`）、`:236`（LOCO 分支 `:219-236`）、`:55`（去重 `:1067-1127`） | 行号整体漂移 ~+27：实际 `split_single_cell_line:222`、`split_all_cell_lines:237`、LOCO 分支 `:246-265`、`divide_data:324-363`、`random_seed` 在 `data_digging.py:287`、`remove_duplicate_rows` 到 `:1126`；且 `project_pipeline_and_code_documentation.md:3` 自述基线为 `git commit 9b2def2b (2026-09-12)`，早于 2026-09-13 的 LOCO/schema 修复，是 A1–A4 的共同根因 |

### B. 文档与产物/代码不符

| # | 文档说法 | 实际 |
| ---: | :--- | :--- |
| B1 | `README.md:352`：**"序列合法性与标签分布检查见 `summary/reports/01_data_quality.md`"** | 该产物实测只含"experiments/valid 计数 + cell-line×environment 覆盖表 + metric inconsistency（`_无_`）"（`results/batch_20260909_full/summary/reports/01_data_quality.md`，由 `analyse/reports/markdown_report.py:221-236` 生成）。**没有任何序列合法性或标签分布检查** |
| B2 | `README.md:344`：**"训练/验证/测试按 0.70/0.15/0.15 在样本级划分"**；`docs/dimension.md:160` 同 | LOCO 分支实际用 **0.85/0.15 硬编码**（`cell_line_division.py:253-254`），test 由留出系全体充当。README/dimension.md 未提该特例（`docs/statistics_and_parameters_zh.md:247` 有提） |
| B3 | `docs/dimension.md:138-139`：**"留一细胞系泛化评估（LOCO）：3 细胞系训练、1 细胞系 100% 留出测试"**（无退化说明） | 当前批次 448/448 个 `all` run 退化为 single（§4.2 五条证据）。`README.md:391-392` 有正确的退化说明 → **`dimension.md` 与 `README.md` 互相矛盾** |
| B4 | `docs/statistics_and_parameters_zh.md:43-45` 运行矩阵表：`all`/`single`/`mixed` 每格 "CNN 192 / 其它 4 类模型 64" | 产物每 split 共 448 = CNN 192（16 env × 3 kernel × 4 cell）+ **其它模型 256**（4 模型 × 16 env × 4 cell）。64 漏乘了 4 个细胞系/seed；同表 `:39` 自己写的 "1 344 = 3 split × 448" 也与 192+64 矛盾 |
| B5 | `docs/paper_analysis/README.md:3-5`："所有文件由 `paper/make_assets.py` …重新计算得到"；`docs/pipeline_integration.md:201`："`paper/make_assets.py` 可重新生成全部论文资产" | `paper/make_assets.py` 只**写** `bootstrap_edge_by_factor.csv`(`:739`)、`factor_level_ci.csv`(`:748`)、`asset_summary.json`(`:765`)；其余 11 个 CSV 是**只读输入**（`:594,605,706-714`）。`cnn_ism_position_profile.csv`、`nucleotide_frequency_by_position.csv` 全仓库**零引用**。（`docs/statistics_and_parameters_zh.md:285-286` 已正确记录 11 个孤本） |
| B6 | `README.md:430`：映射结果"保存即写入 `feature_config.user.json` 供特征工程使用" | `data/feature_config.user.json` **不存在**；`data/*.json` 只有 `feature_config.json`；`src/feature_engineering.py` 的 `--config` 默认就是 `data/feature_config.json`（`:1997-2001`），**不读 `*.user.json`** |
| B7 | `analyse/docs/code_cleanup_report.md:46`：位置/通道解析已统一到 `attribution/extractors._parse_position_channel`，"两者已单测对齐" | 实测 `analyse/visualization.py:155-182` 的 `parse_feature_position_channel` 与 `_parse_position_channel` **不一致**：`pos1_A→2` vs `1`、`pos20_G→21` vs `20`（§2.4 表）。legacy 模块仍是 live Step（`pipeline/steps.py:292-297`） |
| B8 | `docs/HPC_EXPERIMENT_PROTOCOL.md:29,42,110` 引用仓库脚本 `profile_experiment.py`、`HPC_launch_full_batch.sh`、`regression_compare.py` | 这 3 个文件**在仓库内不存在**（全仓库 glob 无命中，仅出现在 docs 文本中） |
| B9 | `README.md:382`："当前权重/日志未入库（`models/`、`logs/` 为空）" | 与同一文件 `README.md:267-268`（"models/ 2880 文件、logs/ 1344 份已入库"）自相矛盾；实测 `models/batch_20260909_full` 1344 个目录、`logs/batch_20260909_full` 1344 个目录 → `:382` 为假 |
| B10 | `docs/statistics_and_parameters_zh.md:286` 引 `paper/make_assets.py:723,732` 生成 2 个 CSV | 实际写入点为 `paper/make_assets.py:739,748`（+`asset_summary.json:765`）；结论正确，仅行号漂移 |

### C. 项目内其它已核实不一致（代码/产物层）

| # | 现象 | 证据与影响 |
| ---: | :--- | :--- |
| C1 | **环境子集两套语义**：置零保 184 vs 丢列得 23K | `cell_environment_combination.py:1228-1236` vs `predict.py:139-142`；§2.7 |
| C2 | **legacy 热图对 1-based 名 +1 错位** | `analyse/visualization.py:177-180`；实测线性/xgb/mlp position 集合 = 2..23（无 1）；产物 `summary/plots/01_position_heatmaps/*_{linear,xgboost,mlp}_heatmap.png` |
| C3 | **`attribution_plots.py` 大小写 bug 丢通道** | `:23-24,28` `.upper()` vs TitleCase 白名单 → Dnase/H3K4me3 被过滤 |
| C4 | **`importance_extraction` 内部 0/1-based 混用** | `extract_feature_position:84-95`（不归一化）vs `get_canonical_feature_id:653-667`（+1）；per-model `.md` 排序与 `key_regulatory_biomarkers.csv` 口径不同 |
| C5 | **`conv_channels1/conv_channels2` 未生效** | `data_digging.py:441-442,506-507` 生成并传递；`train.py:638-639` 接收；但 `build_train_kwargs` 只把参数传给模型 `train()`（`:411-412`），而 `src/cnn/cnn.py::train` 签名（`:498-527`）只有 `sequence_filters/environment_filters/fusion_filters`，**无 `conv_channels*`**，`inspect.signature` 过滤时被丢弃（`train.py:428`）。`all_experiments.csv` 的 `conv_channels1/2` 恒 32/64。文档已在 `docs/project_pipeline_and_code_documentation.md:1136,1401,1729,1734` 与 `docs/_recon_parameters.md:276-279` 正确标注 |
| C6 | **`all_experiments.csv` 无 `n_train/n_valid/n_test`** | `analyse/data/loaders.py:67-86,146-148` 造列后全 NA → `experiment_table.csv` 三列全空、`ExperimentRecord.n_*=0` |
| C7 | **`selected_environments` 大小写不一致** | `all_experiments.csv` 中 `['CTCF']` 与 `['ctcf']` 并存 |
| C8 | **表观通道零方差未纳入 QC** | hek293t/heLa Dnase 100% `A`；`data_QC.py:617-653` 只检查 sgRNA |
| C9 | **跨细胞系孪生行导致 mixed 泄漏 ~21%** | §3.2/§3.3；无任何代码/文档提及 |
| C10 | **`analyse/` 从不应用 LR 的 `_T` 掉列** | 全 `analyse/` grep `_T` 无代码命中；分析层一律按 184/8 假设 |
| C11 | **`data_QC.py:1084-1087` 承诺的"强制禁用/Zero-Masking"无实现、无消费方** | §3.4 |
| C12 | **CNN `CNN_ISM` 的操作子是"通道 toggle + abs"，不是碱基替换** | `src/cnn/cnn.py:304`（`X_mut[:,l,c]=np.where(>0,0,1)`）、`:307`（`np.abs`）；`docs/paper_analysis/position18_ism_audit.py:305-315` 已记录该 caveat；因此它与真正的 signed substitution ISM（`position18_signed_substitution_ism.py`）语义不同、不可直接比较 |
| C13 | **transformer 硬编码 7 通道 fallback** | `src/transformer/transformer.py:572,576` 缺 T；正常路径 `feature_names` 长度=8 时不触发（潜在雷） |
| C14 | **`src/transformer/transformer.py` / `src/cnn/cnn.py` 硬编码 `max_length=23`** | `transformer.py:90,151`；与 schema 解耦不彻底 |

---

## 7. 关键产物索引（可复核对）

| 内容 | 路径 |
| :--- | :--- |
| schema | `data/proceeded_data/feature_schema.json` |
| 特征配置 | `data/feature_config.json` |
| 去重计数 | `data/proceeded_data/feature_engineering_summary.csv` |
| 单实验配置 | `results/batch_20260909_full/<run_name>/*_info.txt` |
| 汇总指标（含分层列） | `results/batch_20260909_full/summary/metrics_tables/all_experiments.csv` |
| 退化检测证据 | 上表 `split_type=='all'` 行的 `cell_lines` 与 `input_shape_*` |
| LOCO（退化产物） | `results/batch_20260909_full/summary/tables/loco_performance.csv` |
| 位置归因（1-based） | `results/batch_20260909_full/summary/tables/attribution_summary.csv` |
| 关键调控特征库（1-based） | `results/batch_20260909_full/summary/feature_importance/key_regulatory_biomarkers.csv` |
| CNN 原始重要性（0-based `Position`） | `results/batch_20260909_full/*cnn*/cnn_feature_importance.csv` |
| legacy 热图（含错位） | `results/batch_20260909_full/summary/plots/01_position_heatmaps/` |
| 独立 QC 会话 | `workspace/qc_sessions/qc_20260912_203603/{qc_summary.json,quality_report.md}` |
| LOCO 修复与重跑说明 | `docs/statistics_and_parameters_zh.md:243-283`；`logs/loco_rerun_20260913.log` |

---

## 8. 一句话结论

变量空间是"23 位点 × (4 碱基 one-hot + 4 条 per-position 指示轨道) = 184"，线性模型再以 T 为参照降到 161；schema（`channel_names` + 1-based `pos{p}_{ch}`）是唯一的位置/通道契约，`attribution`/`key_regulatory_biomarkers`/ISM 均正确对齐，但 legacy 可视化与 `importance_extraction` 内部存在 0/1-based 混用。QC 实际只覆盖**单细胞系的原始表**（列/缺失/整行去重/长度/非 ACGT/形状/NaN），**没有** PAM、标签范围、序列级去重、跨细胞系泄漏、表观零方差等检查，且 70% 门禁无消费方；而当前 1344 个实验里 `all`（448 个）全部退化为 `single`，`mixed` 的 test 有约 21% 样本与训练集重复 —— 这两点分别使"跨细胞系泛化"和"mixed 绝对性能/环境增量"结论在当前批次上不成立。
