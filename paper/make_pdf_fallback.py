"""Fallback PDF renderer for the paper.

The sandbox used to build this repository has **no TeX distribution** (no root, and the
Debian packages that could be fetched cannot build format files), so `main.tex` cannot be
compiled here. This script renders the *same* sources (main.tex + sections/*.tex + tables)
to a review PDF with matplotlib, which can embed the system CJK font.

  python paper/make_pdf_fallback.py   ->  paper/compiled/main.pdf

It is a *review copy*: the authoritative typeset version must be produced with
`latexmk -xelatex -bibtex main.tex` on a machine with TeX Live installed.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

ROOT = Path(__file__).resolve().parent
CJK_FONT = "/usr/share/fonts/NotoSansCJK-Regular.otf"
PAGE = (8.27, 11.69)                 # A4
MARGIN = 0.72                        # inches
MX = MARGIN / PAGE[0]                # same margin as a figure fraction
MY = MARGIN / PAGE[1]
BODY = 8.0
LINE = 0.0128                        # line height in figure fraction

FP = FontProperties(fname=CJK_FONT) if Path(CJK_FONT).exists() else FontProperties()

CITE_ORDER: list[str] = []
CITE_FMT = {"Jinek2012Science": "Jinek 等, Science 2012",
            "Cong2013Science": "Cong 等, Science 2013",
            "Doench2014NatBiotechnol": "Doench 等, Nat Biotechnol 2014",
            "Doench2016NatBiotechnol": "Doench 等, Nat Biotechnol 2016",
            "MorenoMateos2015NatMethods": "Moreno-Mateos 等, Nat Methods 2015",
            "Chuai2018GenomeBiol": "Chuai 等, Genome Biol 2018",
            "Alipanahi2015NatBiotechnol": "Alipanahi 等, Nat Biotechnol 2015",
            "Kelley2016GenomeRes": "Kelley 等, Genome Res 2016",
            "Chen2016KDD": "Chen \\& Guestrin, KDD 2016",
            "Lundberg2017NeurIPS": "Lundberg \\& Lee, NeurIPS 2017",
            "Sundararajan2017ICML": "Sundararajan 等, ICML 2017",
            "Vaswani2017NeurIPS": "Vaswani 等, NeurIPS 2017"}

MATH = {"\\Delta": "Δ", "\\times": "×", "\\le": "≤", "\\ge": "≥", "\\rho": "ρ",
        "\\eta": "η", "\\alpha": "α", "\\in": "∈", "\\cup": "∪", "\\mid": "|",
        "\\max": "max", "\\min": "min", "\\mathrm": "", "\\text": "", "\\;": " ",
        "\\,": " ", "\\ ": " "}


def clean(text: str) -> str:
    """Minimal LaTeX -> unicode for review rendering."""
    text = re.sub(r"%.*", "", text)
    text = re.sub(r"\\citep\{([^}]*)\}", lambda m: "[" + "; ".join(
        CITE_FMT.get(k.strip(), k.strip()) for k in m.group(1).split(",")) + "]", text)
    text = re.sub(r"\\(ref|eqref)\{([^}]*)\}", lambda m: REFS.get(m.group(2), m.group(2)), text)
    text = re.sub(r"\\(textbf|emph|texttt|textit|small|bfseries)\{([^{}]*)\}", r"\2", text)
    text = re.sub(r"\\input\{([^}]*)\}", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\addcontentsline\{[^}]*\}\{[^}]*\}\{[^}]*\}", "", text)
    for k, v in MATH.items():
        text = text.replace(k, v)
    text = re.sub(r"\$([^$]*)\$", r"\1", text)
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_")
    text = text.replace("---", "—").replace("--", "–").replace("~", " ")
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)
    text = re.sub(r"[{}]", "", text)
    return re.sub(r"\s+", " ", text).strip()


REFS: dict[str, str] = {}


def collect_refs(sources: list[str]) -> None:
    n = 0
    for src in sources:
        for label in re.findall(r"\\label\{((?:fig|tab|app):[^}]*)\}", src):
            if label in REFS:
                continue
            n += 1
            REFS[label] = ("图" if label.startswith("fig:") else "表") + str(n)


def expand(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    base = path.parent
    def repl(m):
        target = base / (m.group(1) + ".tex")
        return target.read_text(encoding="utf-8") if target.exists() else ""
    return re.sub(r"\\input\{([^}]*)\}", repl, text)


def blocks_of(text: str) -> list[tuple[str, str]]:
    """Split source into (kind, payload) blocks."""
    blocks: list[tuple[str, str]] = []
    pattern = re.compile(
        r"(\\section\*?\{.*?\}|\\subsection\*?\{.*?\}|"
        r"\\begin\{figure\}.*?\\end\{figure\}|"
        r"\\begin\{table\}.*?\\end\{table\}|"
        r"\\begin\{equation\}.*?\\end\{equation\}|"
        r"\\begin\{enumerate\}.*?\\end\{enumerate\})", re.S)
    pos = 0
    for m in pattern.finditer(text):
        chunk = text[pos:m.start()]
        for para in [p for p in chunk.split("\n\n") if p.strip()]:
            blocks.append(("p", para))
        seg = m.group(0)
        if seg.startswith("\\section"):
            blocks.append(("h1", clean(re.search(r"\{(.*)\}", seg, re.S).group(1))))
        elif seg.startswith("\\subsection"):
            blocks.append(("h2", clean(re.search(r"\{(.*)\}", seg, re.S).group(1))))
        elif seg.startswith("\\begin{figure"):
            img = re.search(r"\\includegraphics\[[^\]]*\]\{([^}]*)\}", seg)
            cap = re.search(r"\\caption\{(.*?)\}\s*\\label", seg, re.S)
            blocks.append(("fig", f"{img.group(1) if img else ''}||{clean(cap.group(1)) if cap else ''}"))
        elif seg.startswith("\\begin{table"):
            rows = _parse_tabular(seg)
            cap = re.search(r"\\caption\{(.*?)\}\s*\\label", seg, re.S)
            blocks.append(("tab", f"{clean(cap.group(1)) if cap else ''}||" + repr(rows)))
        elif seg.startswith("\\begin{equation"):
            blocks.append(("eq", clean(seg.replace("\\begin{equation}", "")
                                            .replace("\\end{equation}", ""))))
        else:  # enumerate
            items = re.findall(r"\\item\s+(.*?)(?=\\item|\\end\{enumerate\})", seg, re.S)
            for i, it in enumerate(items, 1):
                blocks.append(("li", f"{i}. {clean(it)}"))
        pos = m.end()
    for para in [p for p in text[pos:].split("\n\n") if p.strip()]:
        blocks.append(("p", para))
    return blocks


def _parse_tabular(seg: str) -> list[list[str]]:
    body = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", seg, re.S)
    if not body:
        return []
    raw = body.group(1)
    raw = re.sub(r"\\(toprule|midrule|bottomrule|hline)", "", raw)
    rows = []
    for line in raw.split("\\\\"):
        line = line.strip()
        if not line:
            continue
        cells = [clean(c) for c in line.split("&")]
        if any(cells):
            rows.append(cells)
    return rows


def wrap(text: str, width: int) -> list[str]:
    """CJK-aware wrap (wide chars count as 2 columns)."""
    out, line, w = [], "", 0
    for ch in text:
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > width:
            out.append(line)
            line, w = "", 0
        line += ch
        w += cw
    if line:
        out.append(line)
    return out


class Renderer:
    def __init__(self, pdf: PdfPages):
        self.pdf = pdf
        self.fig = None
        self.y = 0.0
        self.page_no = 0
        self.new_page()

    def new_page(self) -> None:
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)
        self.fig = plt.figure(figsize=PAGE)
        self.page_no += 1
        self.fig.text(0.5, 0.035, f"{self.page_no}", ha="center", fontsize=7, fontproperties=FP,
                      color="#666666")
        self.y = 0.955

    def need(self, height: float) -> None:
        if self.y - height < 0.06:
            self.new_page()

    def text(self, s: str, size: float = BODY, weight: str = "normal", indent: float = 0.0,
             width: int = 96, color: str = "#111111") -> None:
        for line in wrap(s, width):
            self.need(LINE * (size / BODY))
            self.fig.text(MX + indent, self.y, line, fontsize=size, fontproperties=FP,
                          va="top", color=color, weight=weight)
            self.y -= LINE * (size / BODY) * 1.02
        self.y -= LINE * 0.35

    def heading(self, s: str, level: int) -> None:
        size = BODY + 3 if level == 1 else BODY + 1.2
        self.need(LINE * 3)
        self.y -= LINE * 0.4
        self.text(s, size=size, weight="bold", width=int(96 * BODY / size))

    def figure(self, path: str, caption: str) -> None:
        img = ROOT / path
        for ext in (".png", ".pdf"):
            cand = img.with_suffix(ext)
            if cand.exists():
                img = cand
                break
        if not img.exists():
            return
        self.need(0.34)
        data = plt.imread(img)
        h, w = data.shape[0], data.shape[1]
        box_w = 1 - 2 * MX
        box_h = min(0.30, box_w * PAGE[1] / PAGE[0] * h / max(w, 1))
        try:
            ax = self.fig.add_axes([MX, max(self.y - box_h, MY), box_w, box_h])
            ax.imshow(data)
            ax.axis("off")
        except Exception as exc:                     # pragma: no cover - diagnostics only
            print(f"[warn] figure skipped ({img.name}): {exc} y={self.y} h={box_h}")
            return
        self.y -= box_h + 0.015
        self.text(caption, size=BODY - 0.8, width=104, color="#333333")

    def table(self, caption: str, rows: list[list[str]]) -> None:
        if not rows:
            return
        n = len(rows)
        row_h = min(0.018, 0.80 / max(n + 1, 1))       # long tables are compressed
        height = row_h * (n + 1)
        self.need(height + 0.10)
        self.text(caption, size=BODY - 0.8, width=104, color="#333333")
        self.need(height + 0.02)
        try:
            ax = self.fig.add_axes([MX, max(self.y - height, MY),
                                    1 - 2 * MX, height])
            ax.axis("off")
            tbl = ax.table(cellText=rows, loc="upper center", cellLoc="center")
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(min(5.2, max(3.0, 5.2 * (0.80 / max(height, 1e-6)) ** 0.35)))
            for cell in tbl.get_celld().values():
                cell.set_text_props(fontproperties=FP)
        except Exception as exc:                     # pragma: no cover
            print(f"[warn] table skipped ({len(rows)} rows, h={height:.3f}): {exc}")
            return
        self.y -= height + LINE * 1.4

    def finish(self) -> None:
        if self.fig is not None:
            self.pdf.savefig(self.fig)
            plt.close(self.fig)


def main() -> None:
    sources = [ROOT / "main.tex"] + sorted((ROOT / "sections").glob("*.tex")) + \
        sorted((ROOT / "tables").glob("*.tex")) + \
        sorted((ROOT / "supplementary").glob("*.tex"))
    texts = [p.read_text(encoding="utf-8") for p in sources]
    collect_refs(texts)

    full = expand(ROOT / "main.tex")
    full = re.sub(r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
                  lambda m: "\\section*{摘要}\n\n" + m.group(1), full, flags=re.S)
    full = re.sub(r"\\maketitle", "", full)
    full = re.sub(r"\\bibliography\{[^}]*\}", "", full)
    full = re.sub(r"\\bibliographystyle\{[^}]*\}", "", full)
    full = re.sub(r"\\appendix", lambda m: "\\section*{附录}", full)
    title = re.search(r"\\title\{(.*?)\}", full, re.S)
    author = re.search(r"\\author\{(.*?)\}", full, re.S)
    full = re.sub(r"\\title\{.*?\}|\\author\{.*?\}|\\date\{.*?\}", lambda m: "", full, flags=re.S)

    out = ROOT / "compiled" / "main.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        r = Renderer(pdf)
        if title:
            r.text(clean(title.group(1).replace("\\\\", " ")), size=BODY + 6, weight="bold",
                   width=62)
        if author:
            r.text(clean(author.group(1)), size=BODY, color="#555555")
        for kind, payload in blocks_of(full):
            if kind == "h1":
                r.heading(payload, 1)
            elif kind == "h2":
                r.heading(payload, 2)
            elif kind == "p":
                text = clean(payload)
                if text:
                    r.text(text)
            elif kind == "li":
                r.text("  " + payload, indent=0.02, width=92)
            elif kind == "eq":
                r.text("    " + payload, size=BODY, color="#000000")
            elif kind == "fig":
                path, cap = payload.split("||", 1)
                r.figure(path.strip(), cap)
            elif kind == "tab":
                cap, rows = payload.split("||", 1)
                r.table(cap, eval(rows))  # noqa: S307 - internal repr round-trip
        r.text("参考文献（完整 BibTeX 见 references.bib）", size=BODY + 1.5, weight="bold")
        for i, (key, label) in enumerate(CITE_FMT.items(), 1):
            r.text(f"[{i}] {label} ({key})", size=BODY - 1, width=100)
        r.finish()
    print("wrote", out, "pages:", "?")


if __name__ == "__main__":
    main()
