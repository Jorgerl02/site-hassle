import { Box, Container, Grid, Heading, HStack, Stack, Text } from "@chakra-ui/react";
import Image from "next/image";
import { EXAMPLES, exampleDimensions, modelSrc, photoSrc, type Example } from "@/lib/examples";
import { LazyModel } from "./LazyModel";

export function Examples() {
  return (
    <Box as="section" id="examples" py={{ base: 14, md: 24 }} bg="bg.subtle" scrollMarginTop="4">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Stack gap="3" maxW="40em" mb={{ base: 8, md: 12 }}>
          <Heading as="h2" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500" letterSpacing="-0.01em">
            Real pieces, with their dimensions
          </Heading>
          <Text color="fg.muted" fontSize="lg" textWrap="pretty">
            On the left, the catalogue photo; on the right, the 3D model made from it. You can spin the first two and,
            on your phone, place them in your room at real size. Dimensions are width × height × depth.
          </Text>
        </Stack>
        <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)", xl: "repeat(3, 1fr)" }} gap={{ base: 4, md: 6 }}>
          {EXAMPLES.map((example) => (
            <ExampleCard key={example.id} example={example} />
          ))}
        </Grid>
      </Container>
    </Box>
  );
}

function ExampleCard({ example }: { example: Example }) {
  const alt3d = `3D model: ${example.name.toLowerCase()}`;
  return (
    <Stack as="article" bg="bg.panel" rounded="xl" borderWidth="1px" borderColor="border" p="4" gap="3">
      <HStack gap="3" align="stretch">
        <Box flex="1" position="relative" aspectRatio="1" rounded="lg" overflow="hidden" bg="white">
          <Image
            src={photoSrc(example.id)}
            alt={`Catalogue photo: ${example.name.toLowerCase()}`}
            fill
            sizes="(max-width: 768px) 45vw, 240px"
            style={{ objectFit: "contain" }}
          />
        </Box>
        <Box flex="1">
          {example.model ? (
            <LazyModel glb={example.model.glb} poster={modelSrc(example.id)} alt={alt3d} />
          ) : (
            <Box position="relative" aspectRatio="1" rounded="lg" overflow="hidden" bg="white">
              <Image src={modelSrc(example.id)} alt={alt3d} fill sizes="(max-width: 768px) 45vw, 240px" style={{ objectFit: "contain" }} />
            </Box>
          )}
        </Box>
      </HStack>
      <Stack gap="0.5">
        <Text fontWeight="600">{example.name}</Text>
        <Text fontSize="sm" color="fg.muted">
          {example.material} · {exampleDimensions(example)}
        </Text>
      </Stack>
    </Stack>
  );
}
