import { describe, expect, it } from "vitest";
import {
  ATTRIBUTION_COOKIE,
  parseAttribution,
  readAttributionCookie,
  serializeAttribution,
} from "@/lib/attribution";

describe("parseAttribution", () => {
  it("returns the utm and ref keys present", () => {
    const params = new URLSearchParams("utm_source=meta&utm_campaign=t1&ref=x");
    expect(parseAttribution(params)).toEqual({
      utm_source: "meta",
      utm_campaign: "t1",
      ref: "x",
    });
  });

  it("returns null without any attribution key", () => {
    expect(parseAttribution(new URLSearchParams(""))).toBeNull();
    expect(parseAttribution(new URLSearchParams("foo=bar&page=2"))).toBeNull();
  });

  it("ignores empty values and unknown keys", () => {
    const params = new URLSearchParams("utm_source=&utm_medium=cpc&gclid=abc");
    expect(parseAttribution(params)).toEqual({ utm_medium: "cpc" });
  });

  it("trims and caps long values", () => {
    const params = new URLSearchParams({ utm_content: `  ${"a".repeat(500)}  ` });
    expect(parseAttribution(params)?.utm_content).toHaveLength(200);
  });
});

describe("attribution cookie", () => {
  it("uses the agreed cookie name", () => {
    expect(ATTRIBUTION_COOKIE).toBe("sh_attr");
  });

  it("round-trips through serialize and read", () => {
    const attr = { utm_source: "meta", ref: "x" };
    expect(readAttributionCookie(serializeAttribution(attr))).toEqual(attr);
  });

  it("rejects malformed or foreign cookie values", () => {
    expect(readAttributionCookie(undefined)).toBeNull();
    expect(readAttributionCookie("not json")).toBeNull();
    expect(readAttributionCookie('{"evil":"1"}')).toBeNull();
    expect(readAttributionCookie('{"utm_source":5,"ref":"ok"}')).toEqual({ ref: "ok" });
  });
});
