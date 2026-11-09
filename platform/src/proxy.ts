import type { NextRequest } from "next/server";
import {
  ATTRIBUTION_COOKIE,
  ATTRIBUTION_MAX_AGE,
  parseAttribution,
  serializeAttribution,
} from "@/lib/attribution";
import { updateSession } from "@/lib/supabase/proxy";

// Next.js 16 renamed `middleware.ts` to `proxy.ts`.
export async function proxy(request: NextRequest) {
  const response = await updateSession(request);

  // Last-touch attribution: a new ad click overwrites the previous one.
  const attribution = parseAttribution(request.nextUrl.searchParams);
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
