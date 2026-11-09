/**
 * «Continue with Google» shows only with `NEXT_PUBLIC_GOOGLE_AUTH_ENABLED=true`
 * (set it once the Supabase Google provider has its keys; see README «Google
 * sign-in»). Inlined at build time.
 */
export function googleAuthEnabled(flag: string | undefined = process.env.NEXT_PUBLIC_GOOGLE_AUTH_ENABLED): boolean {
  return flag?.trim() === "true";
}

/** `/auth/callback?next=…` on this site (same-origin `next`, checked again by the callback). */
export function oauthRedirect(origin: string, next: string, signup = false): string {
  const url = new URL("/auth/callback", origin);
  url.searchParams.set("next", next);
  if (signup) url.searchParams.set("signup", "1");
  return url.toString();
}
