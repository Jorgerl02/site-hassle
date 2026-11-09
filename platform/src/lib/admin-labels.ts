// Admin labels and shape helpers (Spanish: the admin is internal). Not
// server-only, so the admin's client components can use them; `lib/admin`
// re-exports everything.
import type { PieceKind, PieceStatus } from "@/lib/database.types";
import { PIECE_KINDS, SUPPORT_ANSWERS, type RectilinearAnswer, type SupportAnswer } from "@/lib/validation";

export const KIND_LABEL: Record<PieceKind, string> = {
  mesa: "Mesa",
  mesita: "Mesita",
  aparador: "Aparador",
  estanteria: "Estantería",
  cabecero: "Cabecero",
  panel: "Panel",
  sofa: "Sofá",
  sillon: "Sillón",
  silla: "Silla",
  jarron: "Jarrón",
  lampara: "Lámpara",
  otro: "Otro",
};

// The admin stays in Spanish; the customer labels (English) live in `lib/pieces` and `lib/validation`.
export const STATUS_LABEL: Record<PieceStatus, string> = {
  queued: "En cola",
  generating: "Generando",
  review: "En revisión",
  ready: "Lista",
  approved: "Descargada",
  needs_photos: "Faltan fotos",
  rejected: "Rechazada",
  failed: "Error",
};

export const SUPPORT_LABEL: Record<SupportAnswer, string> = {
  patas: "Sobre patas",
  paneles: "Sobre paneles laterales",
  caja: "Es una caja o lleva zócalo",
  no_se: "No lo sé",
};

/** Shape fields the admin can fix before «Regenerar» / «Reintentar» (the customer may leave them as defaults). */
export interface ShapeValues {
  kind: PieceKind;
  /** `si` | `no` | `no_se`, as in the customer form. */
  rectilinear: RectilinearAnswer;
  support: SupportAnswer;
}

export const RECTILINEAR_CHOICES: readonly { value: RectilinearAnswer; label: string }[] = [
  { value: "si", label: "Sí, es recta" },
  { value: "no", label: "No (orgánica)" },
  { value: "no_se", label: "No se sabe" },
];

export function shapeValues(row: { kind: PieceKind; rectilinear: boolean | null; support: string | null }): ShapeValues {
  return {
    kind: row.kind,
    rectilinear: row.rectilinear === true ? "si" : row.rectilinear === false ? "no" : "no_se",
    support: SUPPORT_ANSWERS.includes(row.support as SupportAnswer) ? (row.support as SupportAnswer) : "no_se",
  };
}

/**
 * Piece columns from the admin's shape selects, or `{}` when the form has none
 * (nothing changes). Unknown values throw. As in the customer form, a piece
 * that is not straight has no support (`null`).
 */
export function parseShapeFields(formData: FormData): Partial<{ kind: PieceKind; rectilinear: boolean | null; support: SupportAnswer | null }> {
  const kind = formData.get("kind");
  const rectilinear = formData.get("rectilinear");
  const support = formData.get("support");
  if (kind === null && rectilinear === null && support === null) return {};
  if (!PIECE_KINDS.includes(kind as PieceKind)) throw new Error(`Tipo no válido: ${String(kind)}`);
  if (!RECTILINEAR_CHOICES.some((c) => c.value === rectilinear)) throw new Error(`Valor de «recta» no válido: ${String(rectilinear)}`);
  const supportValue = (support ?? "no_se") as SupportAnswer;
  if (!SUPPORT_ANSWERS.includes(supportValue)) throw new Error(`Apoyo no válido: ${String(support)}`);
  const straight = rectilinear === "si" ? true : rectilinear === "no" ? false : null;
  return { kind: kind as PieceKind, rectilinear: straight, support: straight === false ? null : supportValue };
}
