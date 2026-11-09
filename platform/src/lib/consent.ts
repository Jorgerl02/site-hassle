/**
 * Cookie consent for measurement (Meta Pixel, GA4). EU rule: no measurement
 * script loads and no event is sent until the visitor accepts.
 *
 * Stored in `localStorage`: `sh_consent` = `granted | denied` and
 * `sh_consent_at` = epoch ms of the choice. A choice older than 180 days (or
 * without date) counts as no choice, so the banner asks again.
 */

export type Consent = "granted" | "denied";

export const CONSENT_KEY = "sh_consent";
export const CONSENT_AT_KEY = "sh_consent_at";
export const CONSENT_MAX_AGE_MS = 180 * 24 * 60 * 60 * 1000;
/** Fired on `window` when the choice changes, so the page reacts without a reload. */
export const CONSENT_EVENT = "sh-consent-change";

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function browserStorage(): StorageLike | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null; // storage blocked: behave as "no choice"
  }
}

export function readConsent(storage: StorageLike | null = browserStorage(), now: number = Date.now()): Consent | null {
  if (!storage) return null;
  try {
    const value = storage.getItem(CONSENT_KEY);
    const at = Number(storage.getItem(CONSENT_AT_KEY));
    if (value !== "granted" && value !== "denied") return null;
    if (!Number.isFinite(at) || at <= 0 || now - at > CONSENT_MAX_AGE_MS || at > now + 60_000) return null;
    return value;
  } catch {
    return null;
  }
}

export function writeConsent(value: Consent, storage: StorageLike | null = browserStorage(), now: number = Date.now()): void {
  try {
    storage?.setItem(CONSENT_KEY, value);
    storage?.setItem(CONSENT_AT_KEY, String(now));
  } catch {
    // Storage blocked: the choice lasts for this page view only.
  }
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event(CONSENT_EVENT));
  }
}

export function clearConsent(storage: StorageLike | null = browserStorage()): void {
  try {
    storage?.removeItem(CONSENT_KEY);
    storage?.removeItem(CONSENT_AT_KEY);
  } catch {
    // ignore
  }
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event(CONSENT_EVENT));
  }
}

/** The banner only exists when some measurement id is configured and no valid choice is stored. */
export function shouldAskConsent(analyticsConfigured: boolean, consent: Consent | null): boolean {
  return analyticsConfigured && consent === null;
}

/** Scripts load and events are sent only with an id configured and a stored `granted`. */
export function measurementAllowed(analyticsConfigured: boolean, consent: Consent | null): boolean {
  return analyticsConfigured && consent === "granted";
}
