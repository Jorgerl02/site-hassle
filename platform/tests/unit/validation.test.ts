import { describe, expect, it } from "vitest";
import { MAX_PHOTO_BYTES, parseCm, validatePieceInput, type PieceInput } from "@/lib/validation";

const MB = 1024 * 1024;

function photo(over: Partial<PieceInput["photos"][number]> = {}) {
  return { name: "frente.jpg", type: "image/jpeg", size: 2 * MB, width: 2000, height: 2667, ...over };
}

function input(over: Partial<PieceInput> = {}): PieceInput {
  return {
    name: "Cabecero Rigole",
    kind: "cabecero",
    widthCm: "165",
    heightCm: "60",
    depthCm: "6",
    rectilinear: "si",
    notes: "",
    photos: [photo()],
    ...over,
  };
}

describe("validatePieceInput", () => {
  it("accepts a valid piece and normalises it", () => {
    const result = validatePieceInput(input({ name: "  Cabecero Rigole ", widthCm: "165,5", notes: "  " }));
    expect(result).toEqual({
      ok: true,
      value: {
        name: "Cabecero Rigole",
        kind: "cabecero",
        widthCm: 165.5,
        heightCm: 60,
        depthCm: 6,
        rectilinear: true,
        support: "no_se",
        notes: null,
        photos: [photo()],
      },
    });
  });

  it("stores the support answer, «No lo sé» by default and none for organic pieces", () => {
    const support = (r: ReturnType<typeof validatePieceInput>) => (r.ok ? r.value.support : "error");
    for (const answer of ["patas", "paneles", "caja", "no_se"] as const) {
      expect(support(validatePieceInput(input({ support: answer })))).toBe(answer);
    }
    expect(support(validatePieceInput(input({ support: "" })))).toBe("no_se");
    expect(support(validatePieceInput(input({ support: undefined })))).toBe("no_se");
    expect(support(validatePieceInput(input({ rectilinear: "no", support: "patas" })))).toBeNull();
    expect(validatePieceInput(input({ support: "flotando" }))).toMatchObject({
      ok: false,
      errors: { support: expect.any(String) },
    });
  });


  it("maps the straight-piece answer to true, false or null", () => {
    const ok = (r: ReturnType<typeof validatePieceInput>) => (r.ok ? r.value.rectilinear : "error");
    expect(ok(validatePieceInput(input({ rectilinear: "si" })))).toBe(true);
    expect(ok(validatePieceInput(input({ rectilinear: "no" })))).toBe(false);
    expect(ok(validatePieceInput(input({ rectilinear: "no_se" })))).toBeNull();
    expect(ok(validatePieceInput(input({ rectilinear: "" })))).toBe("error");
  });

  it("checks the name length (2–80)", () => {
    expect(validatePieceInput(input({ name: "A" }))).toMatchObject({ ok: false, errors: { name: expect.any(String) } });
    expect(validatePieceInput(input({ name: "Ab" })).ok).toBe(true);
    expect(validatePieceInput(input({ name: "x".repeat(80) })).ok).toBe(true);
    expect(validatePieceInput(input({ name: "x".repeat(81) })).ok).toBe(false);
  });

  it.each([
    ["1", true],
    ["400", true],
    ["0,5", false],
    ["0.99", false],
    ["400,1", false],
    ["401", false],
    ["0", false],
    ["-3", false],
    ["", false],
    ["abc", false],
    ["12cm", false],
  ])("measure %s → valid %s", (value, valid) => {
    const result = validatePieceInput(input({ depthCm: value }));
    expect(result.ok).toBe(valid);
    if (!result.ok) expect(result.errors.depthCm).toBe("Escribe una medida entre 1 y 400 cm.");
  });

  it("rejects a kind outside the enum", () => {
    const result = validatePieceInput(input({ kind: "trono" }));
    expect(result).toMatchObject({ ok: false, errors: { kind: "Elige el tipo de pieza." } });
  });

  it("requires between 1 and 4 photos", () => {
    expect(validatePieceInput(input({ photos: [] }))).toMatchObject({
      ok: false,
      errors: { photos: "Añade al menos una foto." },
    });
    expect(validatePieceInput(input({ photos: [photo(), photo(), photo(), photo()] })).ok).toBe(true);
    expect(validatePieceInput(input({ photos: [photo(), photo(), photo(), photo(), photo()] }))).toMatchObject({
      ok: false,
      errors: { photos: "Puedes subir 4 fotos como máximo." },
    });
  });

  it("rejects photos that are not JPEG, PNG or WebP", () => {
    for (const type of ["application/pdf", "image/heic", "image/gif", ""]) {
      const result = validatePieceInput(input({ photos: [photo({ name: "catalogo.pdf", type })] }));
      expect(result).toMatchObject({
        ok: false,
        errors: { photos: "«catalogo.pdf» no es una foto válida: usa JPG, PNG o WebP." },
      });
    }
    for (const type of ["image/png", "image/webp"]) {
      expect(validatePieceInput(input({ photos: [photo({ type })] })).ok).toBe(true);
    }
  });

  it("rejects a 25 MB photo with a Spanish message", () => {
    const result = validatePieceInput(input({ photos: [photo({ name: "grande.jpg", size: 25 * MB })] }));
    expect(result).toMatchObject({
      ok: false,
      errors: { photos: "«grande.jpg» pesa 25 MB; el máximo es 20 MB." },
    });
    expect(validatePieceInput(input({ photos: [photo({ size: MAX_PHOTO_BYTES })] })).ok).toBe(true);
    expect(validatePieceInput(input({ photos: [photo({ size: MAX_PHOTO_BYTES + 1 })] })).ok).toBe(false);
  });

  it("rejects photos under 1.000 px on the long side when the size is known", () => {
    const result = validatePieceInput(input({ photos: [photo({ name: "mini.jpg", width: 800, height: 600 })] }));
    expect(result).toMatchObject({
      ok: false,
      errors: { photos: "«mini.jpg» es pequeña (800 px de lado mayor); necesitamos al menos 1.000 px." },
    });
    expect(validatePieceInput(input({ photos: [photo({ width: undefined, height: undefined })] })).ok).toBe(true);
  });

  it("limits notes to 500 characters", () => {
    expect(validatePieceInput(input({ notes: "x".repeat(500) })).ok).toBe(true);
    expect(validatePieceInput(input({ notes: "x".repeat(501) }))).toMatchObject({
      ok: false,
      errors: { notes: "Las notas admiten 500 caracteres como máximo." },
    });
  });

  it("reports every invalid field at once", () => {
    const result = validatePieceInput(input({ name: "", widthCm: "0", photos: [] }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(Object.keys(result.errors).sort()).toEqual(["name", "photos", "widthCm"]);
  });
});

describe("parseCm", () => {
  it("accepts decimal comma or point", () => {
    expect(parseCm("45,5")).toBe(45.5);
    expect(parseCm(" 45.5 ")).toBe(45.5);
    expect(parseCm(12)).toBe(12);
    expect(parseCm("1.000")).toBeNull();
    expect(parseCm("")).toBeNull();
  });
});
