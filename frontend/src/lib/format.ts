// 仅用于展示的科学数值格式化; 绝不回写/重算。原始值保留在单元格 title 中。
export function isMissing(v: string | null | undefined): boolean {
  if (v == null) return true;
  const s = v.trim();
  return s === "" || ["NA", "NaN", "nan", "null", "None", "-", "—"].includes(s);
}

export function missingLabel(): string {
  return "—";
}

export function formatNumber(raw: string): string {
  const s = raw.trim();
  if (isMissing(s)) return missingLabel();
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  const a = Math.abs(n);
  if (a !== 0 && (a >= 1e6 || a < 1e-4)) {
    return n.toExponential(2).replace("e+", "×10^").replace("e-", "×10^-");
  }
  if (Number.isInteger(n) && a < 1e15) return n.toLocaleString("en-US");
  return String(Math.round(n * 100000) / 100000);
}

// 有明确方向的量 (ΔR²/ΔMAE/ΔRMSE/coefficient/effect…) 才允许箭头/颜色
export function effectGlyph(raw: string): { arrow: string; cls: string } | null {
  const s = raw.trim();
  if (isMissing(s)) return null;
  const n = Number(s);
  if (!Number.isFinite(n) || n === 0) return null;
  if (n > 0) return { arrow: "↑", cls: "text-emerald-600" };
  return { arrow: "↓", cls: "text-rose-600" };
}
