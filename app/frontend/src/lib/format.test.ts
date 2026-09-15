import { describe, expect, it } from "vitest";
import { effectGlyph, formatNumber, isMissing, missingLabel } from "./format";

describe("scientific formatting (display only)", () => {
  it("formats numbers and keeps raw semantics", () => {
    expect(formatNumber("0.032")).toBe("0.032");
    expect(formatNumber("0.00123456")).toBe("0.00123");
    expect(formatNumber("0.0000012")).toContain("×10");
    expect(formatNumber("1e7")).toContain("×10");
    expect(formatNumber("1234")).toBe("1,234");
  });
  it("never turns missing into 0", () => {
    expect(isMissing("NA")).toBe(true);
    expect(isMissing("NaN")).toBe(true);
    expect(isMissing(null)).toBe(true);
    expect(missingLabel()).toBe("—");
    expect(formatNumber("NA")).toBe("—");
  });
  it("adds direction only to clearly directed effect columns", () => {
    const g = effectGlyph("+0.032");
    expect(g?.arrow).toBe("↑");
    expect(effectGlyph("-0.006")?.arrow).toBe("↓");
    expect(effectGlyph("0")).toBeNull();
    expect(effectGlyph("NA")).toBeNull();
  });
});
