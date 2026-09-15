#!/usr/bin/env bash
# 编译论文 PDF（XeLaTeX + BibTeX）。用法: bash deploy/paper/build_paper_pdf.sh
#
# 为什么不用 `latexmk main.tex` 默认流程：
#   1) main.tex 位于 docs/paper/main/，章节/表格在上级目录，必须在 main.tex 所在目录编译
#      （本脚本用 cd 保证，不依赖 latexmkrc 是否被读取 —— 你的日志显示它只读了 /etc/LatexMk）；
#   2) latexmk 在缺 main.bbl 时会**先跑 bibtex**；若 main.aux 不存在或为空，bibtex 报
#      "I found no \citation commands" 并中止，真正的 xelatex 错误被掩盖。
#      本脚本改为显式 xelatex → bibtex → xelatex → xelatex，每步失败都打印真实错误。
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
MAIN="docs/paper/main"

command -v xelatex >/dev/null 2>&1 || {
  echo "[FATAL] 未找到 xelatex。ctexart 必须用 XeLaTeX 编译。" >&2
  echo "        Ubuntu/Debian: sudo apt install texlive-xetex texlive-lang-chinese fonts-fandol latexmk" >&2
  exit 3; }
command -v bibtex >/dev/null 2>&1 || { echo "[FATAL] 未找到 bibtex" >&2; exit 3; }
kpsewhich ctexart.cls >/dev/null 2>&1 || {
  echo "[FATAL] 找不到 ctexart.cls（中文文档类）: sudo apt install texlive-lang-chinese" >&2; exit 3; }

show_errors() {
  echo "---- ${1} 中的真实错误 ----" >&2
  grep -nE "^!|^l\.[0-9]+ " "${1}" | head -30 >&2 || true
  echo "---------------------------" >&2
}

cd "${MAIN}"
rm -f main.aux main.log main.bbl main.blg main.out main.xdv main.fdb_latexmk main.fls main.pdf

echo "[1/4] xelatex 第一遍（生成 aux）"
if ! xelatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null 2>&1; then
  echo "[FATAL] 第一遍 xelatex 失败。" >&2; show_errors main.log; exit 1
fi
grep -q '\\citation' main.aux || {
  echo "[FATAL] main.aux 中没有任何 \\citation（参考文献未写入）。" >&2; show_errors main.log; exit 1; }

echo "[2/4] bibtex（生成 main.bbl）"
bibtex main >/dev/null 2>&1 || true
[ -f main.bbl ] || { echo "[FATAL] bibtex 未能生成 main.bbl：" >&2; head -20 main.blg >&2; exit 1; }

echo "[3/4] xelatex 第二遍（插入参考文献与交叉引用）"
xelatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || echo "[WARN] 该遍报告错误，继续检查最终产物。" >&2

echo "[4/4] xelatex 第三遍（稳定编号）"
xelatex -interaction=nonstopmode main.tex >/dev/null 2>&1 || echo "[WARN] 该遍报告错误，继续检查最终产物。" >&2

if [ -f main.pdf ]; then
  echo "[✓] 编译成功: ${MAIN}/main.pdf"
  ls -l --time-style=+%F\ %H:%M main.pdf
  if grep -q "There were undefined references" main.log; then
    echo "[WARN] 仍有 undefined references，再跑一次本脚本即可。"
  fi
else
  echo "[FATAL] 未生成 main.pdf" >&2; show_errors main.log; exit 1
fi
