import { describe, expect, it, vi } from "vitest";
import {
  CLAIM_MAX_AGE_SECONDS,
  isBoundClaim,
  pieceIdOfPath,
  safeNext,
  signClaim,
  signDownloadMarker,
  verifyClaim,
  verifyDownloadMarker,
} from "@/lib/claim-token";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => undefined, set: () => {}, delete: () => {} }) }));
vi.mock("@/lib/supabase/admin", () => ({ createAdminClient: () => ({}) }));

const ANON = "0b5e1c1e-8a3f-4c1e-9d55-2f1a6c0d9e71";
const ACCOUNT = "7d6c5b4a-3f2e-4d1c-8b0a-9f8e7d6c5b4a";
const SECRET = "test-secret";

describe("claim token", () => {
  it("round-trips an unbound claim and one bound to an account", () => {
    expect(verifyClaim(signClaim(ANON, SECRET), SECRET)).toEqual({ from: ANON, to: null });
    expect(verifyClaim(signClaim(ANON, SECRET, Date.now(), ACCOUNT), SECRET)).toEqual({ from: ANON, to: ACCOUNT });
    expect(isBoundClaim(signClaim(ANON, SECRET))).toBe(false);
    expect(isBoundClaim(signClaim(ANON, SECRET, Date.now(), ACCOUNT))).toBe(true);
  });

  it("rejects a forged id or account, another secret, garbage and an expired claim", () => {
    const token = signClaim(ANON, SECRET);
    const [, to, expires, mac] = token.split(".");
    expect(verifyClaim(`${ACCOUNT}.${to}.${expires}.${mac}`, SECRET)).toBeNull();
    expect(verifyClaim(`${ANON}.${ACCOUNT}.${expires}.${mac}`, SECRET)).toBeNull();
    expect(verifyClaim(token, "other-secret")).toBeNull();
    expect(verifyClaim("nope", SECRET)).toBeNull();
    expect(verifyClaim(undefined, SECRET)).toBeNull();
    const old = signClaim(ANON, SECRET, Date.now() - (CLAIM_MAX_AGE_SECONDS + 60) * 1000);
    expect(verifyClaim(old, SECRET)).toBeNull();
  });

  it("refuses to sign anything but user ids", () => {
    expect(() => signClaim("../etc", SECRET)).toThrow();
    expect(() => signClaim(ANON, SECRET, Date.now(), "x")).toThrow();
    expect(() => signClaim(ANON, "")).toThrow();
  });
});

describe("download marker", () => {
  const PIECE = "11111111-2222-4333-8444-555555555555";

  it("is valid for its piece and user for two minutes, once signed", () => {
    const now = Date.now();
    const marker = signDownloadMarker(PIECE, ACCOUNT, SECRET, now);
    expect(verifyDownloadMarker(marker, PIECE, ACCOUNT, SECRET, now)).toBe(true);
    expect(verifyDownloadMarker(marker, PIECE, ACCOUNT, SECRET, now + 119_000)).toBe(true);
    expect(verifyDownloadMarker(marker, PIECE, ACCOUNT, SECRET, now + 121_000)).toBe(false);
  });

  it("does not transfer to another piece, user or secret", () => {
    const marker = signDownloadMarker(PIECE, ACCOUNT, SECRET);
    expect(verifyDownloadMarker(marker, ANON, ACCOUNT, SECRET)).toBe(false);
    expect(verifyDownloadMarker(marker, PIECE, ANON, SECRET)).toBe(false);
    expect(verifyDownloadMarker(marker, PIECE, ACCOUNT, "other")).toBe(false);
    expect(verifyDownloadMarker(undefined, PIECE, ACCOUNT, SECRET)).toBe(false);
  });

  it("reads the piece id of a piece path only", () => {
    expect(pieceIdOfPath(`/piezas/${PIECE}`)).toBe(PIECE);
    expect(pieceIdOfPath(`/piezas/${PIECE}?download=1`)).toBe(PIECE);
    expect(pieceIdOfPath("/panel")).toBeNull();
    expect(pieceIdOfPath(`/piezas/${PIECE}/x`)).toBeNull();
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
    ["/..//evil.com"],
    ["/.//evil.com"],
    ["/%2e%2e//evil.com"],
    ["/%2E%2E//evil.com"],
    ["/a/..//evil.com"],
    ["/a/b/../..//evil.com"],
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
  type Deps = import("@/lib/claim").ClaimDeps;

  function deps(over: Partial<Deps> & { calls?: string[] } = {}): Deps & { calls: string[] } {
    const calls = over.calls ?? [];
    return {
      calls,
      isAnonymous: async () => true,
      listPieces: async () => [
        { id: "p1", status: "ready" },
        { id: "p2", status: "queued" },
        { id: "p3", status: "rejected" },
      ],
      listPhotos: async (_user, piece) => (piece === "p1" ? ["1.jpg", "thumb.jpg"] : ["1.png"]),
      movePhoto: async (from, to) => void calls.push(`${from} -> ${to}`),
      reassign: async (_from, _to, ids) => {
        calls.push(`reassign ${ids.join(",")}`);
        return ids;
      },
      owners: async () => ({}),
      ...over,
    };
  }

  it("moves finished pieces (files, then rows) and leaves queued/generating ones with the trial", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const d = deps();
    expect(await claimAnonymousPieces(ANON, ACCOUNT, d)).toEqual({ moved: ["p1", "p3"], left: 1 });
    expect(d.calls).toEqual([
      `${ANON}/p1/1.jpg -> ${ACCOUNT}/p1/1.jpg`,
      `${ANON}/p1/thumb.jpg -> ${ACCOUNT}/p1/thumb.jpg`,
      `${ANON}/p3/1.png -> ${ACCOUNT}/p3/1.png`,
      "reassign p1,p3",
    ]);
  });

  it("does nothing when both ids are the same, and refuses a user that is not anonymous", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const reassign = vi.fn();
    expect(await claimAnonymousPieces(ANON, ANON, deps({ reassign }))).toEqual({ moved: [], left: 0 });
    const movePhoto = vi.fn();
    await expect(claimAnonymousPieces(ANON, ACCOUNT, deps({ isAnonymous: async () => false, movePhoto, reassign }))).rejects.toThrow();
    expect(movePhoto).not.toHaveBeenCalled();
    expect(reassign).not.toHaveBeenCalled();
  });

  it("moves back the files of a piece the SQL refused (it was re-queued meanwhile)", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    const d = deps({ calls, reassign: async () => ["p1"] });
    expect(await claimAnonymousPieces(ANON, ACCOUNT, d)).toEqual({ moved: ["p1"], left: 2 });
    expect(calls.slice(-1)).toEqual([`${ACCOUNT}/p3/1.png -> ${ANON}/p3/1.png`]);
  });

  it("on a failed call, re-reads ownership: committed pieces keep their files, the rest go back", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    const lost = deps({
      calls,
      reassign: async () => {
        throw new Error("response lost");
      },
      owners: async () => ({ p1: ACCOUNT, p3: ANON }),
    });
    expect(await claimAnonymousPieces(ANON, ACCOUNT, lost)).toEqual({ moved: ["p1"], left: 2 });
    expect(calls.slice(-1)).toEqual([`${ACCOUNT}/p3/1.png -> ${ANON}/p3/1.png`]);

    const calls2: string[] = [];
    const failed = deps({
      calls: calls2,
      reassign: async () => {
        throw new Error("rpc down");
      },
      owners: async () => ({ p1: ANON, p3: ANON }),
    });
    await expect(claimAnonymousPieces(ANON, ACCOUNT, failed)).rejects.toThrow("rpc down");
    expect(calls2.slice(-3)).toEqual([
      `${ACCOUNT}/p1/thumb.jpg -> ${ANON}/p1/thumb.jpg`,
      `${ACCOUNT}/p1/1.jpg -> ${ANON}/p1/1.jpg`,
      `${ACCOUNT}/p3/1.png -> ${ANON}/p3/1.png`,
    ]);
  });

  it("moves back the files already moved when a move fails half-way", async () => {
    const { claimAnonymousPieces } = await import("@/lib/claim");
    const calls: string[] = [];
    const reassign = vi.fn();
    await expect(
      claimAnonymousPieces(
        ANON,
        ACCOUNT,
        deps({
          calls,
          reassign,
          movePhoto: async (from, to) => {
            if (from === `${ANON}/p1/thumb.jpg`) throw new Error("storage down");
            calls.push(`${from} -> ${to}`);
          },
        }),
      ),
    ).rejects.toThrow("storage down");
    expect(calls).toEqual([`${ANON}/p1/1.jpg -> ${ACCOUNT}/p1/1.jpg`, `${ACCOUNT}/p1/1.jpg -> ${ANON}/p1/1.jpg`]);
    expect(reassign).not.toHaveBeenCalled();
  });
});
