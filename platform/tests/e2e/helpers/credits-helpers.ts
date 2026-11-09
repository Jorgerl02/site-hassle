import { existsSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Playwright does not read .env.local; the Next server under test does.
const ENV_FILE = path.resolve(__dirname, "../../../.env.local");
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

export function adminClient(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("E2E needs NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.local");
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
}

export interface TestUser {
  id: string;
  email: string;
}

/** Confirmed `test_*` user created with the service role (the profile comes from the trigger). */
export async function createTestUser(admin: SupabaseClient): Promise<TestUser> {
  const email = `test_credits_${Date.now()}_${Math.random().toString(36).slice(2, 8)}@example.com`;
  const { data, error } = await admin.auth.admin.createUser({ email, email_confirm: true });
  if (error || !data.user) throw new Error(`createUser: ${error?.message}`);
  return { id: data.user.id, email };
}

/** Deletes the user; profiles, ledger and purchases cascade. */
export async function deleteTestUser(admin: SupabaseClient, user: TestUser | undefined): Promise<void> {
  if (!user) return;
  await admin.auth.admin.deleteUser(user.id);
}

/** Signs the browser in through the app's own magic-link callback, without sending email. */
export async function signIn(page: Page, admin: SupabaseClient, user: TestUser): Promise<void> {
  const { data, error } = await admin.auth.admin.generateLink({ type: "magiclink", email: user.email });
  if (error || !data.properties?.hashed_token) throw new Error(`generateLink: ${error?.message}`);
  await page.goto(`/auth/callback?token_hash=${encodeURIComponent(data.properties.hashed_token)}&type=magiclink`);
  await page.waitForURL(/\/panel$/);
}

/** Same call the Stripe webhook makes: `grant_credits(user, n, 'purchase', session)`. */
export async function grantPurchaseCredits(admin: SupabaseClient, userId: string, credits: number): Promise<number> {
  const session = `cs_test_e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const { data, error } = await admin.rpc("grant_credits", {
    p_user: userId,
    p_delta: credits,
    p_reason: "purchase",
    p_session: session,
  });
  if (error) throw new Error(`grant_credits: ${error.message}`);
  return data as number;
}

export function stripeConfigured(): boolean {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}
