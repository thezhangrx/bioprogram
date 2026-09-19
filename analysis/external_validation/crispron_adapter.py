"""CRISPRon 适配层：项目序列 → CRISPRon 输入 → 解析预测结果。

职责边界
--------
本模块**只做序列层面的转换与解析**，不做统计、不画图、不做科学解释。
所有常量都取自 CRISPRon 官方源码（``bin/get_30mers_from_fa.py``）并在下方注明出处，
避免"手抄字符串"式实现。

项目侧约定（不在此硬编码）
--------------------------
* 项目序列长度、protospacer/PAM 划分由 ``core`` 的 feature schema 决定；
* 关注位点（Position 18）由 ``analysis/candidates/wt_position18_selection.py``
  的 ``LocusConvention`` 决定。
两者都作为参数传入，本模块只负责"项目 23 nt ↔ CRISPRon 30 nt"的坐标映射。

坐标映射（显式记录，禁止默认等同）
----------------------------------
    项目 23 nt  =  protospacer(20 nt, 1-based 1..20) + PAM(3 nt, 21..23)
    CRISPRon 30 nt = prefix(4 nt) + target(20 nt) + PAM(3 nt, NGG) + suffix(3 nt)

    项目位点 k（1-based，k ∈ [1, 23]）  →  30 nt 中的下标 (PRE_GUIDE + k - 1)
    因 k=18 时 30 nt 下标 = 4 + 17 = 21

**注意**：项目 Position 18 是"23 nt 内的第 18 位"，不是"20 nt protospacer 的第 18 位"。
两者在本项目里恰好都是第 18 位（因为 protospacer 正好是前 20 nt），但这是**结论而非前提**，
因此代码里按 `spacer_len` 显式推导并在 `describe_mapping()` 里打印。
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

# --------------------------------------------------------------------------- #
# CRISPRon 官方常量（逐条对应 bin/get_30mers_from_fa.py 的模块级常量）
# --------------------------------------------------------------------------- #
PRE_GUIDE = 4          # get_30mers_from_fa.py: PRE_GUIDE=4
GUIDE = 20             # get_30mers_from_fa.py: GUIDE=20
PRE_PAM = 1            # get_30mers_from_fa.py: PRE_PAM=1
PAM_MOTIF = "GG"       # get_30mers_from_fa.py: PAM='GG'
POST_PAM = 3           # get_30mers_from_fa.py: POST_PAM=3
TOTAL = PRE_GUIDE + GUIDE + PRE_PAM + len(PAM_MOTIF) + POST_PAM      # = 30
PAM_OFFSET = PRE_GUIDE + GUIDE + PRE_PAM                             # = 25
#: 30 nt 输入里，target 的第 1 位（0-based）
TARGET_START_IN_30MER = PRE_GUIDE                                     # = 4
#: CRISPRon 对 30 nt 输入给出的 plus-strand 目标 ID 后缀（1-based）
PLUS_TARGET_POSITION_1B = PRE_GUIDE + 1                               # = 5

REVCOMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def revcomp(seq: str) -> str:
    return str(seq).translate(REVCOMP)[::-1]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# 序列转换
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CrispronInput:
    """一条序列的 CRISPRon 输入及其完整溯源。"""

    record_id: str
    project_seq: str          # 项目 23 nt（guide 方向）
    spacer_len: int           # 项目约定的 protospacer 长度
    upstream: str             # 4 nt（guide 方向的 5' 外侧）
    downstream: str           # 3 nt（guide 方向的 3' 外侧）
    crispron_seq: str         # 30 nt

    @property
    def pam(self) -> str:
        return self.crispron_seq[TARGET_START_IN_30MER + self.spacer_len:
                                 TARGET_START_IN_30MER + self.spacer_len + 3]

    @property
    def target_20mer(self) -> str:
        return self.crispron_seq[TARGET_START_IN_30MER:
                                 TARGET_START_IN_30MER + self.spacer_len]

    @property
    def expected_target_id(self) -> str:
        return f"{self.record_id}_p_{PLUS_TARGET_POSITION_1B}"

    def as_row(self) -> Dict[str, object]:
        return {
            "record_id": self.record_id,
            "project_seq": self.project_seq,
            "project_seq_sha256": sha256_text(self.project_seq),
            "upstream4": self.upstream,
            "downstream3": self.downstream,
            "crispron_seq": self.crispron_seq,
            "crispron_seq_sha256": sha256_text(self.crispron_seq),
            "target_20mer": self.target_20mer,
            "pam": self.pam,
            "expected_target_id": self.expected_target_id,
            "position_mapping": (
                f"project pos k (1..{len(self.project_seq)}) -> "
                f"crispron index {TARGET_START_IN_30MER}+k-1"
            ),
        }


def build_crispron_input(record_id: str, project_seq: str, spacer_len: int,
                         upstream: str, downstream: str) -> CrispronInput:
    """把项目序列拼成 CRISPRon 需要的 30 nt（4 + 20 + 3 + 3）。

    只做拼接与校验，不做任何"猜测性"修补；任何不合法都直接报错。
    """
    seq = str(project_seq).strip().upper()
    up = str(upstream).strip().upper()
    down = str(downstream).strip().upper()

    if not re.fullmatch(r"[ACGT]+", seq):
        raise ValueError(f"{record_id}: 项目序列含非 ACGT 字符: {seq!r}")
    if len(up) != PRE_GUIDE:
        raise ValueError(f"{record_id}: upstream 必须 {PRE_GUIDE} nt，收到 {len(up)}")
    if len(down) != POST_PAM:
        raise ValueError(f"{record_id}: downstream 必须 {POST_PAM} nt，收到 {len(down)}")
    if not re.fullmatch(r"[ACGT]+", up + down):
        raise ValueError(f"{record_id}: 侧翼含非 ACGT 字符")

    crispron_seq = up + seq + down
    if len(crispron_seq) != TOTAL:
        raise ValueError(f"{record_id}: 构造出的序列长度 {len(crispron_seq)} != {TOTAL}")

    # CRISPRon 会在 PAM_OFFSET:PAM_OFFSET+2 上要求 'GG'
    if crispron_seq[PAM_OFFSET:PAM_OFFSET + len(PAM_MOTIF)] != PAM_MOTIF:
        raise ValueError(
            f"{record_id}: 构造序列在 CRISPRon 期望的 PAM 位置 "
            f"[{PAM_OFFSET}:{PAM_OFFSET+len(PAM_MOTIF)}] 不是 {PAM_MOTIF}: "
            f"{crispron_seq[PAM_OFFSET:PAM_OFFSET+2]!r}"
        )

    return CrispronInput(record_id=record_id, project_seq=seq, spacer_len=int(spacer_len),
                         upstream=up, downstream=down, crispron_seq=crispron_seq)


def mutate_project_sequence(project_seq: str, index0: int, new_base: str) -> Tuple[str, Dict[str, object]]:
    """只替换 ``index0`` 这一个位置，并返回验证信息。"""
    seq = str(project_seq).strip().upper()
    nb = str(new_base).strip().upper()
    if len(nb) != 1 or nb not in "ACGT":
        raise ValueError(f"new_base 必须是单个 ACGT，收到 {new_base!r}")
    if not (0 <= index0 < len(seq)):
        raise ValueError(f"index0={index0} 超出序列长度 {len(seq)}")

    mut = list(seq)
    old = mut[index0]
    mut[index0] = nb
    mut = "".join(mut)

    info = {
        "wt_base": old,
        "mut_base": nb,
        "index0": int(index0),
        "position_1b": int(index0) + 1,
        "length_equal": len(seq) == len(mut),
        "n_mismatch": sum(1 for a, b in zip(seq, mut) if a != b),
        "prefix_equal": seq[:index0] == mut[:index0],
        "suffix_equal": seq[index0 + 1:] == mut[index0 + 1:],
        "pam_unchanged": False,   # 由调用方结合 spacer_len 填
    }
    return mut, info


def describe_mapping(spacer_len: int, position_1b: int) -> Dict[str, object]:
    """显式记录"项目位点 → CRISPRon 输入下标"的映射（禁止默认等同）。"""
    if not (1 <= position_1b <= spacer_len + 3):
        raise ValueError(f"position_1b={position_1b} 超出 23 nt 范围")
    return {
        "project_sequence_length": spacer_len + 3,
        "project_spacer_len": spacer_len,
        "project_pam_range_1b": [spacer_len + 1, spacer_len + 3],
        "position_of_interest_1b": position_1b,
        "position_within_spacer_1b": position_1b,
        "in_spacer": position_1b <= spacer_len,
        "crispron_total": TOTAL,
        "crispron_prefix_len": PRE_GUIDE,
        "crispron_target_range_0b": [TARGET_START_IN_30MER,
                                     TARGET_START_IN_30MER + spacer_len - 1],
        "crispron_pam_range_0b": [TARGET_START_IN_30MER + spacer_len,
                                  TARGET_START_IN_30MER + spacer_len + 2],
        "crispron_index_of_interest_0b": TARGET_START_IN_30MER + position_1b - 1,
    }


# --------------------------------------------------------------------------- #
# 运行 CRISPRon（调用官方三个组件，**不修改原始软件**）
# --------------------------------------------------------------------------- #
@dataclass
class CrispronRunResult:
    outdir: Path
    commands: List[List[str]]
    stdout: str
    stderr: str
    returncodes: List[int]

    @property
    def ok(self) -> bool:
        return all(rc == 0 for rc in self.returncodes)


def build_crispron_commands(fasta: Path, outdir: Path, *, crispron_dir: Path,
                            crisproff_dir: Path, python_exe: str,
                            rnafold_exe: Optional[str] = None) -> List[List[str]]:
    """构造 CRISPRon 三步命令（与 ``bin/CRISPRon.sh`` 一致）。

    单独抽出来是为了：即使本次复用已有输出（``--skip-run``），
    manifest 里也能记录**产生该输出所用的命令**，不留 provenance 空洞。
    """
    outdir = Path(outdir)
    bin_dir = Path(crispron_dir) / "bin"
    data_dir = Path(crispron_dir) / "data"
    models = sorted((data_dir / "deep_models" / "best").glob("*.model.best"))
    if not models:
        raise FileNotFoundError(f"找不到 CRISPRon 深度模型: {data_dir/'deep_models'/'best'}")

    c2 = [python_exe, str(Path(crisproff_dir) / "CRISPRspec_CRISPRoff_pipeline.py"),
          "--guides", str(outdir / "23mers.fa"),
          "--specificity_report", str(outdir / "CRISPRspec.tsv"),
          "--guide_params_out", str(outdir / "CRISPRparams.tsv"),
          "--duplex_energy_params", str(Path(crisproff_dir) / "energy_dics.pkl"),
          "--no_azimuth"]
    if rnafold_exe:
        c2 += ["--rnafold_x", str(rnafold_exe)]   # CRISPRoff 的实际参数名
    return [
        [python_exe, str(bin_dir / "get_30mers_from_fa.py"),
         "-f", str(fasta), "-m", str(outdir / "30mers.fa"), "-g", str(outdir / "23mers.fa")],
        c2,
        [python_exe, str(bin_dir / "DeepCRISPRon_eval.py"), str(outdir),
         str(outdir / "30mers.fa"), str(outdir / "CRISPRparams.tsv")]
        + [str(m) for m in models],
    ]


def run_crispron(fasta: Path, outdir: Path, *, crispron_dir: Path, crisproff_dir: Path,
                 python_exe: str, rnafold_exe: Optional[str] = None,
                 log_path: Optional[Path] = None) -> CrispronRunResult:
    """按 CRISPRon.sh 的三步流程执行，但直接调用组件（保持原始包不被修改）。

    步骤（与 ``bin/CRISPRon.sh`` 一致）：
      1. ``get_30mers_from_fa.py``      —— 扫描正负链，抽出全部 target+PAM
      2. ``CRISPRspec_CRISPRoff_pipeline.py`` —— 计算能量特征（CRISPRparams.tsv）
      3. ``DeepCRISPRon_eval.py``       —— 6 个深度模型取平均，输出 crispron.csv
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    all_cmds = build_crispron_commands(fasta, outdir, crispron_dir=crispron_dir,
                                       crisproff_dir=crisproff_dir, python_exe=python_exe,
                                       rnafold_exe=rnafold_exe)

    cmds: List[List[str]] = []
    logs: List[str] = []
    rcs: List[int] = []

    def _log(msg: str) -> None:
        logs.append(msg)

    def _run(cmd: List[str]) -> int:
        cmds.append(cmd)
        _log("$ " + " ".join(str(c) for c in cmd))
        proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
        _log(proc.stdout)
        if proc.stderr:
            _log("[stderr] " + proc.stderr)
        return proc.returncode

    for i, cmd in enumerate(all_cmds, 1):
        _log(f"# CRISPRon step {i}")
        rcs.append(_run(cmd))

    text = "\n".join(logs)
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(text, encoding="utf-8")

    return CrispronRunResult(outdir=outdir, commands=cmds, stdout=text[:20000],
                             stderr="", returncodes=rcs)


# --------------------------------------------------------------------------- #
# 解析官方输出
# --------------------------------------------------------------------------- #
def locate_rnafold(venv_bin: Optional[Path] = None) -> Optional[str]:
    """找 RNAfold 可执行文件：优先 venv，其次 PATH。"""
    if venv_bin:
        cand = Path(venv_bin) / "RNAfold"
        if cand.exists():
            return str(cand)
    return shutil.which("RNAfold")


def parse_crispron_output(outdir: Path) -> pd.DataFrame:
    """读取 ``crispron.csv``（CRISPRon 的最终预测表）。"""
    path = Path(outdir) / "crispron.csv"
    if not path.exists():
        raise FileNotFoundError(f"CRISPRon 未产出 {path}")
    df = pd.read_csv(path)
    need = {"ID", "30mer", "CRISPRon"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"crispron.csv 缺列 {missing}；实际列={list(df.columns)}")
    return df


def match_intended_target(predictions: pd.DataFrame, rec: CrispronInput) -> Dict[str, object]:
    """在 CRISPRon 输出里定位"我们要的那条 target"，并清点多余 target。

    匹配依据是 **30 nt 序列完全一致**（而不是 ID 命名规则），因此不依赖对
    CRISPRon 编号公式的理解；随后再用期望 ID 做一次交叉校验。
    """
    sub = predictions[predictions["30mer"].astype(str).str.upper() == rec.crispron_seq]
    row = sub.iloc[0] if len(sub) else None
    prefix_rows = predictions[predictions["ID"].astype(str).str.startswith(rec.record_id + "_")]
    return {
        "record_id": rec.record_id,
        "found": row is not None,
        "n_targets_for_record": int(len(prefix_rows)),
        "target_id": None if row is None else str(row["ID"]),
        "id_matches_expected": None if row is None else (str(row["ID"]) == rec.expected_target_id),
        "prediction": None if row is None else float(row["CRISPRon"]),
        "extra_target_ids": [str(x) for x in prefix_rows["ID"]
                             if row is None or str(x) != str(row["ID"])],
        "crispron_seq": rec.crispron_seq,
    }


def write_fasta(records: Iterable[Tuple[str, str]], path: Path) -> Path:
    """写 FASTA（记录名唯一，CRISPRon 要求）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    lines = []
    for rid, seq in records:
        if rid in seen:
            raise ValueError(f"FASTA 记录名重复: {rid}")
        seen.add(rid)
        lines.append(f">{rid}")
        lines.append(str(seq).upper())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
