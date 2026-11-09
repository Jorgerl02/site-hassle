import { describe, expect, it } from "vitest";
import { PACKS, formatEur } from "@/lib/pricing";

describe("formatEur", () => {
  it("puts the symbol first and drops decimals for whole euros", () => {
    expect(formatEur(6900)).toBe("€69");
    expect(formatEur(900)).toBe("€9");
    expect(formatEur(16900)).toBe("€169");
  });

  it("uses a decimal point with two digits", () => {
    expect(formatEur(690)).toBe("€6.90");
    expect(formatEur(563)).toBe("€5.63");
    expect(formatEur(5)).toBe("€0.05");
  });

  it("groups thousands with a comma", () => {
    expect(formatEur(100000)).toBe("€1,000");
    expect(formatEur(123456789)).toBe("€1,234,567.89");
  });

  it("formats negative amounts", () => {
    expect(formatEur(-690)).toBe("-€6.90");
  });
});

describe("PACKS", () => {
  it("lists the three credit packs in order", () => {
    expect(PACKS.map((p) => p.id)).toEqual(["pieza_1", "pieza_10", "pieza_30"]);
    expect(PACKS.map((p) => p.priceCents)).toEqual([900, 6900, 16900]);
    expect(PACKS.map((p) => p.credits)).toEqual([1, 10, 30]);
  });

  it("highlights the middle pack only", () => {
    expect(PACKS[1].highlighted).toBe(true);
    expect(PACKS.filter((p) => p.highlighted)).toHaveLength(1);
  });

  it("derives the per-piece price from the pack price", () => {
    expect(PACKS.map((p) => p.perPieceCents)).toEqual([900, 690, 563]);
    expect(formatEur(PACKS[2].perPieceCents)).toBe("€5.63");
  });
});
