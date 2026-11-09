import { Badge, Box, Button, Container, Grid, Heading, List, Stack, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { DAILY_PIECE_LIMIT, formatEur, HIGHLIGHT_LABEL, MAX_EXTRA_VERSIONS, PACKS } from "@/lib/pricing";

const RULES = [
  "Solo pagas la pieza que descargas, después de verla.",
  `Pedir otra versión de la misma pieza no cuesta nada (hasta ${MAX_EXTRA_VERSIONS}).`,
  "Si la pieza falla o no te sirve, no gastas ningún crédito.",
  "Los créditos comprados no caducan.",
  "Sin reembolsos: por eso ves cada pieza entera antes de gastar un crédito.",
];

export function Pricing() {
  return (
    <Box as="section" id="precios" py={{ base: 14, md: 24 }} bg="bg.subtle" scrollMarginTop="4">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Stack gap="3" maxW="40em" mb={{ base: 8, md: 12 }}>
          <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em">
            Precios
          </Heading>
          <Text color="fg.muted" fontSize="lg" textWrap="pretty">
            Ver el resultado es gratis: hasta {DAILY_PIECE_LIMIT} piezas al día, con sus medidas y en realidad
            aumentada. Para descargar una pieza (GLB con texturas 2K y USDZ) usas 1 crédito.
          </Text>
        </Stack>

        <Grid templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={{ base: 4, md: 6 }} alignItems="stretch">
          {PACKS.map((pack) => (
            <Stack
              key={pack.id}
              as="article"
              data-testid={`pack-${pack.id}`}
              bg="bg.panel"
              rounded="xl"
              borderWidth={pack.highlighted ? "2px" : "1px"}
              borderColor={pack.highlighted ? "clay.solid" : "border"}
              p={{ base: 6, md: 8 }}
              gap="4"
              position="relative"
            >
              {pack.highlighted ? (
                <Badge position="absolute" top="-3" left="6" colorPalette="clay" variant="solid" rounded="full" px="3">
                  {HIGHLIGHT_LABEL}
                </Badge>
              ) : null}
              <Text fontWeight="600" fontSize="lg">
                {pack.label}
              </Text>
              <Text fontFamily="heading" fontSize="5xl" lineHeight="1" whiteSpace="nowrap">
                {formatEur(pack.priceCents)}
              </Text>
              <Text color="fg.muted" fontSize="sm">
                {pack.credits === 1 ? "Una pieza descargada" : `${formatEur(pack.perPieceCents)} por pieza`}
              </Text>
              <Box flex="1" />
              <Button asChild colorPalette={pack.highlighted ? "clay" : "ink"} variant={pack.highlighted ? "solid" : "outline"} rounded="full">
                <NextLink href="/entrar">Empezar gratis</NextLink>
              </Button>
            </Stack>
          ))}
        </Grid>

        <List.Root mt={{ base: 8, md: 10 }} gap="2" color="fg.muted" ps="5">
          {RULES.map((rule) => (
            <List.Item key={rule}>{rule}</List.Item>
          ))}
        </List.Root>
        <Text mt="4" fontSize="sm" color="fg.muted">
          IVA incluido. Compras los créditos cuando quieras descargar; para empezar no hace falta tarjeta.
        </Text>
      </Container>
    </Box>
  );
}
