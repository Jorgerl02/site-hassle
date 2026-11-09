import type { EmailOtpType, User } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { isFirstSignIn } from "@/lib/analytics";
import { createServerClient } from "@/lib/supabase/server";

/** `type` values a sign-in link may carry (`supabase/templates/magic_link.html` sends `magiclink`). */
const SIGN_IN_TYPES = new Set<EmailOtpType>(["magiclink", "email", "signup"]);

/**
 * Magic-link landing. Links from the email template
 * (`supabase/templates/magic_link.html`) carry `?token_hash=&type=magiclink`
 * and are verified here with `verifyOtp`, so they work in any browser (no
 * PKCE verifier cookie needed). Supabase's default template still sends PKCE
 * links with `?code=` (same browser only), handled too. Both end on /panel,
 * with `?registro=1` on the first sign-in so the panel fires the `signup` event.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const rawType = searchParams.get("type") as EmailOtpType | null;
  const type = rawType && SIGN_IN_TYPES.has(rawType) ? rawType : null;


  const supabase = await createServerClient();
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

  const target = !ok ? "/entrar?error=enlace" : isFirstSignIn(user) ? "/panel?registro=1" : "/panel";
  return NextResponse.redirect(new URL(target, origin));
}
