import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { notFound } from "next/navigation";
import { getCurrentUser, type CurrentUser } from "@/lib/auth";
import type { Json, PieceKind, PieceStatus } from "@/lib/database.types";
import { createAdminClient } from "@/lib/supabase/admin";
import { KIND_LABEL, SUPPORT_LABEL, shapeValues, type ShapeValues } from "@/lib/admin-labels";
import type { SupportAnswer } from "@/lib/validation";

export * from "@/lib/admin-labels";


/** Signed URLs for the review screens live one hour. */
export const SIGNED_URL_SECONDS = 60 * 60;

/** Scale error above which a candidate is flagged (the promise is ±3 % per axis). */
export const SCALE_ERROR_LIMIT = 0.03;

/** `pieces.attempt` is limited to 1..3 by the schema. */
export const MAX_ATTEMPT = 3;

export const NOT_DELIVERABLE_MESSAGE = "Este candidato no tiene archivos descargables.";


/**
 * A candidate can be shown to the customer only if the paid download will work:
 * preview, GLB and USDZ present and no generation error.
 */
export function isDeliverable(row: {
  preview_path: string | null;
  glb_path: string | null;
  usdz_path: string | null;
  meta: Json | null;
}): boolean {
  const meta = asMeta(row.meta);
  return Boolean(row.preview_path && row.glb_path && row.usdz_path) && !meta.error;
}

/** Render views shown per candidate, in display order. */
export const RENDER_VIEWS = ["front", "left", "back", "three_quarter"] as const;
export type RenderView = (typeof RENDER_VIEWS)[number];

export const RENDER_VIEW_LABEL: Record<RenderView, string> = {
  front: "Frente",
  left: "Lateral",
  back: "Detrás",
  three_quarter: "Tres cuartos",
};


export const AXIS_LABEL: Record<string, string> = { width: "Ancho", height: "Alto", depth: "Fondo" };


/**
 * Admin gate for pages and server actions: anyone who is not an admin
 * (signed out included) gets a 404, so the route does not reveal it exists.
 */
export async function requireAdmin(): Promise<CurrentUser> {
  const current = await getCurrentUser();
  if (current?.profile?.is_admin !== true) notFound();
  return current;
}

/**
 * Service-role client for admin reads and writes. Untyped on purpose: the web's
 * `database.types.ts` stub does not cover `piece_models`, `piece_photos` or the
 * `admin_review_queue` view yet, so rows are narrowed by the types below.
 */
export function adminDb(): SupabaseClient {
  return createAdminClient() as unknown as SupabaseClient;
}

// ---------- Formatting (Spanish typography) ----------

const decimal1 = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const signedDecimal1 = new Intl.NumberFormat("es-ES", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});
const integer = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 0, useGrouping: "always" });
const cm = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, useGrouping: "always" });

/** Fraction → «2,4 %» (non-breaking space before %). */
export function formatPercent(fraction: number | null | undefined, signed = false): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return "—";
  const value = Math.abs(fraction * 100) < 0.05 ? 0 : fraction * 100;
  return `${(signed ? signedDecimal1 : decimal1).format(value)} %`;
}

/** «120 × 45 × 75,5 cm». */
export function formatDimensions(width: number, height: number, depth: number): string {
  return `${[width, height, depth].map((v) => cm.format(Number(v))).join(" × ")} cm`;
}

/** Minutes since `iso` → «3 min», «2 h 05 min», «1.440 min» stays readable as hours/days. */
export function formatWaiting(iso: string, now: number = Date.now()): string {
  const minutes = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${integer.format(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${integer.format(hours)} h ${String(minutes % 60).padStart(2, "0")} min`;
  return `${integer.format(Math.floor(hours / 24))} días`;
}

export function minutesWaiting(iso: string, now: number = Date.now()): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
}

// ---------- Rows ----------

type RenderPaths = Partial<Record<RenderView | "contact", string>>;

interface ModelMeta {
  post?: {
    errors?: Record<string, number>;
    errors_before_fit?: Record<string, number>;
    fit_box_applied?: boolean;
  } | null;
  route?: string;
  error?: string;
}

interface QueueRow {
  id: string;
  name: string;
  kind: PieceKind;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  attempt: number;
  updated_at: string;
  created_at: string;
  user_email: string | null;
  provider: string | null;
  max_error: number | null;
  render_paths: Json | null;
}

interface PieceRow {
  id: string;
  name: string;
  kind: PieceKind;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  rectilinear: boolean | null;
  support: string | null;
  notes: string | null;
  status: PieceStatus;
  attempt: number;
  route: string | null;
  review_note: string | null;
  updated_at: string;
  user_id: string;
}

interface ModelRow {
  id: string;
  attempt: number;
  provider: string | null;
  candidate: number;
  preview_path: string | null;
  glb_path: string | null;
  usdz_path: string | null;
  render_paths: Json | null;
  meta: Json | null;
  max_error: number | null;
  cost_usd: number | null;
  selected: boolean;
}

function asRenderPaths(value: Json | null): RenderPaths {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as RenderPaths) : {};
}

function asMeta(value: Json | null): ModelMeta {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as ModelMeta) : {};
}

/** Signs many paths of one bucket in a single request; missing paths map to nothing. */
async function signMany(db: SupabaseClient, bucket: string, paths: string[]): Promise<Map<string, string>> {
  const unique = [...new Set(paths.filter(Boolean))];
  const out = new Map<string, string>();
  if (unique.length === 0) return out;
  const { data, error } = await db.storage.from(bucket).createSignedUrls(unique, SIGNED_URL_SECONDS);
  if (error || !data) return out;
  for (const item of data) {
    if (item.path && item.signedUrl && !item.error) out.set(item.path, item.signedUrl);
  }
  return out;
}

// ---------- Queue ----------

export interface QueueItem {
  id: string;
  name: string;
  kindLabel: string;
  dimensions: string;
  attempt: number;
  provider: string;
  maxError: string;
  maxErrorHigh: boolean;
  waiting: string;
  waitingMinutes: number;
  email: string | null;
  contactUrl: string | null;
}

/** Pieces in `review`, oldest in review first, with a signed contact sheet. */
export async function listReviewQueue(): Promise<QueueItem[]> {
  const db = adminDb();
  const { data, error } = await db
    .from("admin_review_queue")
    .select("id, name, kind, width_cm, height_cm, depth_cm, attempt, updated_at, created_at, user_email, provider, max_error, render_paths")
    .order("updated_at", { ascending: true })
    .order("created_at", { ascending: true });
  if (error) throw new Error(`No se pudo leer la cola de revisión: ${error.message}`);
  const rows = (data ?? []) as QueueRow[];
  const contacts = await signMany(
    db,
    "renders",
    rows.map((r) => asRenderPaths(r.render_paths).contact ?? ""),
  );
  const now = Date.now();
  return rows.map((r) => {
    const contact = asRenderPaths(r.render_paths).contact;
    const maxError = r.max_error === null ? null : Number(r.max_error);
    return {
      id: r.id,
      name: r.name,
      kindLabel: KIND_LABEL[r.kind] ?? r.kind,
      dimensions: formatDimensions(r.width_cm, r.height_cm, r.depth_cm),
      attempt: r.attempt,
      provider: r.provider ?? "—",
      maxError: formatPercent(maxError),
      maxErrorHigh: maxError !== null && maxError > SCALE_ERROR_LIMIT,
      waiting: formatWaiting(r.updated_at, now),
      waitingMinutes: minutesWaiting(r.updated_at, now),
      email: r.user_email,
      contactUrl: contact ? (contacts.get(contact) ?? null) : null,
    };
  });
}

// ---------- Failed pieces ----------

export interface FailedItem {
  id: string;
  name: string;
  kindLabel: string;
  dimensions: string;
  attempt: number;
  route: string | null;
  /** Technical detail written by the worker (never shown to the customer). */
  error: string | null;
  email: string | null;
  waiting: string;
  shape: ShapeValues;
}

interface FailedRow {
  id: string;
  name: string;
  kind: PieceKind;
  width_cm: number;
  height_cm: number;
  depth_cm: number;
  attempt: number;
  route: string | null;
  error: string | null;
  rectilinear: boolean | null;
  support: string | null;
  updated_at: string;
  profiles: { email: string | null } | null;
}

/** Pieces in `failed`, oldest failure first, with the worker's technical error. */
export async function listFailedPieces(): Promise<FailedItem[]> {
  const { data, error } = await adminDb()
    .from("pieces")
    .select("id, name, kind, width_cm, height_cm, depth_cm, attempt, route, error, rectilinear, support, updated_at, profiles(email)")
    .eq("status", "failed")
    .order("updated_at", { ascending: true });
  if (error) throw new Error(`No se pudieron leer las piezas fallidas: ${error.message}`);
  const now = Date.now();
  return ((data ?? []) as unknown as FailedRow[]).map((r) => ({
    id: r.id,
    name: r.name,
    kindLabel: KIND_LABEL[r.kind] ?? r.kind,
    dimensions: formatDimensions(r.width_cm, r.height_cm, r.depth_cm),
    attempt: r.attempt,
    route: r.route,
    error: r.error,
    email: r.profiles?.email ?? null,
    waiting: formatWaiting(r.updated_at, now),
    shape: shapeValues(r),
  }));
}

// ---------- Detail ----------

export interface AxisError {
  axis: string;
  label: string;
  value: string;
  high: boolean;
  beforeFit: string | null;
}

export interface CandidateView {
  id: string;
  candidate: number;
  provider: string;
  selected: boolean;
  maxError: string;
  maxErrorHigh: boolean;
  costUsd: string | null;
  fitBoxApplied: boolean;
  axisErrors: AxisError[];
  renders: { view: RenderView; label: string; url: string | null }[];
  contactUrl: string | null;
  modelUrl: string | null;
  error: string | null;
  /** Preview, GLB and USDZ present and no error: may be shown to the customer. */
  deliverable: boolean;
}

export interface ReviewDetail {
  id: string;
  name: string;
  kindLabel: string;
  dimensions: string;
  status: PieceStatus;
  attempt: number;
  route: string | null;
  notes: string | null;
  rectilinear: boolean | null;
  /** Customer's «¿Cómo se apoya la pieza?» answer, as a label (null when not asked). */
  supportLabel: string | null;
  /** Current shape answers, for the editable selects. */
  shape: ShapeValues;
  reviewNote: string | null;
  email: string | null;
  waiting: string;
  photos: { url: string; position: number }[];
  candidates: CandidateView[];
}

const usd = new Intl.NumberFormat("es-ES", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

function axisErrors(meta: ModelMeta): AxisError[] {
  const errors = meta.post?.errors ?? {};
  const before = meta.post?.errors_before_fit ?? {};
  const fitted = meta.post?.fit_box_applied === true;
  return ["width", "height", "depth"]
    .filter((axis) => typeof errors[axis] === "number")
    .map((axis) => ({
      axis,
      label: AXIS_LABEL[axis] ?? axis,
      value: formatPercent(errors[axis], true),
      high: Math.abs(errors[axis]) > SCALE_ERROR_LIMIT,
      beforeFit: fitted && typeof before[axis] === "number" ? formatPercent(before[axis], true) : null,
    }));
}

/** Everything the detail screen needs, or null when the piece does not exist. */
export async function getReviewDetail(pieceId: string): Promise<ReviewDetail | null> {
  if (!isUuid(pieceId)) return null;
  const db = adminDb();
  const { data: pieceData, error: pieceError } = await db
    .from("pieces")
    .select(
      "id, name, kind, width_cm, height_cm, depth_cm, rectilinear, support, notes, status, attempt, route, review_note, updated_at, user_id",
    )
    .eq("id", pieceId)
    .maybeSingle();
  if (pieceError) throw new Error(`No se pudo leer la pieza: ${pieceError.message}`);
  if (!pieceData) return null;
  const piece = pieceData as PieceRow;

  const [photoRes, modelRes, profileRes] = await Promise.all([
    db.from("piece_photos").select("storage_path, position").eq("piece_id", piece.id).order("position"),
    db
      .from("piece_models")
      .select("id, attempt, provider, candidate, preview_path, glb_path, usdz_path, render_paths, meta, max_error, cost_usd, selected")
      .eq("piece_id", piece.id)
      .eq("attempt", piece.attempt)
      .order("candidate"),
    db.from("profiles").select("email").eq("id", piece.user_id).maybeSingle(),
  ]);
  for (const [label, res] of [
    ["las fotos", photoRes],
    ["los modelos", modelRes],
    ["el perfil", profileRes],
  ] as const) {
    if (res.error) throw new Error(`No se pudo leer ${label}: ${res.error.message}`);
  }
  const profile = profileRes.data;
  const photos = (photoRes.data ?? []) as { storage_path: string; position: number }[];
  const models = (modelRes.data ?? []) as ModelRow[];

  const renderPaths = models.flatMap((m) => Object.values(asRenderPaths(m.render_paths)).filter(Boolean) as string[]);
  // A candidate without a preview falls back to its signed full GLB.
  const glbPaths = models.filter((m) => !m.preview_path && m.glb_path).map((m) => m.glb_path as string);
  const [photoUrls, renderUrls, glbUrls] = await Promise.all([
    signMany(db, "photos", photos.map((p) => p.storage_path)),
    signMany(db, "renders", renderPaths),
    signMany(db, "models", glbPaths),
  ]);

  const candidates: CandidateView[] = models.map((m) => {
    const paths = asRenderPaths(m.render_paths);
    const meta = asMeta(m.meta);
    const maxError = m.max_error === null ? null : Number(m.max_error);
    const modelUrl = m.preview_path
      ? db.storage.from("previews").getPublicUrl(m.preview_path).data.publicUrl
      : m.glb_path
        ? (glbUrls.get(m.glb_path) ?? null)
        : null;
    return {
      id: m.id,
      candidate: m.candidate,
      provider: m.provider ?? "—",
      selected: m.selected,
      maxError: formatPercent(maxError),
      maxErrorHigh: maxError !== null && maxError > SCALE_ERROR_LIMIT,
      costUsd: m.cost_usd === null ? null : usd.format(Number(m.cost_usd)),
      fitBoxApplied: meta.post?.fit_box_applied === true,
      axisErrors: axisErrors(meta),
      renders: RENDER_VIEWS.map((view) => ({
        view,
        label: RENDER_VIEW_LABEL[view],
        url: paths[view] ? (renderUrls.get(paths[view] as string) ?? null) : null,
      })),
      contactUrl: paths.contact ? (renderUrls.get(paths.contact) ?? null) : null,
      modelUrl,
      error: typeof meta.error === "string" ? meta.error : null,
      deliverable: isDeliverable(m),
    };
  });

  return {
    id: piece.id,
    name: piece.name,
    kindLabel: KIND_LABEL[piece.kind] ?? piece.kind,
    dimensions: formatDimensions(piece.width_cm, piece.height_cm, piece.depth_cm),
    status: piece.status,
    attempt: piece.attempt,
    route: piece.route,
    notes: piece.notes,
    rectilinear: piece.rectilinear,
    supportLabel: piece.support ? (SUPPORT_LABEL[piece.support as SupportAnswer] ?? piece.support) : null,
    shape: shapeValues(piece),
    reviewNote: piece.review_note,
    email: (profile as { email: string | null } | null)?.email ?? null,
    waiting: formatWaiting(piece.updated_at),
    photos: photos.flatMap((p) => {
      const url = photoUrls.get(p.storage_path);
      return url ? [{ url, position: p.position }] : [];
    }),
    candidates,
  };
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}
