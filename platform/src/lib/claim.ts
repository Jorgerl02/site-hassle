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
  /** Pieces of the anonymous user. */
  listPieces(userId: string): Promise<string[]>;
  /** Object names under `{userId}/{pieceId}/` in the `photos` bucket. */
  listPhotos(userId: string, pieceId: string): Promise<string[]>;
  movePhoto(from: string, to: string): Promise<void>;
  /** `claim_anonymous_pieces`: owner, photo rows, ledger and purchases; returns pieces moved. */
  reassign(from: string, to: string): Promise<number>;
}

/**
 * Moves an anonymous trial's pieces to the account `to` («email already
 * registered»). Photo objects first (their `{user_id}/` prefix is checked by
 * storage RLS, the photo trigger and the worker), then the rows in one SQL
 * call. Only the pieces of `from`, which `claim_anonymous_pieces` checks is
 * still anonymous.
 */
export async function claimAnonymousPieces(from: string, to: string, deps: ClaimDeps = adminClaimDeps()): Promise<number> {
  if (from === to) return 0;
  for (const pieceId of await deps.listPieces(from)) {
    for (const name of await deps.listPhotos(from, pieceId)) {
      await deps.movePhoto(`${from}/${pieceId}/${name}`, `${to}/${pieceId}/${name}`);
    }
  }
  return deps.reassign(from, to);
}

function adminClaimDeps(): ClaimDeps {
  const db = createAdminClient() as unknown as SupabaseClient;
  const photos = () => db.storage.from("photos");
  return {
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
