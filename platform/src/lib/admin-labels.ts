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

type ShapeFields = ReturnType<typeof parseShapeFields>;

/**
 * Only the three shape columns, validated, from whatever reached a server
 * action (server actions are callable with any argument): `status`, `attempt`
 * or any other column can never ride along into the UPDATE.
 */
export function pickShape(shape: unknown): ShapeFields {
  if (!shape || typeof shape !== "object" || Array.isArray(shape)) return {};
  const source = shape as Record<string, unknown>;
  const out: ShapeFields = {};
  if ("kind" in source) {
    if (!PIECE_KINDS.includes(source.kind as PieceKind)) throw new Error(`Tipo no válido: ${String(source.kind)}`);
    out.kind = source.kind as PieceKind;
  }
  if ("rectilinear" in source) {
    if (source.rectilinear !== null && typeof source.rectilinear !== "boolean") {
      throw new Error(`Valor de «recta» no válido: ${String(source.rectilinear)}`);
    }
    out.rectilinear = source.rectilinear as boolean | null;
  }
  if ("support" in source) {
    if (source.support !== null && !SUPPORT_ANSWERS.includes(source.support as SupportAnswer)) {
      throw new Error(`Apoyo no válido: ${String(source.support)}`);
    }
    out.support = source.support as SupportAnswer | null;
  }
  return out;
}

// ---------- Library materials («Aplicar material») ----------

/**
 * Same ids and Spanish labels as `src/harness/post/materials.json` (a unit test
 * keeps them in sync). The admin's choice travels in `pieces.review_note` as
 * `material:<id>`; the worker reads the last such token on the next attempt.
 */
export const MATERIAL_OPTIONS = [
  { id: "travertine", label: "Travertino" },
  { id: "white_marble", label: "Mármol blanco" },
  { id: "oak", label: "Roble claro" },
  { id: "walnut", label: "Nogal" },
  { id: "white_plaster", label: "Lacado o yeso blanco" },
  { id: "boucle", label: "Bouclé / lana" },
  { id: "linen", label: "Lino" },
  { id: "leather", label: "Piel" },
] as const;
export type MaterialId = (typeof MATERIAL_OPTIONS)[number]["id"];
/** Turns the automatic material detection off (keeps the mesh's own texture). */
export const MATERIAL_NONE = "none";
export type MaterialChoice = MaterialId | typeof MATERIAL_NONE;

export const MATERIAL_LABEL: Record<string, string> = {
  ...Object.fromEntries(MATERIAL_OPTIONS.map((m) => [m.id, m.label])),
  [MATERIAL_NONE]: "Sin material (textura original)",
};

export function isMaterialChoice(value: unknown): value is MaterialChoice {
  return value === MATERIAL_NONE || MATERIAL_OPTIONS.some((m) => m.id === value);
}

const MATERIAL_TOKEN = /(^|\s)material:[a-z_]+\b/g;

/** The admin's note with any old `material:<id>` removed and the new choice appended (or the note alone). */
export function noteWithMaterial(note: string, material: MaterialChoice | null): string {
  const text = note.replace(MATERIAL_TOKEN, " ").replace(/[ \t]+\n/g, "\n").trim();
  if (!material) return text;
  return text ? `${text}\nmaterial:${material}` : `material:${material}`;
}

// ---------- What the worker decided (piece_models.meta) ----------

const percentFormat = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0 });

/** 0.82 → «82 %» (non-breaking space). */
export function confidenceLabel(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${percentFormat.format(value * 100)} %` : "—";
}

export const SOURCE_LABEL: Record<string, string> = {
  customer: "cliente",
  inferred: "foto",
  default: "por defecto",
};

export const ROUTING_KIND_LABEL: Record<string, string> = {
  table: "Mesa con patas",
  panel_table: "Paneles laterales",
  box: "Caja",
  box_legs: "Caja con patas o zócalo",
  pedestal: "Pedestal (pie central)",
};

const FIELD_LABEL: Record<string, string> = { kind: "Tipo", rectilinear: "¿Recta?", support: "Apoyo" };

function answerLabel(field: string, value: unknown): string {
  if (field === "rectilinear") return value === true ? "Sí" : value === false ? "No" : "No se sabe";
  if (field === "support") {
    if (value === "pie_central") return "Pie central";
    return SUPPORT_LABEL[value as SupportAnswer] ?? String(value ?? "—");
  }
  if (field === "kind") return KIND_LABEL[value as PieceKind] ?? String(value ?? "—");
  return String(value ?? "—");
}

export interface AnalysisAnswer {
  label: string;
  value: string;
  source: string;
}

export interface PieceAnalysis {
  /** Effective answers with where each came from (cliente / foto / por defecto). */
  answers: AnalysisAnswer[];
  /** Confidence of the photo reading (rectilinear) and of its support reading. */
  confidence: string;
  supportConfidence: string;
  /** The interpreter's reasons (English, technical). */
  reasons: string[];
  conflicts: string[];
  /** Customer-facing (English) dimension warnings. */
  dimensionWarnings: string[];
  /** Every other warning (spec, delivery, material). */
  warnings: string[];
  routeReasons: string[];
  material: string | null;
  autoReview: { decision: string; auto: boolean; gate: string; reasons: string[]; scores: string | null } | null;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

const MATERIAL_SOURCE_LABEL: Record<string, string> = {
  admin: "elegido por el admin",
  detected: "detectado en el nombre o las notas",
  admin_off: "desactivado por el admin",
};

/** The worker's interpretation, routing, warnings, material and auto-review of a model row, for the admin. */
export function pieceAnalysis(metaValue: unknown): PieceAnalysis | null {
  const meta = record(metaValue);
  const interp = record(meta.interpretation);
  const autoReview = record(meta.auto_review);
  if (!Object.keys(interp).length && !Object.keys(autoReview).length) return null;

  const effective = record(interp.effective);
  const source = record(interp.source);
  const answers: AnalysisAnswer[] = (["kind", "rectilinear", "support"] as const).map((field) => ({
    label: FIELD_LABEL[field],
    value: answerLabel(field, effective[field]),
    source: SOURCE_LABEL[String(source[field])] ?? "—",
  }));
  const routing = record(meta.routing);
  const routingKind = typeof routing.kind === "string" ? routing.kind : (effective.routing_kind as string | null);
  if (routingKind) {
    const params = record(routing.params ?? effective.pedestal_params);
    const ratio = typeof params.base_diameter_ratio === "number" ? `, base ${confidenceLabel(params.base_diameter_ratio)} del tablero` : "";
    answers.push({ label: "Tipo paramétrico", value: `${ROUTING_KIND_LABEL[routingKind] ?? routingKind}${ratio}`, source: "ruta E" });
  }

  const conflicts = (Array.isArray(interp.conflict) ? interp.conflict : []).map((raw) => {
    const c = record(raw);
    const field = String(c.field);
    return `${FIELD_LABEL[field] ?? field}: el cliente dijo «${answerLabel(field, c.customer)}» y la foto dice «${answerLabel(field, c.inferred)}» (${confidenceLabel(c.confidence)})`;
  });

  const dimensionWarnings = strings(meta.dimension_warnings);
  const warnings = strings(meta.warnings).filter((w) => !dimensionWarnings.includes(w));

  const material = record(meta.material);
  let materialText: string | null = null;
  if (typeof material.id === "string") {
    const state = material.applied === true ? "aplicado" : material.applied === false ? "no aplicado" : "previsto";
    materialText = `${MATERIAL_LABEL[material.id] ?? material.id} (${MATERIAL_SOURCE_LABEL[String(material.source)] ?? "—"}), ${state}`;
  } else if (material.source === "admin_off") {
    materialText = "Ninguno (desactivado por el admin)";
  }

  let review: PieceAnalysis["autoReview"] = null;
  if (Object.keys(autoReview).length) {
    const scores = record(autoReview.scores);
    const auto = autoReview.decision === "auto";
    review = {
      decision: auto ? "Publicada automáticamente" : "Revisión manual",
      auto,
      gate: autoReview.gate === "vlm" ? "juez visual" : "reglas",
      reasons: strings(autoReview.reasons),
      scores: Object.keys(scores).length
        ? `parecido ${scores.parecido ?? "—"} · geometría ${scores.geometria ?? "—"} · materiales ${scores.materiales ?? "—"}`
        : null,
    };
  }

  return {
    answers,
    confidence: confidenceLabel(interp.confidence),
    supportConfidence: confidenceLabel(interp.support_confidence),
    reasons: strings(interp.reasons),
    conflicts,
    dimensionWarnings,
    warnings,
    routeReasons: strings(routing.reasons),
    material: materialText,
    autoReview: review,
  };
}

/** The worker published this model's attempt by itself (`meta.auto_review.decision === "auto"`). */
export function isAutoPublished(metaValue: unknown): boolean {
  return record(record(metaValue).auto_review).decision === "auto";
}
