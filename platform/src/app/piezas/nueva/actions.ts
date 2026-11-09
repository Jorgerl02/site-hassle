"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import { DAILY_LIMIT_MESSAGE, isUuid, sqlErrorCode } from "@/lib/pieces";
import { createAdminClient } from "@/lib/supabase/admin";
import { createServerClient } from "@/lib/supabase/server";
import { MAX_PHOTOS, validatePieceInput, type PieceField } from "@/lib/validation";

export type CreatePieceResult = { ok: false; message: string; errors?: Partial<Record<PieceField, string>> };

const PHOTO_NAME_RE = /^(\d+)\.(jpg|png|webp)$/;

/**
 * Creates the piece after the browser has uploaded its photos to
 * `photos/{user_id}/{id}/{n}.{ext}` (the id is generated in the browser).
 * The uploaded objects are the source of truth for the photos: the action
 * lists the folder, validates them with the form fields, then inserts the
 * piece and its photo rows back to back so the worker finds them together.
 * Redirects to the piece page on success.
 */
export async function createPiece(formData: FormData): Promise<CreatePieceResult> {
  const current = await getCurrentUser();
  if (!current) redirect("/entrar");
  const userId = current.user.id;

  const id = formData.get("id");
  if (!isUuid(id)) return { ok: false, message: "No hemos podido crear la pieza. Recarga la página y vuelve a intentarlo." };

  const supabase = await createServerClient();
  const folder = `${userId}/${id}`;
  const { data: objects, error: listError } = await supabase.storage
    .from("photos")
    .list(folder, { limit: 20, sortBy: { column: "name", order: "asc" } });
  if (listError) return { ok: false, message: "No hemos podido comprobar las fotos. Vuelve a intentarlo." };

  const photos = (objects ?? [])
    .map((o) => ({ object: o, match: PHOTO_NAME_RE.exec(o.name) }))
    .filter((p) => p.match !== null)
    .sort((a, b) => Number(a.match![1]) - Number(b.match![1]))
    .slice(0, MAX_PHOTOS + 1)
    .map(({ object }) => {
      const meta = (object.metadata ?? {}) as { mimetype?: string; size?: number };
      return { name: object.name, type: meta.mimetype ?? "", size: meta.size ?? 0 };
    });

  const result = validatePieceInput({
    name: String(formData.get("name") ?? ""),
    kind: String(formData.get("kind") ?? ""),
    widthCm: String(formData.get("widthCm") ?? ""),
    heightCm: String(formData.get("heightCm") ?? ""),
    depthCm: String(formData.get("depthCm") ?? ""),
    rectilinear: String(formData.get("rectilinear") ?? ""),
    notes: String(formData.get("notes") ?? ""),
    photos,
  });
  if (!result.ok) {
    return { ok: false, message: "Revisa los campos marcados.", errors: result.errors };
  }
  const piece = result.value;

  const { error: pieceError } = await supabase.from("pieces").insert({
    id,
    user_id: userId,
    name: piece.name,
    kind: piece.kind,
    width_cm: piece.widthCm,
    height_cm: piece.heightCm,
    depth_cm: piece.depthCm,
    rectilinear: piece.rectilinear,
    notes: piece.notes,
    status: "queued",
  });
  if (pieceError) {
    if (sqlErrorCode(pieceError) === "daily_limit") return { ok: false, message: DAILY_LIMIT_MESSAGE };
    console.error("createPiece: insert piece failed", pieceError.message);
    return { ok: false, message: "No hemos podido crear la pieza. Vuelve a intentarlo en unos minutos." };
  }

  const { error: photosError } = await supabase.from("piece_photos").insert(
    piece.photos.map((photo, i) => ({ piece_id: id, storage_path: `${folder}/${photo.name}`, position: i + 1 })),
  );
  if (photosError) {
    // Without its photo rows the worker would wait 10 min for nothing: undo the
    // piece (clients cannot delete pieces, hence the service role) and let the
    // browser clean its uploads and retry.
    console.error("createPiece: insert piece_photos failed", photosError.message);
    const { error: undoError } = await createAdminClient().from("pieces").delete().eq("id", id).eq("user_id", userId);
    if (undoError) console.error("createPiece: undo piece failed", undoError.message);
    return { ok: false, message: "No hemos podido guardar las fotos. Vuelve a intentarlo." };
  }

  revalidatePath("/panel");
  redirect(`/piezas/${id}`);
}
