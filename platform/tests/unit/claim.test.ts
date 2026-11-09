import { describe, expect, it, vi } from "vitest";
import { CLAIM_MAX_AGE_SECONDS, safeNext, signClaim, verifyClaim } from "@/lib/claim-token";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => undefined, set: () => {}, delete: () => {} }) }));
vi.mock("@/lib/supabase/admin", () => ({ createAdminClient: () => ({}) }));

const ANON = "0b5e1c1e-8a3f-4c1e-9d55-2f1a6c0d9e71";
const ACCOUNT = "7d6c5b4a-3f2e-4d1c-8b0a-9f8e7d6c5b4a";
const SECRET = "test-secret";

describe("claim token", () => {
  it("round-trips the anonymous user id", () => {
    expect(verifyClaim(signClaim(ANON, SECRET), SECRET)).toBe(ANON);
  });

  it("rejects a forged id, another secret, garbage and an expired claim", () => {
    const token = signClaim(ANON, SECRET);
    const [, expires, mac] = token.split(".");
    expect(verifyClaim(`${ACCOUNT}.${expires}.${mac}`, SECRET)).toBeNull();
    expect(verifyClaim(token, "other-secret")).toBeNull();
    expect(verifyClaim("nope", SECRET)).toBeNull();
    expect(verifyClaim(undefined, SECRET)).toBeNull();
    const old = signClaim(ANON, SECRET, Date.now() - (CLAIM_MAX_AGE_SECONDS + 60) * 1000);
    expect(verifyClaim(old, SECRET)).toBeNull();
  });

  it("refuses to sign anything but a user id", () => {
    expect(() => signClaim("../etc", SECRET)).toThrow();
    expect(() => signClaim(ANON, "")).toThrow();
  });
});

describe("safeNext", () => {
  it("keeps same-site paths and falls back to /panel", () => {
    expect(safeNext(`/piezas/${ANON}?download=1`)).toBe(`/piezas/${ANON}?download=1`);
    expect(safeNext("//evil.example/x")).toBe("/panel");
    expect(safeNext("https://evil.example")).toBe("/panel");
    expect(safeNext("/\\evil.example")).toBe("/panel");
    expect(safeNext(null)).toBe("/panel");
  });
});

describe("claimAnonymousPieces", () => {
  it("moves every photo under the new owner's prefix, then reassigns the rows", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    const moved = await claimAnonymousPieces(ANON, ACCOUNT, {
      listPieces: async (user) => (user === ANON ? ["p1", "p2"] : []),
      listPhotos: async (_user, piece) => (piece === "p1" ? ["1.jpg", "thumb.jpg"] : ["1.png"]),
      movePhoto: async (from, to) => void calls.push(`${from} -> ${to}`),
      reassign: async (from, to) => {
        calls.push(`reassign ${from} -> ${to}`);
        return 2;
      },
    });
    expect(moved).toBe(2);
    expect(calls).toEqual([
      `${ANON}/p1/1.jpg -> ${ACCOUNT}/p1/1.jpg`,
      `${ANON}/p1/thumb.jpg -> ${ACCOUNT}/p1/thumb.jpg`,
      `${ANON}/p2/1.png -> ${ACCOUNT}/p2/1.png`,
      `reassign ${ANON} -> ${ACCOUNT}`,
    ]);
  });

  it("does nothing when both ids are the same", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const reassign = vi.fn();
    expect(
      await claimAnonymousPieces(ANON, ANON, { listPieces: vi.fn(), listPhotos: vi.fn(), movePhoto: vi.fn(), reassign }),
    ).toBe(0);
    expect(reassign).not.toHaveBeenCalled();
  });
});
