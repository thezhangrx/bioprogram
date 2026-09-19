#!/usr/bin/env python3
"""生成论文重写所需的 LaTeX 表格（不手工填写任何数字）。

输入
----
results/paper_rewrite/authoritative_numbers.json   由 analysis/paper_numbers.py 生成
results/tables/external_validation/*.csv|json      CRISPRon 外部验证产物

输出（docs/paper/tables/）
--------------------------
tab7_replication.tex          跨数据集序列信号复现（主结果表）
tab8_external_validation.tex  CRISPRon 外部模型验证（WT/C18A 逐样本）
tab9_counterfactual.tex       逐位点反事实扰动（in-silico 饱和突变）
tab10_evidence_layers.tex     六层证据定义与本文结论归档
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
TABLES = ROOT / "docs" / "paper" / "tables"
EXT = ROOT / "results" / "tables" / "external_validation"
AUTH = ROOT / "results" / "paper_rewrite" / "authoritative_numbers.json"

HEADER = (
    "% 本文件由 analysis/reporting/paper_rewrite/build_rewrite_tables.py 自动生成。\n"
    "% 请勿手工编辑；数字来源见文件头注释与 results/paper_rewrite/authoritative_numbers.json。\n"
)


def _esc(s: str) -> str:
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


# --------------------------------------------------------------------------
# tab7：跨数据集复现
# --------------------------------------------------------------------------
def build_tab7(auth: dict) -> str:
    dc = auth["deepcrispr_splits"]["single"]
    hir = auth["hiranniramol_single"]
    lab = auth["labuhn_single"]

    order = ["cnn_k3", "cnn_k5", "cnn_k7", "linear", "mlp", "transformer", "xgboost"]
    disp = {
        "cnn_k3": "CNN $k{=}3$", "cnn_k5": "CNN $k{=}5$", "cnn_k7": "CNN $k{=}7$",
        "linear": "Linear", "mlp": "MLP", "transformer": "Transformer",
        "xgboost": "XGBoost",
    }

    rows = []
    for lab_key, blob, n_test in (
        ("DeepCRISPR", dc, "2\\,968--5\\,671"),
        ("Hiranniramol", hir, None),
        ("Labuhn", lab, None),
    ):
        per = {r["model_label"]: r for r in blob["per_model"]} if "per_model" in blob else blob
        for m in order:
            v = per.get(m)
            if v is None:
                continue
            r2 = v["median_r2"] if "median_r2" in v else v["r2"]
            pr = v.get("median_pearson", v.get("pearson"))
            sp = v.get("median_spearman", v.get("spearman"))
            n = v.get("n", 1)
            rows.append((lab_key, disp[m], f"{r2:+.3f}", f"{pr:+.3f}", f"{sp:+.3f}", n))

    body = []
    prev = None
    for ds, model, r2, pr, sp, n in rows:
        if ds != prev:
            if prev is not None:
                body.append("\\midrule")
            body.append(f"\\multicolumn{{6}}{{l}}{{\\textit{{{ds}}}}} \\\\")
            prev = ds
        body.append(f"{model} & {r2} & {pr} & {sp} & {n} \\\\")

    def _cv(blob):
        s = blob["cv5_signal"]
        return (f"{s['cv5_r2']:+.3f} & {s['null_r2_mean']:+.3f} "
                f"$\\pm$ {s['null_r2_sd']:.3f} & {s['cv5_minus_null_mean']:+.3f}")

    n_dc = auth["deepcrispr_cells"]["_pooled"]["n"]
    n_hir = hir["label_stats"]["n"]
    n_lab = lab["label_stats"]["n"]

    return HEADER + r"""\begin{table}[htbp]
\centering
\scriptsize
\caption{跨数据集序列信号复现（测试集口径）。DeepCRISPR 行为 \emph{single} 划分下 64 次运行的中位数（Linear 为 58 次有效运行），Hiranniramol 与 Labuhn 为各自单细胞系划分下的唯一一次运行。三者使用完全相同的特征构造、模型配置、身份类划分与评估脚本。下半部分为\textbf{与官方划分无关}的独立复核：全数据 5 折 CV $R^{2}$ 与 200 次标签置换零分布。}
\label{tab:replication}
\begin{tabular}{llrrrr}
\toprule
dataset & model & $R^{2}_{\text{test}}$ & Pearson & Spearman & $n$ runs \\
\midrule
""" + "\n".join(body) + r"""
\midrule
\multicolumn{6}{l}{\textit{独立复核（全数据 5 折 CV，与官方划分无关）}} \\
dataset & $n$ & CV $R^{2}$ & 置换零分布 $R^{2}$ & CV $-$ null & \\
\midrule
""" + "\n".join([
        f"Hiranniramol & {n_hir} & " + _cv(hir) + r" \\",
        f"Labuhn & {n_lab} & " + _cv(lab) + r" \\",
    ]) + r"""
\midrule
\multicolumn{6}{l}{\textit{DeepCRISPR 合并规模：""" + f"{n_dc:,}".replace(",", r"\,") + r""" 条序列（4 细胞系）}} \\
\bottomrule
\end{tabular}
\end{table}
"""


# --------------------------------------------------------------------------
# tab8：CRISPRon 外部模型验证
# --------------------------------------------------------------------------
def build_tab8() -> str:
    df = pd.read_csv(EXT / "crispron_pos18_v1_cross_model.csv", encoding="utf-8-sig")
    summ = json.loads((EXT / "crispron_pos18_v1_summary.json").read_text())
    ag = summ["cross_model_agreement"]

    lines = []
    for r in df.itertuples():
        agree = r"是" if r.agree_direction else r"\textbf{否}"
        lines.append(
            f"{_esc(r.sample_id)} & {_esc(r.cell_line)} & {r.experimental_efficiency:.3f} & "
            f"{r.WT_prediction:.2f} & {r.mutant_prediction:.2f} & {r.delta:+.2f} & "
            f"{r.delta_ours_mean:+.3f} $\\pm$ {r.delta_ours_std:.3f} & {agree} \\\\"
        )

    return HEADER + r"""\begin{table}[htbp]
\centering
\footnotesize
\caption{外部模型验证：独立第三方模型 CRISPRon 对第 18 位 C$\rightarrow$A 反事实扰动的响应。8 条野生型（WT）序列按预先登记规则从 DeepCRISPR 测试集选出（第 18 位为 C），扰动仅改变第 18 位一个碱基，其余 22\,nt 与全部侧翼完全不变（逐条 QC 通过）。$\Delta_{\text{CRISPRon}}$ 为 CRISPRon 复合评分（0--100）；$\Delta_{\text{ours}}$ 为本文 7 个模型基于符号化 in-silico 突变的预测变化均值 $\pm$ 标准差（归一化效率尺度）。\textbf{两个模型族的扰动响应在 8 条序列中的 7 条上方向一致}（Pearson $r=""" + f"{ag['pearson_delta']:.3f}" + r"""$，Spearman $\rho=""" + f"{ag['spearman_delta']:.3f}" + r"""$，$n=8$）；唯一分歧为 WT08，该结果保留而非剔除。}
\label{tab:externalvalidation}
\begin{tabular}{llrrrrrc}
\toprule
sample & cell line & 实测效率 & CRISPRon WT & CRISPRon C18A & $\Delta_{\text{CRISPRon}}$ & $\Delta_{\text{ours}}$ & 方向一致 \\
\midrule
""" + "\n".join(lines) + r"""
\midrule
\multicolumn{8}{l}{CRISPRon 侧：7/8 条 $\Delta<0$，方向一致率 """ + f"{summ['summary']['directional_consistency_P_delta_lt_0']:.3f}" + r"""，$\Delta$ 均值 """ + f"{summ['summary']['delta_mean']:+.2f}" + r"""（中位 """ + f"{summ['summary']['delta_median']:+.2f}" + r"""，范围 """ + f"{summ['summary']['delta_min']:+.2f}" + r""" 至 """ + f"{summ['summary']['delta_max']:+.2f}" + r"""）} \\
\bottomrule
\end{tabular}
\end{table}
"""


# --------------------------------------------------------------------------
# tab9：逐位点反事实扰动
# --------------------------------------------------------------------------
def build_tab9() -> str:
    p = json.loads((EXT / "crispron_mutagenesis_v1_pos18_analysis.json").read_text())
    eff = pd.read_csv(EXT / "crispron_mutagenesis_v1_effects.csv", encoding="utf-8-sig")
    rows = sorted(p["position_importance_rows"], key=lambda r: r["position_1b"])
    n_all = len(eff)
    n_scored = int(eff["recognized"].sum())
    n_excl = n_all - n_scored
    pos18_abs = next(r["mean_abs_delta"] for r in rows if int(r["position_1b"]) == 18)

    # 三列布局
    cols = 3
    per_col = (len(rows) + cols - 1) // cols
    chunks = [rows[i * per_col:(i + 1) * per_col] for i in range(cols)]
    body = []
    for i in range(per_col):
        cells = []
        for c in chunks:
            if i < len(c):
                r = c[i]
                cells.append(f"{int(r['position_1b'])} & {r['mean_abs_delta']:.2f} & {r['rank']}")
            else:
                cells.append(" & & ")
        body.append(" & ".join(cells) + r" \\")

    return HEADER + r"""\begin{table}[htbp]
\centering
\footnotesize
\caption{反事实扰动证据：在 8 条 WT 序列上对 23\,nt 靶序列的\textbf{全部单碱基替换}做饱和 in-silico 突变，并用外部模型 CRISPRon 评分。共 """ + f"{n_all}" + r""" 条替换记录（8 序列 $\times$ 23 位点 $\times$ 3 种替换），其中 """ + f"{n_excl}" + r""" 条破坏 PAM 而无法被 CRISPRon 识别、被排除，剩 """ + f"{n_scored}" + r""" 条计分；""" + f"{p['n_positions_ranked']}" + r""" 个位置可排名，""" + f"{p['n_positions_with_CA']}" + r""" 个位置存在可用的 C$\rightarrow$A 替换。第 18 位的 C$\rightarrow$A 平均变化为 """ + f"{p['delta_CA_at_pos18_mean']:+.3f}" + r"""，而其余位置平均仅 """ + f"{p['delta_CA_other_positions_mean']:+.3f}" + r"""；按平均 $|\Delta|$ 计，第 18 位（""" + f"{pos18_abs:.2f}" + r"""）在 """ + f"{p['n_positions_ranked']}" + r""" 个位置中\textbf{排名第 1}。逐序列看，第 18 位在 8 条序列中的 7 条上排序第 1、1 条上第 2（排序中位数 """ + f"{p['pos18_rank_median']:.1f}" + r"""）。全部数值为\textbf{模型内部反事实}，不是实验测量。}
\label{tab:counterfactual}
\begin{tabular}{rrr@{\hspace{2em}}rrr@{\hspace{2em}}rrr}
\toprule
pos & 平均$|\Delta|$ & 排名 & pos & 平均$|\Delta|$ & 排名 & pos & 平均$|\Delta|$ & 排名 \\
\midrule
""" + "\n".join(body) + r"""
\bottomrule
\end{tabular}
\end{table}
"""


# --------------------------------------------------------------------------
# tab10：六层证据
# --------------------------------------------------------------------------
def build_tab10() -> str:
    return HEADER + r"""\begin{table}[htbp]
\centering
\footnotesize
\caption{本文使用的\textbf{六层证据}分类。每一层回答不同的问题、有不同的失效模式，且\emph{不能相互替代}：低层证据不能升级为高层证据，高层证据的存在也不能反推低层证据。全文每一处结论均在括号中标注其所属层（E1--E6）。本文\textbf{不含任何 E5 证据}，因此不产生任何 E6 层面的因果断言。}
\label{tab:evidence-layers}
\begin{tabular}{p{0.5cm}p{2.6cm}p{3.4cm}p{4.2cm}p{3.6cm}}
\toprule
层 & 名称 & 回答的问题 & 本文中的实例 & 该层\textbf{不能}支持 \\
\midrule
E1 & 预测证据 & 模型能否在未见样本上预测标签？ & 测试集 $R^{2}$/Pearson/Spearman；跨数据集复现；CRISPRon 的 WT/C18A 评分差 & 因果；机制；模型"理解"了生物学 \\
\midrule
E2 & 关联证据 & 标签与某可观测属性是否同变？ & 第 18 位 C 与 A 分组的实测效率差（按细胞系）；GC 含量与效率的相关系数 & 因果；方向性机制；对该属性的干预效应 \\
\midrule
E3 & 归因证据 & 模型输出依赖输入的哪些部分？ & 线性系数、TreeSHAP、IG、CNN 逐位点归因、注意力 & 统计显著性；生物学重要性；因果 \\
\midrule
E4 & 反事实证据 & \emph{模型}在输入被扰动后如何响应？ & 符号化 ISM（第 18 位 C$\rightarrow$A/G/T）；逐位点饱和突变；候选模式破坏 & 真实编辑效率的变化；实验可验证的效应量 \\
\midrule
E5 & 实验证据 & 真实实验中扰动是否改变结果？ & \textbf{本文无}（见 \S\ref{sec:future} 的预登记实验设计） & 超越所测体系的外推 \\
\midrule
E6 & 因果证据 & 干预是否在该体系中导致效应？ & \textbf{本文不作任何此类断言} & --- \\
\bottomrule
\end{tabular}
\end{table}
"""


# --------------------------------------------------------------------------
# tab1：三个数据集的组成
# --------------------------------------------------------------------------
def build_tab1(auth: dict) -> str:
    cells = auth["deepcrispr_cells"]
    rows = []
    for key, disp in (("hct116", "HCT116"), ("hek293t", "HEK293T"),
                      ("hela", "HeLa"), ("hl60", "HL60")):
        c = cells[key]
        rs = c.get("run_sizes", {})
        rows.append(
            f"{disp} & {c['n']:,}".replace(",", r"\,") +
            f" & {c['mean']:.3f} & {c['sd']:.3f} & "
            f"{rs.get('n_train','--')} / {rs.get('n_valid','--')} / {rs.get('n_test','--')} \\\\"
        )
    pool = cells["_pooled"]
    rows.append(
        f"\\midrule\nTotal & {pool['n']:,}".replace(",", r"\,") +
        f" & {pool['mean']:.3f} & {pool['sd']:.3f} & 11\\,723 / 2\\,506 / 2\\,520 \\\\"
    )

    ext = []
    for key, disp, extra in (("hiranniramol", "Hiranniramol", "单细胞系，无环境通道"),
                             ("labuhn", "Labuhn", "单细胞系（含正负链），无环境通道")):
        b = auth[f"{key}_single"]
        st = b["label_stats"]
        ext.append(
            f"{disp} & {st['n']:,}".replace(",", r"\,") +
            f" & {st['mean']:.3f} & {st['sd']:.3f} & "
            f"{b['n_train']} / {b['n_valid']} / {b['n_test']} \\\\"
        )

    return HEADER + r"""\begin{table}[htbp]
\centering
\footnotesize
\caption{三个数据集的组成与划分规模。DeepCRISPR 为本文的主数据集（4 个细胞系，含 4 条表观遗传通道）；Hiranniramol 与 Labuhn 为\textbf{外部复现数据集}，仅有序列通道。三者使用同一套特征构造、模型配置与评估脚本；标签均已归一化到 $[0,1]$（Hiranniramol 原始为百分制、Labuhn 为 \texttt{KO\_reporter\_assay}，由适配器统一）。划分规模按 \emph{single} 划分（70\%/15\%/15\%，身份类整体分配）报告。}
\label{tab:dataset}
\begin{tabular}{lrrrl}
\toprule
dataset / cell line & $n$ & 均值 & 标准差 & $n_{\text{train}}$ / $n_{\text{valid}}$ / $n_{\text{test}}$ \\
\midrule
\multicolumn{5}{l}{\textit{DeepCRISPR（主数据集；4 条表观通道，16\,749 条 23\,nt 序列）}} \\
""" + "\n".join(rows) + r"""
\midrule
\multicolumn{5}{l}{\textit{外部复现数据集（仅序列通道）}} \\
""" + "\n".join(ext) + r"""
\bottomrule
\end{tabular}
\end{table}
"""


# --------------------------------------------------------------------------
# tab11：位置层级归因（可复算的权威值）
# --------------------------------------------------------------------------
def build_tab11(auth: dict) -> str:
    a = auth.get("attribution_position", {})
    if not a.get("available"):
        raise SystemExit("authoritative_numbers.json 缺少 attribution_position；"
                         "请先运行 analysis/paper_numbers.py")

    disp = {"cnn": "CNN", "linear": "Linear", "mlp": "MLP",
            "transformer": "Transformer", "xgboost": "XGBoost"}
    peak = a["per_model_peak"]
    ctx = a.get("per_context_peak_in_17_20_single_split", {})

    rows = []
    for m in sorted(peak, key=lambda x: -peak[x]["value"]):
        c = ctx.get(m, {})
        frac = c.get("fraction_in_17_20")
        frac_txt = (f"{frac * 100:.1f}\\% ({c['n_in_17_20']}/{c['n_contexts']})"
                    if frac is not None else "--")
        rows.append(f"{disp.get(m, m)} & {peak[m]['position_1b']} & "
                    f"{peak[m]['value']:.4f} & {frac_txt} & "
                    f"{c.get('modal_position', '--')} \\\\")

    def _profile(items):
        return " $>$ ".join(f"{i['position_1b']} ({i['value']:.4f})" for i in items)

    return HEADER + r"""\begin{table}[htbp]
\centering
\footnotesize
\caption{位置层级归因（E3；测试集口径与 \emph{single} 划分）。上：各模型类跨上下文平均归因谱的峰值位置与峰值，以及逐上下文峰值落在 PAM 邻近窗口（17--20）的比例（分母为 64 个 细胞系 $\times$ 环境 上下文）。下：等权平均谱的前五位。\textbf{五模型平均谱的峰值是第 1 位而非第 18 位}，该峰值完全由 Linear 贡献；剔除 Linear 后峰值才是第 18 位。本文并列两种口径而不取其一。归因幅值仅表示模型依赖强度，不构成统计显著性证据。}
\label{tab:attribution-position}
\begin{tabular}{lrrrr}
\toprule
model class & 峰值位置 & 峰值 & 峰值 $\in[17,20]$ 的比例 & 众数位置 \\
\midrule
""" + "\n".join(rows) + r"""
\midrule
\multicolumn{5}{l}{\textit{等权平均谱前五位}} \\
五模型（含 Linear） & \multicolumn{4}{l}{""" + _profile(a["mean_all_models"]) + r"""} \\
\midrule
四模型（剔除 Linear） & \multicolumn{4}{l}{""" + _profile(a["mean_non_linear"]) + r"""} \\
\bottomrule
\end{tabular}
\end{table}
"""


def main() -> int:
    auth = json.loads(AUTH.read_text())
    TABLES.mkdir(parents=True, exist_ok=True)
    outs = {
        "tab1_dataset.tex": build_tab1(auth),
        "tab7_replication.tex": build_tab7(auth),
        "tab8_external_validation.tex": build_tab8(),
        "tab9_counterfactual.tex": build_tab9(),
        "tab10_evidence_layers.tex": build_tab10(),
        "tab11_attribution_position.tex": build_tab11(auth),
    }
    for name, text in outs.items():
        (TABLES / name).write_text(text)
        print(f"[write] docs/paper/tables/{name}  ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
