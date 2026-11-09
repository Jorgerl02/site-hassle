import { expect, test } from "@playwright/test";

test.describe("landing", () => {
  test("loads with Spanish metadata and the main headline", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(/escala real/);
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("a escala real");
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /foto de catálogo/);
    await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "es_ES");
  });

  test("shows the five sections", async ({ page }) => {
    await page.goto("/");
    for (const name of ["Piezas reales, con sus medidas", "Cómo funciona", "Precios", "Preguntas frecuentes"]) {
      await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
    }
    await expect(page.locator("#ejemplos article")).toHaveCount(7);
  });

  test("primary CTA leads to /entrar", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Prueba con una pieza gratis" }).click();
    await expect(page).toHaveURL(/\/entrar$/);
    await expect(page.getByRole("heading", { level: 1, name: "Entra con tu correo" })).toBeVisible();
    await expect(page.getByLabel("Correo electrónico")).toBeVisible();
  });

  test("pricing block shows the three packs", async ({ page }) => {
    await page.goto("/");
    const pricing = page.locator("#precios");
    await expect(pricing.getByTestId("pack-pieza_1")).toContainText("9 €");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("69 €");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("Más elegido");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("6,90 € por pieza");
    await expect(pricing.getByTestId("pack-pieza_30")).toContainText("169 €");
    await expect(pricing.getByTestId("pack-pieza_30")).toContainText("5,63 € por pieza");
  });

  test("model-viewer loads only when the examples scroll into view", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("model-viewer")).toHaveCount(0);
    await page.locator("#ejemplos").scrollIntoViewIfNeeded();
    await expect(page.locator("model-viewer").first()).toBeAttached({ timeout: 15_000 });
    await expect(page.locator("model-viewer").first()).toHaveAttribute("ar-scale", "fixed");
  });

  test("stores utm and ref in the attribution cookie", async ({ page, context }) => {
    await page.goto("/?utm_source=meta&utm_campaign=t1&ref=x");
    const cookie = (await context.cookies()).find((c) => c.name === "sh_attr");
    expect(cookie).toBeDefined();
    expect(cookie?.httpOnly).toBe(true);
    expect(JSON.parse(decodeURIComponent(cookie!.value))).toEqual({ utm_source: "meta", utm_campaign: "t1", ref: "x" });
  });

  test("panel redirects to /entrar without a session", async ({ page }) => {
    await page.goto("/panel");
    await expect(page).toHaveURL(/\/entrar$/);
  });

  // Regression guard: with Cache Components on, a hydration mismatch froze the
  // main thread a few seconds after load (see next.config.ts).
  test("stays responsive after hydration", async ({ page }) => {
    for (const path of ["/", "/entrar"]) {
      await page.goto(path);
      await page.waitForTimeout(5_000);
      const alive = await Promise.race([
        page.evaluate(() => "alive"),
        new Promise((resolve) => setTimeout(() => resolve("frozen"), 3_000)),
      ]);
      expect(alive, path).toBe("alive");
    }
  });
});
