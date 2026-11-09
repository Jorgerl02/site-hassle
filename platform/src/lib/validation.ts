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

/** Answer to "Is it a straight piece…?" (values stay Spanish: they are stored and shared with the worker). */
export type RectilinearAnswer = "si" | "no" | "no_se";

/** Answer to "How does it stand?" (`pieces.support`). */
export type SupportAnswer = "patas" | "paneles" | "caja" | "no_se";
export const SUPPORT_ANSWERS: readonly SupportAnswer[] = ["patas", "paneles", "caja", "no_se"];

/**
 * Defaults of the optional details (collapsed in the form): an unknown kind,
 * "Not sure" for the straight-piece question and for the support. The admin
 * can correct them in the review screen before regenerating.
 */
export const DEFAULT_KIND: PieceKind = "otro";
export const DEFAULT_RECTILINEAR: RectilinearAnswer = "no_se";
export const DEFAULT_SUPPORT: SupportAnswer = "no_se";

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
  /** Missing or empty = `otro`. */
  kind?: string | null;
  widthCm: string | number;
  heightCm: string | number;
  depthCm: string | number;
  /** Missing or empty = "Not sure". */
  rectilinear?: string | null;
  /** Missing or empty = "Not sure". */
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
  /** Only for pieces that may be rectilinear; null when the piece is not ("No"). */
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

/** «45.5» or «45,5» → 45.5. Thousands separators are not accepted (null). */
export function parseCm(raw: string | number): number | null {
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : null;
  const text = raw.trim();
  if (!CM_RE.test(text)) return null;
  return Number(text.replace(",", "."));
}

const RECTILINEAR: Record<RectilinearAnswer, boolean | null> = { si: true, no: false, no_se: null };

function formatMb(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return Number.isInteger(mb) ? String(mb) : mb.toFixed(1);
}

function formatInt(n: number): string {
  return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function photoError(photo: PhotoMeta): string | null {
  if (!(PHOTO_TYPES as readonly string[]).includes(photo.type)) {
    return `“${photo.name}” isn’t a supported photo: use JPG, PNG or WebP.`;
  }
  if (photo.size > MAX_PHOTO_BYTES) {
    return `“${photo.name}” is ${formatMb(photo.size)} MB; the limit is ${formatMb(MAX_PHOTO_BYTES)} MB.`;
  }
  if (photo.width && photo.height) {
    const longSide = Math.max(photo.width, photo.height);
    if (longSide < MIN_LONG_SIDE_PX) {
      return `“${photo.name}” is too small (${formatInt(longSide)} px on the long side); we need at least ${formatInt(MIN_LONG_SIDE_PX)} px.`;
    }
  }
  return null;
}

/** Validates the new-piece form. Shared by the browser (before uploading) and the server action. */
export function validatePieceInput(input: PieceInput): ValidationResult {
  const errors: Partial<Record<PieceField, string>> = {};

  const name = input.name.trim().replace(/\s+/g, " ");
  if (name.length < NAME_MIN || name.length > NAME_MAX) {
    errors.name = `Enter a name between ${NAME_MIN} and ${NAME_MAX} characters.`;
  }

  const kind = ((input.kind ?? "").trim() || DEFAULT_KIND) as PieceKind;
  if (!PIECE_KINDS.includes(kind)) errors.kind = "Choose the type of piece.";

  const dims = {} as Record<"widthCm" | "heightCm" | "depthCm", number>;
  for (const field of ["widthCm", "heightCm", "depthCm"] as const) {
    const value = parseCm(input[field]);
    if (value === null || value < MIN_CM || value > MAX_CM) {
      errors[field] = `Enter a measurement between ${MIN_CM} and ${MAX_CM} cm.`;
    } else {
      dims[field] = value;
    }
  }

  const answer = ((input.rectilinear ?? "").trim() || DEFAULT_RECTILINEAR) as RectilinearAnswer;
  if (!Object.hasOwn(RECTILINEAR, answer)) errors.rectilinear = "Choose an answer.";

  const support = ((input.support ?? "").trim() || DEFAULT_SUPPORT) as SupportAnswer;
  if (!SUPPORT_ANSWERS.includes(support)) errors.support = "Choose an answer.";

  const notes = (input.notes ?? "").trim();
  if (notes.length > NOTES_MAX) errors.notes = `Notes can be up to ${NOTES_MAX} characters.`;

  if (input.photos.length === 0) {
    errors.photos = "Add at least one photo.";
  } else if (input.photos.length > MAX_PHOTOS) {
    errors.photos = `You can upload up to ${MAX_PHOTOS} photos.`;
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
      // An organic piece ("No") has no support to describe.
      support: answer === "no" ? null : support,
      notes: notes || null,
      photos: input.photos,
    },
  };
}

/**
 * Words (Spanish and English) that put a piece in an excluded category (metal,
 * chrome, glass); the worker uses the same stems (`EXCLUDED_STEMS` in intake.py).
 */
const EXCLUDED_RE = /(^|[^a-záéíóúñ])(metal|acero|inox|steel|stainless|crom|chrom|vidri|cristal|acristal|glass)/i;

/** True when the form shows the "we don't do metal or glass" warning. Non-blocking: the worker decides. */
export function looksExcluded(kind: string, notes: string, name = ""): boolean {
  if (kind === "lampara") return true;
  return EXCLUDED_RE.test(`${name} ${notes}`.normalize("NFD").replace(/[̀-ͯ]/g, ""));
}

/** Customer labels of the "Type" selector, in the order shown (the admin has its own, in Spanish). */
export const KIND_LABEL: Record<PieceKind, string> = {
  mesa: "Table",
  mesita: "Side or bedside table",
  aparador: "Sideboard or chest of drawers",
  estanteria: "Shelving unit",
  cabecero: "Headboard",
  panel: "Panel",
  sofa: "Sofa",
  sillon: "Armchair",
  silla: "Chair or stool",
  jarron: "Vase or ceramics",
  lampara: "Lamp",
  otro: "Other",
};

export const RECTILINEAR_OPTIONS: readonly { value: RectilinearAnswer; label: string }[] = [
  { value: "si", label: "Yes" },
  { value: "no", label: "No" },
  { value: "no_se", label: "Not sure" },
];

export const SUPPORT_OPTIONS: readonly { value: SupportAnswer; label: string }[] = [
  { value: "patas", label: "On legs" },
  { value: "paneles", label: "On side panels" },
  { value: "caja", label: "It's a box or has a plinth" },
  { value: "no_se", label: "Not sure" },
];

/**
 * Name suggested from a photo's file name: «cabecero_rigole-02.JPG» →
 * «Cabecero rigole 02». Empty when nothing readable is left.
 */
export function nameFromFileName(fileName: string): string {
  const stem = fileName
    .replace(/\.[a-z0-9]{2,5}$/i, "")
    .replace(/[_\-.+]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, NAME_MAX)
    .trim();
  return stem ? stem.charAt(0).toUpperCase() + stem.slice(1) : "";
}

/** Stored value → form answer (unknown or null → "Not sure"). */
export function supportAnswer(value: string | null | undefined): SupportAnswer {
  return SUPPORT_ANSWERS.includes(value as SupportAnswer) ? (value as SupportAnswer) : "no_se";
}

export function rectilinearAnswer(value: boolean | null | undefined): RectilinearAnswer {

  return value === true ? "si" : value === false ? "no" : "no_se";
}

