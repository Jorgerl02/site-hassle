import { Box, Button, Container, Flex, Grid, Heading, HStack, Stack, Text } from "@chakra-ui/react";
import Image from "next/image";
import NextLink from "next/link";
import { formatEur, PACKS } from "@/lib/pricing";
import { formatDimensions, modelSrc, photoSrc } from "@/lib/examples";

const cheapest = Math.min(...PACKS.map((p) => p.perPieceCents));

export function Hero() {
  return (
    <Box as="section" pt={{ base: 10, md: 20 }} pb={{ base: 14, md: 24 }}>
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Grid templateColumns={{ base: "1fr", lg: "1.1fr 1fr" }} gap={{ base: 10, lg: 16 }} alignItems="center">
          <Stack gap="6">
            <Text color="clay.fg" fontSize="sm" fontWeight="600" letterSpacing="wide">
              Para tiendas de muebles y decoración
            </Text>
            <Heading
              as="h1"
              fontSize={{ base: "4xl", md: "6xl" }}
              lineHeight="1.05"
              fontWeight="500"
              letterSpacing="-0.02em"
              textWrap="balance"
            >
              Sube la foto y las medidas. Descarga el mueble en 3D a escala real.
            </Heading>
            <Text fontSize={{ base: "lg", md: "xl" }} color="fg.muted" maxW="34em" textWrap="pretty">
              Un modelo listo para tu web y para verlo en casa con realidad aumentada desde el móvil. Lo ves entero
              antes de pagar: solo pagas la pieza que descargas.
            </Text>
            <Flex gap="3" wrap="wrap">
              <Button asChild size="xl" colorPalette="clay" rounded="full" px="7">
                <NextLink href="/entrar">Prueba con una pieza gratis</NextLink>
              </Button>
              <Button asChild size="xl" variant="ghost" colorPalette="ink" rounded="full">
                <a href="#ejemplos">Ver ejemplos</a>
              </Button>
            </Flex>
            <Text fontSize="sm" color="fg.subtle" maxW="34em">
              Ver el resultado es gratis. Descargar la pieza en GLB y USDZ cuesta 1 crédito (desde{" "}
              {formatEur(cheapest)}).
            </Text>
          </Stack>

          <Box bg="bg.panel" rounded="2xl" borderWidth="1px" borderColor="border" p={{ base: 4, md: 6 }} shadow="sm">
            <HStack gap={{ base: 2, md: 4 }} align="stretch">
              <Figure src={photoSrc("p15")} alt="Foto de catálogo de un sillón tapizado en bouclé" label="Foto" preload />
              <Flex align="center" color="fg.subtle" fontSize="2xl" aria-hidden>
                →
              </Flex>
              <Figure src={modelSrc("p15")} alt="Modelo 3D del mismo sillón generado a escala" label="Modelo 3D" />
            </HStack>
            <Text mt="4" textAlign="center" fontSize="sm" color="fg.muted">
              Sillón tapizado · {formatDimensions({ widthCm: 70, heightCm: 77, depthCm: 85 })}
            </Text>
          </Box>
        </Grid>
      </Container>
    </Box>
  );
}

function Figure({ src, alt, label, preload }: { src: string; alt: string; label: string; preload?: boolean }) {
  return (
    <Stack as="figure" flex="1" gap="2" m="0">
      <Box position="relative" aspectRatio="1" rounded="lg" overflow="hidden" bg="white">
        <Image
          src={src}
          alt={alt}
          fill
          sizes="(max-width: 1024px) 45vw, 260px"
          preload={preload}
          style={{ objectFit: "contain" }}
        />
      </Box>
      <Text as="figcaption" fontSize="xs" color="fg.subtle" textAlign="center">
        {label}
      </Text>
    </Stack>
  );
}
