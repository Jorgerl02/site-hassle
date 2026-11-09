import { Badge, Box, Flex, LinkBox, LinkOverlay, Stack, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { formatDimensions } from "@/lib/format";
import { PIECE_STATUS_LABEL, type CustomerPiece } from "@/lib/pieces";

const BADGE_PALETTE: Partial<Record<CustomerPiece["status"], string>> = {
  ready: "clay",
  approved: "green",
  needs_photos: "orange",
  failed: "red",
  rejected: "gray",
};

type CardPiece = Pick<CustomerPiece, "id" | "name" | "status" | "width_cm" | "height_cm" | "depth_cm">;

export function PieceCard({ piece, thumbUrl }: { piece: CardPiece; thumbUrl?: string }) {
  return (
    <LinkBox
      as="article"
      bg="bg.panel"
      borderWidth="1px"
      borderColor="border"
      rounded="xl"
      p="3"
      transition="border-color 0.15s"
      _hover={{ borderColor: "border.emphasized" }}
      data-testid="piece-card"
    >
      <Flex gap="4" align="center">
        <Box boxSize="16" flexShrink="0" rounded="lg" overflow="hidden" bg="bg.subtle">
          {thumbUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- short-lived signed URL, not worth the optimizer
            <img src={thumbUrl} alt="" width={64} height={64} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : null}
        </Box>
        <Stack gap="0.5" flex="1" minW="0">
          <LinkOverlay asChild>
            <NextLink href={`/piezas/${piece.id}`}>
              <Text fontWeight="600" truncate>
                {piece.name}
              </Text>
            </NextLink>
          </LinkOverlay>
          <Text fontSize="sm" color="fg.muted">
            {formatDimensions(piece.width_cm, piece.height_cm, piece.depth_cm)}
          </Text>
        </Stack>
        <Badge colorPalette={BADGE_PALETTE[piece.status] ?? "gray"} flexShrink="0">
          {PIECE_STATUS_LABEL[piece.status]}
        </Badge>
      </Flex>
    </LinkBox>
  );
}
