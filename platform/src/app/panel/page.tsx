import { Badge, Box, Button, Container, Flex, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { signOut } from "@/app/entrar/actions";
import { PRODUCT_NAME } from "@/lib/site";
import { requireUser, type CurrentUser } from "@/lib/auth";
import { STATUS_LABEL } from "@/lib/piece-status";
import { createServerClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Tus piezas",
  robots: { index: false },
};

// Minimal list; Task 4 completes the panel (thumbnails, credits page link…).
export default async function PanelPage() {
  // Redirects to /entrar before anything streams when there is no session.
  const current = await requireUser();
  return (
    <>
      <Box as="header" borderBottomWidth="1px" borderColor="border">
        <Container maxW="5xl" px={{ base: 4, md: 8 }}>
          <Flex h="16" align="center" justify="space-between">
            <Text fontFamily="heading" fontSize="xl" fontWeight="500">
              {PRODUCT_NAME}
            </Text>
            <form action={signOut}>
              <Button type="submit" size="sm" variant="ghost" colorPalette="ink">
                Salir
              </Button>
            </form>
          </Flex>
        </Container>
      </Box>
      <Container as="main" maxW="5xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Flex justify="space-between" align="center" gap="4" wrap="wrap" mb="8">
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            Tus piezas
          </Heading>
          <Button asChild colorPalette="clay" rounded="full">
            <NextLink href="/piezas/nueva">Nueva pieza</NextLink>
          </Button>
        </Flex>
        <PanelContent current={current} />
      </Container>
    </>
  );
}

async function PanelContent({ current: { user } }: { current: CurrentUser }) {
  const supabase = await createServerClient();
  const [{ data: pieces }, { data: balance }] = await Promise.all([
    supabase
      .from("pieces")
      .select("id, name, status, width_cm, height_cm, depth_cm, created_at")
      .order("created_at", { ascending: false }),
    supabase.rpc("credit_balance", { p_user: user.id }),
  ]);

  return (
    <Stack gap="6">
      <Text color="fg.muted">
        {user.email} · Créditos: <strong>{typeof balance === "number" ? balance : "—"}</strong>
      </Text>
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
            <Flex
              as="li"
              key={piece.id}
              bg="bg.panel"
              borderWidth="1px"
              borderColor="border"
              rounded="xl"
              p="4"
              justify="space-between"
              align="center"
              gap="4"
            >
              <Stack gap="0.5">
                <NextLink href={`/piezas/${piece.id}`}>
                  <Text fontWeight="600">{piece.name}</Text>
                </NextLink>
                <Text fontSize="sm" color="fg.muted">
                  {[piece.width_cm, piece.height_cm, piece.depth_cm].map((v) => String(v).replace(".", ",")).join(" × ")}
                  {" "}cm
                </Text>
              </Stack>
              <Badge colorPalette={piece.status === "ready" ? "clay" : "gray"}>{STATUS_LABEL[piece.status]}</Badge>
            </Flex>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
