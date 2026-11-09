"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { after } from "next/server";
import { notifyPieceReady } from "@/lib/notify";
import { MAX_ATTEMPT, NOT_DELIVERABLE_MESSAGE, adminDb, isDeliverable, isUuid, requireAdmin } from "@/lib/admin";
const MAX_TEXT = 2000;

export interface ReviewActionResult {
  ok: boolean;
  message?: string;
}

class ReviewError extends Error {}

function cleanText(value: unknown): string {
  return typeof value === "string" ? value.trim().slice(0, MAX_TEXT) : "";
}

/** Reads the piece and makes sure it is still waiting for review. */
async function loadReviewPiece(pieceId: string): Promise<{ id: string; attempt: number }> {
  if (!isUuid(pieceId)) throw new ReviewError("La pieza no existe.");
  const { data, error } = await adminDb()
    .from("pieces")
    .select("id, status, attempt")
    .eq("id", pieceId)
    .maybeSingle();
  if (error) throw new ReviewError(`No se pudo leer la pieza: ${error.message}`);
  if (!data) throw new ReviewError("La pieza no existe.");
  if (data.status !== "review") throw new ReviewError("Esta pieza ya no está en revisión.");
  return { id: data.id as string, attempt: data.attempt as number };
}

/**
 * Updates a piece only if it is still `review` (and on the expected attempt),
 * so two admins acting at once cannot both win.
 */
async function updateReviewPiece(pieceId: string, attempt: number, fields: Record<string, unknown>) {
  const { data, error } = await adminDb()
    .from("pieces")
    .update(fields)
    .eq("id", pieceId)
    .eq("status", "review")
    .eq("attempt", attempt)
    .select("id");
  if (error) throw new ReviewError(`No se pudo guardar: ${error.message}`);
  if (!data || data.length === 0) throw new ReviewError("Esta pieza ya no está en revisión.");
}

/** Marks `modelId` as the candidate the customer will see; unmarks the rest of its attempt. */
export async function markSelectedModel(pieceId: string, modelId: string): Promise<void> {
  await requireAdmin();
  const piece = await loadReviewPiece(pieceId);
  if (!isUuid(modelId)) throw new ReviewError("Elige un modelo.");
  const db = adminDb();
  const { data: model, error } = await db
    .from("piece_models")
    .select("id, attempt, preview_path, glb_path, usdz_path, meta")
    .eq("id", modelId)
    .eq("piece_id", piece.id)
    .maybeSingle();
  if (error) throw new ReviewError(`No se pudo leer el modelo: ${error.message}`);
  if (!model || model.attempt !== piece.attempt) throw new ReviewError("Ese modelo no es de este intento.");
  if (!isDeliverable(model)) throw new ReviewError(NOT_DELIVERABLE_MESSAGE);

  // TODO: two updates are not atomic. Replace with a partial unique index on
  // piece_models (piece_id, attempt) where selected, or a single SQL function
  // that switches the selection in one statement (Task 1 schema).
  // Paths stay as stored (a non-selected candidate keeps its `cand_n/` paths).
  const unset = await db
    .from("piece_models")
    .update({ selected: false })
    .eq("piece_id", piece.id)
    .eq("attempt", piece.attempt)
    .neq("id", modelId);
  if (unset.error) throw new ReviewError(`No se pudo cambiar el modelo: ${unset.error.message}`);
  const set = await db.from("piece_models").update({ selected: true }).eq("id", modelId);
  if (set.error) throw new ReviewError(`No se pudo cambiar el modelo: ${set.error.message}`);
}

/** «Mostrar al cliente»: `review → ready`, optionally switching the selected candidate first. */
export async function showToClient(pieceId: string, modelId?: string): Promise<void> {
  await requireAdmin();
  const piece = await loadReviewPiece(pieceId);
  if (modelId) await markSelectedModel(pieceId, modelId);
  // Re-read: exactly one deliverable candidate of this attempt must be selected.
  const { data: selected, error } = await adminDb()
    .from("piece_models")
    .select("id, preview_path, glb_path, usdz_path, meta")
    .eq("piece_id", piece.id)
    .eq("attempt", piece.attempt)
    .eq("selected", true);
  if (error) throw new Error(`No se pudo comprobar el modelo elegido: ${error.message}`);
  if (!selected || selected.length === 0) throw new ReviewError("Elige el modelo que verá el cliente.");
  if (selected.length > 1) {
    throw new Error(`Pieza ${piece.id}: ${selected.length} modelos marcados como elegidos en el intento ${piece.attempt}`);
  }
  if (!isDeliverable(selected[0])) throw new ReviewError(NOT_DELIVERABLE_MESSAGE);
  await updateReviewPiece(piece.id, piece.attempt, { status: "ready", review_note: null, reject_reason: null });
  // Customer email after the response; never throws (no-op without RESEND_API_KEY).
  after(() => notifyPieceReady(piece.id));
}

/** «Regenerar»: back to the queue with the next attempt and an internal note. */
export async function regenerate(pieceId: string, note: string): Promise<void> {
  await requireAdmin();
  const piece = await loadReviewPiece(pieceId);
  if (piece.attempt >= MAX_ATTEMPT) {
    throw new ReviewError("Esta pieza ya va por el tercer intento: muéstrala o recházala.");
  }
  await updateReviewPiece(piece.id, piece.attempt, {
    status: "queued",
    attempt: piece.attempt + 1,
    review_note: cleanText(note) || null,
    claimed_at: null,
    error: null,
  });
}

/** «Rechazar»: `review → rejected` with a reason the customer will read. */
export async function rejectInternally(pieceId: string, reason: string): Promise<void> {
  await requireAdmin();
  const text = cleanText(reason);
  if (!text) throw new ReviewError("Escribe el motivo: lo verá el cliente.");
  const piece = await loadReviewPiece(pieceId);
  await updateReviewPiece(piece.id, piece.attempt, { status: "rejected", reject_reason: text });
}

/** Form entry point for the detail screen (`useActionState`). */
export async function submitReview(_prev: ReviewActionResult, formData: FormData): Promise<ReviewActionResult> {
  await requireAdmin();
  const intent = formData.get("intent");
  const pieceId = cleanText(formData.get("pieceId"));
  const modelId = cleanText(formData.get("modelId"));
  const text = cleanText(formData.get("note"));
  try {
    if (intent === "show") await showToClient(pieceId, modelId || undefined);
    else if (intent === "regenerate") await regenerate(pieceId, text);
    else if (intent === "reject") await rejectInternally(pieceId, text);
    else return { ok: false, message: "Acción desconocida." };
  } catch (error) {
    if (error instanceof ReviewError) return { ok: false, message: error.message };
    throw error;
  }
  revalidatePath("/admin/revision");
  redirect("/admin/revision");
}
