"use client";

import { Box, Button, Container, Flex, Link, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { useEffect, useState } from "react";
import { analyticsEnabled } from "@/lib/analytics";
import { CONSENT_EVENT, clearConsent, readConsent, shouldAskConsent, writeConsent } from "@/lib/consent";

/**
 * Bottom bar asking for measurement cookies (Meta Pixel, GA4). Shown only when
 * an analytics id is configured and there is no valid stored choice; decided
 * after mount, so the server HTML never contains it.
 */
export function CookieConsent() {
  const [ask, setAsk] = useState(false);

  useEffect(() => {
    const update = () => setAsk(shouldAskConsent(analyticsEnabled(), readConsent()));
    update();
    window.addEventListener(CONSENT_EVENT, update);
    return () => window.removeEventListener(CONSENT_EVENT, update);
  }, []);

  if (!ask) return null;
  return (
    <Box
      role="region"
      aria-label="Cookie notice"
      data-testid="cookie-consent"
      position="fixed"
      insetX="0"
      bottom="0"
      zIndex="banner"
      bg="bg.panel"
      borderTopWidth="1px"
      borderColor="border"
      boxShadow="lg"
      py="4"
    >
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Flex direction={{ base: "column", md: "row" }} gap={{ base: 3, md: 6 }} align={{ md: "center" }} justify="space-between">
          <Text fontSize="sm" textWrap="pretty">
            We use measurement cookies to see whether our ads work. You can accept or reject them.{" "}
            <Link asChild color="clay.fg" fontWeight="600">
              <NextLink href="/privacy">Privacy and cookies</NextLink>
            </Link>
          </Text>
          <Flex gap="3" flexShrink={0}>
            <Button size="sm" variant="outline" colorPalette="ink" rounded="full" onClick={() => writeConsent("denied")}>
              Reject
            </Button>
            <Button size="sm" colorPalette="clay" rounded="full" onClick={() => writeConsent("granted")}>
              Accept
            </Button>
          </Flex>
        </Flex>
      </Container>
    </Box>
  );
}

/** "Change my cookie choice" on /privacy: forgets the choice so the banner asks again. */
export function ResetConsentButton() {
  // Build-time constant: same answer on the server and in the browser.
  if (!analyticsEnabled()) return null;
  return (
    <Button size="sm" variant="outline" colorPalette="ink" rounded="full" onClick={() => clearConsent()}>
      Change my cookie choice
    </Button>
  );
}
