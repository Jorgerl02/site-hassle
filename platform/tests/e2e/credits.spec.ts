import { expect, test } from "@playwright/test";
import {
  adminClient,
  createTestUser,
  deleteTestUser,
  grantPurchaseCredits,
  signIn,
  stripeConfigured,
  type TestUser,
} from "./helpers/credits-helpers";

test.describe("créditos", () => {
  const admin = adminClient();
  let user: TestUser | undefined;

  test.beforeEach(async ({ page }) => {
    user = await createTestUser(admin);
    await signIn(page, admin, user);
  });

  test.afterEach(async () => {
    await deleteTestUser(admin, user);
    user = undefined;
  });

  test("shows a zero balance and the three packs", async ({ page }) => {
    const response = await page.goto("/creditos");
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { level: 1, name: "Créditos" })).toBeVisible();
    await expect(page.getByTestId("credit-balance")).toHaveText("0");
    await expect(page.getByText("Todavía no hay movimientos.")).toBeVisible();

    await expect(page.getByTestId("pack-pieza_1")).toContainText("9 €");
    await expect(page.getByTestId("pack-pieza_10")).toContainText("69 €");
    await expect(page.getByTestId("pack-pieza_10")).toContainText("Más elegido");
    await expect(page.getByTestId("pack-pieza_10")).toContainText("6,90 € por pieza");
    await expect(page.getByTestId("pack-pieza_30")).toContainText("169 €");
    await expect(page.getByTestId("pack-pieza_30")).toContainText("5,63 € por pieza");
    await expect(page.getByText(/Sin reembolsos/)).toBeVisible();

    if (stripeConfigured()) {
      await expect(page.getByRole("button", { name: "Comprar" })).toHaveCount(3);
    } else {
      // Without Stripe keys the page must not break: buttons say so and stay disabled.
      const buttons = page.getByRole("button", { name: "Pagos no configurados" });
      await expect(buttons).toHaveCount(3);
      for (const button of await buttons.all()) await expect(button).toBeDisabled();
      await expect(page.getByRole("button", { name: "Comprar" })).toHaveCount(0);
    }
  });

  test("shows credits granted by the webhook path as a «Compra»", async ({ page }) => {
    expect(await grantPurchaseCredits(admin, user!.id, 10)).toBe(10);
    await page.goto("/creditos");
    await expect(page.getByTestId("credit-balance")).toHaveText("10");
    const entry = page.getByTestId("ledger-entry");
    await expect(entry).toHaveCount(1);
    await expect(entry).toContainText("Compra");
    await expect(entry).toContainText("+10");
  });
});

test("a signed-out visitor of /creditos is sent to /entrar", async ({ page }) => {
  await page.goto("/creditos");
  await expect(page).toHaveURL(/\/entrar$/);
});
