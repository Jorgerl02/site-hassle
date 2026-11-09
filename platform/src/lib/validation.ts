import { Constants, type PieceKind } from "@/lib/database.types";

/** Same limits as the `photos` bucket (Task 1) and the worker validator. */
export const MAX_PHOTOS = 4;
export const MAX_PHOTO_BYTES = 20 * 1024 * 1024;
export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
/** `MIN_LONG_SIDE_PX` in `src/harness/prep/clean.py`. */
export const MIN_LONG_SIDE_PX = 1000;
export const MIN_CM = 1;
export const MAX_CM = 400;
export const NAME_MIN = 2;
export const NAME_MAX = 80;
export const NOTES_MAX = 500;

export const PIECE_KINDS: readonly PieceKind[] = Constants.public.Enums.piece_kind;

/** Answer to «¿Es una pieza recta…?». */
export type RectilinearAnswer = "si" | "no" | "no_se";

/** Answer to «¿Cómo se apoya la pieza?» (`pieces.support`). */
export type SupportAnswer = "patas" | "paneles" | "caja" | "no_se";
export const SUPPORT_ANSWERS: readonly SupportAnswer[] = ["patas", "paneles", "caja", "no_se"];

export interface PhotoMeta {
  name: string;
  type: string;
  size: number;
  /** Pixel size when known (decoded in the browser); skipped on the server. */
  width?: number;
  height?: number;
}

export interface PieceInput {
  name: string;
  kind: string;
  widthCm: string | number;
  heightCm: string | number;
  depthCm: string | number;
  rectilinear: string;
  /** Missing or empty = «No lo sé». */
  support?: string | null;
  notes?: string | null;
  photos: PhotoMeta[];
}

export interface PieceValue {
  name: string;
  kind: PieceKind;
  widthCm: number;
  heightCm: number;
  depthCm: number;
  rectilinear: boolean | null;
  /** Only for pieces that may be rectilinear; null when the piece is not («No»). */
  support: SupportAnswer | null;
  notes: string | null;
  photos: PhotoMeta[];
}

export type PieceField =
  | "name"
  | "kind"
  | "widthCm"
  | "heightCm"
  | "depthCm"
  | "rectilinear"
  | "support"
  | "notes"
  | "photos";

export type ValidationResult =
  | { ok: true; value: PieceValue }
  | { ok: false; errors: Partial<Record<PieceField, string>> };

const CM_RE = /^\d{1,4}(?:[.,]\d{1,2})?$/;

/** «45,5» or «45.5» → 45.5. Thousands separators are not accepted (null). */
export function parseCm(raw: string | number): number | null {
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  const text = raw.trim();
  if (!CM_RE.test(text)) return null;
  return Number(text.replace(",", "."));
}

const RECTILINEAR: Record<RectilinearAnswer, boolean | null> = { si: true, no: false, no_se: null };

function formatMb(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return (Number.isInteger(mb) ? String(mb) : mb.toFixed(1)).replace(".", ",");
}

function formatInt(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function photoError(photo: PhotoMeta): string | null {
  if (!(PHOTO_TYPES as readonly string[]).includes(photo.type)) {
    return `«${photo.name}» no es una foto válida: usa JPG, PNG o WebP.`;
  }
  if (photo.size > MAX_PHOTO_BYTES) {
    return `«${photo.name}» pesa ${formatMb(photo.size)} MB; el máximo es ${formatMb(MAX_PHOTO_BYTES)} MB.`;
  }
  if (photo.width && photo.height) {
    const longSide = Math.max(photo.width, photo.height);
    if (longSide < MIN_LONG_SIDE_PX) {
      return `«${photo.name}» es pequeña (${formatInt(longSide)} px de lado mayor); necesitamos al menos ${formatInt(MIN_LONG_SIDE_PX)} px.`;
    }
  }
  return null;
}

/** Validates the new-piece form. Shared by the browser (before uploading) and the server action. */
export function validatePieceInput(input: PieceInput): ValidationResult {
  const errors: Partial<Record<PieceField, string>> = {};

  const name = input.name.trim().replace(/\s+/g, " ");
  if (name.length < NAME_MIN || name.length > NAME_MAX) {
    errors.name = `Escribe un nombre de ${NAME_MIN} a ${NAME_MAX} caracteres.`;
  }

  const kind = input.kind as PieceKind;
  if (!PIECE_KINDS.includes(kind)) errors.kind = "Elige el tipo de pieza.";

  const dims = {} as Record<"widthCm" | "heightCm" | "depthCm", number>;
  for (const field of ["widthCm", "heightCm", "depthCm"] as const) {
    const value = parseCm(input[field]);
    if (value === null || value < MIN_CM || value > MAX_CM) {
      errors[field] = `Escribe una medida entre ${MIN_CM} y ${MAX_CM} cm.`;
    } else {
      dims[field] = value;
    }
  }

  const answer = input.rectilinear as RectilinearAnswer;
  if (!(answer in RECTILINEAR)) errors.rectilinear = "Elige una respuesta.";

  const supportRaw = (input.support ?? "").trim() || "no_se";
  const support = supportRaw as SupportAnswer;
  if (!SUPPORT_ANSWERS.includes(support)) errors.support = "Elige una respuesta.";

  const notes = (input.notes ?? "").trim();
  if (notes.length > NOTES_MAX) errors.notes = `Las notas admiten ${NOTES_MAX} caracteres como máximo.`;

  if (input.photos.length === 0) {
    errors.photos = "Añade al menos una foto.";
  } else if (input.photos.length > MAX_PHOTOS) {
    errors.photos = `Puedes subir ${MAX_PHOTOS} fotos como máximo.`;
  } else {
    const first = input.photos.map(photoError).find(Boolean);
    if (first) errors.photos = first;
  }

  if (Object.keys(errors).length > 0) return { ok: false, errors };
  return {
    ok: true,
    value: {
      name,
      kind,
      ...dims,
      rectilinear: RECTILINEAR[answer],
      // An organic piece («No») has no support to describe.
      support: answer === "no" ? null : support,
      notes: notes || null,
      photos: input.photos,
    },
  };
}

/** Words that put a piece in an excluded category (metal, glass); the worker uses the same stems. */
const EXCLUDED_RE = /(^|[^a-záéíóúñ])(metal|acero|inox|crom|vidri|cristal|acristal)/i;

/** True when the form shows the «no hacemos metal ni vidrio» warning. Non-blocking: the worker decides. */
export function looksExcluded(kind: string, notes: string, name = ""): boolean {
  if (kind === "lampara") return true;
  return EXCLUDED_RE.test(`${name} ${notes}`.normalize("NFD").replace(/[̀-ͯ]/g, ""));
}

/** Labels of the «Tipo» selector, in the order shown. */
export const KIND_LABEL: Record<PieceKind, string> = {
  mesa: "Mesa",
  mesita: "Mesita o mesa auxiliar",
  aparador: "Aparador o cómoda",
  estanteria: "Estantería",
  cabecero: "Cabecero",
  panel: "Panel",
  sofa: "Sofá",
  sillon: "Sillón o butaca",
  silla: "Silla o taburete",
  jarron: "Jarrón o cerámica",
  lampara: "Lámpara",
  otro: "Otro",
};

export const RECTILINEAR_OPTIONS: readonly { value: RectilinearAnswer; label: string }[] = [
  { value: "si", label: "Sí" },
  { value: "no", label: "No" },
  { value: "no_se", label: "No sé" },
];

export const SUPPORT_OPTIONS: readonly { value: SupportAnswer; label: string }[] = [
  { value: "patas", label: "Sobre patas" },
  { value: "paneles", label: "Sobre paneles laterales" },
  { value: "caja", label: "Es una caja o lleva zócalo" },
  { value: "no_se", label: "No lo sé" },
];

export const SUPPORT_LABEL: Record<SupportAnswer, string> = {
  patas: "Sobre patas",
  paneles: "Sobre paneles laterales",
  caja: "Es una caja o lleva zócalo",
  no_se: "No lo sé",
};

/** Stored value → form answer (unknown or null → «No lo sé»). */
export function supportAnswer(value: string | null | undefined): SupportAnswer {
  return SUPPORT_ANSWERS.includes(value as SupportAnswer) ? (value as SupportAnswer) : "no_se";
}

export function rectilinearAnswer(value: boolean | null | undefined): RectilinearAnswer {

  return value === true ? "si" : value === false ? "no" : "no_se";
}

