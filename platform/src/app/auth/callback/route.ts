import type { EmailOtpType, User } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import { isFirstSignIn } from "@/lib/analytics";
import { createServerClient } from "@/lib/supabase/server";

/**
 * Magic-link landing. PKCE links carry `?code=`; links built from a custom
 * email template carry `?token_hash=&type=`. Both end on /panel, with
 * `?registro=1` on the first sign-in so the panel fires the `signup` event.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = request.nextUrl;
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;

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
