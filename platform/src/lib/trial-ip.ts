import { createHash } from "node:crypto";

/** Anonymous pieces allowed per IP in 24 h (`TRIAL_IP_DAILY_LIMIT` overrides; the e2e server raises it). */
export const TRIAL_IP_DAILY_LIMIT = 3;
export const TRIAL_IP_WINDOW_MS = 24 * 60 * 60 * 1000;

export const TRIAL_IP_LIMIT_MESSAGE = "Free trial limit reached on this network. Create a free account to keep going.";

export function trialIpLimit(raw: string | undefined = process.env.TRIAL_IP_DAILY_LIMIT): number {
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : TRIAL_IP_DAILY_LIMIT;
}

/** Client IP from the proxy headers (Vercel: first `x-forwarded-for` entry), or null. */
export function clientIp(headers: Pick<Headers, "get">): string | null {
  const forwarded = headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const ip = forwarded || headers.get("x-real-ip")?.trim();
  return ip ? ip.slice(0, 64) : null;
}

/** SHA-256 of the salted IP: the IP itself is never stored. */
export function hashIp(ip: string, salt: string): string {
  return createHash("sha256").update(`trial:${salt}:${ip}`).digest("hex");
}

export interface TrialIpStore {
  countSince(ipHash: string, sinceIso: string): Promise<number>;
  record(ipHash: string): Promise<void>;
  /** Drops rows older than the window (keeps the table small). */
  prune(beforeIso: string): Promise<void>;
}

/** Whether one more anonymous piece is allowed for this IP hash right now. */
export async function trialIpAllowed(ipHash: string, store: TrialIpStore, limit = trialIpLimit(), now = Date.now()): Promise<boolean> {
  const since = new Date(now - TRIAL_IP_WINDOW_MS).toISOString();
  return (await store.countSince(ipHash, since)) < limit;
}
