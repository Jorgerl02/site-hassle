import { Alert, Button, Container, Heading, Link, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { AppHeader } from "@/components/pieces/AppHeader";
import { PieceForm, type PieceFormDefaults } from "@/components/pieces/PieceForm";
import { requireUser } from "@/lib/auth";
import { formatCm } from "@/lib/format";
import { DAILY_LIMIT_MESSAGE, findPieceForUser } from "@/lib/pieces";
import { DAILY_PIECE_LIMIT } from "@/lib/pricing";
import { createServerClient } from "@/lib/supabase/server";
import { rectilinearAnswer, supportAnswer } from "@/lib/validation";

export const metadata: Metadata = {
  title: "Nueva pieza",
  robots: { index: false },
};

/** «Corregir fotos»: `?desde=<id>` starts the form with that piece's data. */
async function defaultsFrom(id: string | undefined): Promise<PieceFormDefaults | null> {
  if (!id) return null;
  const piece = await findPieceForUser(id);
  if (!piece) return null;
  return {
    name: piece.name,
    kind: piece.kind,
    widthCm: formatCm(piece.width_cm),
    heightCm: formatCm(piece.height_cm),
    depthCm: formatCm(piece.depth_cm),
    rectilinear: rectilinearAnswer(piece.rectilinear),
    support: supportAnswer(piece.support),

    notes: piece.notes ?? "",
  };
}

export default async function NewPiecePage({ searchParams }: { searchParams: Promise<{ desde?: string }> }) {
  const { user } = await requireUser();
  const { desde } = await searchParams;
  const supabase = await createServerClient();
  const [{ data: createdToday }, source] = await Promise.all([
    supabase.rpc("pieces_created_today", { p_user: user.id }),
    defaultsFrom(desde),
  ]);
  const limitReached = typeof createdToday === "number" && createdToday >= DAILY_PIECE_LIMIT;

  return (
    <>
      <AppHeader />
      <Container as="main" maxW="3xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Stack gap="2" mb="8">
          <Link asChild fontSize="sm" color="fg.muted">
            <NextLink href="/panel">← Tus piezas</NextLink>
          </Link>
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            {source ? "Corregir fotos" : "Nueva pieza"}
          </Heading>
          <Text color="fg.muted">
            {source
              ? "Hemos copiado los datos de tu pieza. Sube otras fotos y la generamos de nuevo."
              : "Una foto de catálogo y las medidas reales. Te avisamos aquí cuando esté lista."}
          </Text>
        </Stack>

        {limitReached ? (
          <Alert.Root status="info" rounded="xl" role="alert">
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>{DAILY_LIMIT_MESSAGE}</Alert.Title>
              <Alert.Description>
                <Button asChild variant="plain" colorPalette="clay" px="0">
                  <NextLink href="/panel">Volver a tus piezas</NextLink>
                </Button>
              </Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : (
          <PieceForm userId={user.id} defaults={source ?? undefined} />
        )}
      </Container>
    </>
  );
}
