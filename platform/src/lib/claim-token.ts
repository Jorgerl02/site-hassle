import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Proof that this browser owned an anonymous trial user, carried through the
 * sign-in of an existing account («email already registered»): the callback
 * then moves that anonymous user's pieces to the account. The cookie is
 * httpOnly, but its value is still user input, so it is signed (HMAC-SHA256)
 * and expires; a forged or stale value is ignored.
 */
export const CLAIM_COOKIE = "sh_claim";
export const CLAIM_MAX_AGE_SECONDS = 60 * 60 * 24;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function mac(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(`claim:${payload}`).digest("base64url");
}

/** `{uid}.{expires}.{mac}`. */
export function signClaim(anonymousUserId: string, secret: string, now = Date.now()): string {
  if (!UUID_RE.test(anonymousUserId)) throw new Error("claim: not a user id");
  if (!secret) throw new Error("claim: missing secret");
  const payload = `${anonymousUserId.toLowerCase()}.${Math.floor(now / 1000) + CLAIM_MAX_AGE_SECONDS}`;
  return `${payload}.${mac(payload, secret)}`;
}

/** The anonymous user id of a valid, unexpired claim; otherwise null. */
export function verifyClaim(value: string | null | undefined, secret: string, now = Date.now()): string | null {
  if (!value || !secret) return null;
  const parts = value.split(".");
  if (parts.length !== 3) return null;
  const [uid, expires, signature] = parts;
  if (!UUID_RE.test(uid) || !/^\d+$/.test(expires)) return null;
  const expected = Buffer.from(mac(`${uid}.${expires}`, secret));
  const given = Buffer.from(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;
  if (Number(expires) * 1000 < now) return null;
  return uid;
}

/** Same-site path to return to after sign-in (`/piezas/…?download=1`); anything else → `/panel`. */
export function safeNext(value: unknown): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/panel";
  }
  return value.slice(0, 300);
}
