import "server-only";
import { supabaseFulfillmentDeps, type LedgerClient } from "@/lib/credits";
import { fulfillCheckoutSession, getStripe } from "@/lib/stripe";
import { createAdminClient } from "@/lib/supabase/admin";

export type ReturnState = "paid" | "pending" | null;

export interface ReturnInfo {
  state: ReturnState;
  /** Amount actually paid in euros, for the `purchase` conversion. */
  value?: number;
}

/**
 * Back from Checkout (on `/creditos` or on the piece the customer was
 * downloading) the webhook may not have arrived yet: fulfil from the session
 * itself (idempotent with the webhook), only for the signed-in owner.
 */
export async function confirmCheckoutReturn(sessionId: string | undefined, userId: string): Promise<ReturnInfo> {
  const stripe = getStripe();
  if (!stripe || !sessionId?.startsWith("cs_")) return { state: null };
  try {
    const session = await stripe.checkout.sessions.retrieve(sessionId);
    if (session.client_reference_id !== userId) return { state: null };
    if (session.payment_status === "unpaid") return { state: "pending" };
    const result = await fulfillCheckoutSession(
      session,
      supabaseFulfillmentDeps(() => createAdminClient() as unknown as LedgerClient),
    );
    if (!result.handled) return { state: null };
    return { state: "paid", value: session.amount_total != null ? session.amount_total / 100 : undefined };
  } catch (error) {
    console.error("[stripe] return confirmation failed", error);
    return { state: null };
  }
}
