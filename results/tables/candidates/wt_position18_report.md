# WT → Position 18 → CRISPRon 代表性序列集

- 数据集：`DeepCRISPR`（候选池 = `single` 划分的 **test 集**，group-aware 无泄漏，seed=42）
- 位点约定：序列长度 23 nt = protospacer 1-20 + PAM 21-23 (NGG, 判据 'GG' 结尾) | 关注位点 18 (0-based 下标 17, 含 PAM 的 23nt 内)
- 约定交叉校验：与 analysis/reporting/paper/make_assets.py:REGIONS 一致 (PAM (21, 23), seed (17, 20))
- 挑选规则版本：`wt-pos18-representative-v1`（规则预先写死在脚本内）

## 0. 挑选规则（预先登记）
```
wt-pos18-representative-v1
1. 候选池: DeepCRISPR `single` 划分的 test 集 (group-aware 无泄漏, seed=42), 全部细胞系。
2. 过滤: Position18==C; PAM==NGG; canonical identity min(seq,revcomp) 去重;
   标签有限且∈[0,1]; 剔除各细胞系标签 [P1,P99] 之外的极端值; 坐标可取出合法 30-mer。
3. 分层: 在每个细胞系内部, 按标签三分位切 low / medium / high (避免细胞系混淆)。
4. 代表性: 每个 (细胞系 × 区间) 取最接近该区间中位数的 1 条进入短名单 (不取极值)。
5. 终选 8 条 = low 2 + medium 2 + high 2 + 2 条 GC 偏离中位数最多但仍在
   [P5,P95] 内的"特殊但仍正常"序列; 约束 每细胞系<=2 条、两两序列错配>=4 nt。
6. 全程不使用任何突变侧结果。
```

## 1. 最终入选序列（完整信息）

### WT01 — hct116
- WT（23 nt）：`GACAGGAAGGTGCTGTACACAGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`GACAGGAAGGTGCTGTAAACAGG`
- PAM：`AGG`（NGG）｜ protospacer：`GACAGGAAGGTGCTGTACAC`
- PAM-proximal seed (17–20)：`ACAC`
- 原始实验效率：**0.1101**（区间 `low`，该区间中位数 0.1101）
- GC：protospacer 55.0% ｜ 23 nt 56.5%
- 坐标：`chr22:20073880-20073902`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`TAAGGACAGGAAGGTGCTGTACACAGGAGC`
- CRISPRon 30-mer（C18A）：`TAAGGACAGGAAGGTGCTGTAAACAGGAGC`
- 代表性理由：low 区间代表（最接近中位数 0.1101）

### WT02 — hek293t
- WT（23 nt）：`TTATGGTGTGACAGTGCCTCCGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`TTATGGTGTGACAGTGCATCCGG`
- PAM：`CGG`（NGG）｜ protospacer：`TTATGGTGTGACAGTGCCTC`
- PAM-proximal seed (17–20)：`CCTC`
- 原始实验效率：**0.1444**（区间 `low`，该区间中位数 0.1444）
- GC：protospacer 50.0% ｜ 23 nt 56.5%
- 坐标：`chrX:70356761-70356783`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`GCCCTTATGGTGTGACAGTGCCTCCGGACC`
- CRISPRon 30-mer（C18A）：`GCCCTTATGGTGTGACAGTGCATCCGGACC`
- 代表性理由：low 区间代表（最接近中位数 0.1444）

### WT03 — hek293t
- WT（23 nt）：`CCTTCAGCCTCCTTGTGCTCTGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`CCTTCAGCCTCCTTGTGATCTGG`
- PAM：`TGG`（NGG）｜ protospacer：`CCTTCAGCCTCCTTGTGCTC`
- PAM-proximal seed (17–20)：`GCTC`
- 原始实验效率：**0.2145**（区间 `medium`，该区间中位数 0.2145）
- GC：protospacer 60.0% ｜ 23 nt 60.9%
- 坐标：`chrX:70344194-70344216`（- 链，hg19）
- CRISPRon 30-mer（WT）：`GCTGCCTTCAGCCTCCTTGTGCTCTGGGTC`
- CRISPRon 30-mer（C18A）：`GCTGCCTTCAGCCTCCTTGTGATCTGGGTC`
- 代表性理由：medium 区间代表（最接近中位数 0.2145）

### WT04 — hela
- WT（23 nt）：`TCAGAATCCCATTCTTCCACAGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`TCAGAATCCCATTCTTCAACAGG`
- PAM：`AGG`（NGG）｜ protospacer：`TCAGAATCCCATTCTTCCAC`
- PAM-proximal seed (17–20)：`CCAC`
- 原始实验效率：**0.2671**（区间 `medium`，该区间中位数 0.2671）
- GC：protospacer 45.0% ｜ 23 nt 47.8%
- 坐标：`chr15:40942534-40942556`（- 链，hg19）
- CRISPRon 30-mer（WT）：`CATTTCAGAATCCCATTCTTCCACAGGATT`
- CRISPRon 30-mer（C18A）：`CATTTCAGAATCCCATTCTTCAACAGGATT`
- 代表性理由：medium 区间代表（最接近中位数 0.2671）

### WT05 — hct116
- WT（23 nt）：`ACCAACTACCAGCTGGGCACAGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`ACCAACTACCAGCTGGGAACAGG`
- PAM：`AGG`（NGG）｜ protospacer：`ACCAACTACCAGCTGGGCAC`
- PAM-proximal seed (17–20)：`GCAC`
- 原始实验效率：**0.5368**（区间 `high`，该区间中位数 0.5368）
- GC：protospacer 60.0% ｜ 23 nt 60.9%
- 坐标：`chr1:28864370-28864392`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`GGGCACCAACTACCAGCTGGGCACAGGGCA`
- CRISPRon 30-mer（C18A）：`GGGCACCAACTACCAGCTGGGAACAGGGCA`
- 代表性理由：high 区间代表（最接近中位数 0.5368）

### WT06 — hela
- WT（23 nt）：`TAATGCATCTGCCATCACGGTGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`TAATGCATCTGCCATCAAGGTGG`
- PAM：`TGG`（NGG）｜ protospacer：`TAATGCATCTGCCATCACGG`
- PAM-proximal seed (17–20)：`ACGG`
- 原始实验效率：**0.5032**（区间 `high`，该区间中位数 0.5032）
- GC：protospacer 50.0% ｜ 23 nt 52.2%
- 坐标：`chr11:93542990-93543012`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`TTGGTAATGCATCTGCCATCACGGTGGCCT`
- CRISPRon 30-mer（C18A）：`TTGGTAATGCATCTGCCATCAAGGTGGCCT`
- 代表性理由：high 区间代表（最接近中位数 0.5032）

### WT07 — hl60
- WT（23 nt）：`AGCCGGCCCGTAAGATCCGCAGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`AGCCGGCCCGTAAGATCAGCAGG`
- PAM：`AGG`（NGG）｜ protospacer：`AGCCGGCCCGTAAGATCCGC`
- PAM-proximal seed (17–20)：`CCGC`
- 原始实验效率：**0.3435**（区间 `high`，该区间中位数 0.3665）
- GC：protospacer 70.0% ｜ 23 nt 69.6%
- 坐标：`chr16:89627450-89627472`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`AACCAGCCGGCCCGTAAGATCCGCAGGTGA`
- CRISPRon 30-mer（C18A）：`AACCAGCCGGCCCGTAAGATCAGCAGGTGA`
- 代表性理由：序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%)

### WT08 — hl60
- WT（23 nt）：`GGCCGAAAGAGCCGTGGCCTTGG`
- Position 18：`C` → C18A 后 `A`
- C18A（23 nt）：`GGCCGAAAGAGCCGTGGACTTGG`
- PAM：`TGG`（NGG）｜ protospacer：`GGCCGAAAGAGCCGTGGCCT`
- PAM-proximal seed (17–20)：`GCCT`
- 原始实验效率：**0.1871**（区间 `low`，该区间中位数 0.1628）
- GC：protospacer 70.0% ｜ 23 nt 69.6%
- 坐标：`chr3:23960879-23960901`（+ 链，hg19）
- CRISPRon 30-mer（WT）：`TGCAGGCCGAAAGAGCCGTGGCCTTGGAAA`
- CRISPRon 30-mer（C18A）：`TGCAGGCCGAAAGAGCCGTGGACTTGGAAA`
- 代表性理由：序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%)

## 2. 为什么这些序列有代表性

- **分层依据**：在**每个细胞系内部**按原始实验效率的三分位切 low/medium/high，避免「某个细胞系整体偏高」把区间混淆。各切点与中位数：

| cell_line   | bin    |        cut |   median |   n |
|:------------|:-------|-----------:|---------:|----:|
| hct116      | low    |   0.185869 | 0.110119 |  65 |
| hct116      | medium |   0.413918 | 0.271295 |  64 |
| hct116      | high   | nan        | 0.536836 |  65 |
| hek293t     | low    |   0.179776 | 0.144441 |  27 |
| hek293t     | medium |   0.280141 | 0.214475 |  27 |
| hek293t     | high   | nan        | 0.358995 |  27 |
| hela        | low    |   0.185183 | 0.119048 | 120 |
| hela        | medium |   0.370564 | 0.267137 | 119 |
| hela        | high   | nan        | 0.503177 | 119 |
| hl60        | low    |   0.19953  | 0.16281  |  34 |
| hl60        | medium |   0.32056  | 0.235594 |  33 |
| hl60        | high   | nan        | 0.366501 |  34 |

- **取区间中心而非极值**：每个 (细胞系 × 区间) 先取最接近该区间中位数的序列进入短名单，
  终选在这些中心代表里进行，因此不会偏向分布两端。
- **多样性约束**：每个细胞系至多 2 条；两两序列错配 ≥ 4 nt；另含 2 条 GC 明显偏离中位数但仍在 P5–P95 内的「特殊但仍正常」序列。
- **不选最好看的**：挑选阶段完全未接触任何 C18A / CRISPRon 结果（见 §5）。

## 3. WT → C18A 序列修改验证

逐条断言：除 Position 18 外其余 22 个位置完全一致（`wt[:17]==mut[:17]` 且 `wt[18:]==mut[18:]`）。

| ID   | sgRNA                   | mutant                  | verify_prefix_equal   | verify_suffix_equal   | verify_only_pos18_changed   |   verify_n_mismatch |
|:-----|:------------------------|:------------------------|:----------------------|:----------------------|:----------------------------|--------------------:|
| WT01 | GACAGGAAGGTGCTGTACACAGG | GACAGGAAGGTGCTGTAAACAGG | True                  | True                  | True                        |                   1 |
| WT02 | TTATGGTGTGACAGTGCCTCCGG | TTATGGTGTGACAGTGCATCCGG | True                  | True                  | True                        |                   1 |
| WT03 | CCTTCAGCCTCCTTGTGCTCTGG | CCTTCAGCCTCCTTGTGATCTGG | True                  | True                  | True                        |                   1 |
| WT04 | TCAGAATCCCATTCTTCCACAGG | TCAGAATCCCATTCTTCAACAGG | True                  | True                  | True                        |                   1 |
| WT05 | ACCAACTACCAGCTGGGCACAGG | ACCAACTACCAGCTGGGAACAGG | True                  | True                  | True                        |                   1 |
| WT06 | TAATGCATCTGCCATCACGGTGG | TAATGCATCTGCCATCAAGGTGG | True                  | True                  | True                        |                   1 |
| WT07 | AGCCGGCCCGTAAGATCCGCAGG | AGCCGGCCCGTAAGATCAGCAGG | True                  | True                  | True                        |                   1 |
| WT08 | GGCCGAAAGAGCCGTGGCCTTGG | GGCCGAAAGAGCCGTGGACTTGG | True                  | True                  | True                        |                   1 |

## 4. CRISPRon 所需输入序列

CRISPRon 的输入判据（官方 Help）：**30 nt = 4 nt + target(20 nt) + PAM(NGG) + 3 nt**。下表的 30-mer 由 hg19 取窗并按链定向得到，且已核对中间 23 nt 与数据完全一致。

| ID   | cell_line   | crispron_30mer_wt              | crispron_30mer_c18a            | crispron_window            |
|:-----|:------------|:-------------------------------|:-------------------------------|:---------------------------|
| WT01 | hct116      | TAAGGACAGGAAGGTGCTGTACACAGGAGC | TAAGGACAGGAAGGTGCTGTAAACAGGAGC | chr22:20073875-20073905(+) |
| WT02 | hek293t     | GCCCTTATGGTGTGACAGTGCCTCCGGACC | GCCCTTATGGTGTGACAGTGCATCCGGACC | chrX:70356756-70356786(+)  |
| WT03 | hek293t     | GCTGCCTTCAGCCTCCTTGTGCTCTGGGTC | GCTGCCTTCAGCCTCCTTGTGATCTGGGTC | chrX:70344190-70344220(-)  |
| WT04 | hela        | CATTTCAGAATCCCATTCTTCCACAGGATT | CATTTCAGAATCCCATTCTTCAACAGGATT | chr15:40942530-40942560(-) |
| WT05 | hct116      | GGGCACCAACTACCAGCTGGGCACAGGGCA | GGGCACCAACTACCAGCTGGGAACAGGGCA | chr1:28864365-28864395(+)  |
| WT06 | hela        | TTGGTAATGCATCTGCCATCACGGTGGCCT | TTGGTAATGCATCTGCCATCAAGGTGGCCT | chr11:93542985-93543015(+) |
| WT07 | hl60        | AACCAGCCGGCCCGTAAGATCCGCAGGTGA | AACCAGCCGGCCCGTAAGATCAGCAGGTGA | chr16:89627445-89627475(+) |
| WT08 | hl60        | TGCAGGCCGAAAGAGCCGTGGCCTTGGAAA | TGCAGGCCGAAAGAGCCGTGGACTTGGAAA | chr3:23960874-23960904(+)  |

对应的 FASTA（可直接提交 CRISPRon）与本表同目录：`wt_position18_crispron_input.fa`。
若改用 CRISPRon 的「基因组区间」输入模式，可用同目录的 `wt_position18_cellline_reference.csv`。

## 5. 展示用简表

| ID | Cell line | WT sequence (23 nt) | Pos18 | C18A sequence (23 nt) | Experimental efficiency | GC% | Selection reason |
| -- | --------- | ------------------- | ----- | --------------------- | -----------------------: | --: | ---------------- |
| WT01 | hct116 | `GACAGGAAGGTGCTGTACACAGG` | C | `GACAGGAAGGTGCTGTAAACAGG` | 0.110 | 55.0 | low 区间代表（最接近中位数 0.1101） |
| WT02 | hek293t | `TTATGGTGTGACAGTGCCTCCGG` | C | `TTATGGTGTGACAGTGCATCCGG` | 0.144 | 50.0 | low 区间代表（最接近中位数 0.1444） |
| WT03 | hek293t | `CCTTCAGCCTCCTTGTGCTCTGG` | C | `CCTTCAGCCTCCTTGTGATCTGG` | 0.214 | 60.0 | medium 区间代表（最接近中位数 0.2145） |
| WT04 | hela | `TCAGAATCCCATTCTTCCACAGG` | C | `TCAGAATCCCATTCTTCAACAGG` | 0.267 | 45.0 | medium 区间代表（最接近中位数 0.2671） |
| WT05 | hct116 | `ACCAACTACCAGCTGGGCACAGG` | C | `ACCAACTACCAGCTGGGAACAGG` | 0.537 | 60.0 | high 区间代表（最接近中位数 0.5368） |
| WT06 | hela | `TAATGCATCTGCCATCACGGTGG` | C | `TAATGCATCTGCCATCAAGGTGG` | 0.503 | 50.0 | high 区间代表（最接近中位数 0.5032） |
| WT07 | hl60 | `AGCCGGCCCGTAAGATCCGCAGG` | C | `AGCCGGCCCGTAAGATCAGCAGG` | 0.344 | 70.0 | 序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%) |
| WT08 | hl60 | `GGCCGAAAGAGCCGTGGCCTTGG` | C | `GGCCGAAAGAGCCGTGGACTTGG` | 0.187 | 70.0 | 序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%) |

## 6. 最终检查清单

| 项目 | 结果 |
| --- | --- |
| 总候选数（test 集样本） | 2520 |
| Position18=C 候选数 | 734 |
| 合法 PAM(NGG) 数 | 734 |
| 可构造 30-mer（坐标可容）数 | 734 |
| 与 hg19 逐条核对通过数 | 734 |
| 最终入选数 | 8 |
| low / medium / high | 3 / 2 / 3 |
| 各 cell line 数量 | hct116: 2、hek293t: 2、hela: 2、hl60: 2 |
| 是否有重复序列 | 无（已按 canonical identity `min(seq,revcomp)` 去重） |
| 是否有高度相似序列 | 最小两两错配 **10 nt**（阈值 ≥ 4）；共 28 对 |
| 是否存在 C18A 反向筛选 | **不存在**：挑选只用 WT 侧字段；C18A 序列在挑选完成后才生成，脚本内无任何 CRISPRon 调用 |

### 无突变信息自证（selfcheck.json）
```json
{
  "rule_version": "wt-pos18-representative-v1",
  "wt_only_columns": [
    "cell_line",
    "split_type",
    "sgRNA",
    "Normalized efficacy",
    "Chromosome",
    "Start",
    "End",
    "Strand",
    "identity",
    "label_bin",
    "label_bin_median",
    "gc_spacer",
    "gc_23nt",
    "pam",
    "pos18",
    "seed_region",
    "dist_to_center"
  ],
  "mutant_fields_present_in_selection": [],
  "note": "C18A 序列仅在挑选完成后由 build_mutant() 生成；脚本内没有任何 CRISPRon 调用或突变侧预测。"
}
```

### 「特殊但仍正常」的 2 条

| ID   | cell_line   |   gc_spacer | label_bin   |   Normalized efficacy |
|:-----|:------------|------------:|:------------|----------------------:|
| WT07 | hl60        |          70 | high        |              0.343535 |
| WT08 | hl60        |          70 | low         |              0.187057 |

### 取舍日志（节选：被多样性约束拒绝的候选）
```
           stage   n note cell_line    bin                identity                                      why  efficiency
       shortlist NaN  NaN    hct116   high ACCAACTACCAGCTGGGCACAGG               最接近 high 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN    hct116    low CCTGTGTACAGCACCTTCCTGTC                最接近 low 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN    hct116 medium CCACTGGTGCGGGCAGGAGACAG             最接近 medium 区间中位数（|Δ|=0.0002）         NaN
       shortlist NaN  NaN   hek293t   high CCGCTGGTTGCACTCATGGCTGC               最接近 high 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN   hek293t    low CCGGAGGCACTGTCACACCATAA                最接近 low 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN   hek293t medium CCAGAGCACAAGGAGGCTGAAGG             最接近 medium 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN      hela   high CCACCGTGATGGCAGATGCATTA               最接近 high 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN      hela    low CCACTGTCAGCAAATGCAGTCCC                最接近 low 区间中位数（|Δ|=0.0001）         NaN
       shortlist NaN  NaN      hela medium CCTGTGGAAGAATGGGATTCTGA             最接近 medium 区间中位数（|Δ|=0.0000）         NaN
       shortlist NaN  NaN      hl60   high CCACAGTGGCGTCCAGCTCGCTC               最接近 high 区间中位数（|Δ|=0.0005）         NaN
       shortlist NaN  NaN      hl60    low AGTCCCACCACCTCGAACTCTGG                最接近 low 区间中位数（|Δ|=0.0025）         NaN
       shortlist NaN  NaN      hl60 medium AGCTCGCGGAGGCAAGGCCGAGG             最接近 medium 区间中位数（|Δ|=0.0000）         NaN
        consider NaN  NaN    hct116    low CCTGTGTACAGCACCTTCCTGTC                                  通过多样性约束         NaN
          select NaN  NaN    hct116    low CCTGTGTACAGCACCTTCCTGTC                  low 区间代表（最接近中位数 0.1101）    0.110119
        consider NaN  NaN   hek293t    low CCGGAGGCACTGTCACACCATAA                                  通过多样性约束         NaN
          select NaN  NaN   hek293t    low CCGGAGGCACTGTCACACCATAA                  low 区间代表（最接近中位数 0.1444）    0.144441
        consider NaN  NaN   hek293t medium CCAGAGCACAAGGAGGCTGAAGG                                  通过多样性约束         NaN
          select NaN  NaN   hek293t medium CCAGAGCACAAGGAGGCTGAAGG               medium 区间代表（最接近中位数 0.2145）    0.214475
        consider NaN  NaN      hela medium CCTGTGGAAGAATGGGATTCTGA                                  通过多样性约束         NaN
          select NaN  NaN      hela medium CCTGTGGAAGAATGGGATTCTGA               medium 区间代表（最接近中位数 0.2671）    0.267137
        consider NaN  NaN    hct116   high ACCAACTACCAGCTGGGCACAGG                                  通过多样性约束         NaN
          select NaN  NaN    hct116   high ACCAACTACCAGCTGGGCACAGG                 high 区间代表（最接近中位数 0.5368）    0.536836
        consider NaN  NaN   hek293t   high CCGCTGGTTGCACTCATGGCTGC                       细胞系 hek293t 已达上限 2         NaN
        consider NaN  NaN      hela   high CCACCGTGATGGCAGATGCATTA                                  通过多样性约束         NaN
          select NaN  NaN      hela   high CCACCGTGATGGCAGATGCATTA                 high 区间代表（最接近中位数 0.5032）    0.503177
consider_special NaN  NaN      hela   high AAGGAGCGGCACAGGCGCCAGGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hela    low ACAGCGCTGCACCTCTGCCGAGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN    hct116 medium ACAGGCTGTGTGTCGGCCGGCGG GC=70.0% (中位 55.0%) -> 细胞系 hct116 已达上限 2         NaN
consider_special NaN  NaN      hela    low ACCAGGCGGCGCCACTACAGGGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hela medium AGAGACCGTGGTCGTGGCGGTGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hela    low AGAGGCCCGAGGGCATGCACCGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hl60   high AGCCGGCCCGTAAGATCCGCAGG           GC=70.0% (中位 55.0%) -> 通过多样性约束         NaN
          select NaN  NaN      hl60   high AGCCGGCCCGTAAGATCCGCAGG         序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%)    0.343535
consider_special NaN  NaN      hela    low AGGCCCACGAGCTGAAGCGCAGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hela medium AGGTCCTCCTCAGGGAGCGGGGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN    hct116 medium ATCGCCTGCGTGTCCGCCCACGG GC=70.0% (中位 55.0%) -> 细胞系 hct116 已达上限 2         NaN
consider_special NaN  NaN    hct116    low CACGTTGTGCAACGCCGCCCCGG GC=70.0% (中位 55.0%) -> 细胞系 hct116 已达上限 2         NaN
consider_special NaN  NaN      hela   high CAGAGCAGTCCTCCTCGCCGTGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
consider_special NaN  NaN      hela medium CAGAGTGGCTCCGCACGCCATGG   GC=70.0% (中位 55.0%) -> 细胞系 hela 已达上限 2         NaN
```

---

复现：`python analysis/candidates/wt_position18_selection.py --dataset DeepCRISPR --seed 42`
（hg19 取窗结果有本地缓存 `_hg19_window_cache.csv`，重跑不再联网）
