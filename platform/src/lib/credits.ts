import type { SupabaseClient } from "@supabase/supabase-js";
import { groupThousands } from "@/lib/format";
import type { FulfillmentDeps } from "@/lib/stripe";

// Untyped on purpose: `credit_ledger`, `purchases` and `grant_credits` are not
// in the hand-written `database.types.ts` stub yet. Callers pass their typed
// client; the shapes used here are declared below.
export type LedgerClient = SupabaseClient;

export type CreditReason = "purchase" | "consume" | "grant" | "refund" | "plan";

export const LEDGER_REASON_LABEL: Record<CreditReason, string> = {
  purchase: "Purchase",
  consume: "Download",
  grant: "Gift",
  refund: "Refund",
  plan: "Plan",
};

export interface LedgerEntry {
  id: string;
  delta: number;
  reason: CreditReason;
  label: string;
  /** Downloaded piece, for `consume` entries. */
  pieceName: string | null;
  createdAt: string;
}

export interface Ledger {
  balance: number;
  entries: LedgerEntry[];
}

interface LedgerRow {
  id: string;
  delta: number;
  reason: CreditReason;
  created_at: string;
  pieces: { name: string } | null;
}

const LEDGER_LIMIT = 50;

/** Balance and latest ledger entries of a user, read with the caller's client (RLS applies). */
export async function getLedger(userId: string, client: LedgerClient): Promise<Ledger> {
  const [balanceResult, entriesResult] = await Promise.all([
    client.rpc("credit_balance", { p_user: userId }),
    client
      .from("credit_ledger")
      .select("id, delta, reason, created_at, pieces(name)")
      .eq("user_id", userId)
      .order("created_at", { ascending: false })
      .limit(LEDGER_LIMIT),
  ]);
  if (balanceResult.error) throw new Error(`credit_balance: ${balanceResult.error.message}`);
  if (entriesResult.error) throw new Error(`credit_ledger: ${entriesResult.error.message}`);

  const rows = (entriesResult.data ?? []) as unknown as LedgerRow[];
  return {
    balance: typeof balanceResult.data === "number" ? balanceResult.data : 0,
    entries: rows.map((row) => ({
      id: row.id,
      delta: row.delta,
      reason: row.reason,
      label: LEDGER_REASON_LABEL[row.reason] ?? row.reason,
      pieceName: row.pieces?.name ?? null,
      createdAt: row.created_at,
    })),
  };
}

/** Absolute value with English thousands: «1,000». */
function groupDigits(n: number): string {
  return groupThousands(String(Math.abs(Math.trunc(n))));
}

/** «9», «1,000», «−2» (true minus sign). */
export function formatCount(n: number): string {
  return `${n < 0 ? "−" : ""}${groupDigits(n)}`;
}

/** «+10», «−1» (true minus sign), «+1,000». */
export function formatCreditDelta(delta: number): string {
  return `${delta < 0 ? "−" : "+"}${groupDigits(delta)}`;
}

/** «1 credit», «10 credits», «1,000 credits». */
export function formatCredits(n: number): string {
  return `${formatCount(n)} ${Math.abs(n) === 1 ? "credit" : "credits"}`;
}

/**
 * Fulfilment side effects backed by Supabase with the service role.
 * `getClient` is called lazily so ignored events never build a client.
 */
export function supabaseFulfillmentDeps(getClient: () => LedgerClient): FulfillmentDeps {
  return {
    async recordPurchase(record) {
      const { error } = await getClient()
        .from("purchases")
        .upsert(
          {
            user_id: record.userId,
            stripe_session_id: record.sessionId,
            pack: record.pack,
            credits: record.credits,
            amount_cents: record.amountCents,
            status: record.status,
            stripe_payment_intent: record.paymentIntent ?? null,
          },
          { onConflict: "stripe_session_id", ignoreDuplicates: true },
        );
      if (error) throw new Error(`purchases: ${error.message}`);
    },
    async grantCredits(userId, credits, sessionId) {
      const { data, error } = await getClient().rpc("grant_credits", {
        p_user: userId,
        p_delta: credits,
        p_reason: "purchase",
        p_session: sessionId,
      });
      if (error) throw new Error(`grant_credits: ${error.message}`);
      return typeof data === "number" ? data : 0;
    },
    async findPurchaseByPaymentIntent(paymentIntent) {
      const { data, error } = await getClient()
        .from("purchases")
        .select("user_id, stripe_session_id, credits")
        .eq("stripe_payment_intent", paymentIntent)
        .maybeSingle();
      if (error) throw new Error(`purchases: ${error.message}`);
      if (!data) return null;
      const row = data as { user_id: string; stripe_session_id: string; credits: number };
      return { userId: row.user_id, sessionId: row.stripe_session_id, credits: row.credits };
    },
    async recordRefund(userId, credits, eventId) {
      // Unique `stripe_event_id`: a retried event never takes the credits twice.
      const { error } = await getClient()
        .from("credit_ledger")
        .upsert(
          { user_id: userId, delta: -credits, reason: "refund", stripe_event_id: eventId },
          { onConflict: "stripe_event_id", ignoreDuplicates: true },
        );
      if (error) throw new Error(`credit_ledger: ${error.message}`);
      const { data, error: balanceError } = await getClient().rpc("credit_balance", { p_user: userId });
      if (balanceError) throw new Error(`credit_balance: ${balanceError.message}`);
      return typeof data === "number" ? data : 0;
    },

  };
}
