import { Box, Button, Container, Flex, Link, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { signOut } from "@/app/entrar/actions";
import { getCurrentUser } from "@/lib/auth";
import { formatCredits } from "@/lib/credits";
import { getBalance } from "@/lib/pieces";
import { PRODUCT_NAME } from "@/lib/site";

/**
 * Header of the app (panel and pieces). With an account: the credit balance
 * and «Buy» always visible, plus «Sign out». An anonymous trial (or nobody yet,
 * on the new-piece form) only gets «Log in»: signing out would lose the trial.
 */
export async function AppHeader() {
  const current = await getCurrentUser();
  const account = current && !current.user.is_anonymous ? current : null;
  const balance = account ? await getBalance(account.user.id) : null;

  return (
    <Box as="header" borderBottomWidth="1px" borderColor="border">
      <Container maxW="5xl" px={{ base: 4, md: 8 }}>
        <Flex h="16" align="center" justify="space-between" gap="4">
          <Link asChild fontFamily="heading" fontSize="xl" fontWeight="500" _hover={{ textDecoration: "none" }}>
            <NextLink href={current ? "/panel" : "/"}>{PRODUCT_NAME}</NextLink>
          </Link>
          <Flex gap="1" align="center">
            {account ? (
              <>
                <Link asChild fontSize="sm" color="fg.muted" px="2" data-testid="header-credits" _hover={{ textDecoration: "none" }}>
                  <NextLink href="/creditos">
                    <Text as="span" color="fg" fontWeight="600">
                      {formatCredits(balance ?? 0)}
                    </Text>
                    <Text as="span" aria-hidden>
                      {" · "}
                    </Text>
                    <Text as="span" color="clay.fg" fontWeight="600">
                      Buy
                    </Text>
                  </NextLink>
                </Link>
                <form action={signOut}>
                  <Button type="submit" size="sm" variant="ghost" colorPalette="ink">
                    Sign out
                  </Button>
                </form>
              </>
            ) : (
              <Button asChild size="sm" variant="ghost" colorPalette="ink">
                <NextLink href="/entrar">Log in</NextLink>
              </Button>
            )}
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}
