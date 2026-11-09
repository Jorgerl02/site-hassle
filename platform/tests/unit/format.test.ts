import { describe, expect, it } from "vitest";
import { formatCm, formatDimensions } from "@/lib/format";

describe("formatCm", () => {
  it("uses a decimal point and drops trailing zeros", () => {
    expect(formatCm(48.5)).toBe("48.5");
    expect(formatCm(50)).toBe("50");
    expect(formatCm(6.25)).toBe("6.25");
  });

  it("groups thousands with a comma", () => {
    expect(formatCm(1000)).toBe("1,000");
    expect(formatCm(1234.5)).toBe("1,234.5");
  });
});

describe("formatDimensions", () => {
  it("joins width × height × depth with a non-breaking space before cm", () => {
    expect(formatDimensions(35, 50, 35)).toBe("35 × 50 × 35\u00a0cm");
    expect(formatDimensions(50, 48.5, 50)).toBe("50 × 48.5 × 50\u00a0cm");
  });
});
