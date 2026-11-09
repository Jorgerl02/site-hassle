import { randomBytes } from "node:crypto";
import { expect, test } from "@playwright/test";
import type { SupabaseClient } from "@supabase/supabase-js";
import { serviceDb } from "./helpers/pieces-helpers";

// `claim_trial_slot` against the hosted database: the per-network cap holds under concurrency.
test("five concurrent anonymous pieces from one network get exactly three slots", async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Solo en escritorio");
  // Untyped: `database.types.ts` does not cover `trial_ips` and its functions.
  const db = serviceDb() as unknown as SupabaseClient;
  const ipHash = randomBytes(32).toString("hex");
  try {
    const results = await Promise.all(
      Array.from({ length: 5 }, () => db.rpc("claim_trial_slot", { p_ip_hash: ipHash, p_limit: 3 })),
    );
    for (const { error } of results) expect(error).toBeNull();
    const granted = results.map((r) => r.data).filter((id) => typeof id === "number");
    expect(granted).toHaveLength(3);

    // Giving one back frees a slot.
    expect((await db.rpc("release_trial_slot", { p_id: granted[0] as number })).error).toBeNull();
    expect(typeof (await db.rpc("claim_trial_slot", { p_ip_hash: ipHash, p_limit: 3 })).data).toBe("number");
    expect((await db.rpc("claim_trial_slot", { p_ip_hash: ipHash, p_limit: 3 })).data).toBeNull();
  } finally {
    await db.from("trial_ips").delete().eq("ip_hash", ipHash);
  }
});
