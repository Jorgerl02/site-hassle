import { expect, test } from "@playwright/test";
import {
  P12_PNG,
  createPieceTestUser,
  deletePieceTestUser,
  fillDailyQuota,
  serviceDb,
  signInAs,
  simulateWorkerReady,
  type PieceTestUser,
} from "./helpers/pieces-helpers";

// One customer journey against the hosted Supabase project: the steps share
// users and a piece, so they run in order.
test.describe.configure({ mode: "serial" });

const db = serviceDb();
let owner: PieceTestUser;
let other: PieceTestUser;
let pieceId: string;

test.beforeAll(async ({}, testInfo) => {
  const tag = testInfo.project.name;
  owner = await createPieceTestUser(db, `a_${tag}`);
  other = await createPieceTestUser(db, `b_${tag}`);
});

test.afterAll(async () => {
  await deletePieceTestUser(db, owner);
  await deletePieceTestUser(db, other);
});

test("creates a piece from the form and shows it queued", async ({ page }) => {
  // W4: the panel hydrates without a mismatch (Emotion styles go to the head).
  const hydrationErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Hydration|#418|418/.test(msg.text())) hydrationErrors.push(msg.text());
  });
  page.on("pageerror", (error) => {
    if (/Hydration|#418/.test(error.message)) hydrationErrors.push(error.message);
  });
  await signInAs(page, db, owner.email);
  await page.waitForLoadState("networkidle");
  expect(hydrationErrors).toEqual([]);
  await page.getByRole("link", { name: "Nueva pieza" }).click();
  await expect(page).toHaveURL(/\/piezas\/nueva$/);

  // Client-side validation runs before anything is uploaded.
  await page.getByRole("button", { name: "Crear pieza" }).click();
  await expect(page.getByText("Añade al menos una foto.")).toBeVisible();

  await page.getByLabel("Nombre de la pieza").fill("Cabecero Rigole");
  await page.getByLabel("Tipo").selectOption("cabecero");
  await page.getByLabel("Ancho").fill("165");
  await page.getByLabel("Alto").fill("60");
  await page.getByLabel("Fondo").fill("6,5");
  await page.getByText("Sí", { exact: true }).click();
  await page.getByText("Sobre paneles laterales", { exact: true }).click();
  await page.getByLabel("Añadir fotos").setInputFiles(P12_PNG);
  await expect(page.getByRole("img", { name: /Foto 1: p12\.png/ })).toBeVisible();
  await page.getByRole("button", { name: "Crear pieza" }).click();

  await expect(page).toHaveURL(/\/piezas\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  pieceId = page.url().split("/").pop()!;
  await expect(page.getByRole("heading", { level: 1, name: "Cabecero Rigole" })).toBeVisible();
  await expect(page.getByTestId("piece-status")).toHaveText("En cola");
  await expect(page.getByRole("list", { name: "Progreso de la pieza" })).toBeVisible();

  const { data: piece } = await db.from("pieces").select("*").eq("id", pieceId).single();
  expect(piece).toMatchObject({
    user_id: owner.id,
    kind: "cabecero",
    depth_cm: 6.5,
    rectilinear: true,
    support: "paneles",
  });

  // The worker never sees a piece without photos: the rows exist next to the piece.
  const { data: photos } = await db.from("piece_photos").select("storage_path").eq("piece_id", pieceId);
  expect(photos).toEqual([{ storage_path: `${owner.id}/${pieceId}/1.png` }]);
});

test("shows the free viewer with the measures once the piece is ready", async ({ page }) => {
  await simulateWorkerReady(db, pieceId);
  await signInAs(page, db, owner.email);
  await page.goto(`/piezas/${pieceId}`);

  await expect(page.getByTestId("piece-status")).toHaveText("Lista");
  const viewer = page.locator("model-viewer");
  await expect(viewer).toHaveAttribute("src", new RegExp(`/storage/v1/object/public/previews/${pieceId}/1/model_preview\\.glb$`));
  await expect(viewer).toHaveAttribute("ar-scale", "fixed");
  await expect(viewer).not.toHaveAttribute("ios-src", /.*/);
  const measures = page.getByTestId("measures");
  await expect(measures).toContainText("165 cm");
  await expect(measures).toContainText("60 cm");
  await expect(measures).toContainText("6,5 cm");
  // Internal review notes never reach the customer.
  await expect(page.getByText("test_internal_note")).toHaveCount(0);
});

test("asks for a credit, then downloads with one", async ({ page }) => {
  await signInAs(page, db, owner.email);
  await page.goto(`/piezas/${pieceId}`);

  await page.getByRole("button", { name: "Descargar (1 crédito)" }).click();
  await expect(page.getByText("Necesitas 1 crédito")).toBeVisible();
  await expect(page.getByRole("link", { name: "Comprar créditos" }).last()).toHaveAttribute("href", "/creditos");

  const { error } = await db.rpc("grant_credits", { p_user: owner.id, p_delta: 1, p_reason: "grant" });
  expect(error).toBeNull();
  await page.reload();
  await page.getByRole("button", { name: "Descargar (1 crédito)" }).click();
  await page.getByRole("button", { name: "Usar 1 crédito y descargar" }).click();

  await expect(page.getByTestId("piece-status")).toHaveText("Descargada", { timeout: 15_000 });
  const glb = page.getByRole("link", { name: "Descargar GLB" });
  const usdz = page.getByRole("link", { name: "Descargar USDZ" });
  await expect(glb).toHaveAttribute("href", new RegExp(`/storage/v1/object/sign/models/${pieceId}/1/model_web\\.glb\\?token=`));
  await expect(usdz).toHaveAttribute("href", new RegExp(`/storage/v1/object/sign/models/${pieceId}/1/model\\.usdz\\?token=`));
  const download = await page.request.get((await glb.getAttribute("href"))!);
  expect(download.status()).toBe(200);

  const { data: balance } = await db.rpc("credit_balance", { p_user: owner.id });
  expect(balance).toBe(0);
  await page.goto("/panel");
  await expect(page.getByTestId("balance")).toContainText("Créditos: 0");
  const card = page.getByTestId("piece-card").first();
  await expect(card).toContainText("Descargada");
  // Thumbnail uploaded by the form next to the photos, signed for the owner.
  await expect(card.locator("img")).toHaveAttribute("src", new RegExp(`/object/sign/photos/${owner.id}/${pieceId}/thumb\\.jpg`));
});

test("another user gets a 404 for the piece", async ({ page }) => {
  await signInAs(page, db, other.email);
  const response = await page.goto(`/piezas/${pieceId}`);
  expect(response?.status()).toBe(404);
  await expect(page.getByText("Cabecero Rigole")).toHaveCount(0);
});

test("stops at the daily limit", async ({ page }) => {
  await fillDailyQuota(db, other, 3);
  await signInAs(page, db, other.email);
  await page.goto("/piezas/nueva");
  await expect(page.getByText("Has llegado a las 3 piezas de hoy")).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear pieza" })).toHaveCount(0);
});
