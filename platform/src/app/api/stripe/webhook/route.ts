import Stripe from "stripe";
import { supabaseFulfillmentDeps, type LedgerClient } from "@/lib/credits";
import { handleStripeEvent } from "@/lib/stripe";
import { createAdminClient } from "@/lib/supabase/admin";

export const dynamic = "force-dynamic";

/**
 * Stripe webhook. Verifies the signature over the raw body, then credits paid
 * checkouts (idempotent by session id, so Stripe retries are harmless).
 * Non-2xx answers make Stripe retry, which is what we want on our own failures.
 */
export async function POST(request: Request): Promise<Response> {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) return Response.json({ error: "webhook_not_configured" }, { status: 503 });

  const signature = request.headers.get("stripe-signature");
  if (!signature) return Response.json({ error: "missing_signature" }, { status: 400 });

  const body = await request.text();
  let event: Stripe.Event;
  try {
    // Static helper: verifying needs only the signing secret, not the API key.
    event = Stripe.webhooks.constructEvent(body, signature, secret);
  } catch {
    return Response.json({ error: "invalid_signature" }, { status: 400 });
  }

  try {
    const deps = supabaseFulfillmentDeps(() => createAdminClient() as unknown as LedgerClient);
    const result = await handleStripeEvent(event, deps);
    if (!result.handled && result.reason !== "ignored_event") {
      console.warn(`[stripe] ${event.type} ${event.id} not fulfilled: ${result.reason}`);
    }
    return Response.json({ received: true, handled: result.handled });
  } catch (error) {
    console.error(`[stripe] ${event.type} ${event.id} failed`, error);
    return Response.json({ error: "fulfillment_failed" }, { status: 500 });
  }
}
