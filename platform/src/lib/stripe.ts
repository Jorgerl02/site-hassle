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
}

/** Side effects of a paid checkout. Both must be idempotent by `sessionId`. */
export interface FulfillmentDeps {
  recordPurchase(record: PurchaseRecord): Promise<void>;
  /** `grant_credits(user, credits, 'purchase', session)`; returns the new balance. */
  grantCredits(userId: string, credits: number, sessionId: string): Promise<number>;
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
  if (!userId) return { handled: false, reason: "no_user" };
  // Credits come from our own pack table; metadata only names the pack.
  const pack = getPack(session.metadata?.pack ?? "");
  if (!pack) return { handled: false, reason: "unknown_pack" };

  await deps.recordPurchase({
    userId,
    sessionId: session.id,
    pack: pack.id,
    credits: pack.credits,
    amountCents: session.amount_total ?? pack.priceCents,
    status: session.payment_status,
  });
  const balance = await deps.grantCredits(userId, pack.credits, session.id);
  return { handled: true, userId, credits: pack.credits, balance };
}

const FULFILLING_EVENTS = new Set<string>([
  "checkout.session.completed",
  // Delayed payment methods (e.g. SEPA) complete unpaid and settle later.
  "checkout.session.async_payment_succeeded",
]);

/** Pure webhook logic (no HTTP, no signature): the route verifies, this acts. */
export async function handleStripeEvent(event: Stripe.Event, deps: FulfillmentDeps): Promise<FulfillmentResult> {
  if (!FULFILLING_EVENTS.has(event.type)) return { handled: false, reason: "ignored_event" };
  return fulfillCheckoutSession(event.data.object as Stripe.Checkout.Session, deps);
}
