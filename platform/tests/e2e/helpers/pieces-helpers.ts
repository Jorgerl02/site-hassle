import { randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "../../../src/lib/database.types";

export type Db = SupabaseClient<Database>;

/** Playwright does not read Next's env files: load `.env.local` (never printed). */
function loadEnv(): void {
  const file = path.join(process.cwd(), ".env.local");
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY && existsSync(file)) process.loadEnvFile(file);
}

/** Service-role client, used here to play the worker and the admin. */
export function serviceDb(): Db {
  loadEnv();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Faltan NEXT_PUBLIC_SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env.local");
  return createClient<Database>(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

export interface PieceTestUser {
  id: string;
  email: string;
}

export async function createPieceTestUser(db: Db, label: string): Promise<PieceTestUser> {
  const email = `test_pieces_${label}_${randomUUID().slice(0, 8)}@example.com`;
  const { data, error } = await db.auth.admin.createUser({ email, email_confirm: true });
  if (error || !data.user) throw new Error(`createUser: ${error?.message}`);
  return { id: data.user.id, email };
}

/** Removes the user's Storage objects (no cascade there), then the user (cascades to rows). */
export async function deletePieceTestUser(db: Db, user: PieceTestUser | undefined): Promise<void> {
  if (!user) return;
  const { data: pieces } = await db.from("pieces").select("id").eq("user_id", user.id);
  for (const { id } of pieces ?? []) {
    const { data: photos } = await db.storage.from("photos").list(`${user.id}/${id}`);
    if (photos?.length) await db.storage.from("photos").remove(photos.map((o) => `${user.id}/${id}/${o.name}`));
    await db.storage.from("previews").remove([`${id}/1/model_preview.glb`]);
    await db.storage.from("models").remove([`${id}/1/model_web.glb`, `${id}/1/model.usdz`]);
  }
  await db.auth.admin.deleteUser(user.id);
}

type Cookies = Awaited<ReturnType<ReturnType<Page["context"]>["cookies"]>>;
const sessions = new Map<string, Cookies>();

/**
 * Signs the browser in without email: an admin magic link verified by the
 * app's `/auth/callback`. The session cookies are reused for the same user in
 * later tests (Auth rate-limits repeated links for one address).
 */
export async function signInAs(page: Page, db: Db, email: string): Promise<void> {
  const cached = sessions.get(email);
  if (cached) {
    await page.context().addCookies(cached);
    await page.goto("/panel");
    if (/\/panel(\?|$)/.test(page.url())) return;
  }
  // The hosted project shares Auth limits with the other suites running in
  // parallel: a link is occasionally refused, so try a fresh one.
  for (let attempt = 1; ; attempt++) {
    const { data, error } = await db.auth.admin.generateLink({ type: "magiclink", email });
    if (error || !data.properties?.hashed_token) throw new Error(`generateLink: ${error?.message}`);
    await page.goto(`/auth/callback?token_hash=${data.properties.hashed_token}&type=magiclink`);
    if (/\/panel(\?|$)/.test(page.url())) break;
    if (attempt === 4) throw new Error(`sign-in failed for ${email}: landed on ${page.url()}`);
    await page.waitForTimeout(10_000 * attempt); // 429 over_request_rate_limit on /verify
  }
  sessions.set(email, (await page.context().cookies()).filter((c) => c.name.startsWith("sb-")));
}

const PREVIEW_GLB = readFileSync(path.join(process.cwd(), "../tests/fixtures/platform/sample.glb"));

/**
 * Plays the worker and the internal review: uploads the attempt-1 files at
 * the worker's paths, inserts the selected `piece_models` row and moves the
 * piece to `ready`.
 */
export async function simulateWorkerReady(db: Db, pieceId: string): Promise<void> {
  const base = `${pieceId}/1`;
  const uploads = [
    db.storage.from("previews").upload(`${base}/model_preview.glb`, PREVIEW_GLB, { contentType: "model/gltf-binary", upsert: true }),
    db.storage.from("models").upload(`${base}/model_web.glb`, PREVIEW_GLB, { contentType: "model/gltf-binary", upsert: true }),
    db.storage.from("models").upload(`${base}/model.usdz`, Buffer.from("usdz"), { contentType: "model/vnd.usdz+zip", upsert: true }),
  ];
  for (const { error } of await Promise.all(uploads)) if (error) throw new Error(`upload: ${error.message}`);

  const { error: modelError } = await db.from("piece_models").insert({
    piece_id: pieceId,
    attempt: 1,
    provider: "e",
    candidate: 1,
    selected: true,
    preview_path: `${base}/model_preview.glb`,
    glb_path: `${base}/model_web.glb`,
    usdz_path: `${base}/model.usdz`,
    render_paths: null,
    max_error: 0.004,
  });
  if (modelError) throw new Error(`piece_models: ${modelError.message}`);
  const { error } = await db.from("pieces").update({ status: "ready", review_note: "test_internal_note" }).eq("id", pieceId);
  if (error) throw new Error(`pieces ready: ${error.message}`);
}

/** Pieces inserted by the service role count toward the user's daily quota. */
export async function fillDailyQuota(db: Db, user: PieceTestUser, count: number): Promise<void> {
  const rows = Array.from({ length: count }, (_, i) => ({
    user_id: user.id,
    name: `test_cupo_${i + 1}`,
    kind: "mesa" as const,
    width_cm: 100,
    height_cm: 75,
    depth_cm: 60,
    status: "rejected" as const,
  }));
  const { error } = await db.from("pieces").insert(rows);
  if (error) throw new Error(`fillDailyQuota: ${error.message}`);
}

export const P12_PNG = path.join(process.cwd(), "tests/fixtures/p12.png");
