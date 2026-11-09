"use server";

import { headers } from "next/headers";
import { getCurrentUser } from "@/lib/auth";
import { setClaimCookie } from "@/lib/claim";
import { safeNext } from "@/lib/claim-token";
import { oauthRedirect } from "@/lib/google-auth";
import { createServerClient } from "@/lib/supabase/server";

export type SaveAccountState =
  | { status: "idle" }
  | { status: "sent"; email: string; existing: boolean }
  | { status: "error"; message: string; email: string };

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function origin(): Promise<string> {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}

const callbackUrl = oauthRedirect;

/**
 * Turns the anonymous trial into an account with the same user id (and so the
 * same pieces): `updateUser({ email })` sends a confirmation link; once it is
 * opened the user is no longer anonymous. If the email already has an account,
 * this browser is marked as the owner of the anonymous user (signed cookie)
 * and gets a sign-in link to that account; the callback moves the pieces.
 */
export async function saveAccount(_prev: SaveAccountState, formData: FormData): Promise<SaveAccountState> {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const next = safeNext(formData.get("next"));
  if (!EMAIL_RE.test(email)) return { status: "error", message: "Enter a valid email address.", email };

  const current = await getCurrentUser();
  if (!current) return { status: "error", message: "Your session has expired. Reload the page and try again.", email };
  if (!current.user.is_anonymous) return { status: "error", message: "You're already signed in to an account.", email };

  const base = await origin();
  const supabase = await createServerClient();
  const { error } = await supabase.auth.updateUser({ email }, { emailRedirectTo: callbackUrl(base, next, true) });
  if (!error) return { status: "sent", email, existing: false };

  if (error.code === "email_exists" || /already (been )?registered/i.test(error.message)) {
    await setClaimCookie(current.user.id);
    const { error: otpError } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false, emailRedirectTo: callbackUrl(base, next, false) },
    });
    if (!otpError) return { status: "sent", email, existing: true };
    console.error("saveAccount: sign-in link for an existing account failed", otpError.message);
    return { status: "error", message: rateOrGeneric(otpError.status), email };
  }
  console.error("saveAccount: updateUser failed", error.code, error.message);
  return { status: "error", message: rateOrGeneric(error.status), email };
}

/** Before `linkIdentity` (Google) from an anonymous trial: if that Google account already has a user, the callback signs in to it and moves the trial's pieces. */
export async function prepareGoogleLink(): Promise<void> {
  const current = await getCurrentUser();
  if (current?.user.is_anonymous) await setClaimCookie(current.user.id);
}

function rateOrGeneric(status: number | undefined): string {
  return status === 429
    ? "You've requested several emails in a row. Wait a minute and try again."
    : "We couldn't send the email. Please try again in a few minutes.";
}
