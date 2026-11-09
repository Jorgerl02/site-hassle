import { Box, Container, Flex, HStack, Link, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { PRODUCT_NAME } from "@/lib/site";
import { StartCta } from "./StartCta";

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
              <NextLink href="/#how-it-works">How it works</NextLink>
            </Link>
            <Link asChild color="fg.muted" fontSize="sm">
              <NextLink href="/#pricing">Pricing</NextLink>
            </Link>
            <Link asChild color="fg.muted" fontSize="sm">
              <NextLink href="/entrar">Log in</NextLink>
            </Link>
            <Box display={{ base: "none", md: "block" }}>
              <StartCta source="landing_header" size="sm" />
            </Box>
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
          <Text>{PRODUCT_NAME}. True-to-scale 3D furniture models.</Text>
          <Flex gap="4" wrap="wrap">
            <Text>Prices include VAT.</Text>
            <Link asChild color="fg.subtle">
              <NextLink href="/privacy">Privacy and cookies</NextLink>
            </Link>
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
