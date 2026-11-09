import { describe, expect, it } from "vitest";
import { MAX_PHOTO_BYTES, looksExcluded, nameFromFileName, parseCm, validatePieceInput, type PieceInput } from "@/lib/validation";

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

  it("stores the support answer, «no_se» (Not sure) by default and none for organic pieces", () => {
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
    expect(ok(validatePieceInput(input({ rectilinear: "" })))).toBeNull();
    expect(ok(validatePieceInput(input({ rectilinear: "quizá" })))).toBe("error");
  });

  it("accepts the collapsed optional details untouched: kind otro, rectilinear and support unknown", () => {
    const result = validatePieceInput(input({ kind: "", rectilinear: "", support: "" }));
    expect(result).toMatchObject({ ok: true, value: { kind: "otro", rectilinear: null, support: "no_se" } });
    const missing = validatePieceInput(input({ kind: undefined, rectilinear: undefined, support: undefined }));
    expect(missing).toMatchObject({ ok: true, value: { kind: "otro", rectilinear: null, support: "no_se" } });
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
    if (!result.ok) expect(result.errors.depthCm).toBe("Enter a measurement between 1 and 400\u00a0cm.");
  });

  it("rejects a kind outside the enum", () => {
    const result = validatePieceInput(input({ kind: "trono" }));
    expect(result).toMatchObject({ ok: false, errors: { kind: "Choose the type of piece." } });
  });

  it("requires between 1 and 4 photos", () => {
    expect(validatePieceInput(input({ photos: [] }))).toMatchObject({
      ok: false,
      errors: { photos: "Add at least one photo." },
    });
    expect(validatePieceInput(input({ photos: [photo(), photo(), photo(), photo()] })).ok).toBe(true);
    expect(validatePieceInput(input({ photos: [photo(), photo(), photo(), photo(), photo()] }))).toMatchObject({
      ok: false,
      errors: { photos: "You can upload up to 4 photos." },
    });
  });

  it("rejects photos that are not JPEG, PNG or WebP", () => {
    for (const type of ["application/pdf", "image/heic", "image/gif", ""]) {
      const result = validatePieceInput(input({ photos: [photo({ name: "catalogo.pdf", type })] }));
      expect(result).toMatchObject({
        ok: false,
        errors: { photos: "“catalogo.pdf” isn’t a supported photo: use JPG, PNG or WebP." },
      });
    }
    for (const type of ["image/png", "image/webp"]) {
      expect(validatePieceInput(input({ photos: [photo({ type })] })).ok).toBe(true);
    }
  });

  it("rejects a 25 MB photo with an English message", () => {
    const result = validatePieceInput(input({ photos: [photo({ name: "grande.jpg", size: 25 * MB })] }));
    expect(result).toMatchObject({
      ok: false,
      errors: { photos: "“grande.jpg” is 25\u00a0MB; the limit is 20\u00a0MB." },
    });
    expect(validatePieceInput(input({ photos: [photo({ size: MAX_PHOTO_BYTES })] })).ok).toBe(true);
    expect(validatePieceInput(input({ photos: [photo({ size: MAX_PHOTO_BYTES + 1 })] })).ok).toBe(false);
  });

  it("rejects photos under 1,000 px on the long side when the size is known", () => {
    const result = validatePieceInput(input({ photos: [photo({ name: "mini.jpg", width: 800, height: 600 })] }));
    expect(result).toMatchObject({
      ok: false,
      errors: { photos: "“mini.jpg” is too small (800\u00a0px on the long side); we need at least 1,000\u00a0px." },
    });
    expect(validatePieceInput(input({ photos: [photo({ width: undefined, height: undefined })] })).ok).toBe(true);
  });

  it("limits notes to 500 characters", () => {
    expect(validatePieceInput(input({ notes: "x".repeat(500) })).ok).toBe(true);
    expect(validatePieceInput(input({ notes: "x".repeat(501) }))).toMatchObject({
      ok: false,
      errors: { notes: "Notes can be up to 500 characters." },
    });
  });

  it("reports every invalid field at once", () => {
    const result = validatePieceInput(input({ name: "", widthCm: "0", photos: [] }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(Object.keys(result.errors).sort()).toEqual(["name", "photos", "widthCm"]);
  });
});

describe("nameFromFileName", () => {
  it("turns the first photo's file name into an editable name", () => {
    expect(nameFromFileName("cabecero_rigole-02.JPG")).toBe("Cabecero rigole 02");
    expect(nameFromFileName("oak side table.webp")).toBe("Oak side table");
    expect(nameFromFileName(".jpg")).toBe("");
    expect(nameFromFileName(`${"x".repeat(100)}.png`)).toHaveLength(80);
  });
});

describe("looksExcluded", () => {
  it("warns on Spanish and English metal or glass words and on lamps", () => {
    expect(looksExcluded("otro", "Patas cromadas")).toBe(true);
    expect(looksExcluded("otro", "", "Glass coffee table")).toBe(true);
    expect(looksExcluded("otro", "brushed steel frame")).toBe(true);
    expect(looksExcluded("lampara", "")).toBe(true);
    expect(looksExcluded("mesa", "Solid oak")).toBe(false);
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
