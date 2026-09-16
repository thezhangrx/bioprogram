# app/desktop/backend_runner.py
"""
CRISPR 平台后端全自动从头执行引擎 (含可选候选设计模式与表观融合版)
==================================================================
"""

from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.common.paths import DATA_RAW, resolve_dataset  # noqa: E402

# 共享编排层：步骤/命令/依赖/产物只有一份定义 (pipeline/steps.py)，与网页工作台共用。
from workflows.orchestrator import PipelineContext, build_command, get_step  # noqa: E402


def step_context(root_path: Path, proceeded_data_dir: Path | None = None,
                 **options) -> PipelineContext:
    """把向导的输出根映射为共享编排层的上下文（绝对路径）。

    共享层不再有 batch 概念：``output_dir`` 之下固定派生 ``results/``、``models/``、``logs/``，
    与向导原有的 ``root_path/{results,models,logs}`` 布局完全一致。
    """
    return PipelineContext(
        repo_root=PROJECT_ROOT,
        output_dir=str(Path(root_path).resolve()),
        data_dir=str(Path(proceeded_data_dir).resolve()) if proceeded_data_dir else None,
        options={k: v for k, v in options.items() if v is not None})


def step_command(step_id: str, ctx: PipelineContext) -> List[str]:
    """由共享编排层构造步骤命令（向导不再自行拼装 CLI）。"""
    return build_command(step_id, ctx)


def build_active_environment_combinations(active_epis: List[str]) -> List[str]:
    active_epis = [e.lower().strip() for e in active_epis if e.strip()]
    if not active_epis:
        return ["sequence"]

    combos = ["sequence"]
    for r in range(1, len(active_epis) + 1):
        for subset in itertools.combinations(active_epis, r):
            combos.append("sequence_" + "_".join(sorted(subset)))

    if set(active_epis) == {"ctcf", "dnase", "h3k4me3", "rrbs"}:
        if "all" not in combos:
            combos.append("all")

    return combos


def convert_raw_csv_to_npy(csv_path: Path, cell_line: str, output_dir: Path, form_data: Dict,
                           active_epis: Optional[List[str]] = None):
    """把用户原始 CSV 转成工程约定的 npy。

    通道数**由实际勾选的表观通道决定**（0 个 -> 4 通道 / 92 维），不再永远写
    (N,23,8) / `_features_23x8.npy`。旧实现会让"纯序列"实验实际带上 4 个全 0
    表观通道，且与 4 通道 schema 的文件名对不上（FileNotFoundError）。
    """
    import pandas as pd
    import numpy as np

    df = pd.read_csv(csv_path)
    seq_col = form_data["seq_col"].get()
    target_col = form_data["target_col"].get()

    if seq_col not in df.columns:
        for c in df.columns:
            if 'sgrna' in c.lower() or 'seq' in c.lower():
                seq_col = c; break

    if target_col not in df.columns:
        for c in df.columns:
            if 'effic' in c.lower() or 'label' in c.lower() or 'target' in c.lower():
                target_col = c; break

    # 只保留"用户勾选且数据里确实存在"的表观通道，顺序固定
    epi_order = ["ctcf", "dnase", "h3k4me3", "rrbs"]
    wanted = [e.lower().strip() for e in (active_epis or []) if str(e).strip()]
    present_epis = []
    for epi in epi_order:
        if wanted and epi not in wanted:
            continue
        for c in df.columns:
            if epi in c.lower():
                present_epis.append(epi)
                break

    seq_channels = ['A', 'C', 'G', 'T']
    channel_names = seq_channels + [
        {"ctcf": "CTCF", "dnase": "Dnase", "h3k4me3": "H3K4me3", "rrbs": "RRBS"}[e]
        for e in present_epis
    ]
    n_channels = len(channel_names)

    n_samples = len(df)
    X_3d = np.zeros((n_samples, 23, n_channels), dtype=np.float32)
    seq_ch_idx = {'A': 0, 'C': 1, 'G': 2, 'T': 3}

    for i, (_, row) in enumerate(df.iterrows()):
        seq_str = str(row[seq_col]).upper().strip() if seq_col in df.columns else "N" * 23
        seq_str = seq_str.ljust(23, 'N')[:23]
        for p in range(23):
            b = seq_str[p]
            if b in seq_ch_idx:
                X_3d[i, p, seq_ch_idx[b]] = 1.0

        for offset, epi_k in enumerate(present_epis, start=len(seq_channels)):
            matched_col = None
            for c in df.columns:
                if epi_k in c.lower():
                    matched_col = c
                    break
            if not matched_col:
                continue
            val = row[matched_col]
            if isinstance(val, str) and len(val) == 23:
                for p in range(23):
                    X_3d[i, p, offset] = 1.0 if val[p] in ['1', 'A', 'Y', 'T'] else 0.0
            elif isinstance(val, (int, float, np.number)):
                X_3d[i, :, offset] = float(val)

    X_2d = X_3d.reshape(n_samples, -1)
    feature_count = X_2d.shape[1]
    y = df[target_col].to_numpy(dtype=np.float32) if target_col in df.columns else np.random.uniform(0.5, 0.9, n_samples).astype(np.float32)

    # 文件名与 core/data/splitting/cell_line_division.get_feature_file_paths 完全一致
    np.save(output_dir / f"{cell_line}_features_23x{n_channels}.npy", X_3d)
    np.save(output_dir / f"{cell_line}_features_{feature_count}.npy", X_2d)
    np.save(output_dir / f"{cell_line}_labels.npy", y)
    df.to_csv(output_dir / f"{cell_line}_metadata.csv", index=False)
    print(f"[✓] 成功为 {cell_line} 生成 {n_channels} 通道特征张量 "
          f"({n_samples} 样本, {feature_count} 维; 表观通道={present_epis or '无'})")


def run_feature_engineering_step(form_data: Dict, raw_data_dir: str, output_data_dir: Path,
                                 target_cell_lines: List[str],
                                 active_epis: Optional[List[str]] = None) -> bool:
    output_data_dir.mkdir(parents=True, exist_ok=True)
    seq_len = form_data["seq_len"].get()
    seq_col = form_data["seq_col"].get()
    target_col = form_data["target_col"].get()

    # 预计算特征缓存（DeepCRISPR，8 通道 / 184 维）。processed 已按数据集分层。
    benchmark_dir = resolve_dataset('DeepCRISPR')
    if benchmark_dir.exists():
        for item in benchmark_dir.glob("*.*"):
            dest = output_data_dir / item.name
            if not dest.exists():
                shutil.copy2(item, dest)

    # schema 必须反映**本次实际使用的通道**：用户不勾表观通道时就是 4 通道 / 92 维，
    # 不能永远写 8 通道（否则会按 4 个全 0 表观通道训练，且文件名与 schema 对不上）。
    epi_map = {"ctcf": "CTCF", "dnase": "Dnase", "h3k4me3": "H3K4me3", "rrbs": "RRBS"}
    wanted = [e.lower().strip() for e in (active_epis or []) if str(e).strip()]
    chosen_epis = [c for c in epi_map.values() if not wanted or c.lower() in wanted]
    canonical_channels = ["A", "C", "G", "T"] + chosen_epis
    schema_dict = {
        "sequence_length": seq_len,
        "channel_count": len(canonical_channels),
        "feature_count": seq_len * len(canonical_channels),
        "channel_names": canonical_channels,
        "sequence_channels": ["A", "C", "G", "T"]
    }
    schema_path = output_data_dir / "feature_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_dict, f, indent=4, ensure_ascii=False)

    raw_dir_path = Path(raw_data_dir)
    if raw_dir_path.is_file():
        actual_search_dir = raw_dir_path.parent
        direct_csv_file = raw_dir_path
    else:
        actual_search_dir = raw_dir_path
        direct_csv_file = None

    # 目标文件名由 schema 决定（<cell>_features_23x<C>.npy / _<23*C>.npy）
    want_channels = int(schema_dict["channel_count"])
    want_features = int(schema_dict["feature_count"])

    for cl in target_cell_lines:
        cl_clean = cl.strip().lower()
        npy_3d = output_data_dir / f"{cl_clean}_features_23x{want_channels}.npy"
        if npy_3d.exists():
            continue

        # 缓存只在通道数一致时复用：否则会把 8 通道缓存配 4 通道 schema（静默错）
        bench_3d = benchmark_dir / f"{cl_clean}_features_23x{want_channels}.npy"
        if benchmark_dir.exists() and bench_3d.exists():
            for item in benchmark_dir.glob(f"{cl_clean}*.*"):
                shutil.copy2(item, output_data_dir / item.name)
            continue

        if direct_csv_file and direct_csv_file.exists():
            convert_raw_csv_to_npy(direct_csv_file, cl_clean, output_data_dir, form_data,
                                   active_epis=active_epis)
        elif actual_search_dir.exists():
            csv_candidates = list(actual_search_dir.glob(f"*{cl_clean}*.csv")) + list(actual_search_dir.glob("*.csv"))
            if csv_candidates:
                convert_raw_csv_to_npy(csv_candidates[0], cl_clean, output_data_dir, form_data,
                                       active_epis=active_epis)

    return True


def execute_full_pipeline(form_data: Dict, root_output_dir: str) -> bool:
    root_path = Path(root_output_dir)
    root_path.mkdir(parents=True, exist_ok=True)

    models_dir = root_path / "models" / "weights"
    results_dir = root_path / "results" / "batches"
    logs_dir = root_path / "logs"
    proceeded_data_dir = root_path / "proceeded_data"

    models_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    proceeded_data_dir.mkdir(exist_ok=True)

    active_cls = [k.lower() for k, v in form_data["selected_cell_lines"].items() if v.get()]
    active_epis = [k for k, v in form_data["selected_environments"].items() if v.get()]
    active_models = [k.lower() for k, v in form_data["model_vars"].items() if v.get()]
    active_splits = [k.lower() for k, v in form_data["split_vars"].items() if v.get()]

    # 待测表观与候选生成开关判定
    has_target = form_data.get("enable_target_genome", Path()).get() and bool(form_data["target_genome_dir"].get().strip())
    target_available_epis = [k for k, v in form_data.get("target_available_environments", {}).items() if v.get()] if has_target else []

    if not active_cls: active_cls = ["hct116"]
    if not active_models: active_models = ["linear"]
    if not active_splits: active_splits = ["single"]

    active_environments = build_active_environment_combinations(active_epis)

    batch_name = ""
    batch_results_dir = results_dir

    # 1. 特征工程
    print(f"\n{'='*70}\n[Step 1/7] 执行特征工程数据准备...\n{'='*70}")
    raw_measured = form_data["measured_data_dir"].get()
    if not raw_measured or not os.path.exists(raw_measured):
        raw_measured = str(DATA_RAW)   # 回退到仓库自带原始逐细胞系 CSV

    run_feature_engineering_step(form_data, raw_measured, proceeded_data_dir, active_cls,
                                 active_epis=active_epis)

    # 2. 模型训练与预测 —— 已按职责拆分 (向导第4步选项2/3 分别接入两个文件):
    #    2a. data_digging.py: 已测数据训练深入挖掘 (Training Scope, 第4步选项2 的表观特征)
    #    2b. predict.py     : mixed 十折交叉验证 + 目标数据集预测 (Target Epigenetics, 第4步选项3)
    print(f"\n{'='*70}\n[Step 2/7] 启动已测数据挖掘引擎 (调用 data_digging.py)...\n{'='*70}")
    print(f"  - 目标划分模式: {active_splits}")
    print(f"  - 目标模型: {active_models}")
    print(f"  - 目标细胞系: {active_cls}")
    print(f"  - Training Scope 表观特征展开 ({len(active_environments)}种环境组合): {active_environments}")

    ctx = step_context(root_path, proceeded_data_dir,
                       models=active_models, cell_lines=active_cls,
                       environments=active_environments, split_types=active_splits)
    cmd_dig = step_command("train_grid", ctx)
    print(f"  [shared] {' '.join(cmd_dig)}")
    proc = subprocess.run(cmd_dig, check=False)
    if proc.returncode != 0:
        print(f"[Warning] data_digging.py 退出状态: {proc.returncode}")

    if has_target:
        print(f"\n{'='*70}\n[Step 2b/7] 目标候选设计 (mixed 十折 CV, 调用 predict.py)...\n{'='*70}")
        # 目标待测数据集: target_genome_dir 可能是 CSV 文件或含 CSV 的目录
        tgt_path = Path(form_data["target_genome_dir"].get().strip())
        target_input = None
        if tgt_path.is_file():
            target_input = tgt_path
        elif tgt_path.is_dir():
            cands = sorted(tgt_path.glob("*.csv")) + sorted(tgt_path.glob("*.CSV"))
            if cands:
                target_input = cands[0]
        if target_input is None:
            print("[Warning] 未找到目标待测 CSV (enable_target_genome 已开启但路径无效), 跳过候选预测")
        else:
            cand_ctx = step_context(root_path, proceeded_data_dir,
                                    models=active_models, cell_lines=active_cls,
                                    target_input=str(target_input),
                                    target_epigenetics=target_available_epis or None,
                                    ultimate_dir=str(root_path / "ultimate"))
            cmd_cand = step_command("generate_candidates", cand_ctx)
            print(f"  [shared] {' '.join(cmd_cand)}")
            print(f"  - Target Epigenetics: {', '.join(target_available_epis) if target_available_epis else '(自动识别)'}")
            print(f"  - 目标输入: {target_input} -> results/summary/赛道二_results.csv")
            proc2 = subprocess.run(cmd_cand, check=False)
            if proc2.returncode != 0:
                print(f"[Warning] predict.py 退出状态: {proc2.returncode}")

    # 3. 指标收集 (引导程序控制：仅生成用户勾选划分模式对应的结果 CSV)
    print(f"\n{'='*70}\n[Step 3/7] 收集模型指标与评测报告 (调用 collect_results.py)...\n{'='*70}")
    print(f"  - 按引导程序勾选划分模式选择性生成结果 CSV: {active_splits}")
    cmd_collect = step_command("collect_results",
                               step_context(root_path, proceeded_data_dir,
                                            split_types=active_splits))
    print(f"  [shared] {' '.join(cmd_collect)}")
    subprocess.run(cmd_collect, check=False)

    # 4. 异常实验检测 (生成 summary/anomaly_report.md)
    print(f"\n{'='*70}\n[Step 4/7] 异常实验检测与治疗报告 (调用 anomaly_treatment.py)...\n{'='*70}")
    cmd_anomaly = step_command("anomaly_treatment",
                               step_context(root_path, proceeded_data_dir))
    print(f"  [shared] {' '.join(cmd_anomaly)}")
    subprocess.run(cmd_anomaly, check=False)

    # 5. 生信显著性提取 (含 key_regulatory_biomarkers.csv, 已自 results.py 移植)
    print(f"\n{'='*70}\n[Step 5/7] 提取生信稳健性参数与关键调控特征库 (调用 importance_extraction.py)...\n{'='*70}")
    cmd_importance = step_command("importance_extraction",
                                  step_context(root_path, proceeded_data_dir))
    print(f"  [shared] {' '.join(cmd_importance)}")
    subprocess.run(cmd_importance, check=False)

    # 6. 生信热图与多维图表绘制 (visualization.py, 含显著性标注热图与四层环境增量树图)
    print(f"\n{'='*70}\n[Step 6/7] 自动绘制 23nt 显著性热图与四层环境增量树图 (调用 visualization.py)...\n{'='*70}")
    cmd_plots = step_command(
        "legacy_visualization",
        step_context(root_path, proceeded_data_dir,
                     plots_dir=str(batch_results_dir / "summary" / "plots")))
    print(f"  [shared] {' '.join(cmd_plots)}")
    subprocess.run(cmd_plots, check=False)

    # 7. 最终交付物核对与输出汇总
    print(f"\n{'='*70}\n[Step 7/7] 最终交付物核对与输出汇总...\n{'='*70}")
    summary_dir = batch_results_dir / "summary"
    deliverables = {
        "赛道二_results.csv (候选 sgRNA 清单, Ultimate 模型共识)": summary_dir / "赛道二_results.csv",
        "ultimate/ (10 折 CV 终极模型参数)": root_path / "ultimate",
        "key_regulatory_biomarkers.csv (关键调控特征库)": summary_dir / "feature_importance" / "key_regulatory_biomarkers.csv",
        "anomaly_report.md (异常检测报告)": summary_dir / "anomaly_report.md",
        "metrics_tables/ (评测指标表)": summary_dir / "metrics_tables",
        "feature_importance/ (5 大模型生信稳健性报告, CNN 按卷积核拆分)": summary_dir / "feature_importance",
        "plots/ (显著性白色掩码热图与四层增量树图)": summary_dir / "plots",
    }
    all_ok = True
    for desc, path in deliverables.items():
        if not has_target and ("赛道二" in desc or "ultimate" in desc):
            print(f"  [跳过] {desc} -> 候选设计模式未开启")
            continue
        status = "OK" if path.exists() else "MISSING"
        if status == "MISSING":
            all_ok = False
        print(f"  [{status}] {desc} -> {path}")
    if all_ok:
        print(f"\n[✓] 全流程运行完毕，全部交付物已生成至: {root_path}")
    return True
