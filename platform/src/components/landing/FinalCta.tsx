import { Box, Container, Heading, Stack, Text } from "@chakra-ui/react";
import { StartCta } from "./StartCta";

export function FinalCta() {
  return (
    <Box as="section" py={{ base: 14, md: 20 }} bg="bg.subtle">
      <Container maxW="3xl" px={{ base: 4, md: 8 }}>
        <Stack gap="5" align="center" textAlign="center">
          <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em" textWrap="balance">
            See your own piece in 3D in a few minutes
          </Heading>
          <StartCta source="landing_footer" />
          <Text fontSize="sm" color="fg.muted">
            No credit card required · Free preview &amp; AR
          </Text>
        </Stack>
      </Container>
    </Box>
  );
}
