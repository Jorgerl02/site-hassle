import { describe, expect, it } from "vitest";
import {
  CONSENT_AT_KEY,
  CONSENT_KEY,
  CONSENT_MAX_AGE_MS,
  measurementAllowed,
  readConsent,
  shouldAskConsent,
  writeConsent,
} from "@/lib/consent";

function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    map,
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
  };
}

const NOW = Date.parse("2026-11-09T12:00:00Z");

describe("readConsent / writeConsent", () => {
  it("stores the choice with its date and reads it back", () => {
    const storage = memoryStorage();
    writeConsent("granted", storage, NOW);
    expect(storage.map.get(CONSENT_KEY)).toBe("granted");
    expect(storage.map.get(CONSENT_AT_KEY)).toBe(String(NOW));
    expect(readConsent(storage, NOW + 1000)).toBe("granted");
    writeConsent("denied", storage, NOW);
    expect(readConsent(storage, NOW)).toBe("denied");
  });

  it("forgets a choice older than 180 days", () => {
    const storage = memoryStorage({ [CONSENT_KEY]: "granted", [CONSENT_AT_KEY]: String(NOW) });
    expect(readConsent(storage, NOW + CONSENT_MAX_AGE_MS)).toBe("granted");
    expect(readConsent(storage, NOW + CONSENT_MAX_AGE_MS + 1)).toBeNull();
  });

  it("treats missing, unknown or undated values as no choice", () => {
    expect(readConsent(memoryStorage(), NOW)).toBeNull();
    expect(readConsent(memoryStorage({ [CONSENT_KEY]: "yes", [CONSENT_AT_KEY]: String(NOW) }), NOW)).toBeNull();
    expect(readConsent(memoryStorage({ [CONSENT_KEY]: "granted" }), NOW)).toBeNull();
    expect(readConsent(null, NOW)).toBeNull();
  });

  it("survives a storage that throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {},
    };
    expect(readConsent(broken, NOW)).toBeNull();
    expect(() => writeConsent("granted", broken, NOW)).not.toThrow();
  });
});

describe("the consent gate", () => {
  it("asks only when an id is configured and there is no choice", () => {
    expect(shouldAskConsent(false, null)).toBe(false);
    expect(shouldAskConsent(true, null)).toBe(true);
    expect(shouldAskConsent(true, "granted")).toBe(false);
    expect(shouldAskConsent(true, "denied")).toBe(false);
  });

  it("allows measurement only with an id and a stored «granted»", () => {
    expect(measurementAllowed(true, "granted")).toBe(true);
    expect(measurementAllowed(true, "denied")).toBe(false);
    expect(measurementAllowed(true, null)).toBe(false);
    expect(measurementAllowed(false, "granted")).toBe(false);
  });
});
