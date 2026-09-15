/**
 * 显示层中文标签：把后端产出的英文枚举值翻译成中文。
 * 只做展示映射，不改动任何数值或后端字段（前端不重算科学结论）。
 */

const TIER: [RegExp, string][] = [
  [/tier\s*1|strong/i, "等级 1：强一致性证据"],
  [/tier\s*2|moderate/i, "等级 2：中等一致性证据"],
  [/tier\s*3|model-specific|exploratory/i, "等级 3：模型特异 / 探索性证据"],
  [/inconclusive/i, "不确定（Inconclusive）"],
];

const CONSISTENCY: [RegExp, string][] = [
  [/context-consistent/i, "上下文一致"],
  [/context-dependent/i, "上下文依赖"],
  [/context-conflicting/i, "上下文冲突"],
  [/uncertain/i, "不确定"],
  [/^\s*\d+\s*cell\s*lines?/i, ""],   // “1 cell line(s)” 之类的覆盖度描述，另行展示
];

const STATUS: Record<string, string> = {
  completed: "已完成", running: "运行中", failed: "失败", pending: "待处理",
  skipped: "已跳过", unavailable: "不可用", warning: "需复核",
  "dry-run": "仅预览", submitted_external: "已提交外部作业", cancelled: "已取消",
  partial: "部分完成", ok: "正常",
};

export function tierLabel(value: unknown): string {
  const v = String(value ?? "").trim();
  if (!v) return "—";
  for (const [rx, label] of TIER) if (rx.test(v)) return label;
  return v;
}

export function consistencyLabel(value: unknown): string {
  const v = String(value ?? "").trim();
  if (!v) return "—";
  for (const [rx, label] of CONSISTENCY) if (rx.test(v)) return label || v;
  return v;
}

export function statusLabel(value: unknown): string {
  const v = String(value ?? "").trim();
  if (!v) return "—";
  return STATUS[v.toLowerCase()] ?? v;
}

/** True/False/"" → 是/否/— */
export function boolLabel(value: unknown): string {
  const v = String(value ?? "").trim().toLowerCase();
  if (v === "true") return "是";
  if (v === "false") return "否";
  return "—";
}

/** 方向：+/- 或 positive/negative → 正向/负向 */
export function directionLabel(value: unknown): string {
  const v = String(value ?? "").trim().toLowerCase();
  if (v === "+" || v === "positive" || v === "pos") return "正向";
  if (v === "-" || v === "negative" || v === "neg") return "负向";
  return v || "—";
}
