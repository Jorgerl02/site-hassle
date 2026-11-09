"use server";

import type { SupabaseClient } from "@supabase/supabase-js";
import { revalidatePath } from "next/cache";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import { dailyLimitMessage, isUuid, sqlErrorCode } from "@/lib/pieces";
import { createAdminClient } from "@/lib/supabase/admin";
import { createServerClient } from "@/lib/supabase/server";
import { TRIAL_IP_LIMIT_MESSAGE, TRIAL_IP_WINDOW_MS, clientIp, hashIp, trialIpLimit, type TrialIpStore } from "@/lib/trial-ip";
import { MAX_PHOTOS, validatePieceInput, type PieceField } from "@/lib/validation";

/** `trial_ips` through the service role (SQL functions; the table has no client policies). */
function trialIpStore(): TrialIpStore {
  const db = createAdminClient() as unknown as SupabaseClient;
  return {
    async claim(ipHash, limit) {
      const { data, error } = await db.rpc("claim_trial_slot", { p_ip_hash: ipHash, p_limit: limit });
      if (error) throw new Error(`claim_trial_slot: ${error.message}`);
      return typeof data === "number" ? data : null;
    },
    async release(id) {
      const { error } = await db.rpc("release_trial_slot", { p_id: id });
      if (error) throw new Error(`release_trial_slot: ${error.message}`);
    },
    async prune(beforeIso) {
      await db.from("trial_ips").delete().lt("created_at", beforeIso);
    },
  };
}

function ipSalt(): string {
  return process.env.IP_HASH_SALT?.trim() || process.env.WORKER_SHARED_SECRET?.trim() || process.env.SUPABASE_SERVICE_ROLE_KEY || "";
}

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
  if (!isUuid(id)) return { ok: false, message: "We couldn't create the piece. Reload the page and try again." };

  const supabase = await createServerClient();
  const folder = `${userId}/${id}`;
  const { data: objects, error: listError } = await supabase.storage
    .from("photos")
    .list(folder, { limit: 20, sortBy: { column: "name", order: "asc" } });
  if (listError) return { ok: false, message: "We couldn't check your photos. Please try again." };

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
    support: String(formData.get("support") ?? ""),
    notes: String(formData.get("notes") ?? ""),
    photos,
  });
  if (!result.ok) {
    return { ok: false, message: "Please check the highlighted fields.", errors: result.errors };
  }
  const piece = result.value;

  // Anonymous trials: also capped per network (hashed IP or IPv6 /64), on top of 1 a day per
  // user. The slot is taken atomically before the piece exists and given back if it fails.
  const anonymous = current.user.is_anonymous === true;
  const ip = anonymous ? clientIp(await headers()) : null;
  const store = trialIpStore();
  let slot: number | null = null;
  if (ip) {
    try {
      slot = await store.claim(hashIp(ip, ipSalt()), trialIpLimit());
      if (slot === null) return { ok: false, message: TRIAL_IP_LIMIT_MESSAGE };
    } catch (error) {
      // Never block a trial because the counter is down; the daily limit per user still applies.
      console.error("createPiece: trial IP slot failed", error);
    }
  }
  const releaseSlot = async () => {
    if (slot !== null) await store.release(slot).catch((error) => console.error("createPiece: release slot failed", error));
  };

  const { error: pieceError } = await supabase.from("pieces").insert({
    id,
    user_id: userId,
    name: piece.name,
    kind: piece.kind,
    width_cm: piece.widthCm,
    height_cm: piece.heightCm,
    depth_cm: piece.depthCm,
    rectilinear: piece.rectilinear,
    support: piece.support,

    notes: piece.notes,
    status: "queued",
  });
  if (pieceError) {
    await releaseSlot();
    if (sqlErrorCode(pieceError) === "daily_limit") {
      return { ok: false, message: dailyLimitMessage(current.user.is_anonymous === true) };
    }
    console.error("createPiece: insert piece failed", pieceError.message);
    return { ok: false, message: "We couldn't create the piece. Please try again in a few minutes." };
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
    await releaseSlot();
    return { ok: false, message: "We couldn't save your photos. Please try again." };
  }

  if (slot !== null) {
    await store.prune(new Date(Date.now() - 2 * TRIAL_IP_WINDOW_MS).toISOString()).catch(() => {});
  }

  revalidatePath("/panel");
  redirect(`/piezas/${id}`);
}
