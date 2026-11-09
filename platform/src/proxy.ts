import type { NextRequest } from "next/server";
import {
  ATTRIBUTION_COOKIE,
  ATTRIBUTION_MAX_AGE,
  mergeAttribution,
  parseAttribution,
  readAttributionCookie,
  serializeAttribution,
} from "@/lib/attribution";
import { CLAIM_COOKIE, isBoundClaim } from "@/lib/claim-token";
import { updateSession } from "@/lib/supabase/proxy";

// Next.js 16 renamed `middleware.ts` to `proxy.ts`.
export async function proxy(request: NextRequest) {
  const { response, user } = await updateSession(request);

  // An unbound claim (anonymous trial → whichever account signs in next) is
  // stale once an account is signed in by any other way: drop it on the
  // account pages. A claim bound to an account (pieces still generating) stays
  // for that account's next sign-in.
  const path = request.nextUrl.pathname;
  const claimCookie = request.cookies.get(CLAIM_COOKIE)?.value;
  if (user && !user.isAnonymous && (path === "/entrar" || path === "/panel") && claimCookie && !isBoundClaim(claimCookie)) {
    response.cookies.delete(CLAIM_COOKIE);
  }

  // Last-touch attribution: a new ad click overwrites the previous one; an
  // internal CTA (`?source=` only) is added to it instead of erasing the ad.
  const fresh = parseAttribution(request.nextUrl.searchParams);
  const attribution = fresh ? mergeAttribution(readAttributionCookie(request.cookies.get(ATTRIBUTION_COOKIE)?.value), fresh) : null;
  if (attribution) {
    response.cookies.set(ATTRIBUTION_COOKIE, serializeAttribution(attribution), {
      path: "/",
      maxAge: ATTRIBUTION_MAX_AGE,
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
    });
  }

  return response;
}

export const config = {
  matcher: [
    // Skip static assets, images and the example models.
    "/((?!_next/static|_next/image|favicon.ico|examples/|robots.txt|sitemap.xml|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|glb|usdz)$).*)",
  ],
};
