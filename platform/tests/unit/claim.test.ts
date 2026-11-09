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
  const ORIGIN = "https://pieza-3d.vercel.app";

  it("keeps same-site paths", () => {
    expect(safeNext(`/piezas/${ANON}?download=1`, ORIGIN)).toBe(`/piezas/${ANON}?download=1`);
    expect(safeNext("/panel#x", ORIGIN)).toBe("/panel#x");
  });

  it.each([
    // What `searchParams.get("next")` returns for ?next=/%09/evil.com and ?next=/%0a/evil.com.
    ["/\t/evil.com"],
    ["/\n/evil.com"],
    ["/\r/evil.com"],
    ["/\u0000/evil.com"],
    ["/\\evil.com"],
    ["/\\/evil.com"],
    ["//evil.com"],
    ["https://evil.com"],
    ["evil.com"],
    [""],
    [null],
    [42],
  ])("sends %j to /panel", (value) => {
    expect(safeNext(value, ORIGIN)).toBe("/panel");
  });

  it("keeps still-encoded input on the site (it is a path, never a host)", () => {
    expect(safeNext("/%09/evil.com", ORIGIN)).toBe("/%09/evil.com");
    expect(safeNext("/%0a/evil.com", ORIGIN)).toBe("/%0a/evil.com");
    expect(safeNext("/%2F%2Fevil", ORIGIN)).toBe("/%2F%2Fevil");
    expect(new URL(safeNext("/%2F%2Fevil", ORIGIN), ORIGIN).origin).toBe(ORIGIN);
  });
});

describe("claimAnonymousPieces", () => {
  it("moves every photo under the new owner's prefix, then reassigns the rows", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    const moved = await claimAnonymousPieces(ANON, ACCOUNT, {
      inspect: async () => ({ anonymous: true, generating: false }),
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
      await claimAnonymousPieces(ANON, ANON, { inspect: vi.fn(), listPieces: vi.fn(), listPhotos: vi.fn(), movePhoto: vi.fn(), reassign }),
    ).toBe(0);
    expect(reassign).not.toHaveBeenCalled();
  });

  it("checks before touching any file: not anonymous or a piece generating → nothing moves", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    for (const state of [{ anonymous: false, generating: false }, { anonymous: true, generating: true }]) {
      const movePhoto = vi.fn();
      const reassign = vi.fn();
      await expect(
        claimAnonymousPieces(ANON, ACCOUNT, {
          inspect: async () => state,
          listPieces: async () => ["p1"],
          listPhotos: async () => ["1.jpg"],
          movePhoto,
          reassign,
        }),
      ).rejects.toThrow();
      expect(movePhoto).not.toHaveBeenCalled();
      expect(reassign).not.toHaveBeenCalled();
    }
  });

  it("moves the files back when the SQL reassignment fails", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    await expect(
      claimAnonymousPieces(ANON, ACCOUNT, {
        inspect: async () => ({ anonymous: true, generating: false }),
        listPieces: async () => ["p1"],
        listPhotos: async () => ["1.jpg", "2.jpg"],
        movePhoto: async (from, to) => void calls.push(`${from} -> ${to}`),
        reassign: async () => {
          throw new Error("rpc down");
        },
      }),
    ).rejects.toThrow("rpc down");
    expect(calls).toEqual([
      `${ANON}/p1/1.jpg -> ${ACCOUNT}/p1/1.jpg`,
      `${ANON}/p1/2.jpg -> ${ACCOUNT}/p1/2.jpg`,
      `${ACCOUNT}/p1/2.jpg -> ${ANON}/p1/2.jpg`,
      `${ACCOUNT}/p1/1.jpg -> ${ANON}/p1/1.jpg`,
    ]);
  });

  it("moves back the files already moved when a move fails half-way", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    await expect(
      claimAnonymousPieces(ANON, ACCOUNT, {
        inspect: async () => ({ anonymous: true, generating: false }),
        listPieces: async () => ["p1"],
        listPhotos: async () => ["1.jpg", "2.jpg"],
        movePhoto: async (from, to) => {
          if (from.endsWith("2.jpg") && from.startsWith(ANON)) throw new Error("storage down");
          calls.push(`${from} -> ${to}`);
        },
        reassign: vi.fn(),
      }),
    ).rejects.toThrow("storage down");
    expect(calls).toEqual([`${ANON}/p1/1.jpg -> ${ACCOUNT}/p1/1.jpg`, `${ACCOUNT}/p1/1.jpg -> ${ANON}/p1/1.jpg`]);
  });
});
