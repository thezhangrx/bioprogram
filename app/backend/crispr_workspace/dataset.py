"""数据集探测（Data Inspection）：从**用户自己的数据集**推断可选项。

用途（对应前端 Data Input / User Decision-Mapping 两个模块）
----------------------------------------------------------
1. 扫描用户提供的已测数据集（CSV/TSV 或目录），输出：
   * ``cell_lines``：细胞系（来自文件名/目录名或 ``cell_line`` 列）；
   * ``channels``：检测到的表观通道列（CTCF / Dnase / H3K4me3 / RRBS 等）；
   * ``sequence_column`` / ``label_column`` / ``sequence_length``；
   * ``mapping_items``：**需要在 User Decision/Mapping 中确认的符号**，
     即通道逐位点字符串里出现的每个取值（例如 ``A`` 与 ``N``），
     并给出默认建议（沿用项目 feature_config 的 ``encoding`` 语义：A→1, N→0）。
2. 把这些决策写成一份用户专属的 feature_config（``feature_config.user.json``），
   供 ``src/feature_engineering.py --config`` 使用。

设计约束：只读用户数据，不写入数据集目录；结果可复现（同一输入 → 同一输出）。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

#: 已知表观通道列名（大小写不敏感匹配）
KNOWN_CHANNELS = ("CTCF", "Dnase", "H3K4me3", "RRBS")
#: 序列/标签列的候选名
SEQUENCE_ALIASES = ("sgrna", "sequence", "seq", "guide", "protospacer")
LABEL_ALIASES = ("normalized efficacy", "efficacy", "label", "target", "activity", "efficiency")
#: 逐位点通道字符串里允许的符号 → 默认二值编码（与 data/metadata/feature_config.json 一致）
DEFAULT_SYMBOL_ENCODING = {"A": 1, "N": 0, "1": 1, "0": 0, "Y": 1, "T": 1}
#: 需要用户显式确认的"非平凡"符号（0/1 已明确）
AMBIGUOUS_SYMBOLS = ("N", "?", ".", "-", "X")
MAX_SCAN_ROWS = 500


class DatasetError(ValueError):
    pass


def _iter_files(paths: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            # 递归扫描：数据集现在按 data/raw/<dataset>/ 分层存放
            # （DeepCRISPR / Hiranniramol / Labuhn），只扫一层会一个都找不到。
            # 扩展名大小写不敏感：Hiranniramol.CSV / Labuhn.CSV 是大写，
            # 在区分大小写的文件系统上 `*.csv` 匹配不到它们。
            files += sorted(
                f for f in p.rglob("*")
                if f.is_file() and f.suffix.lower() in (".csv", ".tsv")
            )
        elif p.is_file():
            files.append(p)
    return files


def _read_head(path: Path, n: int = MAX_SCAN_ROWS) -> tuple[list[str], list[dict]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        sample = fh.read(8192)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(fh, dialect=dialect)
        header = list(reader.fieldnames or [])
        rows = []
        for i, row in enumerate(reader):
            if i >= n:
                break
            rows.append(row)
    return header, rows


def _infer_cell_line(path: Path, header: List[str], rows: List[dict]) -> Optional[str]:
    for key in ("cell_line", "cellline", "cell", "细胞系"):
        for h in header:
            if h.strip().lower() == key:
                vals = {str(r.get(h, "")).strip().lower() for r in rows if r.get(h)}
                vals.discard("")
                if len(vals) == 1:
                    return vals.pop()
    # 回退：文件名主干（hct116.csv -> hct116）
    stem = path.stem.strip().lower()
    for sep in ("_", "-", "."):
        stem = stem.split(sep)[0]
    return stem or None


def _match_column(header: List[str], aliases: Iterable[str]) -> Optional[str]:
    low = {h.strip().lower(): h for h in header}
    for a in aliases:
        if a in low:
            return low[a]
    return None


def _symbol_inventory(rows: List[dict], column: str) -> Dict[str, int]:
    """统计逐位点字符串列中每个符号出现的**样本数**。"""
    counts: Dict[str, int] = {}
    for r in rows:
        val = str(r.get(column, "") or "").strip()
        if not val:
            continue
        for ch in set(val.upper()):
            counts[ch] = counts.get(ch, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def inspect_dataset(paths: List[str], sample_rows: int = MAX_SCAN_ROWS) -> Dict[str, Any]:
    """扫描数据集并给出可用于前端选择/映射的清单。"""
    files = _iter_files(paths)
    if not files:
        raise DatasetError(f"未找到可读取的 CSV/TSV 数据集: {paths}")

    cell_lines: List[str] = []
    channels: List[str] = []
    symbols: Dict[str, Dict[str, int]] = {}
    seq_col: Optional[str] = None
    label_col: Optional[str] = None
    seq_len = 0
    per_file: List[Dict[str, Any]] = []
    seq_alphabet: Dict[str, int] = {}

    for f in files:
        header, rows = _read_head(f, sample_rows)
        cl = _infer_cell_line(f, header, rows)
        if cl and cl not in cell_lines:
            cell_lines.append(cl)

        local_channels = [h for h in header if h.strip().lower() in
                          {c.lower() for c in KNOWN_CHANNELS}]
        for c in local_channels:
            if c not in channels:
                channels.append(c)
            inv = _symbol_inventory(rows, c)
            symbols.setdefault(c, {})
            for sym, n in inv.items():
                symbols[c][sym] = symbols[c].get(sym, 0) + n

        sc = _match_column(header, SEQUENCE_ALIASES)
        lc = _match_column(header, LABEL_ALIASES)
        seq_col = seq_col or sc
        label_col = label_col or lc
        if sc:
            for r in rows:
                s = str(r.get(sc, "") or "").strip()
                seq_len = max(seq_len, len(s))
                for ch in set(s.upper()):
                    seq_alphabet[ch] = seq_alphabet.get(ch, 0) + 1
        per_file.append({"file": str(f), "rows_sampled": len(rows), "columns": len(header),
                         "cell_line": cl, "channels": local_channels})

    # ---- 生成待 Mapping 决策项 ----
    mapping_items: List[Dict[str, Any]] = []
    for ch in channels:
        for sym, n in symbols.get(ch, {}).items():
            default = DEFAULT_SYMBOL_ENCODING.get(sym)
            mapping_items.append({
                "scope": "channel", "channel": ch, "symbol": sym,
                "n_samples_with_symbol": n,
                "ambiguous": sym in AMBIGUOUS_SYMBOLS,
                "default_value": default if default is not None else 0,
                "options": [{"value": 1, "label": "1（可及/阳性）"},
                            {"value": 0, "label": "0（不可及/阴性）"}],
                "decision": None,
            })
    for sym, n in sorted(seq_alphabet.items()):
        if sym in ("A", "C", "G", "T"):
            continue
        mapping_items.append({
            "scope": "sequence", "channel": seq_col, "symbol": sym,
            "n_samples_with_symbol": n, "ambiguous": True,
            "default_value": 0,
            "options": [{"value": 0, "label": "丢弃该位点/样本（推荐）"},
                        {"value": 1, "label": "保留并置 1"}],
            "decision": None,
        })

    pending = [m for m in mapping_items if m["ambiguous"]]
    return {
        "schema": "dataset.inspection/1",
        "inputs": [str(Path(p).expanduser()) for p in paths],
        "files": per_file,
        "cell_lines": cell_lines,
        "channels": channels,
        "sequence_column": seq_col,
        "label_column": label_col,
        "sequence_length": seq_len,
        "symbols": symbols,
        "mapping_items": mapping_items,
        "pending_mapping": len(pending),
        "requires_mapping": bool(pending),
        "sample_rows": sample_rows,
    }


def build_user_config(base_config: Path, inspection: Dict[str, Any],
                      decisions: Optional[Dict[str, int]] = None,
                      out_path: Optional[Path] = None) -> Dict[str, Any]:
    """把用户 Mapping 决策合并进 feature_config，写出用户专属配置。

    ``decisions`` 形如 ``{"CTCF:N": 0, "Dnase:A": 1}``（键 = ``通道:符号``）。
    未给出的符号沿用其默认值。
    """
    cfg = json.loads(Path(base_config).read_text(encoding="utf-8"))
    decisions = decisions or {}
    applied: List[Dict[str, Any]] = []

    for feat in cfg.get("environment_features", []):
        name = feat.get("name") or feat.get("column")
        enc = dict(feat.get("encoding") or {})
        for item in inspection.get("mapping_items", []):
            if item.get("scope") != "channel" or str(item.get("channel")) != str(feat.get("column")):
                continue
            sym = str(item["symbol"])
            key = f"{name}:{sym}"
            value = decisions.get(key, item.get("default_value", enc.get(sym, 0)))
            enc[sym] = int(value)
            applied.append({"channel": name, "symbol": sym, "value": int(value),
                            "user_decided": key in decisions})
        feat["encoding"] = enc
        feat["enabled"] = bool(feat.get("enabled", True))

    cfg["_source"] = {"base_config": str(base_config),
                      "inspection_inputs": inspection.get("inputs", []),
                      "applied": applied}
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
    return cfg
