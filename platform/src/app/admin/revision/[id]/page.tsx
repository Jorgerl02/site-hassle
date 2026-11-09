import { Badge, Box, Container, Flex, Heading, Image, SimpleGrid, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { notFound } from "next/navigation";
import { AdminHeader } from "@/components/admin/AdminHeader";
import { ReviewForm } from "@/components/admin/ReviewForm";
import { getReviewDetail, requireAdmin } from "@/lib/admin";
import { STATUS_LABEL } from "@/lib/piece-status";

export const metadata: Metadata = {
  title: "Revisar pieza",
  robots: { index: false, follow: false },
};

const MAX_ATTEMPT = 3;

const RECTILINEAR_LABEL = { true: "Sí", false: "No", null: "No sabe" } as const;

export default async function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  await requireAdmin();
  const { id } = await params;
  const piece = await getReviewDetail(id);
  if (!piece) notFound();
  const inReview = piece.status === "review";

  return (
    <>
      <AdminHeader />
      <Container as="main" maxW="6xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Text fontSize="sm" mb="4">
          <NextLink href="/admin/revision">← Volver a la cola</NextLink>
        </Text>
        <Flex justify="space-between" align="baseline" gap="4" wrap="wrap" mb="2">
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            {piece.name}
          </Heading>
          <Badge colorPalette={inReview ? "clay" : "gray"} data-testid="piece-status">
            {STATUS_LABEL[piece.status]}
          </Badge>
        </Flex>
        <Flex gap="2" wrap="wrap" color="fg.muted" mb="8">
          <Text>{piece.kindLabel}</Text>
          <Text aria-hidden>·</Text>
          <Text fontVariantNumeric="tabular-nums">{piece.dimensions}</Text>
          <Text aria-hidden>·</Text>
          <Text>Intento {piece.attempt}</Text>
          {piece.route ? (
            <>
              <Text aria-hidden>·</Text>
              <Text>Ruta {piece.route}</Text>
            </>
          ) : null}
          <Text aria-hidden>·</Text>
          <Text>En revisión desde hace {piece.waiting}</Text>
        </Flex>

        <SimpleGrid columns={{ base: 1, md: 3 }} gap="6" mb="10">
          <Box gridColumn={{ md: "span 2" }}>
            <Heading as="h2" fontSize="xl" fontWeight="500" mb="3">
              Fotos originales
            </Heading>
            {piece.photos.length === 0 ? (
              <Text color="fg.muted">Sin fotos.</Text>
            ) : (
              <SimpleGrid columns={{ base: 2, md: 4 }} gap="2">
                {piece.photos.map((photo) => (
                  <a key={photo.position} href={photo.url} target="_blank" rel="noreferrer">
                    <Image
                      src={photo.url}
                      alt={`Foto ${photo.position} de ${piece.name}`}
                      data-testid="original-photo"
                      aspectRatio="1"
                      objectFit="contain"
                      bg="white"
                      rounded="md"
                      borderWidth="1px"
                      borderColor="border"
                    />
                  </a>
                ))}
              </SimpleGrid>
            )}
          </Box>
          <Stack as="dl" gap="2" fontSize="sm">
            <Box>
              <Text as="dt" color="fg.muted">
                Cliente
              </Text>
              <Text as="dd">{piece.email ?? "—"}</Text>
            </Box>
            <Box>
              <Text as="dt" color="fg.muted">
                ¿Pieza recta?
              </Text>
              <Text as="dd">{RECTILINEAR_LABEL[String(piece.rectilinear) as keyof typeof RECTILINEAR_LABEL]}</Text>
            </Box>
            <Box>
              <Text as="dt" color="fg.muted">
                Notas del cliente
              </Text>
              <Text as="dd" whiteSpace="pre-line">
                {piece.notes || "—"}
              </Text>
            </Box>
            {piece.reviewNote ? (
              <Box>
                <Text as="dt" color="fg.muted">
                  Nota de la revisión anterior
                </Text>
                <Text as="dd" whiteSpace="pre-line">
                  {piece.reviewNote}
                </Text>
              </Box>
            ) : null}
          </Stack>
        </SimpleGrid>

        <Heading as="h2" fontSize="xl" fontWeight="500" mb="3">
          Modelos del intento {piece.attempt}
        </Heading>
        {inReview ? (
          <ReviewForm pieceId={piece.id} candidates={piece.candidates} canRegenerate={piece.attempt < MAX_ATTEMPT} />
        ) : (
          <Box bg="bg.subtle" rounded="xl" p="6">
            <Text>Esta pieza ya no está en revisión.</Text>
          </Box>
        )}
      </Container>
    </>
  );
}
