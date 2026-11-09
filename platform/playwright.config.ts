import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT ?? 3150);

/**
 * Secret shared by the e2e web server and the worker launched by
 * `full-flow.spec.ts`, so the worker → web notice is exercised for real.
 */
export const E2E_WORKER_SECRET = process.env.E2E_WORKER_SECRET ?? "e2e-worker-secret";
process.env.E2E_WORKER_SECRET = E2E_WORKER_SECRET;

export default defineConfig({
  testDir: "tests/e2e",
  // Every suite signs users in against the hosted Supabase project, whose Auth
  // answers 429 on /verify when many sign-ins arrive at once: run serially.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: "es-ES",
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
    env: { ...(process.env as Record<string, string>), WORKER_SHARED_SECRET: E2E_WORKER_SECRET },
  },
});
