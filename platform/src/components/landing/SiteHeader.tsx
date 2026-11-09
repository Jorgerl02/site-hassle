import { Box, Button, Container, Flex, HStack, Link, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { PRODUCT_NAME } from "@/lib/site";

export function SiteHeader() {
  return (
    <Box as="header" borderBottomWidth="1px" borderColor="border" bg="bg">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Flex h="16" align="center" justify="space-between">
          <Link asChild fontFamily="heading" fontSize="xl" fontWeight="500" color="fg" _hover={{ textDecoration: "none" }}>
            <NextLink href="/">{PRODUCT_NAME}</NextLink>
          </Link>
          <HStack gap={{ base: 3, md: 6 }}>
            <Link asChild display={{ base: "none", sm: "inline-flex" }} color="fg.muted" fontSize="sm">
              <NextLink href="/#como-funciona">Cómo funciona</NextLink>
            </Link>
            <Link asChild color="fg.muted" fontSize="sm">
              <NextLink href="/#precios">Precios</NextLink>
            </Link>
            <Button asChild size="sm" variant="outline" colorPalette="ink" rounded="full">
              <NextLink href="/entrar">Entrar</NextLink>
            </Button>
          </HStack>
        </Flex>
      </Container>
    </Box>
  );
}

export function SiteFooter() {
  return (
    <Box as="footer" borderTopWidth="1px" borderColor="border" py="10">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Flex direction={{ base: "column", sm: "row" }} gap="3" justify="space-between" color="fg.subtle" fontSize="sm">
          <Text>{PRODUCT_NAME}. Modelos 3D de muebles a escala real.</Text>
          <Text>Precios con IVA incluido.</Text>
        </Flex>
      </Container>
    </Box>
  );
}
