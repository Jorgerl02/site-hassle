import { groupThousands } from "@/lib/format";

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
  pack("pieza_1", 1, 900, "1 piece"),
  pack("pieza_10", 10, 6900, "10 pieces", true),
  pack("pieza_30", 30, 16900, "30 pieces"),
]);

/** Badge shown on the highlighted pack. */
export const HIGHLIGHT_LABEL = "Most popular";

/** Pieces a free account can create per day (mirrors `daily_piece_limit` in SQL). */
export const DAILY_PIECE_LIMIT = 3;

/** Pieces an anonymous trial (no email yet) can create per day (mirrors `anonymous_daily_piece_limit`). */
export const ANONYMOUS_DAILY_PIECE_LIMIT = 1;

/** Extra versions a customer can request per piece. */
export const MAX_EXTRA_VERSIONS = 2;

export function getPack(id: string): Pack | undefined {
  return PACKS.find((p) => p.id === id);
}


/**
 * English euro formatting: «€69», «€6.90», «€1,000», «-€6.90». Symbol first,
 * no space; whole euros drop the decimals; thousands are always grouped.
 */
export function formatEur(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.round(cents));
  const euros = groupThousands(String(Math.floor(abs / 100)));
  const rest = abs % 100;
  const amount = rest === 0 ? euros : `${euros}.${String(rest).padStart(2, "0")}`;
  return `${sign}€${amount}`;
}

/** Required checkbox before paying (digital content delivered at once: no 14-day withdrawal). */
export const WAIVER_TEXT =
  "I agree that the digital content is delivered immediately and I waive my right of withdrawal.";
