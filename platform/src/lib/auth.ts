import "server-only";
import type { User } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { cache } from "react";
import type { Profile } from "@/lib/database.types";
import { createServerClient } from "@/lib/supabase/server";

export interface CurrentUser {
  user: User;
  /** Created by the `handle_new_user` trigger; null only if the trigger has not run. */
  profile: Profile | null;
}

/** Signed-in user or null. Deduplicated per request. */
export const getCurrentUser = cache(async (): Promise<CurrentUser | null> => {
  const supabase = await createServerClient();
  // getUser() validates the token with Supabase Auth; never trust the cookie alone.
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;
  const { data: profile } = await supabase.from("profiles").select("*").eq("id", user.id).maybeSingle();
  return { user, profile };
});

/** For pages behind sign-in: redirects to /entrar when there is no session. */
export async function requireUser(): Promise<CurrentUser> {
  const current = await getCurrentUser();
  if (!current) redirect("/entrar");
  return current;
}
