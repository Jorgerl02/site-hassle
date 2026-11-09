import { createHash } from "node:crypto";

/** Anonymous pieces allowed per network in 24 h (`TRIAL_IP_DAILY_LIMIT` overrides; the e2e server raises it). */
export const TRIAL_IP_DAILY_LIMIT = 3;
export const TRIAL_IP_WINDOW_MS = 24 * 60 * 60 * 1000;

export const TRIAL_IP_LIMIT_MESSAGE = "Free trial limit reached on this network. Create a free account to keep going.";

export function trialIpLimit(raw: string | undefined = process.env.TRIAL_IP_DAILY_LIMIT): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : TRIAL_IP_DAILY_LIMIT;
}

/**
 * Client IP from the proxy headers, or null. On Vercel `x-forwarded-for` is
 * set by the platform (a client value is overwritten); behind any other proxy
 * it must be configured to do the same, or the cap can be dodged.
 */
export function clientIp(headers: Pick<Headers, "get">): string | null {
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const ip = forwarded || headers.get("x-real-ip")?.trim();
  return ip ? ip.slice(0, 64) : null;
}

/** Expands an IPv6 address to its 8 hextets (lowercase, 4 digits); null if it is not one. */
function expandIpv6(ip: string): string[] | null {
  const parts = ip.split("::");
  if (parts.length > 2) return null;
  const head = parts[0] ? parts[0].split(":") : [];
  const tail = parts.length === 2 && parts[1] ? parts[1].split(":") : [];
  const fill = parts.length === 2 ? 8 - head.length - tail.length : 0;
  if (fill < 0) return null;
  const all = [...head, ...Array<string>(fill).fill("0"), ...tail];
  if (all.length !== 8 || !all.every((h) => /^[0-9a-f]{1,4}$/i.test(h))) return null;
  return all.map((h) => h.toLowerCase().padStart(4, "0"));
}

/**
 * The network a trial counts against: the full IPv4 address (also when
 * written as IPv4-mapped IPv6), or the /64 prefix of an IPv6 address (one
 * home or phone usually gets a whole /64, so per-address limits would be
 * trivial to dodge). Unknown formats are used as given.
 */
export function ipKey(ip: string): string {
  const clean = ip.trim().replace(/^\[|\]$/g, "").replace(/%.*$/, "");
  const mapped = /^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/i.exec(clean);
  if (mapped) return mapped[1];
  if (!clean.includes(":")) return clean;
  const hextets = expandIpv6(clean);
  return hextets ? `${hextets.slice(0, 4).join(":")}::/64` : clean.toLowerCase();
}

/** SHA-256 of the salted network key: the IP itself is never stored. */
export function hashIp(ip: string, salt: string): string {
  return createHash("sha256").update(`trial:${salt}:${ipKey(ip)}`).digest("hex");
}

export interface TrialIpStore {
  /** `claim_trial_slot`: atomically takes a slot; its id, or null when the cap is reached. */
  claim(ipHash: string, limit: number): Promise<number | null>;
  /** `release_trial_slot`: gives a slot back (the piece was not created). */
  release(id: number): Promise<void>;
  /** Drops rows older than the window (keeps the table small). */
  prune(beforeIso: string): Promise<void>;
}
