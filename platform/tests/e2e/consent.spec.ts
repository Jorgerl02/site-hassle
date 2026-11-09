import { expect, test, type Page, type Request } from "@playwright/test";

// A fresh visitor: no stored choice (the config pre-stores «denied» for the other specs).
test.use({ storageState: { cookies: [], origins: [] } });

const THIRD_PARTY = /connect\.facebook\.net|googletagmanager\.com|google-analytics\.com|facebook\.com\/tr/;

/** Records (and answers locally) every request to Meta or Google: nothing leaves the machine. */
async function watchThirdParty(page: Page): Promise<Request[]> {
  const seen: Request[] = [];
  await page.route(THIRD_PARTY, (route) => {
    seen.push(route.request());
    return route.fulfill({ status: 200, contentType: "application/javascript", body: "" });
  });
  return seen;
}

test("no measurement script is requested before «Aceptar», and it loads after", async ({ page }) => {
  const seen = await watchThirdParty(page);
  await page.goto("/");
  const banner = page.getByTestId("cookie-consent");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Usamos cookies de medición para saber si los anuncios funcionan.");
  await expect(banner.getByRole("link", { name: "Privacidad y cookies" })).toHaveAttribute("href", "/privacidad");
  // lazyOnload scripts would start at idle: give them time to (not) appear.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1_500);
  expect(seen.map((r) => r.url())).toEqual([]);

  const loaded = page.waitForRequest(THIRD_PARTY);
  await banner.getByRole("button", { name: "Aceptar" }).click();
  await loaded;
  await expect(banner).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("sh_consent"))).toBe("granted");

  // Later visits: no banner, the scripts load from the stored choice.
  seen.length = 0;
  await page.reload();
  await page.waitForLoadState("networkidle");
  await expect.poll(() => seen.length, { timeout: 10_000 }).toBeGreaterThan(0);
  await expect(page.getByTestId("cookie-consent")).toHaveCount(0);
});

test("«Rechazar» keeps every measurement script away, also on later visits", async ({ page }) => {
  const seen = await watchThirdParty(page);
  await page.goto("/");
  await page.getByTestId("cookie-consent").getByRole("button", { name: "Rechazar" }).click();
  await expect(page.getByTestId("cookie-consent")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("sh_consent"))).toBe("denied");

  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1_500);
  await expect(page.getByTestId("cookie-consent")).toHaveCount(0);
  expect(seen.map((r) => r.url())).toEqual([]);
});

test("/privacidad explains the processors and lets the visitor change the choice", async ({ page }) => {
  await page.goto("/privacidad");
  await expect(page.getByRole("heading", { level: 1, name: "Privacidad y cookies" })).toBeVisible();
  await expect(page.getByText("Supabase")).toBeVisible();
  await expect(page.getByText("Stripe", { exact: false }).first()).toBeVisible();
  await page.getByTestId("cookie-consent").getByRole("button", { name: "Rechazar" }).click();
  await page.getByRole("button", { name: "Cambiar mi elección de cookies" }).click();
  await expect(page.getByTestId("cookie-consent")).toBeVisible();
});
