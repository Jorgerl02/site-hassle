import { describe, expect, it } from "vitest";
import { clientIp, hashIp, ipKey, trialIpLimit } from "@/lib/trial-ip";

describe("trial IP cap", () => {
  it("reads the limit from the environment, defaulting to 3", () => {
    expect(trialIpLimit(undefined)).toBe(3);
    expect(trialIpLimit("1000")).toBe(1000);
    expect(trialIpLimit("x")).toBe(3);
  });

  it("takes the first forwarded IP", () => {
    expect(clientIp(new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" }))).toBe("203.0.113.7");
    expect(clientIp(new Headers({ "x-real-ip": "198.51.100.2" }))).toBe("198.51.100.2");
    expect(clientIp(new Headers())).toBeNull();
  });
});

describe("ipKey", () => {
  it("keeps a full IPv4 address (also IPv4-mapped IPv6)", () => {
    expect(ipKey("203.0.113.7")).toBe("203.0.113.7");
    expect(ipKey("::ffff:203.0.113.7")).toBe("203.0.113.7");
  });

  it("reduces IPv6 to its expanded /64 prefix", () => {
    expect(ipKey("2001:db8:abcd:12:1:2:3:4")).toBe("2001:0db8:abcd:0012::/64");
    expect(ipKey("2001:DB8:ABCD:12::99")).toBe("2001:0db8:abcd:0012::/64");
    expect(ipKey("[2001:db8::1]")).toBe("2001:0db8:0000:0000::/64");
    expect(ipKey("fe80::1%en0")).toBe("fe80:0000:0000:0000::/64");
    expect(ipKey("::1")).toBe("0000:0000:0000:0000::/64");
  });

  it("hashes one /64 to one value, salted, never containing the address", () => {
    const a = hashIp("2001:db8:abcd:12::1", "salt");
    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(hashIp("2001:db8:abcd:12:ffff:ffff:ffff:ffff", "salt")).toBe(a);
    expect(hashIp("2001:db8:abcd:13::1", "salt")).not.toBe(a);
    expect(hashIp("2001:db8:abcd:12::1", "other")).not.toBe(a);
    expect(hashIp("203.0.113.7", "salt")).not.toContain("203");
  });
});
