import { Button } from "@chakra-ui/react";
import NextLink from "next/link";

/** The one start action of the site; `source` tells the funnel which CTA started the trial. */
export const START_LABEL = "Turn a photo into a 3D model";

export function startHref(source: string): string {
  return `/piezas/nueva?source=${encodeURIComponent(source)}`;
}

export function StartCta({ source, size = "xl" }: { source: string; size?: "sm" | "md" | "lg" | "xl" }) {
  return (
    <Button asChild size={size} colorPalette="clay" rounded="full" px={size === "sm" ? "4" : "7"}>
      <NextLink href={startHref(source)}>{START_LABEL}</NextLink>
    </Button>
  );
}
