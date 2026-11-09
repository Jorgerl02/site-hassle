import { describe, expect, it } from "vitest";
import { clientIp, hashIp, trialIpAllowed, trialIpLimit, type TrialIpStore } from "@/lib/trial-ip";

function store(counts: number): TrialIpStore & { since: string[] } {
  const since: string[] = [];
  return {
    since,
    async countSince(_hash, iso) {
      since.push(iso);
      return counts;
    },
    async record() {},
    async prune() {},
  };
}

describe("trial IP cap", () => {
  it("allows up to 3 anonymous pieces per IP in 24 h", async () => {
    const now = Date.parse("2026-11-09T12:00:00Z");
    const s = store(2);
    expect(await trialIpAllowed("h", s, 3, now)).toBe(true);
    expect(s.since).toEqual(["2026-11-08T12:00:00.000Z"]);
    expect(await trialIpAllowed("h", store(3), 3, now)).toBe(false);
  });

  it("reads the limit from the environment, defaulting to 3", () => {
    expect(trialIpLimit(undefined)).toBe(3);
    expect(trialIpLimit("1000")).toBe(1000);
    expect(trialIpLimit("x")).toBe(3);
  });

  it("takes the first forwarded IP and hashes it with the salt", () => {
    const headers = new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" });
    expect(clientIp(headers)).toBe("203.0.113.7");
    expect(clientIp(new Headers({ "x-real-ip": "198.51.100.2" }))).toBe("198.51.100.2");
    expect(clientIp(new Headers())).toBeNull();
    const a = hashIp("203.0.113.7", "salt");
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(a).not.toBe(hashIp("203.0.113.7", "other"));
    expect(a).not.toContain("203");
  });
});
