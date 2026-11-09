import "server-only";
import type { PostgrestError } from "@supabase/supabase-js";
import { notFound } from "next/navigation";
import type { Piece, PieceModel, PieceStatus } from "@/lib/database.types";
import { DAILY_PIECE_LIMIT } from "@/lib/pricing";
import { createAdminClient } from "@/lib/supabase/admin";
import { supabaseUrl } from "@/lib/supabase/env";
import { createServerClient } from "@/lib/supabase/server";

/** Signed URLs (renders, downloads) last one hour. */
export const SIGNED_URL_SECONDS = 60 * 60;

/** Customer-facing label for each status. */
export const PIECE_STATUS_LABEL: Record<PieceStatus, string> = {
  queued: "En cola",
  generating: "Generando",
  review: "En revisión",
  ready: "Lista",
  approved: "Descargada",
  needs_photos: "Faltan fotos",
  rejected: "Rechazada",
  failed: "Error",
};

/** Statuses where nothing changes without the customer (or an admin): no polling. */
export const SETTLED_STATUSES: readonly PieceStatus[] = ["ready", "approved", "rejected", "needs_photos", "failed"];

/** Statuses where the client may read the current attempt's models (RLS mirrors this). */
export const MODEL_STATUSES: readonly PieceStatus[] = ["ready", "approved", "rejected"];

export const DAILY_LIMIT_MESSAGE = `Has llegado a las ${DAILY_PIECE_LIMIT} piezas de hoy. Mañana podrás crear más.`;

/**
 * Columns the customer may read: exactly the column-level SELECT grant of
 * `authenticated` (migration 20261109000007). `review_note`, `route`,
 * `claimed_at`, `provider_cost_usd` and `not_before` are not granted, so a
 * `select *` with the user's session fails. `error` is shown only in
 * `needs_photos` (in `failed` the customer sees a fixed message).
 */
const PIECE_COLUMNS =
  "id, user_id, name, kind, width_cm, height_cm, depth_cm, rectilinear, support, notes, status, attempt, error, reject_reason, created_at, updated_at";

/** Customer copy for `failed`: the technical detail stays in `pieces.error` for the admin. */
export const FAILED_MESSAGE = "No hemos podido generar esta pieza. Lo revisamos y te escribimos.";

export type CustomerPiece = Pick<
  Piece,
  | "id"
  | "user_id"
  | "name"
  | "kind"
  | "width_cm"
  | "height_cm"
  | "depth_cm"
  | "rectilinear"
  | "support"
  | "notes"
  | "status"
  | "attempt"
  | "error"
  | "reject_reason"
  | "created_at"
  | "updated_at"
>;

export const RENDER_VIEWS = ["front", "left", "back", "three_quarter", "contact"] as const;
export type RenderView = (typeof RENDER_VIEWS)[number];

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

/** Error code raised by our SQL functions (`daily_limit`, `insufficient_credits`…), if any. */
export function sqlErrorCode(error: Pick<PostgrestError, "message"> | null | undefined): string | null {
  if (!error) return null;
  const match = /^(daily_limit|insufficient_credits|invalid_state|max_versions|not_found|forbidden|not_authenticated)\b/.exec(
    error.message ?? "",
  );
  return match ? match[1] : null;
}

/** The piece if it belongs to the signed-in user, else null (RLS hides other users' rows). */
export async function findPieceForUser(id: string): Promise<CustomerPiece | null> {
  if (!isUuid(id)) return null;
  const supabase = await createServerClient();
  const { data, error } = await supabase.from("pieces").select(PIECE_COLUMNS).eq("id", id).maybeSingle();
  if (error) throw new Error(`pieces select failed: ${error.message}`);
  return (data as CustomerPiece | null) ?? null;
}

/** The piece if it belongs to the signed-in user; otherwise the 404 page. */
export async function getPieceForUser(id: string): Promise<CustomerPiece> {
  const piece = await findPieceForUser(id);
  if (!piece) notFound();
  return piece;
}

/** `piece_models` columns granted to `authenticated` (never `meta`, `cost_usd`, `provider`). */
const MODEL_COLUMNS = "id, piece_id, attempt, preview_path, glb_path, usdz_path, render_paths, selected, created_at";

export type CustomerModel = Pick<
  PieceModel,
  "id" | "piece_id" | "attempt" | "preview_path" | "glb_path" | "usdz_path" | "render_paths" | "selected" | "created_at"
>;

/** Selected model (`selected = true`) of the current attempt, once the piece has been shown to the customer. */
export async function getSelectedModel(piece: CustomerPiece): Promise<CustomerModel | null> {
  if (!MODEL_STATUSES.includes(piece.status)) return null;
  const supabase = await createServerClient();
  const { data } = await supabase
    .from("piece_models")
    .select(MODEL_COLUMNS)
    .eq("piece_id", piece.id)
    .eq("attempt", piece.attempt)
    .eq("selected", true)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  return data;
}

function encodePath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}

/** Public URL of the free preview GLB (bucket `previews` is public). */
export function previewUrl(model: Pick<PieceModel, "preview_path"> | null): string | null {
  if (!model?.preview_path) return null;
  return `${supabaseUrl()}/storage/v1/object/public/previews/${encodePath(model.preview_path)}`;
}

/** Signed URLs (1 h) of the renders. Call only after checking the piece is the user's. */
export async function signedRenderUrls(
  model: Pick<PieceModel, "render_paths"> | null,
): Promise<Partial<Record<RenderView, string>>> {
  const raw = model?.render_paths;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const entries = RENDER_VIEWS.flatMap((view) => {
    const path = (raw as Record<string, unknown>)[view];
    return typeof path === "string" && path ? [[view, path] as const] : [];
  });
  if (entries.length === 0) return {};
  const { data } = await createAdminClient()
    .storage.from("renders")
    .createSignedUrls(
      entries.map(([, path]) => path),
      SIGNED_URL_SECONDS,
    );
  const urls: Partial<Record<RenderView, string>> = {};
  entries.forEach(([view], i) => {
    const signed = data?.[i]?.signedUrl;
    if (signed) urls[view] = signed;
  });
  return urls;
}

export interface DownloadUrls {
  glb: string;
  usdz: string;
}

function fileStem(name: string): string {
  const stem = name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return stem || "pieza";
}

/**
 * Signed download URLs (1 h) of the paid files. Only for an `approved` piece
 * the caller has already loaded through the user's session (ownership by RLS).
 */
export async function signedModelUrls(piece: CustomerPiece, model: CustomerModel | null): Promise<DownloadUrls | null> {

  if (piece.status !== "approved" || !model?.glb_path || !model.usdz_path) return null;
  const bucket = createAdminClient().storage.from("models");
  const stem = fileStem(piece.name);
  const [glb, usdz] = await Promise.all([
    bucket.createSignedUrl(model.glb_path, SIGNED_URL_SECONDS, { download: `${stem}.glb` }),
    bucket.createSignedUrl(model.usdz_path, SIGNED_URL_SECONDS, { download: `${stem}.usdz` }),
  ]);
  if (!glb.data || !usdz.data) return null;
  return { glb: glb.data.signedUrl, usdz: usdz.data.signedUrl };
}

/** Credit balance of the signed-in user (null if the call fails). */
export async function getBalance(userId: string): Promise<number | null> {
  const supabase = await createServerClient();
  const { data, error } = await supabase.rpc("credit_balance", { p_user: userId });
  return error || typeof data !== "number" ? null : data;
}

/** Thumbnail written by the form next to the photos (best effort). */
export function thumbPath(userId: string, pieceId: string): string {
  return `${userId}/${pieceId}/thumb.jpg`;
}

/** Signed thumbnail URLs (own photos, via the user's session) keyed by piece id. */
export async function signedThumbUrls(userId: string, pieceIds: string[]): Promise<Record<string, string>> {
  if (pieceIds.length === 0) return {};
  const supabase = await createServerClient();
  const { data } = await supabase.storage.from("photos").createSignedUrls(
    pieceIds.map((id) => thumbPath(userId, id)),
    SIGNED_URL_SECONDS,
  );
  const urls: Record<string, string> = {};
  data?.forEach((item, i) => {
    if (item.signedUrl && !item.error) urls[pieceIds[i]] = item.signedUrl;
  });
  return urls;
}

export type StepState = "done" | "current" | "upcoming";
export interface StatusStep {
  key: "queued" | "generating" | "review" | "ready";
  label: string;
  hint: string;
  state: StepState;
}

const STEPS: readonly Omit<StatusStep, "state">[] = [
  { key: "queued", label: "En cola", hint: "Tu pieza espera turno." },
  { key: "generating", label: "Generando", hint: "Creamos el modelo y lo ajustamos a tus medidas." },
  { key: "review", label: "En revisión", hint: "Lo revisamos antes de enseñártelo." },
  { key: "ready", label: "Lista", hint: "Ya puedes verla en 3D y en tu casa." },
];

/** Progress steps for the pieces on the happy path; null for needs_photos, rejected and failed. */
export function statusSteps(status: PieceStatus): StatusStep[] | null {
  const order = ["queued", "generating", "review", "ready"];
  const index = status === "approved" ? order.length : order.indexOf(status);
  if (index < 0) return null;
  return STEPS.map((step, i) => ({
    ...step,
    state: i < index || (i === index && status === "ready") ? "done" : i === index ? "current" : "upcoming",
  }));
}
