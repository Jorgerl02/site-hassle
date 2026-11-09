import type { EmailOtpType, User } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { isFirstSignIn } from "@/lib/analytics";
import { claimAnonymousPieces, takeClaim } from "@/lib/claim";
import { safeNext } from "@/lib/claim-token";
import { createServerClient } from "@/lib/supabase/server";

/**
 * `type` values a link may carry: sign-in (`supabase/templates/magic_link.html`
 * sends `magiclink`), sign-up, and `email_change`, which confirms the email an
 * anonymous trial added («Save this piece»).
 */
const LINK_TYPES = new Set<EmailOtpType>(["magiclink", "email", "signup", "email_change"]);

/**
 * Link landing (email links and OAuth: Google sign-in and `linkIdentity`). Links from the email templates carry
 * `?token_hash=&type=` and are verified with `verifyOtp` (any browser);
 * Supabase's default templates and OAuth send PKCE links with `?code=` (same
 * browser only). Then:
 *
 * - a valid `sh_claim` cookie (set when an anonymous trial typed the email of
 *   an existing account) moves that anonymous user's pieces to this account;
 * - the customer goes back to `next` (a same-site path, e.g. the piece with
 *   `?download=1`), else `/panel`, with `?registro=1` on a sign-up or on the
 *   conversion of an anonymous trial (`signup=1`) so the page fires `signup`.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const rawType = searchParams.get("type") as EmailOtpType | null;
  const type = rawType && LINK_TYPES.has(rawType) ? rawType : null;
  const next = safeNext(searchParams.get("next"));

  const supabase = await createServerClient();

  // «Continue with Google» from an anonymous trial (`linkIdentity`) whose Google
  // account already has a user: sign in to that user instead; the claim cookie
  // set before linking moves the trial's pieces there on the way back.
  const oauthError = searchParams.get("error_code") ?? "";
  if (oauthError === "identity_already_exists" || /already (linked|exists)/i.test(searchParams.get("error_description") ?? "")) {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${origin}/auth/callback?next=${encodeURIComponent(next)}` },
    });
    if (!error && data.url) return NextResponse.redirect(data.url);
  }

  let ok = false;
  let user: User | null = null;
  if (code) {
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);
    ok = !error;
    user = data?.user ?? null;
  } else if (tokenHash && type) {
    const { data, error } = await supabase.auth.verifyOtp({ token_hash: tokenHash, type });
    ok = !error;
    user = data?.user ?? null;
  }
  if (!ok || !user) return NextResponse.redirect(new URL("/entrar?error=enlace", origin));

  const claimedFrom = await takeClaim();
  if (claimedFrom && claimedFrom !== user.id && !user.is_anonymous) {
    try {
      const moved = await claimAnonymousPieces(claimedFrom, user.id);
      console.info(`[claim] ${moved} piece(s) moved from anonymous ${claimedFrom} to ${user.id}`);
    } catch (error) {
      // The sign-in still succeeds; the pieces stay with the anonymous user (admin can move them).
      console.error("[claim] failed", error);
    }
  }

  const target = new URL(next, origin);
  const converted = searchParams.get("signup") === "1" && !user.is_anonymous;
  if (converted || isFirstSignIn(user)) target.searchParams.set("registro", "1");
  return NextResponse.redirect(target);
}
