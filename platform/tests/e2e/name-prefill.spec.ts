import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { P12_PNG } from "./helpers/pieces-helpers";

// The form is open without a session; nothing is submitted here.
const photo = { name: "travertine-pedestal.png", mimeType: "image/png", buffer: readFileSync(P12_PNG) };

test("a photo dropped first prefills the name from its file name", async ({ page }) => {
  await page.goto("/piezas/nueva");
  await page.getByLabel("Add photos").setInputFiles(photo);
  await expect(page.getByRole("img", { name: /Photo 1: travertine-pedestal\.png/ })).toBeVisible();
  const name = page.getByLabel("Name", { exact: true });
  await expect(name).toHaveValue("Travertine pedestal");
  // Typing replaces it like any value; another photo never appends to it.
  await name.fill("Mesa Travertino");
  await page.getByLabel("Add photos").setInputFiles({ ...photo, name: "other-photo.png" });
  await expect(page.getByRole("img", { name: /Photo 2: other-photo\.png/ })).toBeVisible();
  await expect(name).toHaveValue("Mesa Travertino");
});

test("a name typed before the photo is never changed by it", async ({ page }) => {
  await page.goto("/piezas/nueva");
  const name = page.getByLabel("Name", { exact: true });
  await name.pressSequentially("test_ Mesa Travertino");
  await page.getByLabel("Add photos").setInputFiles(photo);
  await expect(page.getByRole("img", { name: /Photo 1: travertine-pedestal\.png/ })).toBeVisible();
  await expect(name).toHaveValue("test_ Mesa Travertino");
});
