# 论文构建说明（paper/）

## 目录结构

```
paper/
├── main.tex                  # 主文件 (ctexart + natbib)
├── references.bib            # 12 篇参考文献 (全部经 PubMed/Crossref/OpenAlex/arXiv 核验)
├── sections/                 # 摘要 + Introduction/Methods/Results/Discussion/Limitations/Conclusion/Availability
├── tables/                   # 由 make_assets.py 从结果文件自动生成的 LaTeX 表格
├── figures/                  # Figure 1–7 (PDF 矢量 + PNG 预览)
├── supplementary/            # 附录 (S1–S6 + 结论→结果文件映射表)
├── make_assets.py            # 从 results/ 只读重算全部图表
├── make_pdf_fallback.py      # 无 TeX 环境下的审阅用 PDF 渲染器
└── compiled/
    ├── main.pdf              # 审阅版 PDF (由 make_pdf_fallback.py 生成)
    └── README_PDF.md         # 编译状态说明
```

## 正式编译（推荐，需要 TeX Live）

```bash
cd paper
latexmk -xelatex -bibtex main.tex       # 或: xelatex main && bibtex main && xelatex main && xelatex main
```

* 中文排版使用 `ctex`，需要 XeLaTeX 与中文字体（Fandol 或 Noto Sans CJK）。
* 参考文献样式为 `unsrtnat`（数字顺序引用）。如目标期刊要求其他样式，只需替换
  `\bibliographystyle{...}`，正文 `\citep{}` 无需改动。
* 若期刊要求双栏/特定模板，请用其模板包裹 `sections/*.tex` 的内容，无需改动图表。

## 图表与数值的重新生成

```bash
python paper/make_assets.py             # 重新生成 figures/*、tables/*、docs/paper_analysis/*
```

该脚本只读取 `results/batch_20260909_full/analyse_out/` 与 `data/proceeded_data/`，
不修改任何训练或分析产物；论文中每个数值均可在 `docs/paper_claim_provenance.md` 中追溯。

## 编译状态（已实际编译 ✅）

本论文已在沙箱内**真实编译通过**：使用用户模式安装的 TeX Live 2023（`scheme-small` +
`ctex/xecjk/fandol/zhnumber`），命令为：

```bash
export PATH=/tmp/texlive/bin/x86_64-linux:$PATH
cd paper
xelatex -interaction=nonstopmode main.tex     # 第 1 遍
bibtex main                                    # 生成参考文献
xelatex -interaction=nonstopmode main.tex      # 第 2、3 遍（解析交叉引用）
```

编译结果（`compiled/main.pdf`，同目录保留 `main.log` 编译日志）：

| 指标 | 值 |
| :--- | :--- |
| 页数 | **22** |
| LaTeX 错误 | **0** |
| 未定义引用 / 引用文献 | **0 / 0** |
| Overfull hbox | 9（主要为宽表，已用 `\resizebox` 缩放；不影响阅读） |
| 中文字体 | Fandol（Song/Bold/Kai/Fang），由 ctex 自动配置 |
| 图表 | 7 幅正文图（PDF 矢量）+ 7 个表格全部嵌入 |

说明：本沙箱原先没有 TeX 发行版（无 root），本轮的 TeX Live 通过 CTAN 镜像以**用户模式**
安装到 `/tmp/texlive`（不进入仓库、不影响结果数据）。在具备 TeX Live 的机器上，按上面的
三条命令即可复现同一 PDF；仓库内不依赖该临时安装。

`make_pdf_fallback.py` 是备用渲染器（在完全无 TeX 的环境下生成审阅版 PDF），当前**不再需要**，
保留以备离线审阅。
