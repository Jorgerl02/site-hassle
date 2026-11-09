import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  MATERIAL_OPTIONS,
  isMaterialChoice,
  noteWithMaterial,
  pickShape,
  pieceAnalysis,
} from "@/lib/admin-labels";

describe("pickShape (server actions accept any argument)", () => {
  it("keeps only kind / rectilinear / support", () => {
    expect(pickShape({ kind: "mesa", rectilinear: true, support: "patas", status: "ready", attempt: 1 })).toEqual({
      kind: "mesa",
      rectilinear: true,
      support: "patas",
    });
    expect(pickShape({ status: "ready" })).toEqual({});
    expect(pickShape(null)).toEqual({});
    expect(pickShape(["mesa"])).toEqual({});
    expect(pickShape({ rectilinear: null, support: null })).toEqual({ rectilinear: null, support: null });
  });

  it("rejects values outside the enums", () => {
    expect(() => pickShape({ kind: "trono" })).toThrow();
    expect(() => pickShape({ rectilinear: "si" })).toThrow();
    expect(() => pickShape({ support: "pie_central" })).toThrow();
  });
});

describe("«Aplicar material»", () => {
  it("mirrors the worker's materials.json", () => {
    const file = path.resolve(process.cwd(), "../src/harness/post/materials.json");
    const manifest = JSON.parse(readFileSync(file, "utf8")) as { materials: { id: string; label: { es: string } }[] };
    expect(MATERIAL_OPTIONS.map((m) => ({ id: m.id, label: m.label }))).toEqual(
      manifest.materials.map((m) => ({ id: m.id, label: m.label.es })),
    );
  });

  it("validates the choice", () => {
    expect(isMaterialChoice("oak")).toBe(true);
    expect(isMaterialChoice("none")).toBe(true);
    expect(isMaterialChoice("gold")).toBe(false);
    expect(isMaterialChoice("")).toBe(false);
  });

  it("writes the choice into the note as material:<id>, replacing an old one", () => {
    expect(noteWithMaterial("", "oak")).toBe("material:oak");
    expect(noteWithMaterial("Más cálido.", "travertine")).toBe("Más cálido.\nmaterial:travertine");
    expect(noteWithMaterial("Más cálido.\nmaterial:oak", "none")).toBe("Más cálido.\nmaterial:none");
    expect(noteWithMaterial("Más cálido. material:oak", null)).toBe("Más cálido.");
    expect(noteWithMaterial("Sin cambios", null)).toBe("Sin cambios");
  });
});

describe("pieceAnalysis", () => {
  const meta = {
    interpretation: {
      rectilinear: true,
      support: "pie_central",
      kind: "mesa",
      confidence: 0.82,
      support_confidence: 0.9,
      reasons: ["pedestal: top on one central column → buildable (parametric pedestal)"],
      effective: { kind: "mesa", rectilinear: true, support: "patas", routing_kind: "table", pedestal_params: null },
      source: { kind: "customer", rectilinear: "inferred", support: "customer" },
      conflict: [{ field: "support", customer: "patas", inferred: "pie_central", confidence: 0.9 }],
    },
    routing: { route: "E", kind: "pedestal", params: { base_diameter_ratio: 0.51, top_shape: "round" }, reasons: ["Ruta E"] },
    dimension_warnings: ["From the photo, the height looks closer to ~45 cm than 30 cm."],
    warnings: ["From the photo, the height looks closer to ~45 cm than 30 cm.", "GLB sin optimizar"],
    material: { id: "linen", source: "detected", applied: true },
    auto_review: { decision: "manual", gate: "rules", reasons: ["Conflicto en «support»"] },
  };

  it("summarises the interpretation, warnings and decision in Spanish", () => {
    const analysis = pieceAnalysis(meta)!;
    expect(analysis.answers).toEqual([
      { label: "Tipo", value: "Mesa", source: "cliente" },
      { label: "¿Recta?", value: "Sí", source: "foto" },
      { label: "Apoyo", value: "Sobre patas", source: "cliente" },
      { label: "Tipo paramétrico", value: "Pedestal (pie central), base 51 % del tablero", source: "ruta E" },
    ]);
    expect(analysis.confidence).toBe("82 %");
    expect(analysis.conflicts).toEqual(["Apoyo: el cliente dijo «Sobre patas» y la foto dice «Pie central» (90 %)"]);
    expect(analysis.dimensionWarnings).toHaveLength(1);
    expect(analysis.warnings).toEqual(["GLB sin optimizar"]);
    expect(analysis.material).toBe("Lino (detectado en el nombre o las notas), aplicado");
    expect(analysis.autoReview).toMatchObject({ decision: "Revisión manual", auto: false, gate: "reglas" });
  });

  it("is null for rows the worker wrote before the wiring", () => {
    expect(pieceAnalysis({ post: {} })).toBeNull();
    expect(pieceAnalysis(null)).toBeNull();
  });

  it("shows the judge's scores", () => {
    const analysis = pieceAnalysis({
      auto_review: { decision: "auto", gate: "vlm", reasons: ["Juez visual"], scores: { parecido: 5, geometria: 4, materiales: 4 } },
    })!;
    expect(analysis.autoReview).toMatchObject({ auto: true, gate: "juez visual", scores: "parecido 5 · geometría 4 · materiales 4" });
  });
});
