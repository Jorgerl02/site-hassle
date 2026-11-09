import { expect, test } from "@playwright/test";

test.describe("landing", () => {
  test("loads with English metadata and the main headline", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(/true-to-scale/);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("true to scale");
    await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /catalogue photo/);
    await expect(page.locator('meta[property="og:locale"]')).toHaveAttribute("content", "en_GB");
  });

  test("hydrates / and /entrar without a mismatch", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && /Hydration|418/.test(msg.text())) errors.push(msg.text());
    });
    page.on("pageerror", (error) => {
      if (/Hydration|#418/.test(error.message)) errors.push(error.message);
    });
    for (const path of ["/", "/entrar"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
    }
    expect(errors).toEqual([]);
    // Emotion's styles are flushed into <head>, never inline in <body>.
    await expect(page.locator("body style[data-emotion]")).toHaveCount(0);
  });

  test("sends anti-framing headers", async ({ request }) => {
    const response = await request.get("/");
    expect(response.headers()["x-frame-options"]).toBe("DENY");
    expect(response.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
  });

  test("shows the five sections", async ({ page }) => {

    await page.goto("/");
    for (const name of ["Real pieces, with their dimensions", "How it works", "Pricing", "Frequently asked questions"]) {
      await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
    }
    await expect(page.locator("#examples article")).toHaveCount(7);
  });

  test("primary CTA leads to /entrar", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Try a piece for free" }).click();
    await expect(page).toHaveURL(/\/entrar$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in with your email" })).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
  });

  test("pricing block shows the three packs", async ({ page }) => {
    await page.goto("/");
    const pricing = page.locator("#pricing");
    await expect(pricing.getByTestId("pack-pieza_1")).toContainText("€9");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("€69");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("Most popular");
    await expect(pricing.getByTestId("pack-pieza_10")).toContainText("€6.90 per piece");
    await expect(pricing.getByTestId("pack-pieza_30")).toContainText("€169");
    await expect(pricing.getByTestId("pack-pieza_30")).toContainText("€5.63 per piece");
  });

  test("model-viewer loads only when the examples scroll into view", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("model-viewer")).toHaveCount(0);
    await page.locator("#examples").scrollIntoViewIfNeeded();
    await expect(page.locator("model-viewer").first()).toBeAttached({ timeout: 15_000 });
    await expect(page.locator("model-viewer").first()).toHaveAttribute("ar-scale", "fixed");
    await expect(page.locator("model-viewer").first()).toHaveAttribute("ar-modes", "webxr scene-viewer quick-look");
    // The USDZ files are not deployed: Quick Look must derive them from the GLB.
    await expect(page.locator("model-viewer[ios-src]")).toHaveCount(0);
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
