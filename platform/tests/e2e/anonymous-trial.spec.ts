import { expect, test, type Page } from "@playwright/test";
import { isBoundClaim, signClaim, signDownloadMarker } from "../../src/lib/claim-token";
import {
  P12_PNG,
  createPieceTestUser,
  deletePieceTestUser,
  serviceDb,
  signInAs,
  simulateWorkerReady,
  type PieceTestUser,
} from "./helpers/pieces-helpers";

// Anonymous free trial against the hosted project: one journey, in order.
// Desktop only: every run creates anonymous Auth users (rate-limited per IP).
test.describe.configure({ mode: "serial" });

const db = serviceDb();
const SECRET = process.env.CLAIM_SECRET?.trim() || process.env.SUPABASE_SERVICE_ROLE_KEY!;
let anonymousId: string;
let pieceId: string;
const users: PieceTestUser[] = [];

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo en escritorio");
});

test.afterAll(async () => {
  for (const user of users) await deletePieceTestUser(db, user);
  if (anonymousId) await deletePieceTestUser(db, { id: anonymousId, email: "" });
});

async function createPieceFromLanding(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("main").getByRole("link", { name: "Turn a photo into a 3D model" }).first().click();
  await expect(page).toHaveURL(/\/piezas\/nueva\?source=landing_hero$/);
  await page.getByLabel("Add photos").setInputFiles(P12_PNG);
  await page.getByLabel("Name", { exact: true }).fill(name);
  await page.getByLabel("Width").fill("165");
  await page.getByLabel("Height").fill("60");
  await page.getByLabel("Depth").fill("6");
  await page.getByRole("button", { name: "Create piece" }).click();
  await expect(page).toHaveURL(/\/piezas\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  return page.url().split("/").pop()!;
}

test("a visitor creates a piece without an email", async ({ page }) => {
  pieceId = await createPieceFromLanding(page, "test_ Anonymous headboard");
  await expect(page.getByTestId("piece-status")).toHaveText("Queued");
  // The optional «save this piece» card while it generates; the header only offers «Log in».
  await expect(page.getByTestId("save-account-card")).toContainText("Save this piece and get an email when it's ready");
  await expect(page.getByRole("link", { name: "Log in" })).toBeVisible();

  const { data: piece } = await db.from("pieces").select("user_id").eq("id", pieceId).single();
  anonymousId = piece!.user_id;
  const { data: auth } = await db.auth.admin.getUserById(anonymousId);
  expect(auth.user?.is_anonymous).toBe(true);
  expect(auth.user?.email ?? "").toBe("");
  const { data: profile } = await db.from("profiles").select("attribution").eq("id", anonymousId).single();
  expect(profile?.attribution).toMatchObject({ source: "landing_hero" });
});

test("anonymous trials get one piece a day", async ({ page }) => {
  await signInAnonymousCookies(page);
  await page.goto("/piezas/nueva");
  await expect(page.getByText("You've used today's free piece")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create piece" })).toHaveCount(0);
});

test("download asks an anonymous trial to save the account first", async ({ page }) => {
  await simulateWorkerReady(db, pieceId, { previewUsdz: true });
  await signInAnonymousCookies(page);
  await page.goto(`/piezas/${pieceId}`);
  await expect(page.getByTestId("piece-status")).toHaveText("Ready");
  // The worker's preview USDZ goes to iOS Quick Look as `ios-src`.
  await expect(page.locator("model-viewer")).toHaveAttribute(
    "ios-src",
    new RegExp(`/storage/v1/object/public/previews/${pieceId}/1/model_preview\\.usdz$`),
  );
  await page.getByRole("button", { name: "Download GLB + USDZ (1 credit)" }).click();
  const dialog = page.getByTestId("signup-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Email")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Create my account" })).toBeVisible();
  // Google first, above the email (the e2e build has NEXT_PUBLIC_GOOGLE_AUTH_ENABLED=true).
  await expect(dialog.getByRole("button", { name: "Continue with Google" })).toBeVisible();
});

test("converting the trial keeps the same user and piece, then the pack modal and auto-download", async ({ page }) => {
  // Plays the confirmation link of `updateUser({ email })`: same id, now with an email.
  const email = `test_pieces_anon_${anonymousId.slice(0, 8)}@example.com`;
  const { data: updated, error } = await db.auth.admin.updateUserById(anonymousId, { email, email_confirm: true });
  expect(error).toBeNull();
  expect(updated.user?.is_anonymous).toBe(false);
  const { data: profile } = await db.from("profiles").select("email").eq("id", anonymousId).single();
  expect(profile?.email).toBe(email); // synced by the auth.users trigger

  await signInAs(page, db, email);
  await page.goto(`/piezas/${pieceId}`);
  await expect(page.getByRole("heading", { level: 1, name: "test_ Anonymous headboard" })).toBeVisible();
  await expect(page.getByTestId("header-credits")).toContainText("0 credits");

  // Out of credits: the three packs, 10 highlighted, price per piece.
  await page.getByRole("button", { name: "Download GLB + USDZ (1 credit)" }).click();
  const packs = page.getByTestId("packs-dialog");
  await expect(packs).toBeVisible();
  await expect(packs.getByTestId("modal-pack-pieza_10")).toContainText("Most popular");
  await expect(packs.getByTestId("modal-pack-pieza_10")).toContainText("€6.90");
  await expect(packs.getByTestId("modal-pack-pieza_30")).toContainText("€5.63");
  await expect(packs).toContainText("Used credits are non-refundable · unused credits never expire.");

  expect((await db.rpc("grant_credits", { p_user: anonymousId, p_delta: 1, p_reason: "grant" })).error).toBeNull();
  // A bare `?download=1` (bookmark, shared link) never spends by itself: it asks first.
  await page.goto(`/piezas/${pieceId}?download=1`);
  await expect(page.getByRole("button", { name: "Use 1 credit and download" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByTestId("piece-status")).toHaveText("Ready");

  // A forged `registro=1` does not spend either.
  await page.goto(`/piezas/${pieceId}?download=1&registro=1`);
  await expect(page.getByRole("button", { name: "Use 1 credit and download" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  // Right after sign-up the callback leaves a one-shot marker for this piece: downloads without another click.
  await page.context().addCookies([
    {
      name: "sh_dl",
      value: signDownloadMarker(pieceId, anonymousId, SECRET),
      domain: "localhost",
      path: `/piezas/${pieceId}`,
      httpOnly: true,
    },
  ]);
  const download = page.waitForEvent("download");
  await page.goto(`/piezas/${pieceId}?download=1`);
  await expect(page.getByTestId("piece-status")).toHaveText("Downloaded", { timeout: 15_000 });
  await expect(page.getByTestId("auto-download")).toBeVisible();
  expect((await download).suggestedFilename()).toMatch(/\.glb$/);
  await expect(page).toHaveURL(new RegExp(`/piezas/${pieceId}$`));
  // The marker was consumed.
  expect((await page.context().cookies()).some((c) => c.name === "sh_dl")).toBe(false);
  users.push({ id: anonymousId, email });
  anonymousId = "";
});

test("an existing account claims an anonymous trial's piece on sign-in", async ({ browser }) => {
  const account = await createPieceTestUser(db, "claim");
  users.push(account);
  const context = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  const claimed = await createPieceFromLanding(page, "test_ Claimed headboard");
  const { data: before } = await db.from("pieces").select("user_id").eq("id", claimed).single();
  const trial = before!.user_id;
  users.push({ id: trial, email: "" });

  // What «email already registered» leaves in the browser, then the sign-in link of that account.
  await context.addCookies([{ name: "sh_claim", value: signClaim(trial, SECRET), domain: "localhost", path: "/", httpOnly: true }]);
  await signInAs(page, db, account.email);

  // Still queued: the worker reads its photos by the trial's path, so it stays with the trial
  // and the claim is kept, bound to this account, for its next sign-in.
  expect((await db.from("pieces").select("user_id").eq("id", claimed).single()).data?.user_id).toBe(trial);
  const pending = (await context.cookies()).find((c) => c.name === "sh_claim");
  expect(pending && isBoundClaim(pending.value)).toBe(true);
  await page.goto("/panel"); // a bound claim survives the account pages
  expect((await context.cookies()).some((c) => c.name === "sh_claim")).toBe(true);

  // Once it is ready, the next sign-in of that account moves it.
  await simulateWorkerReady(db, claimed);
  const { data: link } = await db.auth.admin.generateLink({ type: "magiclink", email: account.email });
  await page.goto(`/auth/callback?token_hash=${link.properties!.hashed_token}&type=magiclink`);
  await expect(page).toHaveURL(/\/panel(\?|$)/);

  const { data: after } = await db.from("pieces").select("user_id").eq("id", claimed).single();
  expect(after?.user_id).toBe(account.id);
  const { data: photos } = await db.from("piece_photos").select("storage_path").eq("piece_id", claimed);
  expect(photos).toEqual([{ storage_path: `${account.id}/${claimed}/1.png` }]);
  const { data: objects } = await db.storage.from("photos").list(`${account.id}/${claimed}`);
  expect(objects?.map((o) => o.name)).toContain("1.png");
  const { data: left } = await db.storage.from("photos").list(`${trial}/${claimed}`);
  expect(left ?? []).toEqual([]);
  await page.goto("/panel");
  await expect(page.getByTestId("piece-card").filter({ hasText: "test_ Claimed headboard" })).toHaveCount(1);
  await context.close();
});

/** Each test gets a fresh context and an anonymous user has no email for a magic link: reuse the first test's session cookies. */
async function signInAnonymousCookies(page: Page): Promise<void> {
  const cookies = anonymousCookies;
  if (!cookies) throw new Error("no anonymous session yet");
  await page.context().addCookies(cookies);
}

let anonymousCookies: Awaited<ReturnType<ReturnType<Page["context"]>["cookies"]>> | null = null;
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.title === "a visitor creates a piece without an email") {
    anonymousCookies = (await page.context().cookies()).filter((c) => c.name.startsWith("sb-"));
  }
});
