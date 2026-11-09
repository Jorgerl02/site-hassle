import { Alert, Badge, Box, Button, Container, Flex, Heading, Link, SimpleGrid, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { AppHeader } from "@/components/pieces/AppHeader";
import { ModelViewer } from "@/components/pieces/ModelViewer";
import { ResultActions } from "@/components/pieces/ResultActions";
import { StatusSteps } from "@/components/pieces/StatusSteps";
import { requireUser } from "@/lib/auth";
import { formatCm } from "@/lib/format";
import {
  FAILED_MESSAGE,
  PIECE_STATUS_LABEL,
  SETTLED_STATUSES,
  getBalance,
  getPieceForUser,
  getSelectedModel,
  previewUrl,
  signedModelUrls,
  signedRenderUrls,
  statusSteps,
  type CustomerPiece,
} from "@/lib/pieces";
import { MAX_EXTRA_VERSIONS } from "@/lib/pricing";
import { KIND_LABEL } from "@/lib/validation";

export const metadata: Metadata = {
  title: "Your piece",
  robots: { index: false },
};

const NBSP = " ";

function Measures({ piece }: { piece: CustomerPiece }) {
  const items = [
    ["Width", piece.width_cm],
    ["Height", piece.height_cm],
    ["Depth", piece.depth_cm],
  ] as const;
  return (
    <SimpleGrid as="dl" columns={3} gap="3" data-testid="measures">
      {items.map(([label, value]) => (
        <Box key={label} bg="bg.panel" borderWidth="1px" rounded="lg" px="3" py="2">
          <Text as="dt" fontSize="xs" color="fg.muted" textTransform="uppercase" letterSpacing="wide">
            {label}
          </Text>
          <Text as="dd" fontWeight="600" fontSize="lg">
            {formatCm(value)}
            {NBSP}cm
          </Text>
        </Box>
      ))}
    </SimpleGrid>
  );
}

function Notice({
  status,
  title,
  children,
}: {
  status: "info" | "warning" | "error";
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <Alert.Root status={status} rounded="xl" role="status">
      <Alert.Indicator />
      <Alert.Content gap="2">
        <Alert.Title>{title}</Alert.Title>
        {children ? <Alert.Description>{children}</Alert.Description> : null}
      </Alert.Content>
    </Alert.Root>
  );
}

export default async function PiecePage({ params }: { params: Promise<{ id: string }> }) {
  const { user } = await requireUser();
  const { id } = await params;
  const piece = await getPieceForUser(id);
  const model = await getSelectedModel(piece);
  const [renders, downloads, balance] = await Promise.all([
    signedRenderUrls(model),
    signedModelUrls(piece, model),
    piece.status === "ready" ? getBalance(user.id) : Promise.resolve(null),
  ]);
  const preview = previewUrl(model);
  const steps = statusSteps(piece.status);
  const showModel = (piece.status === "ready" || piece.status === "approved") && preview;

  return (
    <>
      <AppHeader />
      <Container as="main" maxW="5xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Stack gap="2" mb="8">
          <Link asChild fontSize="sm" color="fg.muted">
            <NextLink href="/panel">← Your pieces</NextLink>
          </Link>
          <Flex align="center" gap="3" wrap="wrap">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              {piece.name}
            </Heading>
            <Badge size="lg" colorPalette={piece.status === "ready" ? "clay" : "gray"} data-testid="piece-status">
              {PIECE_STATUS_LABEL[piece.status]}
            </Badge>
          </Flex>
          <Text color="fg.muted">{KIND_LABEL[piece.kind]}</Text>
        </Stack>

        <SimpleGrid columns={{ base: 1, md: showModel ? 5 : 1 }} gap={{ base: 6, md: 10 }} alignItems="start">
          {showModel ? (
            <Box gridColumn={{ md: "span 3" }}>
              <ModelViewer
                src={preview}
                poster={renders.three_quarter ?? renders.front}
                alt={`3D model of ${piece.name}`}
                placement={piece.kind === "cabecero" || piece.kind === "panel" ? "wall" : "floor"}
              />
              <Text fontSize="sm" color="fg.subtle" mt="2">
                Free preview. Turn it with your finger or mouse; on your phone, “View in your room” places it at
                real size.
              </Text>
            </Box>
          ) : null}

          <Stack gap="6" gridColumn={{ md: showModel ? "span 2" : undefined }} maxW={showModel ? undefined : "xl"}>
            <Measures piece={piece} />

            {steps && piece.status !== "ready" && piece.status !== "approved" ? (
              <Stack gap="3">
                <StatusSteps steps={steps} poll={!SETTLED_STATUSES.includes(piece.status)} />
                <Text fontSize="sm" color="fg.subtle">
                  You can close this page: we keep working and the piece will show up in your dashboard.
                </Text>
              </Stack>
            ) : null}

            {piece.status === "ready" ? (
              showModel ? (
                <ResultActions
                  pieceId={piece.id}
                  balance={balance}
                  versionsLeft={Math.max(0, MAX_EXTRA_VERSIONS - (piece.attempt - 1))}
                />
              ) : (
                <Notice status="warning" title="The preview isn't available right now." />
              )
            ) : null}

            {piece.status === "approved" ? (
              downloads ? (
                <Stack gap="3">
                  <Text fontWeight="600">Your files</Text>
                  <Stack direction={{ base: "column", sm: "row" }} gap="3">
                    <Button asChild colorPalette="clay" rounded="full">
                      <a href={downloads.glb} download>
                        Download GLB
                      </a>
                    </Button>
                    <Button asChild variant="outline" colorPalette="ink" rounded="full">
                      <a href={downloads.usdz} download>
                        Download USDZ
                      </a>
                    </Button>
                  </Stack>
                  <Text fontSize="sm" color="fg.subtle">
                    GLB for your website and Android; USDZ for iPhone and iPad. The links expire after 1 hour: come
                    back to this page for new ones, at no cost.
                  </Text>
                </Stack>
              ) : (
                <Notice status="warning" title="We couldn't prepare your downloads. Reload the page in a moment." />
              )
            ) : null}

            {piece.status === "needs_photos" ? (
              <Notice status="warning" title="We need different photos">
                <Stack gap="3" align="flex-start">
                  {piece.error ? <Text whiteSpace="pre-line">{piece.error}</Text> : null}
                  <Button asChild colorPalette="clay" rounded="full" size="sm">
                    <NextLink href={`/piezas/nueva?desde=${piece.id}`}>Fix photos</NextLink>
                  </Button>
                </Stack>
              </Notice>
            ) : null}

            {piece.status === "rejected" ? (
              <Notice status="info" title="This piece is closed and hasn't cost you anything.">
                {piece.reject_reason ? <Text>Reason: {piece.reject_reason}</Text> : null}
              </Notice>
            ) : null}

            {piece.status === "failed" ? (
              // Fixed copy: `piece.error` holds technical detail meant for the admin only.
              <Notice status="error" title={FAILED_MESSAGE}>
                <Text>It doesn&apos;t cost you anything.</Text>
              </Notice>
            ) : null}

          </Stack>
        </SimpleGrid>
      </Container>
    </>
  );
}
