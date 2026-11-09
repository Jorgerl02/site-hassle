import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import {
  CLAIM_COOKIE,
  CLAIM_MAX_AGE_SECONDS,
  PENDING_CLAIM_MAX_AGE_SECONDS,
  signClaim,
  verifyClaim,
  type Claim,
} from "@/lib/claim-token";
import { createAdminClient } from "@/lib/supabase/admin";

/** HMAC key of the claim and download-marker cookies: `CLAIM_SECRET`, else the service-role key (both server-only). */
export function claimSecret(): string {
  return process.env.CLAIM_SECRET?.trim() || process.env.SUPABASE_SERVICE_ROLE_KEY || "";
}

/**
 * Remembers (signed, httpOnly) that this browser owns the anonymous user
 * `anonymousUserId`: 24 h for any account, or 7 days bound to `to` when some
 * pieces are left to claim later.
 */
export async function setClaimCookie(anonymousUserId: string, to: string | null = null): Promise<void> {
  (await cookies()).set(CLAIM_COOKIE, signClaim(anonymousUserId, claimSecret(), Date.now(), to), {
    path: "/",
    maxAge: to ? PENDING_CLAIM_MAX_AGE_SECONDS : CLAIM_MAX_AGE_SECONDS,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
  });
}

/** Reads and clears the claim cookie; the claim when it is valid. */
export async function takeClaim(): Promise<Claim | null> {
  const store = await cookies();
  const value = store.get(CLAIM_COOKIE)?.value;
  if (value) store.delete(CLAIM_COOKIE);
  return verifyClaim(value, claimSecret());
}

export type PieceState = { id: string; status: string };

export interface ClaimDeps {
  /** Whether `from` is still anonymous (service role). */
  isAnonymous(userId: string): Promise<boolean>;
  /** Pieces of the anonymous user, with their status. */
  listPieces(userId: string): Promise<PieceState[]>;
  /** Object names under `{userId}/{pieceId}/` in the `photos` bucket. */
  listPhotos(userId: string, pieceId: string): Promise<string[]>;
  movePhoto(from: string, to: string): Promise<void>;
  /** `claim_anonymous_pieces(from, to, ids)`: moves the listed pieces still not queued/generating; returns their ids. */
  reassign(from: string, to: string, pieceIds: string[]): Promise<string[]>;
  /** Current owner of each piece (to settle a lost `reassign` response). */
  owners(pieceIds: string[]): Promise<Record<string, string>>;
}

export class ClaimError extends Error {}

export interface ClaimResult {
  moved: string[];
  /** Pieces left with the anonymous user (queued or generating): claim them on the next sign-in. */
  left: number;
}

/** The worker reads the photos of these by their `{user_id}/` path: never move them under it. */
const BUSY = new Set(["queued", "generating"]);

/**
 * Moves an anonymous trial's finished pieces to the account `to` («email
 * already registered», or Google). Pieces in `queued`/`generating` stay with
 * the anonymous user (claimed on a later sign-in). For the others: photo
 * objects first (their prefix is checked by storage RLS, the photo trigger and
 * the worker), then the rows in one SQL call that rechecks each status under
 * lock; the files of any piece it did not move go back. If the call's answer
 * is lost, ownership is re-read before undoing anything.
 */
export async function claimAnonymousPieces(from: string, to: string, deps: ClaimDeps = adminClaimDeps()): Promise<ClaimResult> {
  if (from === to) return { moved: [], left: 0 };
  if (!(await deps.isAnonymous(from))) throw new ClaimError("claim: the source user is not anonymous");

  const pieces = await deps.listPieces(from);
  const candidates = pieces.filter((p) => !BUSY.has(p.status)).map((p) => p.id);
  const busy = pieces.length - candidates.length;
  const movedFiles = new Map<string, [string, string][]>();

  const undo = async (pieceIds: string[]) => {
    for (const id of pieceIds) {
      for (const [original, current] of (movedFiles.get(id) ?? []).reverse()) {
        await deps.movePhoto(current, original).catch((error) => console.error("[claim] could not move back", current, error));
      }
    }
  };

  try {
    for (const pieceId of candidates) {
      const files: [string, string][] = [];
      movedFiles.set(pieceId, files);
      for (const name of await deps.listPhotos(from, pieceId)) {
        const pair: [string, string] = [`${from}/${pieceId}/${name}`, `${to}/${pieceId}/${name}`];
        await deps.movePhoto(...pair);
        files.push(pair);
      }
    }
  } catch (error) {
    await undo([...movedFiles.keys()]);
    throw error;
  }

  let moved: string[];
  try {
    moved = candidates.length ? await deps.reassign(from, to, candidates) : [];
  } catch (error) {
    // The SQL may have committed and only the answer been lost: trust the rows.
    let owners: Record<string, string>;
    try {
      owners = await deps.owners(candidates);
    } catch {
      console.error("[claim] reassign failed and ownership is unknown; files left where they are", error);
      throw error;
    }
    moved = candidates.filter((id) => owners[id] === to);
    await undo(candidates.filter((id) => !moved.includes(id)));
    if (moved.length === 0) throw error;
  }
  await undo(candidates.filter((id) => !moved.includes(id)));
  return { moved, left: busy + (candidates.length - moved.length) };
}

function adminClaimDeps(): ClaimDeps {
  const db = createAdminClient() as unknown as SupabaseClient;
  const photos = () => db.storage.from("photos");
  return {
    async isAnonymous(userId) {
      const { data, error } = await db.auth.admin.getUserById(userId);
      if (error || !data.user) throw new ClaimError(`claim: user: ${error?.message ?? "not found"}`);
      return data.user.is_anonymous === true;
    },
    async listPieces(userId) {
      const { data, error } = await db.from("pieces").select("id, status").eq("user_id", userId);
      if (error) throw new Error(`claim: pieces: ${error.message}`);
      return (data ?? []) as PieceState[];
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
    async reassign(from, to, pieceIds) {
      const { data, error } = await db.rpc("claim_anonymous_pieces", { p_from: from, p_to: to, p_pieces: pieceIds });
      if (error) throw new Error(`claim: ${error.message}`);
      return Array.isArray(data) ? (data as string[]) : [];
    },
    async owners(pieceIds) {
      const { data, error } = await db.from("pieces").select("id, user_id").in("id", pieceIds);
      if (error) throw new Error(`claim: owners: ${error.message}`);
      return Object.fromEntries((data ?? []).map((row) => [row.id as string, row.user_id as string]));
    },
  };
}
