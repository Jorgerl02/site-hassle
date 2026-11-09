import { Box, Button, Container, Flex, Grid, Heading, HStack, Stack, Text } from "@chakra-ui/react";
import Image from "next/image";
import { formatEur, PACKS } from "@/lib/pricing";
import { modelSrc, photoSrc } from "@/lib/examples";
import { formatDimensions } from "@/lib/format";
import { StartCta } from "./StartCta";

const cheapest = Math.min(...PACKS.map((p) => p.perPieceCents));

export function Hero() {
  return (
    <Box as="section" pt={{ base: 10, md: 20 }} pb={{ base: 14, md: 24 }}>
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Grid templateColumns={{ base: "1fr", lg: "1.1fr 1fr" }} gap={{ base: 10, lg: 16 }} alignItems="center">
          <Stack gap="6">
            <Text color="clay.fg" fontSize="sm" fontWeight="600" letterSpacing="wide">
              For furniture and home decor stores
            </Text>
            <Heading
              as="h1"
              fontSize={{ base: "4xl", md: "6xl" }}
              lineHeight="1.05"
              fontWeight="500"
              letterSpacing="-0.02em"
              textWrap="balance"
            >
              True-to-scale 3D models of your furniture from one photo
            </Heading>
            <Text fontSize={{ base: "lg", md: "xl" }} color="fg.muted" maxW="34em" textWrap="pretty">
              Photo to 3D model for furniture stores: upload a catalogue photo and the dimensions, and get a model
              ready for your website and for augmented reality on any phone. You only pay for the files you download.
            </Text>
            <Flex gap="3" wrap="wrap">
              <StartCta source="landing_hero" />
              <Button asChild size="xl" variant="ghost" colorPalette="ink" rounded="full">
                <a href="#examples">See examples</a>
              </Button>
            </Flex>
            <Stack gap="1">
              <Text fontSize="sm" fontWeight="600" color="fg.muted">
                No credit card required · Free preview &amp; AR
              </Text>
              <Text fontSize="sm" color="fg.subtle" maxW="34em">
                Downloading the piece as GLB and USDZ costs 1 credit (from {formatEur(cheapest)}).
              </Text>
            </Stack>
          </Stack>

          <Box bg="bg.panel" rounded="2xl" borderWidth="1px" borderColor="border" p={{ base: 4, md: 6 }} shadow="sm">
            <HStack gap={{ base: 2, md: 4 }} align="stretch">
              <Figure src={photoSrc("p15")} alt="Catalogue photo of a bouclé upholstered armchair" label="Photo" preload />
              <Flex align="center" color="fg.subtle" fontSize="2xl" aria-hidden>
                →
              </Flex>
              <Figure src={modelSrc("p15")} alt="3D model of the same armchair, generated to scale" label="3D model" />
            </HStack>
            <Text mt="4" textAlign="center" fontSize="sm" color="fg.muted">
              Upholstered armchair · {formatDimensions(70, 77, 85)}
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
