# compiled/main.pdf 编译记录

`main.pdf` 为 **XeLaTeX 正式编译产物**（非替代渲染）：

* 引擎：XeLaTeX（TeX Live 2023，用户模式安装于 `/tmp/texlive`）
* 命令：`xelatex main.tex` → `bibtex main` → `xelatex main.tex` ×2
* 结果：**22 页，0 错误，0 未定义引用，0 未定义引用文献**，9 处 Overfull hbox（宽表已缩放）
* 中文字体：Fandol（ctex 默认），已随 PDF 嵌入
* 完整编译日志：`main.log`；源文件快照：`main.tex`（正文在 `../sections/`）

复现方式见 `../README_BUILD.md`。
