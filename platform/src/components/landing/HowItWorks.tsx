import { Box, Container, Grid, Heading, Stack, Text } from "@chakra-ui/react";

const STEPS = [
  {
    title: "Upload the photo and dimensions",
    body: "A clean catalogue photo, front or three-quarter view, plus the width, height and depth in centimetres. That's it: no technical settings.",
  },
  {
    title: "We check it, you see it in 3D",
    body: "We fit the model to your dimensions (±3% per axis) and check it before showing it to you. Spin it, check the measurements and place it in your room with your phone. For free.",
  },
  {
    title: "Download it and add it to your store",
    body: "GLB for the web and USDZ for iPhone. Shopify shows its “View in your space” button with the GLB; on WooCommerce or PrestaShop you embed it with a standard viewer.",
  },
] as const;

export function HowItWorks() {
  return (
    <Box as="section" id="how-it-works" py={{ base: 14, md: 24 }} scrollMarginTop="4">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em" mb={{ base: 8, md: 12 }}>
          How it works
        </Heading>
        <Grid as="ol" listStyleType="none" templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={{ base: 8, md: 10 }}>
          {STEPS.map((step, index) => (
            <Stack as="li" key={step.title} gap="3">
              <Text fontFamily="heading" fontSize="4xl" lineHeight="1" color="clay.solid" aria-hidden>
                {index + 1}
              </Text>
              <Heading as="h3" fontSize="xl" fontWeight="600" fontFamily="body">
                {step.title}
              </Heading>
              <Text color="fg.muted" textWrap="pretty">
                {step.body}
              </Text>
            </Stack>
          ))}
        </Grid>
      </Container>
    </Box>
  );
}
