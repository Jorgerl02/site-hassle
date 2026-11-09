import { Box, Button, Container, Flex, Heading, Link, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { TrackEvent } from "@/components/Analytics";
import { AppHeader } from "@/components/pieces/AppHeader";
import { PieceCard } from "@/components/pieces/PieceCard";
import { requireUser } from "@/lib/auth";
import { getBalance, signedThumbUrls } from "@/lib/pieces";
import { createServerClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Tus piezas",
  robots: { index: false },
};

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // Redirects to /entrar before anything streams when there is no session.
  const { user } = await requireUser();
  // `/auth/callback` adds `?registro=1` on the first sign-in of an account.
  const firstSignIn = (await searchParams).registro === "1";
  const supabase = await createServerClient();
  const [{ data: pieces }, balance] = await Promise.all([
    supabase
      .from("pieces")
      .select("id, name, status, width_cm, height_cm, depth_cm, created_at")
      .order("created_at", { ascending: false }),
    getBalance(user.id),
  ]);
  const thumbs = await signedThumbUrls(
    user.id,
    (pieces ?? []).map((p) => p.id),
  );

  return (
    <>
      <AppHeader />
      {firstSignIn ? <TrackEvent event="signup" onceKey={`signup:${user.id}`} cleanParam="registro" /> : null}
      <Container as="main" maxW="5xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Flex justify="space-between" align="center" gap="4" wrap="wrap" mb="6">
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            Tus piezas
          </Heading>
          <Button asChild colorPalette="clay" rounded="full">
            <NextLink href="/piezas/nueva">Nueva pieza</NextLink>
          </Button>
        </Flex>

        <Flex
          bg="bg.subtle"
          rounded="xl"
          px="4"
          py="3"
          mb="6"
          justify="space-between"
          align="center"
          gap="3"
          wrap="wrap"
          data-testid="balance"
        >
          <Text>
            Créditos: <strong>{balance ?? "—"}</strong>
            <Text as="span" color="fg.muted">
              {" "}
              · 1 crédito = 1 pieza descargada
            </Text>
          </Text>
          <Link asChild color="clay.fg" fontWeight="600">
            <NextLink href="/creditos">Comprar créditos</NextLink>
          </Link>
        </Flex>

        {!pieces || pieces.length === 0 ? (
          <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p="8" textAlign="center">
            <Text fontWeight="600">Todavía no tienes piezas</Text>
            <Text color="fg.muted" mt="1">
              Sube la foto y las medidas de un mueble para ver su modelo 3D gratis.
            </Text>
          </Box>
        ) : (
          <Stack as="ul" listStyleType="none" gap="3">
            {pieces.map((piece) => (
              <li key={piece.id}>
                <PieceCard piece={piece} thumbUrl={thumbs[piece.id]} />
              </li>
            ))}
          </Stack>
        )}
        <Text fontSize="sm" color="fg.subtle" mt="8">
          {user.email}
        </Text>
      </Container>
    </>
  );
}
