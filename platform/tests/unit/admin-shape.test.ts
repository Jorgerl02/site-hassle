import { describe, expect, it } from "vitest";
import { parseShapeFields, shapeValues } from "@/lib/admin-labels";

function form(fields: Record<string, string>): FormData {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) data.set(key, value);
  return data;
}

describe("parseShapeFields", () => {
  it("returns nothing to change when the form has no shape selects", () => {
    expect(parseShapeFields(form({ note: "x" }))).toEqual({});
  });

  it("maps the selects to piece columns", () => {
    expect(parseShapeFields(form({ kind: "aparador", rectilinear: "si", support: "patas" }))).toEqual({
      kind: "aparador",
      rectilinear: true,
      support: "patas",
    });
    expect(parseShapeFields(form({ kind: "otro", rectilinear: "no_se", support: "no_se" }))).toEqual({
      kind: "otro",
      rectilinear: null,
      support: "no_se",
    });
  });

  it("drops the support of a piece that is not straight (its select is disabled)", () => {
    expect(parseShapeFields(form({ kind: "sofa", rectilinear: "no" }))).toEqual({
      kind: "sofa",
      rectilinear: false,
      support: null,
    });
  });

  it("rejects values outside the enums", () => {
    expect(() => parseShapeFields(form({ kind: "trono", rectilinear: "si", support: "patas" }))).toThrow();
    expect(() => parseShapeFields(form({ kind: "mesa", rectilinear: "quizá", support: "patas" }))).toThrow();
    expect(() => parseShapeFields(form({ kind: "mesa", rectilinear: "si", support: "flotando" }))).toThrow();
  });
});

describe("shapeValues", () => {
  it("turns the stored columns into select values", () => {
    expect(shapeValues({ kind: "mesa", rectilinear: true, support: "paneles" })).toEqual({
      kind: "mesa",
      rectilinear: "si",
      support: "paneles",
    });
    expect(shapeValues({ kind: "otro", rectilinear: null, support: null })).toEqual({
      kind: "otro",
      rectilinear: "no_se",
      support: "no_se",
    });
  });
});
