import { execFile } from "node:child_process";
import { accessSync, constants, existsSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { expect, test, type Browser, type Page } from "@playwright/test";
import Stripe from "stripe";
import { createTestUser, deleteTestUser, signIn, type TestUser } from "./helpers/admin-helpers";
import {
  P12_PNG,
  createPieceTestUser,
  deletePieceTestUser,
  serviceDb,
  signInAs,
  type PieceTestUser,
} from "./helpers/pieces-helpers";

/**
 * The whole MVP once, with the real worker: sign-up → rectilinear piece from
 * the form with `p12.png` → `platform-worker run --once --provider fake`
 * (route E, real Blender) → published automatically (customer explicit
 * «cabecero» + «Yes», support read from the photo at 90 %, exact scale) → the
 * admin sees it under «Publicadas automáticamente», «Retirar» sends it back to
 * review and «Mostrar al cliente» publishes it again → free viewer (preview GLB
 * + iOS USDZ) → «Download» blocked without credits → a credit (Stripe webhook
 * when configured, else `grant_credits` by service role) → download, GLB and
 * USDZ answer 200.
 */
test.describe.configure({ mode: "serial", timeout: 420_000 });

const REPO_ROOT = path.resolve(process.cwd(), "..");
const WORKDIR = "runs/platform-e2e";
const PORT = Number(process.env.E2E_PORT ?? 3150);
const SECRET = process.env.E2E_WORKER_SECRET ?? "e2e-worker-secret";
const MAC_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender";
const run = promisify(execFile);

/** `HARNESS_BLENDER_TEST_BIN`, else `BLENDER_BIN` of the repo `.env`, else the macOS app. */
function blenderBin(): string | null {
  const fromEnvFile = (() => {
    const file = path.join(REPO_ROOT, ".env");
    if (!existsSync(file)) return undefined;
    return readFileSync(file, "utf8").match(/^BLENDER_BIN=(.*)$/m)?.[1]?.trim();
  })();
  for (const candidate of [process.env.HARNESS_BLENDER_TEST_BIN, process.env.BLENDER_BIN, fromEnvFile, MAC_BLENDER]) {
    if (!candidate) continue;
    try {
      accessSync(candidate, constants.X_OK);
      return candidate;
    } catch {
      // try the next one
    }
  }
  return null;
}

/** `STRIPE_WEBHOOK_SECRET` from the environment or `platform/.env.local` (what the server under test reads). */
function stripeWebhookSecret(): string | undefined {
  if (process.env.STRIPE_WEBHOOK_SECRET) return process.env.STRIPE_WEBHOOK_SECRET;
  const file = path.join(process.cwd(), ".env.local");
  if (!existsSync(file)) return undefined;
  return readFileSync(file, "utf8").match(/^STRIPE_WEBHOOK_SECRET=(.*)$/m)?.[1]?.trim() || undefined;
}

const db = serviceDb();
let customer: PieceTestUser | undefined;
let admin: TestUser | undefined;
let pieceId: string | undefined;
let adminPage: Page | undefined;

test.beforeAll(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Recorrido completo solo en escritorio");
  test.skip(!blenderBin(), "Sin Blender: define HARNESS_BLENDER_TEST_BIN o BLENDER_BIN");
  customer = await createPieceTestUser(db, "fullflow");
  admin = await createTestUser(db, "admin_fullflow", true);
});

test.afterAll(async () => {
  await adminPage?.context().close();
  if (pieceId) {
    // Worker outputs of every attempt/candidate: `{piece}/{attempt}/…` and `…/cand_n/…`.
    for (const bucket of ["previews", "models", "renders"]) {
      const { data: attempts } = await db.storage.from(bucket).list(pieceId);
      for (const attempt of attempts ?? []) {
        const prefix = `${pieceId}/${attempt.name}`;
        const { data: entries } = await db.storage.from(bucket).list(prefix);
        const files: string[] = [];
        for (const entry of entries ?? []) {
          if (entry.id) files.push(`${prefix}/${entry.name}`);
          else {
            const { data: nested } = await db.storage.from(bucket).list(`${prefix}/${entry.name}`);
            files.push(...(nested ?? []).map((n) => `${prefix}/${entry.name}/${n.name}`));
          }
        }
        if (files.length) await db.storage.from(bucket).remove(files);
      }
    }
    rmSync(path.join(REPO_ROOT, WORKDIR, pieceId), { recursive: true, force: true });
  }
  await deletePieceTestUser(db, customer); // photos + user (rows cascade)
  await deleteTestUser(db, admin);
});

async function signedInAdmin(browser: Browser): Promise<Page> {
  if (!adminPage) {
    adminPage = await (await browser.newContext()).newPage();
    await signIn(adminPage, db, admin!.email);
  }
  return adminPage;
}

test("the customer creates a straight piece from the form", async ({ page }) => {
  await signInAs(page, db, customer!.email);
  await page.goto("/piezas/nueva");
  await page.getByLabel("Add photos").setInputFiles(P12_PNG);
  await page.getByLabel("Name", { exact: true }).fill("test_ Cabecero recorrido completo");
  await page.getByLabel("Width").fill("165");
  await page.getByLabel("Height").fill("60");
  await page.getByLabel("Depth").fill("6");
  // Route E needs the shape: open the optional details.
  await page.getByText("Optional details (helps us get the shape right)").click();
  await page.getByLabel("Type").selectOption("cabecero");
  await page.getByText("Yes", { exact: true }).click();
  // The photo is read asynchronously (size, preview): submit only once it is listed.
  await expect(page.getByRole("img", { name: /Photo 1: p12\.png/ })).toBeVisible();
  await page.getByRole("button", { name: "Create piece" }).click();

  await expect(page).toHaveURL(/\/piezas\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  pieceId = page.url().split("/").pop()!;
  await expect(page.getByTestId("piece-status")).toHaveText("Queued");
});

test("the real worker publishes it automatically", async () => {
  expect(pieceId).toBeTruthy();
  // `run --once` claims the oldest queued piece of the whole project; if someone
  // else's piece is ahead in the queue, process ours by id instead.
  const { data: ahead } = await db
    .from("pieces")
    .select("id")
    .eq("status", "queued")
    .neq("id", pieceId!)
    .lte("created_at", new Date().toISOString());
  const args =
    ahead && ahead.length > 0
      ? ["run", "platform-worker", "piece", pieceId!, "--provider", "fake", "--workdir", WORKDIR]
      : ["run", "platform-worker", "run", "--once", "--provider", "fake", "--workdir", WORKDIR];

  const { stdout, stderr } = await run("uv", args, {
    cwd: REPO_ROOT,
    timeout: 360_000,
    maxBuffer: 16 * 1024 * 1024,
    env: {
      ...process.env,
      BLENDER_BIN: blenderBin()!,
      NOTIFY_URL: `http://localhost:${PORT}/api/internal/notify`,
      WORKER_SHARED_SECRET: SECRET,
    },
  });
  expect(stdout).toContain("→ estado ready");
  // The worker → web notice (customer «ready») was accepted (the server under test shares the secret).
  expect(stderr).not.toContain("No se pudo avisar a la web");

  const { data: piece } = await db.from("pieces").select("status, route, error, support").eq("id", pieceId!).single();
  // The support read from the photo lives in the model's meta, never in `pieces.support`.
  expect(piece).toMatchObject({ status: "ready", route: "E", error: null, support: "no_se" });
  const { data: models } = await db.from("piece_models").select("*").eq("piece_id", pieceId!);
  expect(models).toHaveLength(1);
  expect(models![0]).toMatchObject({
    selected: true,
    provider: "parametric",
    preview_path: `${pieceId}/1/model_preview.glb`,
    glb_path: `${pieceId}/1/model_web.glb`,
    usdz_path: `${pieceId}/1/model.usdz`,
  });
  expect(Number(models![0].max_error)).toBeLessThan(0.03);
  const meta = models![0].meta as {
    auto_review: { decision: string; gate: string };
    interpretation: { effective: { routing_kind: string }; source: Record<string, string> };
    deliver: { preview_usdz: boolean; warnings: string[] };
  };
  expect(meta.auto_review).toMatchObject({ decision: "auto", gate: "rules" });
  expect(meta.interpretation.effective.routing_kind).toBe("box");
  expect(meta.interpretation.source).toMatchObject({ kind: "customer", rectilinear: "customer", support: "inferred" });
  expect(meta.deliver).toMatchObject({ preview_usdz: true, warnings: [] });
  const usdz = await db.storage.from("previews").download(`${pieceId}/1/model_preview.usdz`);
  expect(usdz.error).toBeNull();
});

test("the admin withdraws it and shows it again", async ({ page, browser }) => {
  const adminTab = await signedInAdmin(browser);
  await adminTab.goto("/admin/revision");
  const item = adminTab.getByTestId("auto-published-item").filter({ hasText: "test_ Cabecero recorrido completo" });
  await expect(item).toContainText("Visible para el cliente");
  await expect(item.getByTestId("auto-published-reasons")).toContainText("Ruta E con escala exacta");
  await item.getByRole("button", { name: "Retirar" }).click();
  await expect(adminTab.getByTestId("queue-item").filter({ hasText: "test_ Cabecero recorrido completo" })).toBeVisible();

  // Withdrawn: the customer waits again, without the viewer.
  await signInAs(page, db, customer!.email);
  await page.goto(`/piezas/${pieceId}`);
  await expect(page.getByTestId("piece-status")).toHaveText("In review");
  await expect(page.locator("model-viewer")).toHaveCount(0);

  await adminTab.goto(`/admin/revision/${pieceId}`);
  await expect(adminTab.getByTestId("candidate")).toHaveCount(1);
  await expect(adminTab.getByTestId("auto-review-decision")).toHaveText("Publicada automáticamente (reglas)");
  await adminTab.getByRole("button", { name: "Mostrar al cliente" }).click();
  await expect(adminTab).toHaveURL(/\/admin\/revision$/);
  const { data: piece } = await db.from("pieces").select("status").eq("id", pieceId!).single();
  expect(piece?.status).toBe("ready");
});

test("the customer sees the free viewer and cannot download without credits", async ({ page }) => {
  await signInAs(page, db, customer!.email);
  await page.goto(`/piezas/${pieceId}`);
  await expect(page.getByTestId("piece-status")).toHaveText("Ready");
  const viewer = page.locator("model-viewer");
  await expect(viewer).toHaveAttribute("src", new RegExp(`/storage/v1/object/public/previews/${pieceId}/1/model_preview\\.glb$`));
  await expect(viewer).toHaveAttribute("ar-scale", "fixed");
  await expect(viewer).toHaveAttribute("ios-src", new RegExp(`/storage/v1/object/public/previews/${pieceId}/1/model_preview\\.usdz$`));
  const preview = await page.request.get((await viewer.getAttribute("src"))!);
  expect(preview.status()).toBe(200);
  const measures = page.getByTestId("measures");
  await expect(measures).toContainText("165 cm");
  await expect(measures).toContainText("60 cm");

  await page.getByRole("button", { name: "Download GLB + USDZ (1 credit)" }).click();
  await expect(page.getByTestId("packs-dialog")).toBeVisible();
  await page.getByRole("button", { name: "Not now" }).click();
  const { data: piece } = await db.from("pieces").select("status").eq("id", pieceId!).single();
  expect(piece?.status).toBe("ready");
});

test("with a credit the customer downloads the GLB and the USDZ", async ({ page, request }) => {
  const webhookSecret = stripeWebhookSecret();
  if (webhookSecret) {
    // Stripe configured: a signed `checkout.session.completed` through the real webhook route.
    const payload = JSON.stringify({
      id: `evt_test_fullflow_${Date.now()}`,
      object: "event",
      type: "checkout.session.completed",
      data: {
        object: {
          id: `cs_test_fullflow_${Date.now()}`,
          object: "checkout.session",
          mode: "payment",
          payment_status: "paid",
          client_reference_id: customer!.id,
          amount_total: 900,
          currency: "eur",
          metadata: { pack: "pieza_1", credits: "1" },
        },
      },
    });
    const signature = Stripe.webhooks.generateTestHeaderString({ payload, secret: webhookSecret });
    const response = await request.post("/api/stripe/webhook", {
      data: payload,
      headers: { "content-type": "application/json", "stripe-signature": signature },
    });
    expect(response.status()).toBe(200);
  } else {
    const { error } = await db.rpc("grant_credits", { p_user: customer!.id, p_delta: 1, p_reason: "grant" });
    expect(error).toBeNull();
  }

  await signInAs(page, db, customer!.email);
  await page.goto(`/piezas/${pieceId}`);
  await page.getByRole("button", { name: "Download GLB + USDZ (1 credit)" }).click();
  await page.getByRole("button", { name: "Use 1 credit and download" }).click();
  await expect(page.getByTestId("piece-status")).toHaveText("Downloaded", { timeout: 15_000 });

  for (const name of ["Download GLB", "Download USDZ"]) {
    const href = await page.getByRole("link", { name }).getAttribute("href");
    expect(href).toMatch(new RegExp(`/storage/v1/object/sign/models/${pieceId}/1/`));
    const file = await page.request.get(href!);
    expect(file.status()).toBe(200);
    expect((await file.body()).byteLength).toBeGreaterThan(1_000);
  }
  const { data: balance } = await db.rpc("credit_balance", { p_user: customer!.id });
  expect(balance).toBe(0);
  const { data: piece } = await db.from("pieces").select("status").eq("id", pieceId!).single();
  expect(piece?.status).toBe("approved");
});
