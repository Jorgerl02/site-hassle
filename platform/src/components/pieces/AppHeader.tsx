import { Box, Button, Container, Flex, Link } from "@chakra-ui/react";
import NextLink from "next/link";
import { signOut } from "@/app/entrar/actions";
import { PRODUCT_NAME } from "@/lib/site";

/** Header of the signed-in area (panel and pieces). */
export function AppHeader() {
  return (
    <Box as="header" borderBottomWidth="1px" borderColor="border">
      <Container maxW="5xl" px={{ base: 4, md: 8 }}>
        <Flex h="16" align="center" justify="space-between" gap="4">
          <Link asChild fontFamily="heading" fontSize="xl" fontWeight="500" _hover={{ textDecoration: "none" }}>
            <NextLink href="/panel">{PRODUCT_NAME}</NextLink>
          </Link>
          <Flex gap="1" align="center">
            <Button asChild size="sm" variant="ghost" colorPalette="ink">
              <NextLink href="/creditos">Credits</NextLink>
            </Button>
            <form action={signOut}>
              <Button type="submit" size="sm" variant="ghost" colorPalette="ink">
                Sign out
              </Button>
            </form>
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
