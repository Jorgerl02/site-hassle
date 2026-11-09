import { expect, test } from "@playwright/test";

// The e2e build sets NEXT_PUBLIC_GOOGLE_AUTH_ENABLED=true; Google itself is never reached.
test("«Continue with Google» on /entrar starts the Supabase Google OAuth flow back to the callback", async ({ page }) => {
  await page.route(/\/auth\/v1\/authorize\?/, (route) => route.fulfill({ status: 200, contentType: "text/html", body: "<p>google</p>" }));
  await page.goto("/entrar");
  const button = page.getByRole("button", { name: "Continue with Google" });
  await expect(button).toBeVisible();
  const request = page.waitForRequest(/\/auth\/v1\/authorize\?/);
  await button.click();
  const url = new URL((await request).url());
  expect(url.searchParams.get("provider")).toBe("google");
  const redirect = new URL(url.searchParams.get("redirect_to")!);
  expect(redirect.pathname).toBe("/auth/callback");
  expect(redirect.searchParams.get("next")).toBe("/panel");
});

test("a Google account already linked to another user lands on /entrar with an explanation", async ({ page }) => {
  await page.goto("/auth/callback?error=server_error&error_code=identity_already_exists&next=/panel");
  await expect(page).toHaveURL(/\/entrar\?error=google$/);
  await expect(page.getByText("This Google account already has a Pieza 3D account.")).toBeVisible();
});

test("the callback never redirects off-site through `next`", async ({ page }) => {
  // No code/token: the callback fails, but must not follow `next` anywhere.
  await page.goto("/auth/callback?next=//evil.example/x");
  await expect(page).toHaveURL(/\/entrar\?error=enlace$/);
});
