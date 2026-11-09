import { afterEach, describe, expect, it, vi } from "vitest";
import { eventForNavigation, isFirstSignIn } from "@/lib/analytics";

const PIECE = "/piezas/0b5e1c1e-8a3f-4c1e-9d55-2f1a6c0d9e71";

describe("eventForNavigation", () => {
  it("reads piece_created from the form landing on the new piece", () => {
    expect(eventForNavigation("/piezas/nueva", PIECE)).toBe("piece_created");
  });
  it("ignores every other navigation", () => {
    expect(eventForNavigation(null, PIECE)).toBeNull();
    expect(eventForNavigation("/panel", PIECE)).toBeNull();
    expect(eventForNavigation("/piezas/nueva", "/panel")).toBeNull();
    expect(eventForNavigation("/piezas/nueva", "/piezas/nueva")).toBeNull();
  });
});

describe("isFirstSignIn", () => {
  it("is true when the email was confirmed by this sign-in", () => {
    expect(isFirstSignIn({ email_confirmed_at: "2026-11-09T10:00:00Z", last_sign_in_at: "2026-11-09T10:00:01Z" })).toBe(true);
  });
  it("is false for later sign-ins or missing data", () => {
    expect(isFirstSignIn({ email_confirmed_at: "2026-11-01T10:00:00Z", last_sign_in_at: "2026-11-09T10:00:00Z" })).toBe(false);
    expect(isFirstSignIn({ email_confirmed_at: null, last_sign_in_at: "2026-11-09T10:00:00Z" })).toBe(false);
    expect(isFirstSignIn(null)).toBe(false);
  });
});

describe("track", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  async function load(env: Record<string, string>) {
    for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
    const storage = new Map<string, string>();
    vi.stubGlobal("window", {
      location: { href: "https://pieza3d.example/creditos" },
      localStorage: {
        getItem: (k: string) => storage.get(k) ?? null,
        setItem: (k: string, v: string) => void storage.set(k, v),
      },
    });
    return import("@/lib/analytics");
  }

  it("is a no-op without ids", async () => {
    const analytics = await load({ NEXT_PUBLIC_META_PIXEL_ID: "", NEXT_PUBLIC_GA_ID: "" });
    analytics.track("purchase", { value: 69 });
    expect(analytics.analyticsEnabled()).toBe(false);
    expect((window as Window).fbq).toBeUndefined();
    expect((window as Window).gtag).toBeUndefined();
  });

  it("queues the pixel init and the mapped events, once per key", async () => {
    const analytics = await load({ NEXT_PUBLIC_META_PIXEL_ID: "123", NEXT_PUBLIC_GA_ID: "G-TEST" });
    analytics.trackOnce("purchase", "purchase:cs_1", { value: 69, transactionId: "cs_1" });
    analytics.trackOnce("purchase", "purchase:cs_1", { value: 69, transactionId: "cs_1" });
    analytics.track("piece_created");

    const fbqQueue = (window as Window).fbq!.queue;
    expect(fbqQueue).toEqual([
      ["init", "123"],
      ["track", "Purchase", { value: 69, currency: "EUR" }],
      ["trackCustom", "PieceCreated", {}],
    ]);
    const layer = ((window as Window).dataLayer ?? []).map((args) => Array.from(args as ArrayLike<unknown>));
    expect(layer[1]).toEqual(["config", "G-TEST", { send_page_view: false }]);
    expect(layer.slice(2)).toEqual([
      ["event", "purchase", { value: 69, currency: "EUR", transaction_id: "cs_1" }],
      ["event", "piece_created", {}],
    ]);
  });
});
