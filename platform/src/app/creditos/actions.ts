"use server";

import { headers } from "next/headers";
import { redirect, unstable_rethrow } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { getPack } from "@/lib/pricing";
import { getStripe } from "@/lib/stripe";

async function origin(): Promise<string> {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}

class CheckoutError extends Error {}


/**
 * Creates a Stripe Checkout Session for a credit pack and returns its URL.
 * The price is looked up by `lookup_key` (= pack id), created by `pnpm stripe:setup`.
 */
export async function createCheckoutSession(packId: string): Promise<string> {
  const { user } = await requireUser();
  const pack = getPack(packId);
  if (!pack) throw new CheckoutError(`unknown pack ${packId}`);
  const stripe = getStripe();
  if (!stripe) throw new CheckoutError("stripe_not_configured");

  const prices = await stripe.prices.list({ lookup_keys: [pack.id], active: true, limit: 1 });
  const price = prices.data[0];
  if (!price) throw new CheckoutError(`no active price with lookup_key ${pack.id}`);

  const base = await origin();
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    // Card only (Apple Pay / Google Pay ride on it): paid on return, no delayed methods like SEPA.
    // stripe@23 types expose this filter rather than `payment_method_types`.
    allowed_payment_method_types: ["card"],
    line_items: [{ price: price.id, quantity: 1 }],
    client_reference_id: user.id,
    customer_email: user.email ?? undefined,
    // The customer ticked the withdrawal waiver (checked by `startCheckout`); kept on the session as evidence.
    metadata: { pack: pack.id, credits: String(pack.credits), withdrawal_waiver: "accepted" },
    locale: "es",
    // Invoice with the customer's tax id (companies need it to deduct the VAT).
    invoice_creation: { enabled: true },
    tax_id_collection: { enabled: true },
    customer_creation: "always",
    billing_address_collection: "required",
    success_url: `${base}/creditos?ok=1&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${base}/creditos`,
  });
  if (!session.url) throw new CheckoutError("checkout session without url");
  return session.url;
}

/** Form action for the pack buttons: sends the browser to Stripe Checkout. */
export async function startCheckout(formData: FormData): Promise<void> {
  const packId = String(formData.get("pack") ?? "");
  if (formData.get("waiver") !== "on") redirect("/creditos?error=desistimiento");
  let url: string;

  try {
    url = await createCheckoutSession(packId);
  } catch (error) {
    // requireUser() redirects by throwing; let Next handle it.
    unstable_rethrow(error);
    console.error("[stripe] checkout failed", error);
    redirect("/creditos?error=pago");
  }
  redirect(url);
}
