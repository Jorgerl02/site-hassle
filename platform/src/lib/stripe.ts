import Stripe from "stripe";
import { getPack, type PackId } from "@/lib/pricing";

// Server-side only (secret key). Kept free of `server-only` so the pure
// fulfilment logic below can run in unit tests; never import it from a
// Client Component.

let client: Stripe | null = null;

/** Stripe client, or null while `STRIPE_SECRET_KEY` is not configured. */
export function getStripe(): Stripe | null {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return null;
  // Default API version of the pinned SDK (stripe@23).
  client ??= new Stripe(key, { appInfo: { name: "pieza-3d-platform" } });
  return client;
}

export function isStripeConfigured(): boolean {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}

export interface PurchaseRecord {
  userId: string;
  sessionId: string;
  pack: PackId;
  credits: number;
  amountCents: number;
  status: string;
  /** Stripe PaymentIntent of the session: a later `charge.refunded` finds the purchase by it. */
  paymentIntent?: string;
}

/** The purchase a refunded charge belongs to. */
export interface RefundablePurchase {
  userId: string;
  sessionId: string;
  credits: number;
}

/** Side effects of a paid checkout. Both must be idempotent by `sessionId`. */
export interface FulfillmentDeps {
  recordPurchase(record: PurchaseRecord): Promise<void>;
  /** `grant_credits(user, credits, 'purchase', session)`; returns the new balance. */
  grantCredits(userId: string, credits: number, sessionId: string): Promise<number>;
  /** Purchase paid with this PaymentIntent, or null (refunds only). */
  findPurchaseByPaymentIntent?(paymentIntent: string): Promise<RefundablePurchase | null>;
  /** Negative `refund` ledger row (−credits), idempotent by Stripe event id; returns the balance. */
  recordRefund?(userId: string, credits: number, eventId: string): Promise<number>;
}

export type FulfillmentResult =
  | { handled: true; userId: string; credits: number; balance: number }
  | { handled: false; reason: string };

/**
 * Credits a paid Checkout Session. Safe to call any number of times for the
 * same session (webhook retries, return page): purchases and the ledger are
 * unique by Stripe session id.
 */
export async function fulfillCheckoutSession(
  session: Stripe.Checkout.Session,
  deps: FulfillmentDeps,
): Promise<FulfillmentResult> {
  if (session.mode !== "payment") return { handled: false, reason: "not_payment_mode" };
  // `no_payment_required` would only happen with a 100 % coupon; we never create one.
  if (session.payment_status !== "paid") return { handled: false, reason: "not_paid" };
  const userId = session.client_reference_id;
  // Credits come from our own pack table; metadata only names the pack.
  const pack = getPack(session.metadata?.pack ?? "");
  if (!userId || !pack) {
    const reason = !userId ? "no_user" : "unknown_pack";
    // Money was taken but nothing will be credited: needs a human.
    console.error(
      `[stripe] paid session ${session.id} refused (${reason}); amount_total=${session.amount_total} pack=${session.metadata?.pack ?? "-"}`,
    );
    return { handled: false, reason };
  }
  if (session.amount_total !== pack.priceCents) {
    console.error(
      `[stripe] session ${session.id} amount mismatch: amount_total=${session.amount_total}, ${pack.id} costs ${pack.priceCents}; granting anyway`,
    );
  }

  await deps.recordPurchase({
    userId,
    sessionId: session.id,
    pack: pack.id,
    credits: pack.credits,
    amountCents: session.amount_total ?? pack.priceCents,
    status: session.payment_status,
    paymentIntent: idOf(session.payment_intent),
  });
  const balance = await deps.grantCredits(userId, pack.credits, session.id);
  return { handled: true, userId, credits: pack.credits, balance };
}

const FULFILLING_EVENTS = new Set<string>([
  "checkout.session.completed",
  // Delayed payment methods (e.g. SEPA) complete unpaid and settle later.
  "checkout.session.async_payment_succeeded",
]);

function idOf(value: string | { id: string } | null | undefined): string | undefined {
  if (!value) return undefined;
  return typeof value === "string" ? value : value.id;
}

/**
 * `charge.refunded`: takes back the purchase's credits with a negative
 * `refund` row, once per Stripe event and only for a purchase we know.
 * Only full refunds are automatic; a partial refund is logged for a human,
 * and so are disputes (`charge.dispute.*` are not handled). The balance may
 * go negative if the credits were already spent.
 */
export async function refundCharge(
  charge: Stripe.Charge,
  eventId: string,
  deps: FulfillmentDeps,
): Promise<FulfillmentResult> {
  if (!deps.findPurchaseByPaymentIntent || !deps.recordRefund) return { handled: false, reason: "refunds_not_configured" };
  const paymentIntent = idOf(charge.payment_intent);
  if (!paymentIntent) return { handled: false, reason: "no_payment_intent" };
  if (!charge.refunded) {
    console.error(
      `[stripe] partial refund on ${charge.id} (${charge.amount_refunded}/${charge.amount}): adjust credits by hand`,
    );
    return { handled: false, reason: "partial_refund" };
  }
  const purchase = await deps.findPurchaseByPaymentIntent(paymentIntent);
  if (!purchase) return { handled: false, reason: "unknown_purchase" };
  const balance = await deps.recordRefund(purchase.userId, purchase.credits, eventId);
  return { handled: true, userId: purchase.userId, credits: -purchase.credits, balance };

}

/** Pure webhook logic (no HTTP, no signature): the route verifies, this acts. */
export async function handleStripeEvent(event: Stripe.Event, deps: FulfillmentDeps): Promise<FulfillmentResult> {
  if (event.type === "charge.refunded") return refundCharge(event.data.object as Stripe.Charge, event.id, deps);
  if (!FULFILLING_EVENTS.has(event.type)) return { handled: false, reason: "ignored_event" };
  return fulfillCheckoutSession(event.data.object as Stripe.Checkout.Session, deps);
}

