import { Box, Image, Text } from "@chakra-ui/react";

interface ContactSheetProps {
  url: string | null;
  alt: string;
}

/** The worker's contact sheet (photo + four renders in a row), or a placeholder. */
export function ContactSheet({ url, alt }: ContactSheetProps) {
  if (!url) {
    return (
      <Box bg="bg.subtle" rounded="md" aspectRatio="5 / 1" display="grid" placeItems="center">
        <Text fontSize="sm" color="fg.muted">
          Sin hoja de contacto
        </Text>
      </Box>
    );
  }
  return (
    <Image
      src={url}
      alt={alt}
      data-testid="contact-sheet"
      w="full"
      aspectRatio="5 / 1"
      objectFit="contain"
      bg="white"
      rounded="md"
      borderWidth="1px"
      borderColor="border"
      loading="lazy"
    />
  );
}
