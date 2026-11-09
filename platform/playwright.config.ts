import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 3150);

/**
 * Secret shared by the e2e web server and the worker launched by
 * `full-flow.spec.ts`, so the worker → web notice is exercised for real.
 */
export const E2E_WORKER_SECRET = process.env.E2E_WORKER_SECRET ?? "e2e-worker-secret";
process.env.E2E_WORKER_SECRET = E2E_WORKER_SECRET;

/**
 * The e2e build has measurement ids (fake unless real ones are exported) so
 * the cookie banner exists; `consent.spec.ts` checks that nothing loads
 * before «Aceptar». Every other spec starts with `sh_consent=denied` stored,
 * so the banner never covers the page (the third-party scripts never load).
 */
const E2E_META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID || "000000000000000";
const E2E_GA_ID = process.env.NEXT_PUBLIC_GA_ID || "G-E2ETEST000";
const BASE_URL = `http://localhost:${PORT}`;
export const CONSENT_DENIED_STATE = {
  cookies: [],
  origins: [
    {
      origin: BASE_URL,
      localStorage: [
        { name: "sh_consent", value: "denied" },
        { name: "sh_consent_at", value: String(Date.now()) },
      ],
    },
  ],
};

export default defineConfig({
  testDir: "tests/e2e",
  // Every suite signs users in against the hosted Supabase project, whose Auth
  // answers 429 on /verify when many sign-ins arrive at once: run serially.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    locale: "es-ES",
    storageState: CONSENT_DENIED_STATE,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    // One production server on a fixed port for every spec: the landing must
    // pass against the real build. Reused when one is already listening.
    command: `pnpm build && pnpm start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: {
      ...(process.env as Record<string, string>),
      WORKER_SHARED_SECRET: E2E_WORKER_SECRET,
      // Never email real people from a test run, even with a key in .env.local.
      RESEND_API_KEY: "",
      NEXT_PUBLIC_META_PIXEL_ID: E2E_META_PIXEL_ID,
      NEXT_PUBLIC_GA_ID: E2E_GA_ID,
      // The Google button is built in so its wiring is tested; the OAuth request itself is intercepted
      // (`google-auth.spec.ts`). Without the flag the button is absent (unit test `google-auth.test.ts`).
      NEXT_PUBLIC_GOOGLE_AUTH_ENABLED: "true",
      // Every run creates anonymous pieces from localhost: don't trip the per-network trial cap.
      TRIAL_IP_DAILY_LIMIT: "1000",
    },
  },
});
