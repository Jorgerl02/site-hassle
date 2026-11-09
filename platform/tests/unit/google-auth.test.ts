import { describe, expect, it } from "vitest";
import { googleAuthEnabled, oauthRedirect } from "@/lib/google-auth";

describe("googleAuthEnabled", () => {
  it("is on only with the flag set to true", () => {
    expect(googleAuthEnabled("true")).toBe(true);
    expect(googleAuthEnabled(" true ")).toBe(true);
    expect(googleAuthEnabled(undefined)).toBe(false);
    expect(googleAuthEnabled("")).toBe(false);
    expect(googleAuthEnabled("1")).toBe(false);
  });
});

describe("oauthRedirect", () => {
  it("points at the callback with the next path (and signup for conversions)", () => {
    expect(oauthRedirect("https://pieza-3d.vercel.app", "/piezas/x?download=1")).toBe(
      "https://pieza-3d.vercel.app/auth/callback?next=%2Fpiezas%2Fx%3Fdownload%3D1",
    );
    expect(oauthRedirect("https://pieza-3d.vercel.app", "/panel", true)).toBe(
      "https://pieza-3d.vercel.app/auth/callback?next=%2Fpanel&signup=1",
    );
  });
});
