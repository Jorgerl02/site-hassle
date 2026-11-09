"use client";

import { Badge, Box, Button, Dialog, Grid, Portal, Stack, Text } from "@chakra-ui/react";
import { startCheckout } from "@/app/creditos/actions";
import { formatEur, HIGHLIGHT_LABEL, PACKS, WAIVER_TEXT } from "@/lib/pricing";

/**
 * Out of credits at download: the three packs (10 highlighted) with the price
 * per piece in large type. Checkout brings the customer back to this piece,
 * which then downloads by itself.
 */
export function PacksDialog({
  open,
  onClose,
  pieceId,
  paymentsEnabled,
}: {
  open: boolean;
  onClose: () => void;
  pieceId: string;
  paymentsEnabled: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(e) => (!e.open ? onClose() : undefined)} placement="center" size="lg">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner px="4">
          <Dialog.Content rounded="2xl" data-testid="packs-dialog">
            <Dialog.Header>
              <Dialog.Title>Get credits to download</Dialog.Title>
            </Dialog.Header>
            <Dialog.Body>
              <form action={startCheckout}>
                <input type="hidden" name="piece" value={pieceId} />
                <Stack gap="5">
                  <Text color="fg.muted">1 credit = 1 downloaded piece (GLB with 2K textures and USDZ). VAT included.</Text>
                  <Grid templateColumns={{ base: "1fr", sm: "repeat(3, 1fr)" }} gap="3">
                    {PACKS.map((pack) => (
                      <Stack
                        key={pack.id}
                        data-testid={`modal-pack-${pack.id}`}
                        position="relative"
                        rounded="xl"
                        borderWidth={pack.highlighted ? "2px" : "1px"}
                        borderColor={pack.highlighted ? "clay.solid" : "border"}
                        p="4"
                        pt="5"
                        gap="1"
                      >
                        {pack.highlighted ? (
                          <Badge position="absolute" top="-3" left="4" colorPalette="clay" variant="solid" rounded="full" px="3">
                            {HIGHLIGHT_LABEL}
                          </Badge>
                        ) : null}
                        <Text fontFamily="heading" fontSize="4xl" lineHeight="1" whiteSpace="nowrap">
                          {formatEur(pack.perPieceCents)}
                        </Text>
                        <Text fontSize="sm" color="fg.muted">
                          per piece
                        </Text>
                        <Text fontSize="sm" mt="2">
                          {pack.label} · {formatEur(pack.priceCents)}
                        </Text>
                        <Box flex="1" />
                        <Button
                          type="submit"
                          name="pack"
                          value={pack.id}
                          mt="3"
                          size="sm"
                          colorPalette={pack.highlighted ? "clay" : "ink"}
                          variant={pack.highlighted ? "solid" : "outline"}
                          rounded="full"
                          disabled={!paymentsEnabled}
                        >
                          {paymentsEnabled ? "Buy" : "Payments not configured"}
                        </Button>
                      </Stack>
                    ))}
                  </Grid>
                  {paymentsEnabled ? (
                    <label style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start", fontSize: "0.875rem" }}>
                      <input
                        type="checkbox"
                        name="waiver"
                        required
                        data-testid="modal-waiver"
                        style={{ marginTop: "0.2rem", width: "1rem", height: "1rem", accentColor: "#9A5132", flexShrink: 0 }}
                      />
                      <span>{WAIVER_TEXT}</span>
                    </label>
                  ) : null}
                  <Text fontSize="sm" color="fg.muted">
                    Used credits are non-refundable · unused credits never expire.
                  </Text>
                </Stack>
              </form>
            </Dialog.Body>
            <Dialog.Footer>
              <Button variant="ghost" colorPalette="ink" onClick={onClose}>
                Not now
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
