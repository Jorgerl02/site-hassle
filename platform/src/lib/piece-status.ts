import type { PieceStatus } from "@/lib/database.types";

/** Customer-facing label for each piece status. */
export const STATUS_LABEL: Record<PieceStatus, string> = {
  queued: "En cola",
  generating: "Generando",
  review: "Revisando",
  ready: "Lista",
  approved: "Descargada",
  needs_photos: "Necesita otras fotos",
  rejected: "Descartada",
  failed: "Con error",
};
