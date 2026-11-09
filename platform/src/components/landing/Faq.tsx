import { Box, Container, Heading, Stack, Text } from "@chakra-ui/react";

const QUESTIONS: { q: string; a: string }[] = [
  {
    q: "Which photos work best?",
    a: "A front or three-quarter catalogue photo on a light background with no other furniture, the whole piece in the frame and at least 1,000\u00a0px on the long side. You can upload up to 4 photos of the same piece.",
  },
  {
    q: "Which pieces don't you do?",
    a: "For now, no metal, chrome or glass, and no pieces with thin legs or tubes: the reflections and proportions don't come out right, and we'd rather not charge you for that. Solid wood and stone, ceramics and upholstery work well.",
  },
  {
    q: "Does the model match the dimensions I give?",
    a: "Yes: we fit it to your dimensions within ±3% per axis and check it before showing it to you. The viewer shows the dimensions before you download anything.",
  },
  {
    q: "Which files do I get?",
    a: "A GLB with 2K textures that works on any website, and a USDZ for augmented reality on iPhone. Both at real scale.",
  },
  {
    q: "How do I see it in my room?",
    a: "On your phone, the augmented reality button places the piece in your living room at real size. It works on most iPhone and Android phones, with nothing to install.",
  },
  {
    q: "What if I don't like the result?",
    a: "Request another version (up to two per piece) or close it. Neither uses credits: you only pay for the pieces you download.",
  },
  {
    q: "How long does it take?",
    a: "There's no fixed turnaround: it depends on the generation queue and on our review. We'll email you when your piece is ready.",
  },
];

export function Faq() {
  return (
    <Box as="section" id="faq" py={{ base: 14, md: 24 }} scrollMarginTop="4">
      <Container maxW="3xl" px={{ base: 4, md: 8 }}>
        <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em" mb="8">
          Frequently asked questions
        </Heading>
        <Stack gap="0" borderTopWidth="1px" borderColor="border">
          {QUESTIONS.map(({ q, a }) => (
            // Native <details>: no JavaScript needed for the accordion.
            <Box as="details" key={q} borderBottomWidth="1px" borderColor="border" py="4" css={{ "& > summary::-webkit-details-marker": { display: "none" } }}>
              <Box as="summary" cursor="pointer" fontWeight="600" fontSize="lg" listStyleType="none" display="flex" justifyContent="space-between" gap="4">
                {q}
                <Text as="span" color="fg.subtle" aria-hidden>
                  +
                </Text>
              </Box>
              <Text mt="3" color="fg.muted" textWrap="pretty">
                {a}
              </Text>
            </Box>
          ))}
        </Stack>
      </Container>
    </Box>
  );
}
