// Creates (or reuses) the Stripe product «Piezas 3D» and one one-off EUR price
// per credit pack, with `lookup_key` = pack id (pieza_1 | pieza_10 | pieza_30).
// Idempotent: run it as often as you like.
//
//   pnpm --dir platform stripe:setup        (reads STRIPE_SECRET_KEY from .env.local)
//
// Runs on Node's built-in TypeScript type stripping (Node >= 22.18 / 24).
import Stripe from "stripe";
import type { Pack } from "../src/lib/pricing";

const PRODUCT_NAME = "Piezas 3D";
const PRODUCT_KEY = "piezas_3d"; // metadata.app, to find the product again

// Runtime import with the .ts extension Node needs; the type comes from the import above.
const { PACKS } = (await import(new URL("../src/lib/pricing.ts", import.meta.url).href)) as {
  PACKS: readonly Pack[];
};

const key = process.env.STRIPE_SECRET_KEY;
if (!key) {
  console.error("Falta STRIPE_SECRET_KEY (en platform/.env.local o en el entorno).");
  process.exit(1);
}
const stripe = new Stripe(key);
console.log(`Modo: ${key.startsWith("sk_live_") || key.startsWith("rk_live_") ? "PRODUCCIÓN" : "pruebas"}`);

async function findOrCreateProduct(): Promise<Stripe.Product> {
  for await (const product of stripe.products.list({ active: true, limit: 100 })) {
    if (product.metadata?.app === PRODUCT_KEY) return product;
  }
  return stripe.products.create({
    name: PRODUCT_NAME,
    description: "Créditos para descargar piezas 3D a escala real (GLB 2K y USDZ). 1 crédito = 1 pieza.",
    metadata: { app: PRODUCT_KEY },
  });
}

async function ensurePrice(product: Stripe.Product, pack: Pack): Promise<void> {
  const existing = (await stripe.prices.list({ lookup_keys: [pack.id], active: true, limit: 1 })).data[0];
  const productId = existing ? (typeof existing.product === "string" ? existing.product : existing.product.id) : null;
  if (
    existing &&
    productId === product.id &&
    existing.unit_amount === pack.priceCents &&
    existing.currency === "eur" &&
    existing.type === "one_time"
  ) {
    console.log(`= ${pack.id}: ${existing.id} (sin cambios)`);
    return;
  }

  // Prices are immutable: create a new one and move the lookup_key to it.
  const price = await stripe.prices.create({
    product: product.id,
    currency: "eur",
    unit_amount: pack.priceCents,
    tax_behavior: "inclusive", // IVA incluido
    nickname: pack.label,
    lookup_key: pack.id,
    transfer_lookup_key: true,
    metadata: { pack: pack.id, credits: String(pack.credits) },
  });
  if (existing) await stripe.prices.update(existing.id, { active: false });
  console.log(`+ ${pack.id}: ${price.id} (${pack.label}, ${pack.priceCents / 100} €)${existing ? `; desactivado ${existing.id}` : ""}`);
}

try {
  const product = await findOrCreateProduct();
  console.log(`Producto «${product.name}»: ${product.id}`);
  for (const pack of PACKS) await ensurePrice(product, pack);
  console.log("Listo.");
} catch (error) {
  console.error(`Error de Stripe: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
