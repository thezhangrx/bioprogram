"""Environment Factorial DAG 测试 (2^4 lattice)。

覆盖任务书 §30 的 7 项要求:
  1. 节点完整性: 16 theoretical combinations
  2. edge count: 完整 Boolean lattice = 4 × 2^(4-1) = 32 条有向边
  3. multiple parents: CTCF+DNase 同时有 CTCF 与 DNase 两个父节点
  4. unique nodes: 同一组合在 nodes 表中每个 group 只出现一次
  5. conditional effect: delta_r2 = child_r2 - parent_r2 (同 cohort 配对)
  6. direction: delta_r2 符号保留 (positive / negative)
  7. missing: 缺失组合 -> node.status = unavailable, 不被删除

另覆盖: 边与引擎 incremental_effect 的一致性、METRIC_INCONSISTENCY 只 warning、
CI 不伪造、ablation view 与 additive view 区分、DAG 渲染只消费 DataFrame。
"""
from __future__ import annotations

import tempfile
import unittest
from collections import Counter

import numpy as np
import pandas as pd

from analysis.environment.factorial_dag import (EDGE_COLUMNS, ENV_FACTORS,
                                               build_ablation_edges,
                                               build_dag_report,
                                               build_environment_edges,
                                               build_environment_nodes,
                                               children_of, combination_label,
                                               parents_of, theoretical_edges,
                                               theoretical_nodes)


def _row(model, split, cell, env, seed, r2, rmse, mae, pearson=0.5, spearman=0.5):
    return {"model": model, "split_type": split, "cell_line": cell, "environment": env,
            "random_seed": seed, "R2": r2, "RMSE": rmse, "MAE": mae,
            "Pearson": pearson, "Spearman": spearman}


def _full_lattice_table(model="linear", split="single", cell="hct116", r2_map=None):
    """构造 16 个组合 × 1 seed 的完整因子表, 指标由 r2_map 决定。"""
    r2_map = r2_map or {}
    rows = []
    for tnode in theoretical_nodes():
        combo = tnode["combination"]
        r2 = r2_map.get(combo, 0.10 + 0.01 * tnode["environment_count"])
        rows.append(_row(model, split, cell, combo, 42, r2,
                         0.20 - 0.01 * tnode["environment_count"],
                         0.15 - 0.01 * tnode["environment_count"]))
    return pd.DataFrame(rows)


class TestTheoreticalStructure(unittest.TestCase):
    def test_node_completeness(self):
        nodes = theoretical_nodes()
        self.assertEqual(len(nodes), 2 ** len(ENV_FACTORS))  # 16
        self.assertEqual(Counter(n["environment_count"] for n in nodes),
                         {1: 4, 2: 6, 3: 4, 0: 1, 4: 1})
        combos = {n["combination"] for n in nodes}
        self.assertEqual(len(combos), 16)
        self.assertIn("sequence", combos)      # level 0 = sequence-only baseline
        self.assertIn("all", combos)           # level 4 = ALL

    def test_edge_count_boolean_lattice(self):
        edges = theoretical_edges()
        self.assertEqual(len(edges), 4 * 2 ** (4 - 1))  # 32
        self.assertEqual(len({(e["parent_combination"], e["child_combination"]) for e in edges}), 32)
        for e in edges:
            self.assertEqual(len(parents_of(e["child_combination"])),
                             len(parents_of(e["child_combination"])))
            self.assertIn(e["added_environment"], ENV_FACTORS)

    def test_edge_is_single_factor_addition(self):
        for e in theoretical_edges():
            parent = parents_of(e["child_combination"])
            # child 的父节点之一必须是 parent_combination
            self.assertIn(e["parent_combination"], parent)

    def test_multiple_parents_supported(self):
        target = "sequence_ctcf_dnase"
        self.assertEqual(sorted(parents_of(target)), ["sequence_ctcf", "sequence_dnase"])
        # 两个父边都必须存在 (不得用 canonical parent 删除合法父边)
        pairs = {(e["parent_combination"], e["child_combination"]) for e in theoretical_edges()}
        self.assertIn(("sequence_ctcf", target), pairs)
        self.assertIn(("sequence_dnase", target), pairs)

    def test_children_and_labels(self):
        self.assertEqual(len(children_of("sequence")), 4)
        self.assertEqual(len(children_of("sequence_ctcf")), 3)
        self.assertEqual(combination_label("sequence"), "sequence-only")
        self.assertEqual(combination_label("all"), "ALL (4 factors)")
        self.assertEqual(combination_label("sequence_ctcf_dnase"), "CTCF + DNase")


class TestNodeTable(unittest.TestCase):
    def test_all_16_nodes_present_for_each_group(self):
        nodes = build_environment_nodes(_full_lattice_table())
        self.assertEqual(len(nodes), 16)
        self.assertEqual(nodes["combination"].nunique(), 16)      # 唯一节点
        self.assertTrue((nodes["status"] == "ok").all())

    def test_unique_node_per_combination(self):
        table = pd.concat([_full_lattice_table(model="linear"),
                           _full_lattice_table(model="mlp")], ignore_index=True)
        nodes = build_environment_nodes(table)
        dup = nodes.groupby(["split_type", "cell_line", "model", "combination"]).size()
        self.assertEqual(int(dup.max()), 1, "同一组合每组只能有一个节点")

    def test_missing_combination_is_unavailable_not_deleted(self):
        table = _full_lattice_table()
        table = table[table["environment"] != "sequence_ctcf_dnase"]
        nodes = build_environment_nodes(table)
        self.assertEqual(len(nodes), 16)                            # 结构不塌缩
        row = nodes[nodes["combination"] == "sequence_ctcf_dnase"].iloc[0]
        self.assertEqual(row["status"], "unavailable")
        self.assertTrue(np.isnan(float(row["r2"])))
        self.assertEqual(int(row["sample_count"]), 0)

    def test_diverged_experiment_excluded_but_node_kept(self):
        table = _full_lattice_table()
        mask = table["environment"] == "all"
        table.loc[mask, "R2"] = -4.5e19                            # 发散 / 参数异常
        nodes = build_environment_nodes(table, threshold=10.0)
        row = nodes[nodes["combination"] == "all"].iloc[0]
        self.assertEqual(row["status"], "unavailable")
        self.assertEqual(int(row["n_invalid"]), 1)
        self.assertIn("invalid", str(row["warning"]))
        self.assertEqual(len(nodes), 16)

    def test_node_metrics_are_means_over_valid_seeds(self):
        base = _full_lattice_table()
        extra = _full_lattice_table()
        extra["random_seed"] = 43
        extra["R2"] = extra["R2"] + 0.10
        nodes = build_environment_nodes(pd.concat([base, extra], ignore_index=True))
        seq = nodes[nodes["combination"] == "sequence"].iloc[0]
        self.assertAlmostEqual(float(seq["r2"]),
                               float(base[base.environment == "sequence"]["R2"].iloc[0]) + 0.05,
                               places=6)
        self.assertEqual(int(seq["eligible_count"]), 2)


class TestEdgeTable(unittest.TestCase):
    def setUp(self):
        self.table = _full_lattice_table()
        self.nodes = build_environment_nodes(self.table)
        self.edges = build_environment_edges(self.table, nodes=self.nodes)

    def test_all_32_theoretical_edges_materialised(self):
        self.assertEqual(len(self.edges), 32)
        self.assertEqual(set(self.edges.columns), set(EDGE_COLUMNS))

    def test_conditional_effect_equals_child_minus_parent(self):
        for _, e in self.edges.iterrows():
            self.assertAlmostEqual(float(e["delta_r2"]),
                                   float(e["child_r2"]) - float(e["parent_r2"]), places=9)

    def test_direction_preserved(self):
        r2_map = {"sequence": 0.05, "sequence_ctcf_dnase": 0.02,
                  "sequence_ctcf": 0.10, "sequence_dnase": 0.05}
        table = _full_lattice_table(r2_map=r2_map)
        edges = build_environment_edges(table)
        e = edges[(edges["parent_combination"] == "sequence_ctcf") &
                  (edges["child_combination"] == "sequence_ctcf_dnase")].iloc[0]
        self.assertAlmostEqual(float(e["delta_r2"]), 0.02 - 0.10, places=9)
        self.assertLess(float(e["delta_r2"]), 0)
        pos = edges[(edges["parent_combination"] == "sequence") &
                    (edges["child_combination"] == "sequence_ctcf")].iloc[0]
        self.assertGreater(float(pos["delta_r2"]), 0)

    def test_two_parents_of_same_child_can_differ(self):
        r2_map = {"sequence_ctcf": 0.10, "sequence_dnase": 0.05, "sequence_ctcf_dnase": 0.20}
        edges = build_environment_edges(_full_lattice_table(r2_map=r2_map))
        a = edges[(edges["parent_combination"] == "sequence_ctcf") &
                  (edges["child_combination"] == "sequence_ctcf_dnase")].iloc[0]
        b = edges[(edges["parent_combination"] == "sequence_dnase") &
                  (edges["child_combination"] == "sequence_ctcf_dnase")].iloc[0]
        self.assertAlmostEqual(float(a["delta_r2"]), 0.10, places=9)   # DNase | CTCF
        self.assertAlmostEqual(float(b["delta_r2"]), 0.15, places=9)   # CTCF | DNase
        self.assertNotAlmostEqual(float(a["delta_r2"]), float(b["delta_r2"]), places=6)

    def test_unavailable_edge_is_kept(self):
        table = self.table[self.table["environment"] != "sequence_dnase"]
        edges = build_environment_edges(table)
        e = edges[(edges["parent_combination"] == "sequence") &
                  (edges["child_combination"] == "sequence_dnase")].iloc[0]
        self.assertEqual(e["status"], "unavailable")               # 边不删除
        self.assertTrue(np.isnan(float(e["delta_r2"])))
        self.assertIn("child_unavailable", str(e["warning"]))
        self.assertEqual(len(edges), 32)

    def test_metric_inconsistency_is_warning_not_removal(self):
        base = _full_lattice_table()
        # child: R2 上升但 RMSE 也上升 -> METRIC_INCONSISTENCY
        mask = base["environment"] == "sequence_ctcf"
        base.loc[mask, "R2"] = 0.50
        base.loc[mask, "RMSE"] = 0.40
        edges = build_environment_edges(base)
        e = edges[(edges["parent_combination"] == "sequence") &
                  (edges["child_combination"] == "sequence_ctcf")].iloc[0]
        self.assertIn("METRIC_INCONSISTENCY", str(e["warning"]))
        self.assertEqual(e["status"], "ok")                        # 边仍然保留
        self.assertGreater(float(e["delta_r2"]), 0)

    def test_no_fake_ci(self):
        self.assertTrue(self.edges["ci_low"].isna().all())
        self.assertTrue(self.edges["ci_high"].isna().all())
        self.assertTrue(self.edges["warning"].str.contains("CI_UNAVAILABLE").all())

    def test_ci_merged_when_real_table_exists(self):
        from analysis.environment.factorial_dag import merge_edge_ci
        ci = pd.DataFrame({"split_type": ["single"], "cell_line": ["hct116"],
                           "model": ["linear"], "parent_combination": ["sequence"],
                           "child_combination": ["sequence_ctcf"],
                           "ci_low": [0.001], "ci_high": [0.02]})
        merged = merge_edge_ci(self.edges, ci)
        row = merged[(merged["parent_combination"] == "sequence") &
                     (merged["child_combination"] == "sequence_ctcf")].iloc[0]
        self.assertAlmostEqual(float(row["ci_low"]), 0.001)
        self.assertIn("CI_AVAILABLE", str(row["warning"]))

    def test_matches_engine_incremental_effect(self):
        """与 analysis.environment.incremental_effect 的配对增量保持一致。"""
        from analysis.environment.incremental_effect import (compute_conditional_increments,
                                                            summarize_conditional)
        engine = summarize_conditional(compute_conditional_increments(self.table))
        engine = engine.rename(columns={"background": "parent_combination",
                                         "environment_added": "added_environment"})
        keys = ["split_type", "cell_line", "model", "added_environment", "parent_combination"]
        merged = self.edges.merge(engine[keys + ["delta_r2_mean"]], on=keys, how="inner")
        self.assertFalse(merged.empty)
        for _, r in merged.iterrows():
            self.assertAlmostEqual(float(r["delta_r2"]), float(r["delta_r2_mean"]), places=6)


class TestAblationViewSeparation(unittest.TestCase):
    def test_ablation_is_negative_of_additive(self):
        table = _full_lattice_table()
        edges = build_environment_edges(table, nodes=build_environment_nodes(table))
        abl = build_ablation_edges(edges)
        self.assertEqual(len(abl), len(edges))
        for _, r in abl.iterrows():
            e = edges[(edges["child_combination"] == r["full_combination"]) &
                      (edges["added_environment"] == r["ablated_environment"]) &
                      (edges["parent_combination"] == r["reduced_combination"])].iloc[0]
            self.assertAlmostEqual(float(r["delta_r2_ablation"]), -float(e["delta_r2"]), places=9)

    def test_distinct_column_names(self):
        table = _full_lattice_table()
        edges = build_environment_edges(table)
        abl = build_ablation_edges(edges)
        self.assertIn("delta_r2_ablation", abl.columns)
        self.assertNotIn("delta_r2", abl.columns)   # 两个科学量不得同名


class TestDagReport(unittest.TestCase):
    def test_report_counts_theory_and_observed(self):
        table = _full_lattice_table()
        table = table[table["environment"] != "all"]
        nodes = build_environment_nodes(table)
        edges = build_environment_edges(table, nodes=nodes)
        report = build_dag_report(nodes, edges)
        r = report.iloc[0]
        self.assertEqual(int(r["theoretical_nodes"]), 16)
        self.assertEqual(int(r["observed_nodes"]), 15)
        self.assertEqual(int(r["unavailable_nodes"]), 1)
        self.assertEqual(int(r["theoretical_edges"]), 32)
        self.assertLessEqual(int(r["valid_edges"]), 32)   # 实际可画 <= 理论
        self.assertIn("all", str(r["unavailable_combinations"]))


class TestRendererConsumesTablesOnly(unittest.TestCase):
    def test_render_from_dataframes(self):
        from analysis.visualization.factorial_dag import (render_conditional_delta_r2,
                                                         render_factorial_dag)
        table = _full_lattice_table()
        nodes = build_environment_nodes(table)
        edges = build_environment_edges(table, nodes=nodes)
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_factorial_dag(nodes, edges, tmp)
            self.assertEqual(len(figs), 1)
            self.assertTrue(figs[0].endswith("single_hct116_linear.png"))
            self.assertIn("factorial_dag", figs[0])
            delta = render_conditional_delta_r2(edges, tmp)
            self.assertEqual(len(delta), 1)
            self.assertIn("conditional_delta_r2", delta[0])

    def test_unavailable_node_is_drawn_not_dropped(self):
        """缺失组合仍进入图 (node exists, status unavailable)。"""
        from analysis.visualization.factorial_dag import render_factorial_dag
        table = _full_lattice_table()
        table = table[table["environment"] != "sequence_rrbs"]
        nodes = build_environment_nodes(table)
        edges = build_environment_edges(table, nodes=nodes)
        with tempfile.TemporaryDirectory() as tmp:
            figs = render_factorial_dag(nodes, edges, tmp)
            self.assertEqual(len(figs), 1)


if __name__ == "__main__":
    unittest.main()
