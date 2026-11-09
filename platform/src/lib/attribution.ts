export const ATTRIBUTION_COOKIE = "sh_attr";

/** 90 days: long enough to cover an ad click followed by a later sign-up. */
export const ATTRIBUTION_MAX_AGE = 60 * 60 * 24 * 90;

export const ATTRIBUTION_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "ref",
] as const;

export type AttributionKey = (typeof ATTRIBUTION_KEYS)[number];
export type Attribution = Partial<Record<AttributionKey, string>>;

const MAX_VALUE_LENGTH = 200;

function clean(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim().slice(0, MAX_VALUE_LENGTH);
  return trimmed.length > 0 ? trimmed : null;
}

function pick(get: (key: AttributionKey) => unknown): Attribution | null {
  const result: Attribution = {};
  for (const key of ATTRIBUTION_KEYS) {
    const value = clean(get(key));
    if (value !== null) result[key] = value;
  }
  return Object.keys(result).length > 0 ? result : null;
}

/** Reads `utm_*` and `ref` from a URL; null when none is present. */
export function parseAttribution(searchParams: URLSearchParams): Attribution | null {
  return pick((key) => searchParams.get(key));
}

export function serializeAttribution(attribution: Attribution): string {
  return JSON.stringify(attribution);
}

/** Parses the cookie value defensively: it is user-controlled input. */
export function readAttributionCookie(value: string | undefined | null): Attribution | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
    const record = parsed as Record<string, unknown>;
    return pick((key) => record[key]);
  } catch {
    return null;
  }
}
