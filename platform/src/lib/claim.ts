import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { CLAIM_COOKIE, CLAIM_MAX_AGE_SECONDS, signClaim, verifyClaim } from "@/lib/claim-token";
import { createAdminClient } from "@/lib/supabase/admin";

/** HMAC key of the claim cookie: `CLAIM_SECRET`, else the service-role key (both server-only). */
function claimSecret(): string {
  return process.env.CLAIM_SECRET?.trim() || process.env.SUPABASE_SERVICE_ROLE_KEY || "";
}

/** Remembers (signed, httpOnly, 24 h) that this browser owns the anonymous user `anonymousUserId`. */
export async function setClaimCookie(anonymousUserId: string): Promise<void> {
  (await cookies()).set(CLAIM_COOKIE, signClaim(anonymousUserId, claimSecret()), {
    path: "/",
    maxAge: CLAIM_MAX_AGE_SECONDS,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
}

/** Reads and clears the claim cookie; the anonymous user id when it is valid. */
export async function takeClaim(): Promise<string | null> {
  const store = await cookies();
  const value = store.get(CLAIM_COOKIE)?.value;
  if (value) store.delete(CLAIM_COOKIE);
  return verifyClaim(value, claimSecret());
}

export interface ClaimDeps {
  /** `from` as seen by the service role: still anonymous, and whether any piece is being generated. */
  inspect(userId: string): Promise<{ anonymous: boolean; generating: boolean }>;
  /** Pieces of the anonymous user. */
  listPieces(userId: string): Promise<string[]>;
  /** Object names under `{userId}/{pieceId}/` in the `photos` bucket. */
  listPhotos(userId: string, pieceId: string): Promise<string[]>;
  movePhoto(from: string, to: string): Promise<void>;
  /** `claim_anonymous_pieces`: owner, photo rows, ledger and purchases; returns pieces moved. */
  reassign(from: string, to: string): Promise<number>;
}

export class ClaimError extends Error {}

/**
 * Moves an anonymous trial's pieces to the account `to` («email already
 * registered», or Google). Checks first (service role) that `from` is still
 * anonymous and that none of its pieces is `generating` (the worker reads the
 * photos by their `{user_id}/` path). Then moves the photo objects (checked by
 * storage RLS, the photo trigger and the worker) and the rows in one SQL call;
 * if that call fails, the objects go back where they were.
 */
export async function claimAnonymousPieces(from: string, to: string, deps: ClaimDeps = adminClaimDeps()): Promise<number> {
  if (from === to) return 0;
  const state = await deps.inspect(from);
  if (!state.anonymous) throw new ClaimError("claim: the source user is not anonymous");
  if (state.generating) throw new ClaimError("claim: a piece is being generated; try again later");

  const moved: [string, string][] = [];
  try {
    for (const pieceId of await deps.listPieces(from)) {
      for (const name of await deps.listPhotos(from, pieceId)) {
        const pair: [string, string] = [`${from}/${pieceId}/${name}`, `${to}/${pieceId}/${name}`];
        await deps.movePhoto(...pair);
        moved.push(pair);
      }
    }
    return await deps.reassign(from, to);
  } catch (error) {
    for (const [original, current] of moved.reverse()) {
      await deps.movePhoto(current, original).catch((undo) => console.error("[claim] could not move back", current, undo));
    }
    throw error;
  }
}

function adminClaimDeps(): ClaimDeps {
  const db = createAdminClient() as unknown as SupabaseClient;
  const photos = () => db.storage.from("photos");
  return {
    async inspect(userId) {
      const { data, error } = await db.auth.admin.getUserById(userId);
      if (error || !data.user) throw new ClaimError(`claim: user: ${error?.message ?? "not found"}`);
      const { count, error: piecesError } = await db
        .from("pieces")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .eq("status", "generating");
      if (piecesError) throw new ClaimError(`claim: pieces: ${piecesError.message}`);
      return { anonymous: data.user.is_anonymous === true, generating: (count ?? 0) > 0 };
    },
    async listPieces(userId) {
      const { data, error } = await db.from("pieces").select("id").eq("user_id", userId);
      if (error) throw new Error(`claim: pieces: ${error.message}`);
      return (data ?? []).map((row) => row.id as string);
    },
    async listPhotos(userId, pieceId) {
      const { data, error } = await photos().list(`${userId}/${pieceId}`, { limit: 20 });
      if (error) throw new Error(`claim: list photos: ${error.message}`);
      return (data ?? []).filter((o) => o.id).map((o) => o.name);
    },
    async movePhoto(from, to) {
      const { error } = await photos().move(from, to);
      if (error) throw new Error(`claim: move ${from}: ${error.message}`);
    },
    async reassign(from, to) {
      const { data, error } = await db.rpc("claim_anonymous_pieces", { p_from: from, p_to: to });
      if (error) throw new Error(`claim: ${error.message}`);
      return typeof data === "number" ? data : 0;
    },
  };
}
