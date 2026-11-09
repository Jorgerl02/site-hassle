import Stripe from "stripe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { handleStripeEvent, type FulfillmentDeps, type PurchaseRecord } from "@/lib/stripe";

// The route imports server-only modules; neutralise them for the node test runner.
vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase/admin", () => ({
  createAdminClient: () => {
    throw new Error("the admin client must not be reached with an invalid signature");
  },
}));

/** In-memory stand-in for `purchases` + `grant_credits` (idempotent by session id, like the SQL). */
function fakeDb() {
  const purchases = new Map<string, PurchaseRecord>();
  const ledger: { userId: string; delta: number; sessionId: string }[] = [];
  const deps: FulfillmentDeps = {
    async recordPurchase(record) {
      if (!purchases.has(record.sessionId)) purchases.set(record.sessionId, record);
    },
    async grantCredits(userId, credits, sessionId) {
      if (!ledger.some((e) => e.sessionId === sessionId)) ledger.push({ userId, delta: credits, sessionId });
      return ledger.filter((e) => e.userId === userId).reduce((sum, e) => sum + e.delta, 0);
    },
  };
  const balance = (userId: string) => ledger.filter((e) => e.userId === userId).reduce((s, e) => s + e.delta, 0);
  return { deps, purchases, ledger, balance };
}

function checkoutEvent(
  overrides: Partial<Stripe.Checkout.Session> = {},
  type: string = "checkout.session.completed",
): Stripe.Event {
  return {
    id: "evt_test_1",
    object: "event",
    type,
    data: {
      object: {
        id: "cs_test_123",
        object: "checkout.session",
        mode: "payment",
        payment_status: "paid",
        status: "complete",
        client_reference_id: "11111111-1111-1111-1111-111111111111",
        metadata: { pack: "pieza_10", credits: "10" },
        amount_total: 6900,
        currency: "eur",
        ...overrides,
      },
    },
  } as unknown as Stripe.Event;
}

const USER = "11111111-1111-1111-1111-111111111111";

describe("handleStripeEvent", () => {
  let db: ReturnType<typeof fakeDb>;
  beforeEach(() => {
    db = fakeDb();
  });

  it("grants the pack credits once and records the purchase", async () => {
    const result = await handleStripeEvent(checkoutEvent(), db.deps);
    expect(result.handled).toBe(true);
    expect(db.balance(USER)).toBe(10);
    expect(db.purchases.get("cs_test_123")).toEqual({
      userId: USER,
      sessionId: "cs_test_123",
      pack: "pieza_10",
      credits: 10,
      amountCents: 6900,
      status: "paid",
    });
  });

  it("does not grant twice for the same session (webhook retried)", async () => {
    await handleStripeEvent(checkoutEvent(), db.deps);
    const again = await handleStripeEvent(checkoutEvent(), db.deps);
    expect(again.handled).toBe(true);
    expect(db.balance(USER)).toBe(10);
    expect(db.ledger).toHaveLength(1);
    expect(db.purchases.size).toBe(1);
  });

  it("takes the credits from the pack, not from the metadata", async () => {
    await handleStripeEvent(checkoutEvent({ metadata: { pack: "pieza_1", credits: "999" } }), db.deps);
    expect(db.balance(USER)).toBe(1);
  });

  it("ignores other event types", async () => {
    const result = await handleStripeEvent(checkoutEvent({}, "payment_intent.succeeded"), db.deps);
    expect(result.handled).toBe(false);
    expect(db.ledger).toHaveLength(0);
  });

  it("waits for the money when the session is completed but unpaid", async () => {
    const result = await handleStripeEvent(checkoutEvent({ payment_status: "unpaid" }), db.deps);
    expect(result.handled).toBe(false);
    expect(db.ledger).toHaveLength(0);
  });

  it("grants on async_payment_succeeded (delayed payment methods)", async () => {
    const result = await handleStripeEvent(checkoutEvent({}, "checkout.session.async_payment_succeeded"), db.deps);
    expect(result.handled).toBe(true);
    expect(db.balance(USER)).toBe(10);
  });

  it("refuses paid sessions without a user or with an unknown pack, logging them as errors", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const noUser = await handleStripeEvent(checkoutEvent({ client_reference_id: null }), db.deps);
      expect(noUser).toEqual({ handled: false, reason: "no_user" });
      const unknown = await handleStripeEvent(checkoutEvent({ metadata: { pack: "pieza_99" } }), db.deps);
      expect(unknown).toEqual({ handled: false, reason: "unknown_pack" });
      expect(db.ledger).toHaveLength(0);
      expect(log).toHaveBeenCalledTimes(2);
      for (const [message] of log.mock.calls) {
        expect(message).toContain("cs_test_123");
        expect(message).toContain("amount_total=6900");
      }
    } finally {
      log.mockRestore();
    }
  });

  it("grants but flags a paid amount that does not match the pack price", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const result = await handleStripeEvent(checkoutEvent({ amount_total: 100 }), db.deps);
      expect(result.handled).toBe(true);
      expect(db.balance(USER)).toBe(10);
      expect(log).toHaveBeenCalledOnce();
      expect(log.mock.calls[0][0]).toMatch(/cs_test_123 amount mismatch: amount_total=100, pieza_10 costs 6900/);
    } finally {
      log.mockRestore();
    }
  });

  it("does not log when the amount matches", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      await handleStripeEvent(checkoutEvent(), db.deps);
      expect(log).not.toHaveBeenCalled();
    } finally {
      log.mockRestore();
    }
  });
});

describe("POST /api/stripe/webhook", () => {
  const SECRET = "whsec_test_secret";

  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  async function post(body: string, signature: string | null) {
    const { POST } = await import("@/app/api/stripe/webhook/route");
    const headers = new Headers({ "content-type": "application/json" });
    if (signature) headers.set("stripe-signature", signature);
    return POST(new Request("http://localhost/api/stripe/webhook", { method: "POST", body, headers }));
  }

  it("rejects an invalid signature with 400", async () => {
    vi.stubEnv("STRIPE_WEBHOOK_SECRET", SECRET);
    const payload = JSON.stringify(checkoutEvent());
    const forged = Stripe.webhooks.generateTestHeaderString({ payload, secret: "whsec_other_secret" });
    const response = await post(payload, forged);
    expect(response.status).toBe(400);
  });

  it("rejects a missing signature with 400", async () => {
    vi.stubEnv("STRIPE_WEBHOOK_SECRET", SECRET);
    const response = await post(JSON.stringify(checkoutEvent()), null);
    expect(response.status).toBe(400);
  });

  it("answers 503 when the webhook secret is not configured", async () => {
    vi.stubEnv("STRIPE_WEBHOOK_SECRET", "");
    const payload = JSON.stringify(checkoutEvent());
    const header = Stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET });
    const response = await post(payload, header);
    expect(response.status).toBe(503);
  });

  it("accepts a valid signature for an event it ignores without touching the database", async () => {
    vi.stubEnv("STRIPE_WEBHOOK_SECRET", SECRET);
    const payload = JSON.stringify(checkoutEvent({}, "customer.created"));
    const header = Stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET });
    const response = await post(payload, header);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ received: true, handled: false });
  });
});

describe("charge.refunded", () => {
  const PI = "pi_test_1";

  function refundDb() {
    const base = fakeDb();
    const refunds = new Map<string, number>();
    const deps: FulfillmentDeps = {
      ...base.deps,
      async findPurchaseByPaymentIntent(pi) {
        const purchase = [...base.purchases.values()].find((p) => p.paymentIntent === pi);
        return purchase ? { userId: purchase.userId, sessionId: purchase.sessionId, credits: purchase.credits } : null;
      },
      async recordRefund(userId, credits, eventId) {
        if (!refunds.has(eventId)) {
          refunds.set(eventId, -credits);
          base.ledger.push({ userId, delta: -credits, sessionId: `refund:${eventId}` });
        }
        return base.balance(userId);
      },
    };
    return { ...base, deps, refunds };
  }

  function refundEvent(charge: Partial<Stripe.Charge>, id = "evt_refund_1"): Stripe.Event {
    return {
      id,
      object: "event",
      type: "charge.refunded",
      data: { object: { id: "ch_1", object: "charge", amount: 6900, amount_refunded: 6900, refunded: true, payment_intent: PI, ...charge } },
    } as unknown as Stripe.Event;
  }

  it("takes back the pack credits once per event", async () => {
    const db = refundDb();
    await handleStripeEvent(checkoutEvent({ payment_intent: PI }), db.deps);
    expect(db.balance(USER)).toBe(10);
    const result = await handleStripeEvent(refundEvent({}), db.deps);
    expect(result).toEqual({ handled: true, userId: USER, credits: -10, balance: 0 });
    await handleStripeEvent(refundEvent({}), db.deps); // Stripe retry
    expect(db.balance(USER)).toBe(0);
    expect(db.refunds.size).toBe(1);
  });

  it("ignores refunds of unknown purchases and leaves partial refunds to a human", async () => {
    const db = refundDb();
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(await handleStripeEvent(refundEvent({ payment_intent: "pi_other" }), db.deps)).toEqual({
      handled: false,
      reason: "unknown_purchase",
    });
    expect(await handleStripeEvent(refundEvent({ refunded: false, amount_refunded: 100 }), db.deps)).toEqual({
      handled: false,
      reason: "partial_refund",
    });
    expect(db.refunds.size).toBe(0);
    vi.restoreAllMocks();
  });
});
