import { createHmac, timingSafeEqual } from "node:crypto";

/**
 * Proof that this browser owned an anonymous trial user, carried through the
 * sign-in of an existing account («email already registered», Google): the
 * callback then moves that anonymous user's pieces to the account. The cookie
 * is httpOnly, but its value is still user input, so it is signed
 * (HMAC-SHA256) and expires; a forged or stale value is ignored.
 *
 * Unbound (`to` = null, 24 h): set before signing in. Bound to an account
 * (7 days): set by the callback when some pieces could not move yet (queued or
 * generating); only that account's next sign-in claims them.
 */
export const CLAIM_COOKIE = "sh_claim";
export const CLAIM_MAX_AGE_SECONDS = 60 * 60 * 24;
export const PENDING_CLAIM_MAX_AGE_SECONDS = 60 * 60 * 24 * 7;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function mac(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(`claim:${payload}`).digest("base64url");
}

export interface Claim {
  /** Anonymous trial user. */
  from: string;
  /** Account it is bound to, or null (any account signing in). */
  to: string | null;
}

/** `{from}.{to|-}.{expires}.{mac}`. */
export function signClaim(anonymousUserId: string, secret: string, now = Date.now(), to: string | null = null): string {
  if (!UUID_RE.test(anonymousUserId) || (to !== null && !UUID_RE.test(to))) throw new Error("claim: not a user id");
  if (!secret) throw new Error("claim: missing secret");
  const ttl = to ? PENDING_CLAIM_MAX_AGE_SECONDS : CLAIM_MAX_AGE_SECONDS;
  const payload = `${anonymousUserId.toLowerCase()}.${to ? to.toLowerCase() : "-"}.${Math.floor(now / 1000) + ttl}`;
  return `${payload}.${mac(payload, secret)}`;
}

/** The claim of a valid, unexpired cookie; otherwise null. */
export function verifyClaim(value: string | null | undefined, secret: string, now = Date.now()): Claim | null {
  if (!value || !secret) return null;
  const parts = value.split(".");
  if (parts.length !== 4) return null;
  const [from, to, expires, signature] = parts;
  if (!UUID_RE.test(from) || (to !== "-" && !UUID_RE.test(to)) || !/^\d+$/.test(expires)) return null;
  const expected = Buffer.from(mac(`${from}.${to}.${expires}`, secret));
  const given = Buffer.from(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;
  if (Number(expires) * 1000 < now) return null;
  return { from, to: to === "-" ? null : to };
}

/** Whether a claim cookie (not verified) is bound to an account: the proxy keeps those. */
export function isBoundClaim(value: string | undefined): boolean {
  const to = value?.split(".")[1];
  return Boolean(to && to !== "-");
}

const FALLBACK = "/panel";
// Control characters (tab, newline… are dropped by the URL parser, so «/\t/evil.com»
// would become «//evil.com») and backslashes (read as «/» by browsers).
const UNSAFE = /[\u0000-\u001f\u007f\\]/;

/**
 * Same-site path to return to after sign-in (`/piezas/…?download=1`);
 * anything else → `/panel`. Rejects control characters, backslashes and
 * protocol-relative `//`, then resolves against `origin` and requires the
 * result to stay on it and not to start with `//` once dot segments are resolved.
 */
export function safeNext(value: unknown, origin = "https://pieza-3d.invalid"): string {
  if (typeof value !== "string" || value.length > 300) return FALLBACK;
  if (UNSAFE.test(value) || !value.startsWith("/") || value.startsWith("//")) return FALLBACK;
  try {
    const base = new URL(origin);
    const url = new URL(value, base);
    // Dot segments are resolved here («/..//evil.com», «/%2e%2e//evil.com» → «//evil.com»):
    // a path that now starts with «//» would leave the site when used as a redirect.
    if (url.origin !== base.origin || url.pathname.startsWith("//")) return FALLBACK;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return FALLBACK;
  }
}

/**
 * One-shot permission to spend the credit without another click right after a
 * sign-up that started from «Download» on a piece: set by `/auth/callback`
 * (httpOnly, path `/piezas/{id}`, 2 min), bound to that piece and user, and
 * consumed by the download action. A bare `?download=1` never spends alone.
 */
export const DOWNLOAD_MARKER_COOKIE = "sh_dl";
export const DOWNLOAD_MARKER_MAX_AGE_SECONDS = 120;

function markerMac(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(`download:${payload}`).digest("base64url");
}

export function signDownloadMarker(pieceId: string, userId: string, secret: string, now = Date.now()): string {
  if (!UUID_RE.test(pieceId) || !UUID_RE.test(userId)) throw new Error("download marker: not an id");
  if (!secret) throw new Error("download marker: missing secret");
  const payload = `${pieceId.toLowerCase()}.${userId.toLowerCase()}.${Math.floor(now / 1000) + DOWNLOAD_MARKER_MAX_AGE_SECONDS}`;
  return `${payload}.${markerMac(payload, secret)}`;
}

export function verifyDownloadMarker(
  value: string | null | undefined,
  pieceId: string,
  userId: string,
  secret: string,
  now = Date.now(),
): boolean {
  if (!value || !secret) return false;
  const parts = value.split(".");
  if (parts.length !== 4) return false;
  const [piece, user, expires, signature] = parts;
  if (piece !== pieceId.toLowerCase() || user !== userId.toLowerCase() || !/^\d+$/.test(expires)) return false;
  const expected = Buffer.from(markerMac(`${piece}.${user}.${expires}`, secret));
  const given = Buffer.from(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return false;
  return Number(expires) * 1000 >= now;
}

const PIECE_PATH = /^\/piezas\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:[?#]|$)/i;

/** Piece id of a `/piezas/{id}…` path, else null. */
export function pieceIdOfPath(path: string): string | null {
  return PIECE_PATH.exec(path)?.[1]?.toLowerCase() ?? null;
}
