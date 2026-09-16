# app/desktop/main_wizard.py
"""
CRISPR-Cas9 细胞环境感知型智能设计与生信规律挖掘平台 - 7步引导向导客户端 (交互与联动高级版)
=============================================================================================
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class CRISPRPlatformWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CRISPR-Cas9 细胞环境感知型编辑效率预测与规律挖掘平台")
        self.geometry("880x700")
        self.resizable(True, True)

        self.form_data = {
            "measured_data_dir": tk.StringVar(value=""),
            # Folder B 可选开关
            "enable_target_genome": tk.BooleanVar(value=True),
            "target_genome_dir": tk.StringVar(value=""),
            
            "cell_lines_raw": tk.StringVar(value="hct116, hek293t, hela, hl60"),
            "seq_len": tk.IntVar(value=23),
            "seq_col": tk.StringVar(value="sgRNA"),
            "target_col": tk.StringVar(value="Normalized efficacy"),
            "epi_cols_raw": tk.StringVar(value="CTCF, Dnase, H3K4me3, RRBS"),
            "chrom_col": tk.StringVar(value="Chromosome"),
            "start_col": tk.StringVar(value="Start"),
            "end_col": tk.StringVar(value="End"),
            
            "selected_cell_lines": {},
            "selected_environments": {},
            "target_available_environments": {},

            "split_vars": {
                "single": tk.BooleanVar(value=True),
                "all": tk.BooleanVar(value=True),
                "mixed": tk.BooleanVar(value=True),
            },
            "model_vars": {
                "linear": tk.BooleanVar(value=True),
                "xgboost": tk.BooleanVar(value=True),
                "mlp": tk.BooleanVar(value=True),
                "cnn": tk.BooleanVar(value=True),
                "transformer": tk.BooleanVar(value=True),
            },
            "xai_vars": {
                "xgb_shap": tk.BooleanVar(value=True),
                "cnn_ism": tk.BooleanVar(value=True),
                "trans_entropy": tk.BooleanVar(value=True),
            },
            "root_output_dir": tk.StringVar(value=str(PROJECT_ROOT / "Project_Output"))
        }

        self.current_step = 1
        self.total_steps = 7

        # 存放动态 UI 控件
        self.target_genome_widgets = []
        self.step3_coord_widgets = []
        self.step4_target_epi_widgets = {}

        self._setup_ui_skeleton()
        self._show_step(1)

    def _setup_ui_skeleton(self):
        self.header_frame = ttk.Frame(self, padding="15 10")
        self.header_frame.pack(fill=tk.X)

        self.title_lbl = ttk.Label(self.header_frame, text="", font=("Arial", 13, "bold"), foreground="#003366")
        self.title_lbl.pack(anchor=tk.W)

        self.progress_bar = ttk.Progressbar(self.header_frame, maximum=self.total_steps, value=1)
        self.progress_bar.pack(fill=tk.X, pady=(6, 0))

        self.container = ttk.Frame(self, padding="20 10")
        self.container.pack(fill=tk.BOTH, expand=True)

        self.footer_frame = ttk.Frame(self, padding="15 10")
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.step_tracker_lbl = ttk.Label(self.footer_frame, text="", font=("Arial", 9), foreground="gray")
        self.step_tracker_lbl.pack(side=tk.LEFT, padx=5)

        self.btn_next = ttk.Button(self.footer_frame, text="下一步 >", command=self.next_step)
        self.btn_next.pack(side=tk.RIGHT, padx=5)

        self.btn_prev = ttk.Button(self.footer_frame, text="< 上一步", command=self.prev_step)
        self.btn_prev.pack(side=tk.RIGHT, padx=5)

    def _clear_content(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def _show_step(self, step: int):
        self._clear_content()
        self.current_step = step
        self.progress_bar["value"] = step
        self.step_tracker_lbl.config(text=f"步骤 {step} / {self.total_steps}")
        self.btn_prev.config(state=tk.NORMAL if step > 1 else tk.DISABLED)
        self.btn_next.config(text="确认配置并启动流程" if step == self.total_steps else "下一步 >")

        # Step 1
        if step == 1:
            self.title_lbl.config(text="第 1 步：平台核心宗旨与数据准备规范")
            notice_box = ttk.LabelFrame(self.container, text=" 💡 平台科学定位与核心宗旨 ", padding=12)
            notice_box.pack(fill=tk.X, pady=(0, 10))
            notice_txt = (
                "【重要说明】\n"
                "本平台的核心目的不仅是做单纯的数值拟合，更关键的是在您提供的真实实验数据中，"
                "深度挖掘目标细胞系中究竟是哪些序列 Motif 与表观微环境因素（染色质开放度、CTCF绝缘环化、甲基化等）"
                "显著影响了 CRISPR-Cas9 的剪切动力学，揭示生物物理机制，为后续湿实验改造与序列设计提供高可信的科学指示。"
            )
            ttk.Label(notice_box, text=notice_txt, justify=tk.LEFT, font=("Arial", 9, "bold"), foreground="#004080").pack(anchor=tk.W)

            spec_box = ttk.LabelFrame(self.container, text=" 📋 输入数据目录与格式准备要求 ", padding=12)
            spec_box.pack(fill=tk.BOTH, expand=True)
            spec_txt = (
                "请在开始前将数据分别归类准备：\n\n"
                "1. 【已测量效率数据集】(Folder A / 必填)：\n"
                "   - 存放已完成实验测量效率的细胞系数据 CSV (如 hela.csv 或整个数据目录)；\n"
                "   - 效率标签（Target）支持原始测定值或标准化小数，系统特征工程将自动自适应处理；\n"
                "   - 表观修饰特征若为字符串：确保 'A' 代表有修饰信号（1），'N' 代表无信号（0）；\n"
                "   - 表观特征若为数值：完全兼容连续型浮点小数（如 0.0 ~ 1.0 信号密度）。\n\n"
                "2. 【待预测全基因组/靶区】(Folder B / 可选)：\n"
                "   - 若您需要从头筛选未知序列，请提供基因组 CSV (包含 Chromosome, Start, End 与 23nt 序列)；\n"
                "   - 若您仅需探索生物学调控机制而无需生成候选序列清单，可不选择此项。"
            )
            ttk.Label(spec_box, text=spec_txt, justify=tk.LEFT, font=("Arial", 9)).pack(anchor=tk.W)

        # Step 2 (Folder B 可选模式)
        elif step == 2:
            self.title_lbl.config(text="第 2 步：选择已测量数据与待预测基因组")

            # Folder A
            f1 = ttk.LabelFrame(self.container, text=" 1. 已测量编辑效率的数据集 (Folder A / 必填) ", padding=12)
            f1.pack(fill=tk.X, pady=6)
            ttk.Label(f1, text="包含已完成测量的细胞系特征与编辑效率 CSV (支持单文件或文件夹)：").pack(anchor=tk.W, pady=(0, 4))
            r1 = ttk.Frame(f1)
            r1.pack(fill=tk.X)
            ttk.Entry(r1, textvariable=self.form_data["measured_data_dir"], width=55).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            ttk.Button(r1, text="选择文件...", command=lambda: self._choose_file("measured_data_dir")).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(r1, text="选择目录...", command=lambda: self._choose_dir("measured_data_dir")).pack(side=tk.LEFT)

            # Folder B (带可选开关)
            f2 = ttk.LabelFrame(self.container, text=" 2. 待预测/设计的未知全基因组或靶区 (Folder B / 可选) ", padding=12)
            f2.pack(fill=tk.X, pady=8)

            cb_enable_b = ttk.Checkbutton(
                f2, text="开启未知基因组/靶区候选序列智能预测与筛选 (生成 赛道二_results.csv)",
                variable=self.form_data["enable_target_genome"],
                command=self._update_folder_b_state
            )
            cb_enable_b.pack(anchor=tk.W, pady=(0, 6))

            self.target_genome_widgets = []
            lbl_b = ttk.Label(f2, text="包含未知编辑效率的基因组 CSV (不选则平台仅进行机制挖掘，不生成候选清单)：")
            lbl_b.pack(anchor=tk.W, pady=(0, 4))
            self.target_genome_widgets.append(lbl_b)

            r2 = ttk.Frame(f2)
            r2.pack(fill=tk.X)
            ent_b = ttk.Entry(r2, textvariable=self.form_data["target_genome_dir"], width=55)
            ent_b.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            btn_b1 = ttk.Button(r2, text="选择文件...", command=lambda: self._choose_file("target_genome_dir"))
            btn_b1.pack(side=tk.LEFT, padx=(0, 4))
            btn_b2 = ttk.Button(r2, text="选择目录...", command=lambda: self._choose_dir("target_genome_dir"))
            btn_b2.pack(side=tk.LEFT)

            self.target_genome_widgets.extend([ent_b, btn_b1, btn_b2])
            self._update_folder_b_state()

        # Step 3
        elif step == 3:
            self.title_lbl.config(text="第 3 步：设定特征维度与 CSV 列名映射")
            f = ttk.Frame(self.container)
            f.pack(fill=tk.BOTH, expand=True)

            ttk.Label(f, text="包含的细胞系列表 (逗号分隔):").grid(row=0, column=0, sticky=tk.W, pady=6)
            ttk.Entry(f, textvariable=self.form_data["cell_lines_raw"], width=45).grid(row=0, column=1, sticky=tk.W, pady=6)

            ttk.Label(f, text="sgRNA 序列长度 (nt):").grid(row=1, column=0, sticky=tk.W, pady=6)
            ttk.Spinbox(f, from_=15, to=30, textvariable=self.form_data["seq_len"], width=10).grid(row=1, column=1, sticky=tk.W, pady=6)

            ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)

            ttk.Label(f, text="已测数据 - 序列列名 (sgRNA):").grid(row=3, column=0, sticky=tk.W, pady=4)
            ttk.Entry(f, textvariable=self.form_data["seq_col"], width=30).grid(row=3, column=1, sticky=tk.W, pady=4)

            ttk.Label(f, text="已测数据 - 效率标签列名 (Target):").grid(row=4, column=0, sticky=tk.W, pady=4)
            ttk.Entry(f, textvariable=self.form_data["target_col"], width=30).grid(row=4, column=1, sticky=tk.W, pady=4)

            ttk.Label(f, text="表观环境修饰列 (逗号分隔):").grid(row=5, column=0, sticky=tk.W, pady=4)
            ttk.Entry(f, textvariable=self.form_data["epi_cols_raw"], width=45).grid(row=5, column=1, sticky=tk.W, pady=4)

            ttk.Separator(f, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=2, sticky="ew", pady=8)

            # 待测基因组坐标 (若 Folder B 未开启则置灰)
            self.step3_coord_widgets = []
            lbl_c = ttk.Label(f, text="待测基因组 - 染色体列名:")
            lbl_c.grid(row=7, column=0, sticky=tk.W, pady=4)
            ent_c = ttk.Entry(f, textvariable=self.form_data["chrom_col"], width=20)
            ent_c.grid(row=7, column=1, sticky=tk.W, pady=4)

            lbl_co = ttk.Label(f, text="待测基因组 - 起始/终止坐标列名:")
            lbl_co.grid(row=8, column=0, sticky=tk.W, pady=4)
            coord_frame = ttk.Frame(f)
            coord_frame.grid(row=8, column=1, sticky=tk.W, pady=4)
            ent_s = ttk.Entry(coord_frame, textvariable=self.form_data["start_col"], width=12)
            ent_s.pack(side=tk.LEFT, padx=(0, 5))
            lbl_tilde = ttk.Label(coord_frame, text="~")
            lbl_tilde.pack(side=tk.LEFT, padx=2)
            ent_e = ttk.Entry(coord_frame, textvariable=self.form_data["end_col"], width=12)
            ent_e.pack(side=tk.LEFT, padx=(5, 0))

            self.step3_coord_widgets.extend([lbl_c, ent_c, lbl_co, ent_s, lbl_tilde, ent_e])
            is_b_active = self.form_data["enable_target_genome"].get()
            for w in self.step3_coord_widgets:
                w.config(state=tk.NORMAL if is_b_active else tk.DISABLED)

        # Step 4 (表观级联联动更新)
        elif step == 4:
            self.title_lbl.config(text="第 4 步：选择细胞系挖掘范围与待测表观环境完备度")

            raw_cls = [c.strip().lower() for c in self.form_data["cell_lines_raw"].get().split(",") if c.strip()]
            raw_epis = [e.strip() for e in self.form_data["epi_cols_raw"].get().split(",") if e.strip()]

            # 同步状态
            new_cl_dict = {}
            for cl in raw_cls:
                old_val = self.form_data["selected_cell_lines"].get(cl, tk.BooleanVar(value=True)).get()
                new_cl_dict[cl] = tk.BooleanVar(value=old_val)
            self.form_data["selected_cell_lines"] = new_cl_dict

            new_epi_dict = {}
            new_target_epi_dict = {}
            for epi in raw_epis:
                old_val1 = self.form_data["selected_environments"].get(epi, tk.BooleanVar(value=True)).get()
                new_epi_dict[epi] = tk.BooleanVar(value=old_val1)

                old_val2 = self.form_data["target_available_environments"].get(epi, tk.BooleanVar(value=True)).get()
                new_target_epi_dict[epi] = tk.BooleanVar(value=old_val2)

            self.form_data["selected_environments"] = new_epi_dict
            self.form_data["target_available_environments"] = new_target_epi_dict

            # 1. 目标细胞系
            c_box = ttk.LabelFrame(self.container, text=" 1. 目标细胞系挖掘范围 (已测训练集) ", padding=10)
            c_box.pack(fill=tk.X, pady=4)
            c_grid = ttk.Frame(c_box)
            c_grid.pack(fill=tk.X)
            for i, cl in enumerate(raw_cls):
                ttk.Checkbutton(c_grid, text=cl.upper(), variable=self.form_data["selected_cell_lines"][cl]).grid(row=i//4, column=i%4, padx=12, pady=3, sticky=tk.W)

            # 2. 训练集表观环境 (绑定联动事件)
            e_box = ttk.LabelFrame(self.container, text=" 2. 已测数据训练时深入挖掘的表观特征 (Training Scope) ", padding=10)
            e_box.pack(fill=tk.X, pady=6)
            e_grid = ttk.Frame(e_box)
            e_grid.pack(fill=tk.X)
            for j, epi in enumerate(raw_epis):
                cb_train_epi = ttk.Checkbutton(
                    e_grid, text=epi, variable=self.form_data["selected_environments"][epi],
                    command=self._update_epigenetic_cascade_linkage
                )
                cb_train_epi.grid(row=j//4, column=j%4, padx=12, pady=3, sticky=tk.W)

            # 3. 待测目标序列实际具备的表观环境
            self.t_box = ttk.LabelFrame(self.container, text=" 3. 待预测目标基因组/序列【实际具备】的表观环境 (Target Epigenetics) ", padding=10)
            self.t_box.pack(fill=tk.X, pady=6)
            t_grid = ttk.Frame(self.t_box)
            t_grid.pack(fill=tk.X)

            self.step4_target_epi_widgets = {}
            for k, epi in enumerate(raw_epis):
                cb_tgt_epi = ttk.Checkbutton(
                    t_grid, text=f"包含 {epi}", variable=self.form_data["target_available_environments"][epi]
                )
                cb_tgt_epi.grid(row=k//4, column=k%4, padx=12, pady=3, sticky=tk.W)
                self.step4_target_epi_widgets[epi] = cb_tgt_epi

            self._update_epigenetic_cascade_linkage()

        # Step 5
        elif step == 5:
            self.title_lbl.config(text="第 5 步：训练划分模式、预测模型与生信稳健性配置")

            split_box = ttk.LabelFrame(self.container, text=" 1. 训练划分模式选择 (按需勾选) ", padding=10)
            split_box.pack(fill=tk.X, pady=(0, 6))
            s_row = ttk.Frame(split_box)
            s_row.pack(fill=tk.X)
            ttk.Checkbutton(s_row, text="Single (单一细胞系独立训练 70/15/15)", variable=self.form_data["split_vars"]["single"]).pack(side=tk.LEFT, padx=10)
            ttk.Checkbutton(s_row, text="All (留一细胞系跨域泛化测试 LOSO)", variable=self.form_data["split_vars"]["all"]).pack(side=tk.LEFT, padx=10)
            ttk.Checkbutton(s_row, text="Mixed (多细胞系混合 4-Seed 重复求均值)", variable=self.form_data["split_vars"]["mixed"]).pack(side=tk.LEFT, padx=10)

            box = ttk.LabelFrame(self.container, text=" 2. 模型阵列选择与高级生信参数配置 (联动控制) ", padding=10)
            box.pack(fill=tk.BOTH, expand=True)

            self.xai_widgets = {}

            # Linear
            r1 = ttk.Frame(box)
            r1.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(r1, text="Linear Regression", variable=self.form_data["model_vars"]["linear"]).pack(side=tk.LEFT)
            ttk.Label(r1, text="[内置: t-stat, p-value, FDR显著性]", foreground="#555555").pack(side=tk.LEFT, padx=15)

            # XGBoost
            r2 = ttk.Frame(box)
            r2.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(r2, text="XGBoost", variable=self.form_data["model_vars"]["xgboost"], command=self._update_xai_linkage).pack(side=tk.LEFT)
            cb_xgb_shap = ttk.Checkbutton(r2, text="计算 TreeSHAP 归因信噪比 (SHAP_SNR)", variable=self.form_data["xai_vars"]["xgb_shap"])
            cb_xgb_shap.pack(side=tk.LEFT, padx=15)
            self.xai_widgets["xgboost"] = [cb_xgb_shap]

            # MLP
            r3 = ttk.Frame(box)
            r3.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(r3, text="MLP (全连接网络)", variable=self.form_data["model_vars"]["mlp"], command=self._update_xai_linkage).pack(side=tk.LEFT)
            self.xai_widgets["mlp"] = []

            # CNN
            r4 = ttk.Frame(box)
            r4.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(r4, text="Dual-Branch CNN", variable=self.form_data["model_vars"]["cnn"], command=self._update_xai_linkage).pack(side=tk.LEFT)
            cb_cnn_ism = ttk.Checkbutton(r4, text="计算 In-Silico Mutagenesis (ISM 虚拟饱和突变)", variable=self.form_data["xai_vars"]["cnn_ism"])
            cb_cnn_ism.pack(side=tk.LEFT, padx=15)
            self.xai_widgets["cnn"] = [cb_cnn_ism]

            # Transformer
            r5 = ttk.Frame(box)
            r5.pack(fill=tk.X, pady=3)
            ttk.Checkbutton(r5, text="Transformer", variable=self.form_data["model_vars"]["transformer"], command=self._update_xai_linkage).pack(side=tk.LEFT)
            cb_trans_ent = ttk.Checkbutton(r5, text="计算 Self-Attention 空间聚焦度与香农注意力熵", variable=self.form_data["xai_vars"]["trans_entropy"])
            cb_trans_ent.pack(side=tk.LEFT, padx=15)
            self.xai_widgets["transformer"] = [cb_trans_ent]

            self._update_xai_linkage()

        # Step 6
        elif step == 6:
            self.title_lbl.config(text="第 6 步：核对与确认全流程配置信息")
            txt_box = tk.Text(self.container, wrap=tk.WORD, font=("Consolas", 10), bg="#F8F9FA", relief=tk.SOLID, bd=1)
            txt_box.pack(fill=tk.BOTH, expand=True, pady=5)

            active_splits = [k.upper() for k, v in self.form_data["split_vars"].items() if v.get()]
            active_cls = [k.upper() for k, v in self.form_data["selected_cell_lines"].items() if v.get()]
            active_epis = [k for k, v in self.form_data["selected_environments"].items() if v.get()]
            has_b = self.form_data["enable_target_genome"].get() and bool(self.form_data["target_genome_dir"].get().strip())
            target_epis = [k for k, v in self.form_data["target_available_environments"].items() if v.get()] if has_b else []
            active_models = [k.upper() for k, v in self.form_data["model_vars"].items() if v.get()]

            review_summary = (
                "======================================================================\n"
                "                      CRISPR 平台全流程配置核对单                      \n"
                "======================================================================\n\n"
                f"【1. 输入路径与模式】\n"
                f"  - 已测数据集 (Folder A) : {self.form_data['measured_data_dir'].get() or '默认/自动识别'}\n"
                f"  - 候选设计模式 (Folder B) : {'开启 (生成 赛道二_results.csv)' if has_b else '未开启 (纯机制挖掘模式，不生成候选清单)'}\n"
                f"  - 待测基因组路径 : {self.form_data['target_genome_dir'].get() if has_b else '无'}\n\n"
                f"【2. 特征与挖掘范围】\n"
                f"  - 训练划分模式 ({len(active_splits)}种) : {', '.join(active_splits)}\n"
                f"  - 目标细胞系 ({len(active_cls)}个) : {', '.join(active_cls)}\n"
                f"  - 训练集挖掘表观特征 : {', '.join(active_epis) if active_epis else '纯序列 (Sequence-only)'}\n"
                f"  - 待测序列具备表观特征 : {', '.join(target_epis) if target_epis else ('纯序列预测' if has_b else '不适用')}\n\n"
                f"【3. 启用模型阵列】\n"
                f"  - 已勾选模型 ({len(active_models)}个) : {', '.join(active_models)}\n"
                "======================================================================\n"
            )
            txt_box.insert(tk.END, review_summary)
            txt_box.config(state=tk.DISABLED)

        # Step 7
        elif step == 7:
            self.title_lbl.config(text="第 7 步：确认总输出目录并启动全流程")
            out_box = ttk.LabelFrame(self.container, text=" 设定工程总输出目录 ", padding=14)
            out_box.pack(fill=tk.X, pady=8)

            r = ttk.Frame(out_box)
            r.pack(fill=tk.X)
            ttk.Entry(r, textvariable=self.form_data["root_output_dir"], width=60).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            ttk.Button(r, text="更改目录...", command=lambda: self._choose_dir("root_output_dir")).pack(side=tk.LEFT)

            flow_box = ttk.LabelFrame(self.container, text=" 📂 运行后文件归档结构说明 ", padding=12)
            flow_box.pack(fill=tk.BOTH, expand=True, pady=10)

            has_b = self.form_data["enable_target_genome"].get() and bool(self.form_data["target_genome_dir"].get().strip())
            cand_txt = "│   └── 📄 赛道二_results.csv              <-- 【核心交付物】Ultimate模型共识Top候选sgRNA清单\n" if has_b else ""
            ult_txt = "├── 📁 ultimate/                        <-- 10折交叉验证终极模型参数 (Ultimate)\n" if has_b else ""

            flow_txt = (
                "点击【确认配置并启动】后，系统将自动执行：\n\n"
                "📁 [您指定的总输出目录]/\n"
                "├── 📄 pipeline_config.json             <-- 全局流水线配置记录\n"
                f"{ult_txt}"
                "├── 📁 models/                          <-- 存放训练完成的模型权重\n"
                "├── 📁 logs/                            <-- 存放运行日志\n"
                "└── 📁 results/                         <-- 存放各实验结果\n"
                "    └── summary/\n"
                f"{cand_txt}"
                "        ├── 📄 anomaly_report.md          <-- 实验级/数据级异常检测报告\n"
                "        ├── 📁 metrics_tables/            <-- 评测指标表 (按勾选的划分模式生成)\n"
                "        │       ├── all_experiments.csv\n"
                "        │       ├── single_cell_line_result.csv  (勾选 Single 时生成)\n"
                "        │       ├── all_cell_line_result.csv    (勾选 All 时生成)\n"
                "        │       ├── mixed_cell_line_result.csv  (勾选 Mixed 时生成)\n"
                "        │       └── baseline.csv\n"
                "        ├── 📁 feature_importance/      <-- 5 大模型生信稳健性报告\n"
                "        │       ├── cnn33/53/73_importance.md   <-- CNN 按卷积核拆分\n"
                "        │       └── 📄 key_regulatory_biomarkers.csv <-- 【核心交付物】显著调控特征库\n"
                "        └── 📁 plots/                   <-- 显著性白色掩码热图与四层环境增量树图\n"
            )
            ttk.Label(flow_box, text=flow_txt, justify=tk.LEFT, font=("Consolas", 9)).pack(anchor=tk.W)

    def _choose_file(self, var_name: str):
        f = filedialog.askopenfilename(title="选择数据 CSV 文件", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if f: self.form_data[var_name].set(f)

    def _choose_dir(self, var_name: str):
        d = filedialog.askdirectory(title="选择包含数据的文件夹")
        if d: self.form_data[var_name].set(d)

    def _update_folder_b_state(self):
        """控制 Folder B 控件的激活与禁用状态"""
        is_active = self.form_data["enable_target_genome"].get()
        for w in self.target_genome_widgets:
            w.config(state=tk.NORMAL if is_active else tk.DISABLED)

    def _update_epigenetic_cascade_linkage(self):
        """
        核心联动：
          1. 若未开启 Folder B，待测表观面板全部禁用
          2. 若训练集取消了某项表观 (如 RRBS)，待测表观中的对应项强制取消勾选并置灰禁用
        """
        is_b_active = self.form_data["enable_target_genome"].get()

        for epi, tgt_widget in self.step4_target_epi_widgets.items():
            train_is_checked = self.form_data["selected_environments"].get(epi, tk.BooleanVar(value=False)).get()

            if is_b_active and train_is_checked:
                tgt_widget.config(state=tk.NORMAL)
            else:
                # 强制取消勾选并禁用
                if epi in self.form_data["target_available_environments"]:
                    self.form_data["target_available_environments"][epi].set(False)
                tgt_widget.config(state=tk.DISABLED)

    def _update_xai_linkage(self):
        xai_var_map = {
            "xgboost": "xgb_shap",
            "cnn": "cnn_ism",
            "transformer": "trans_entropy"
        }
        for m_name, widgets in self.xai_widgets.items():
            is_active = self.form_data["model_vars"][m_name].get()
            var_key = xai_var_map.get(m_name)
            for w in widgets:
                if is_active:
                    w.config(state=tk.NORMAL)
                    if var_key:
                        self.form_data["xai_vars"][var_key].set(True)
                else:
                    if var_key:
                        self.form_data["xai_vars"][var_key].set(False)
                    w.config(state=tk.DISABLED)

    def prev_step(self):
        if self.current_step > 1:
            self._show_step(self.current_step - 1)

    def next_step(self):
        if self.current_step == 4:
            if not any(v.get() for v in self.form_data["selected_cell_lines"].values()):
                messagebox.showwarning("校验未通过", "请至少勾选一个目标细胞系！")
                return

        if self.current_step == 5:
            if not any(v.get() for v in self.form_data["split_vars"].values()):
                messagebox.showwarning("校验未通过", "请至少勾选一种训练划分模式 (Single / All / Mixed)！")
                return
            if not any(v.get() for v in self.form_data["model_vars"].values()):
                messagebox.showwarning("校验未通过", "请至少勾选一个预测模型！")
                return

        if self.current_step < self.total_steps:
            self._show_step(self.current_step + 1)
        else:
            self._launch_pipeline()

    def _launch_pipeline(self):
        out_root = self.form_data["root_output_dir"].get()
        if not out_root:
            messagebox.showwarning("提示", "请指定有效的总输出目录！")
            return

        self.btn_next.config(state=tk.DISABLED, text="正在全自动运行中...")
        self.btn_prev.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._run_backend_task, args=(out_root,))
        thread.daemon = True
        thread.start()

    def _run_backend_task(self, out_root: str):
        try:
            from Input.backend_runner import execute_full_pipeline
            success = execute_full_pipeline(self.form_data, out_root)
            if success:
                messagebox.showinfo("运行完成", f"恭喜！全流程已成功运行完毕！\n结果已保存至:\n{out_root}")
            else:
                messagebox.showerror("运行中断", "流水线执行遇到问题，请查看控制台输出。")
        except Exception as e:
            messagebox.showerror("运行错误", f"启动后端发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.destroy()


if __name__ == "__main__":
    app = CRISPRPlatformWizard()
    app.mainloop()
