export type PackId = "pieza_1" | "pieza_10" | "pieza_30";

export interface Pack {
  /** Also the Stripe price `lookup_key`. */
  id: PackId;
  credits: number;
  /** VAT included, EUR cents. */
  priceCents: number;
  label: string;
  perPieceCents: number;
  highlighted: boolean;
}

function pack(id: PackId, credits: number, priceCents: number, label: string, highlighted = false): Pack {
  return { id, credits, priceCents, label, perPieceCents: Math.round(priceCents / credits), highlighted };
}

export const PACKS: readonly Pack[] = Object.freeze([
  pack("pieza_1", 1, 900, "1 pieza"),
  pack("pieza_10", 10, 6900, "10 piezas", true),
  pack("pieza_30", 30, 16900, "30 piezas"),
]);

/** Badge shown on the highlighted pack. */
export const HIGHLIGHT_LABEL = "Más elegido";

/** Pieces a free account can create per day (mirrors `daily_piece_limit` in SQL). */
export const DAILY_PIECE_LIMIT = 3;

/** Extra versions a customer can request per piece. */
export const MAX_EXTRA_VERSIONS = 2;

export function getPack(id: string): Pack | undefined {
  return PACKS.find((p) => p.id === id);
}

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/**
 * Spanish euro formatting: «69 €», «6,90 €», «1.000 €», with a non-breaking
 * space (U+00A0) before «€» so the amount never wraps away from the symbol.
 * Whole euros drop the decimals; thousands are always grouped (Intl's es-ES
 * leaves four-digit numbers ungrouped, which we don't want).
 */
export function formatEur(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.round(cents));
  const euros = groupThousands(String(Math.floor(abs / 100)));
  const rest = abs % 100;
  const amount = rest === 0 ? euros : `${euros},${String(rest).padStart(2, "0")}`;
  return `${sign}${amount}\u00a0€`;
}

/** Required checkbox before paying (digital content delivered at once: no 14-day withdrawal). */
export const WAIVER_TEXT =
  "Acepto que el contenido digital se entrega de inmediato y renuncio al derecho de desistimiento.";
