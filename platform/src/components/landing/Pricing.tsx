import { Badge, Box, Container, Grid, Heading, List, Stack, Text } from "@chakra-ui/react";
import { DAILY_PIECE_LIMIT, formatEur, HIGHLIGHT_LABEL, MAX_EXTRA_VERSIONS, PACKS } from "@/lib/pricing";
import { StartCta } from "./StartCta";

const RULES = [
  "You only pay for the pieces you download, after seeing them.",
  `Requesting another version of the same piece is free (up to ${MAX_EXTRA_VERSIONS}).`,
  "If a piece fails or isn't useful to you, you don't spend a credit.",
  "Used credits are non-refundable · unused credits never expire. That's why you see every piece in full before you spend a credit.",
];

export function Pricing() {
  return (
    <Box as="section" id="pricing" py={{ base: 14, md: 24 }} bg="bg.subtle" scrollMarginTop="4">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Stack gap="3" maxW="40em" mb={{ base: 8, md: 12 }}>
          <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em">
            Pricing
          </Heading>
          <Text color="fg.muted" fontSize="lg" textWrap="pretty">
            Viewing the result is free: up to {DAILY_PIECE_LIMIT} pieces a day, with their dimensions and in augmented
            reality. Downloading a piece (GLB with 2K textures and USDZ) takes 1 credit.
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
                {pack.credits === 1 ? "One downloaded piece" : `${formatEur(pack.perPieceCents)} per piece`}
              </Text>
              <Box flex="1" />
            </Stack>
          ))}
        </Grid>

        <Stack mt={{ base: 8, md: 10 }} gap="2" align={{ base: "stretch", sm: "flex-start" }}>
          <StartCta source="landing_pricing" />
          <Text fontSize="sm" color="fg.muted">
            No credit card required · Free preview &amp; AR
          </Text>
        </Stack>

        <List.Root mt={{ base: 8, md: 10 }} gap="2" color="fg.muted" ps="5">
          {RULES.map((rule) => (
            <List.Item key={rule}>{rule}</List.Item>
          ))}
        </List.Root>
        <Text mt="4" fontSize="sm" color="fg.muted">
          VAT included. Buy credits only when you want to download.
        </Text>
      </Container>
    </Box>
  );
}
