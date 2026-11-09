import { expect, test, type Browser, type BrowserContextOptions, type Page } from "@playwright/test";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  cleanupPiece,
  createTestUser,
  deleteTestUser,
  seedReviewPiece,
  serviceClient,
  signIn,
  type SeededPiece,
  type TestUser,
} from "./helpers/admin-helpers";

// Hosted Supabase and Auth rate limits: one browser project, tests in order.
test.describe.configure({ mode: "serial", timeout: 120_000 });

let db: SupabaseClient;
let admin: TestUser;
let customer: TestUser;
const pieces: SeededPiece[] = [];
let adminState: BrowserContextOptions["storageState"];
let baseURL: string | undefined;

/**
 * One magic-link sign-in for the admin, reused by every test: repeated
 * verifications for the same user in a few seconds get refused by Auth.
 */
async function adminPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ storageState: adminState, baseURL, locale: "es-ES" });
  return context.newPage();
}

test.beforeAll(async ({ browser }, testInfo) => {
  // The review queue is a desktop tool; one project is enough (and spares Auth rate limits).
  test.skip(testInfo.project.name !== "desktop", "Solo en escritorio");
  db = serviceClient();
  admin = await createTestUser(db, "admin", true);
  customer = await createTestUser(db, "cliente");
  baseURL = testInfo.project.use.baseURL;
  const context = await browser.newContext({ baseURL });
  await signIn(await context.newPage(), db, admin.email);
  adminState = await context.storageState();
  await context.close();
});

test.afterAll(async () => {
  if (!db) return; // skipped project
  for (const piece of pieces) await cleanupPiece(db, piece);
  await deleteTestUser(db, admin);
  await deleteTestUser(db, customer);
});

test("signed-out and non-admin users get a 404", async ({ page }) => {
  expect((await page.goto("/admin/revision"))?.status()).toBe(404);
  await signIn(page, db, customer.email);
  expect((await page.goto("/admin/revision"))?.status()).toBe(404);
  expect((await page.goto(`/admin/revision/${crypto.randomUUID()}`))?.status()).toBe(404);
});

test("admin shows the second candidate to the customer", async ({ browser }) => {
  const piece = await seedReviewPiece(db, customer, `test_ Sillón revisión ${Date.now()}`);
  pieces.push(piece);
  const page = await adminPage(browser);

  const response = await page.goto("/admin/revision");
  expect(response?.status()).toBe(200);
  await expect(page.getByRole("heading", { level: 1, name: "Cola de revisión" })).toBeVisible();
  const item = page.getByTestId("queue-item").filter({ hasText: piece.name });
  await expect(item).toBeVisible();
  await expect(item).toContainText("82 × 76,5 × 80 cm");
  await expect(item).toContainText("Sillón");
  await expect(item).toContainText("Intento 1");
  await expect(item).toContainText("tripo");
  await expect(item).toContainText("Error máx. 2,1 %");
  await expect(item).toContainText(/Esperando \d+ min/);
  await expect(item.getByTestId("contact-sheet")).toHaveAttribute("src", /\/renders\/.*contact\.jpg\?token=/);

  await item.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/admin/revision/${piece.id}$`));
  await expect(page.getByRole("heading", { level: 1, name: piece.name })).toBeVisible();
  await expect(page.getByTestId("original-photo")).toHaveAttribute("src", /\/photos\/.*1\.png\?token=/);
  const candidates = page.getByTestId("candidate");
  await expect(candidates).toHaveCount(2);
  await expect(candidates.nth(0)).toContainText("tripo");
  await expect(candidates.nth(0).getByTestId("scale-errors")).toContainText("+2,1 %");
  await expect(candidates.nth(1).getByTestId("scale-errors")).toContainText("+1,1 %");
  // React 19 sets `src` as a property on the upgraded custom element, not as an attribute.
  const viewer = candidates.nth(1).locator("model-viewer");
  await expect(viewer).toBeAttached();
  expect(await viewer.evaluate((el) => (el as HTMLElement & { src: string }).src)).toMatch(
    /\/previews\/.*cand_2\/model_preview\.glb$/,
  );

  await page.getByLabel(/Candidato 2/).check();
  await page.getByRole("button", { name: "Mostrar al cliente" }).click();
  await expect(page).toHaveURL(/\/admin\/revision$/);
  await expect(page.getByTestId("queue-item").filter({ hasText: piece.name })).toHaveCount(0);

  const { data: row } = await db.from("pieces").select("status").eq("id", piece.id).single();
  expect(row?.status).toBe("ready");
  const { data: models } = await db.from("piece_models").select("id, selected, glb_path").eq("piece_id", piece.id);
  const selected = (models ?? []).filter((m) => m.selected);
  expect(selected.map((m) => m.id)).toEqual([piece.modelIds[1]]);
  expect(selected[0].glb_path).toBe(`${piece.id}/1/cand_2/model_web.glb`);
});

test("a candidate without USDZ cannot be shown to the customer", async ({ browser }) => {
  const piece = await seedReviewPiece(db, customer, `test_ Sillón sin USDZ ${Date.now()}`, { withoutUsdz: 2 });
  pieces.push(piece);
  const page = await adminPage(browser);
  await page.goto(`/admin/revision/${piece.id}`);

  const candidates = page.getByTestId("candidate");
  await expect(candidates.nth(1)).toContainText("Sin archivos descargables");
  await expect(page.getByLabel(/Candidato 1/)).toBeChecked();

  await page.getByLabel(/Candidato 2/).check();
  await page.getByRole("button", { name: "Mostrar al cliente" }).click();
  await expect(page.getByTestId("review-error")).toHaveText("Este candidato no tiene archivos descargables.");

  const { data: row } = await db.from("pieces").select("status").eq("id", piece.id).single();
  expect(row?.status).toBe("review");
  const { data: models } = await db.from("piece_models").select("id").eq("piece_id", piece.id).eq("selected", true);
  expect((models ?? []).map((m) => m.id)).toEqual([piece.modelIds[0]]);
});

test("reject needs a reason the customer will read", async ({ browser }) => {
  const piece = await seedReviewPiece(db, customer, `test_ Sillón rechazo ${Date.now()}`);
  pieces.push(piece);
  const page = await adminPage(browser);
  await page.goto(`/admin/revision/${piece.id}`);

  await page.getByRole("button", { name: "Rechazar" }).click();
  await expect(page.getByTestId("review-error")).toHaveText("Escribe el motivo: lo verá el cliente.");

  await page.getByLabel("Nota o motivo").fill("Las fotos no muestran el respaldo.");
  await page.getByRole("button", { name: "Rechazar" }).click();
  await expect(page).toHaveURL(/\/admin\/revision$/);
  const { data: row } = await db.from("pieces").select("status, reject_reason").eq("id", piece.id).single();
  expect(row).toEqual({ status: "rejected", reject_reason: "Las fotos no muestran el respaldo." });
});

test("regenerate saves the corrected shape and sends the piece back with the next attempt", async ({ browser }) => {
  const piece = await seedReviewPiece(db, customer, `test_ Sillón regenerar ${Date.now()}`);
  pieces.push(piece);
  // What a customer who never opened the optional details leaves.
  await db.from("pieces").update({ kind: "otro", rectilinear: null, support: "no_se" }).eq("id", piece.id);
  const page = await adminPage(browser);
  await page.goto(`/admin/revision/${piece.id}`);

  await page.getByLabel("Tipo").selectOption("aparador");
  await page.getByLabel("¿Pieza recta?").selectOption("si");
  await page.getByLabel("¿Cómo se apoya?").selectOption("patas");
  await page.getByLabel("Nota o motivo").fill("Patas demasiado gruesas.");
  await page.getByRole("button", { name: "Regenerar" }).click();
  await expect(page).toHaveURL(/\/admin\/revision$/);
  const { data: row } = await db
    .from("pieces")
    .select("status, attempt, review_note, kind, rectilinear, support")
    .eq("id", piece.id)
    .single();
  // Delete straight away so a running worker never picks the test piece up.
  await cleanupPiece(db, piece);
  expect(row).toEqual({
    status: "queued",
    attempt: 2,
    review_note: "Patas demasiado gruesas.",
    kind: "aparador",
    rectilinear: true,
    support: "patas",
  });
});

test("failed pieces: technical error, «Reintentar» on the same attempt and «Rechazar»", async ({ browser }) => {
  const retry = await seedReviewPiece(db, customer, `test_ Sillón fallido ${Date.now()}`);
  const reject = await seedReviewPiece(db, customer, `test_ Sillón fallido rechazo ${Date.now()}`);
  pieces.push(retry, reject);
  for (const piece of [retry, reject]) {
    const { error } = await db
      .from("pieces")
      .update({ status: "failed", error: "No se pudo generar ningún modelo: RuntimeError: proveedor caído" })
      .eq("id", piece.id);
    expect(error).toBeNull();
  }
  const page = await adminPage(browser);
  await page.goto("/admin/revision");

  const retryItem = page.getByTestId("failed-item").filter({ hasText: retry.name });
  await expect(retryItem.getByTestId("failed-error")).toContainText("proveedor caído");
  await retryItem.getByLabel("¿Pieza recta?").selectOption("no");
  await retryItem.getByLabel("Tipo").selectOption("silla");
  await retryItem.getByRole("button", { name: "Reintentar" }).click();
  // The action revalidates the page: the piece leaves the «Fallidas» list.
  await expect(retryItem).toHaveCount(0);

  const { data: retried } = await db
    .from("pieces")
    .select("status, attempt, error, kind, rectilinear, support")
    .eq("id", retry.id)
    .single();
  await cleanupPiece(db, retry); // a running worker must never pick the test piece up
  // Not straight: no support, as in the customer form.
  expect(retried).toEqual({ status: "queued", attempt: 1, error: null, kind: "silla", rectilinear: false, support: null });

  const rejectItem = page.getByTestId("failed-item").filter({ hasText: reject.name });
  await rejectItem.getByRole("button", { name: "Rechazar" }).click();
  await expect(rejectItem.getByTestId("failed-message")).toHaveText("Escribe el motivo: lo verá el cliente.");
  await rejectItem.getByLabel("Motivo del rechazo (lo leerá el cliente)").fill("No podemos generar esta pieza.");
  await rejectItem.getByRole("button", { name: "Rechazar" }).click();
  await expect(page.getByTestId("failed-item").filter({ hasText: reject.name })).toHaveCount(0);
  const { data: rejected } = await db.from("pieces").select("status, reject_reason").eq("id", reject.id).single();
  expect(rejected).toEqual({ status: "rejected", reject_reason: "No podemos generar esta pieza." });
});

test("the detail shows the customer's support answer", async ({ browser }) => {
  const piece = await seedReviewPiece(db, customer, `test_ Aparador apoyo ${Date.now()}`);
  pieces.push(piece);
  await db.from("pieces").update({ support: "paneles" }).eq("id", piece.id);
  const page = await adminPage(browser);
  await page.goto(`/admin/revision/${piece.id}`);
  await expect(page.getByTestId("piece-support")).toHaveText("Sobre paneles laterales");
});
