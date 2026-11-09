"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { ATTRIBUTION_COOKIE, readAttributionCookie } from "@/lib/attribution";
import { createServerClient } from "@/lib/supabase/server";

export type SignInState =
  | { status: "idle" }
  | { status: "sent"; email: string }
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

export async function sendMagicLink(_prev: SignInState, formData: FormData): Promise<SignInState> {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!EMAIL_RE.test(email)) {
    return { status: "error", message: "Escribe un correo válido.", email };
  }

  const attribution = readAttributionCookie((await cookies()).get(ATTRIBUTION_COOKIE)?.value);
  const supabase = await createServerClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${await origin()}/auth/callback`,
      shouldCreateUser: true,
      // Copied to profiles.attribution by the handle_new_user trigger (first sign-up only).
      data: attribution ? { attribution } : undefined,
    },
  });

  if (error) {
    const message =
      error.status === 429
        ? "Has pedido varios enlaces seguidos. Espera un minuto y vuelve a intentarlo."
        : "No hemos podido enviar el enlace. Inténtalo de nuevo en unos minutos.";
    return { status: "error", message, email };
  }
  return { status: "sent", email };
}

export async function signOut(): Promise<void> {
  const supabase = await createServerClient();
  await supabase.auth.signOut();
  redirect("/");
}
