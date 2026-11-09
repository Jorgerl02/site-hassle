import { Badge, Box, Button, Container, Flex, Grid, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { TrackEvent } from "@/components/Analytics";
import { requireUser } from "@/lib/auth";
import { SaveAccountCard } from "@/components/pieces/SaveAccount";
import { confirmCheckoutReturn, type ReturnInfo } from "@/lib/checkout-return";
import { formatCount, formatCreditDelta, formatCredits, getLedger, type LedgerClient } from "@/lib/credits";
import { formatEur, HIGHLIGHT_LABEL, PACKS, WAIVER_TEXT, type Pack } from "@/lib/pricing";

import { PRODUCT_NAME } from "@/lib/site";
import { isStripeConfigured } from "@/lib/stripe";
import { createServerClient } from "@/lib/supabase/server";
import { startCheckout } from "./actions";

export const metadata: Metadata = {
  title: "Credits",
  robots: { index: false },
};

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Madrid",
});

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function param(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CreditsPage({ searchParams }: { searchParams: SearchParams }) {
  // Redirects to /entrar before anything streams when there is no session.
  const { user } = await requireUser();
  const anonymous = user.is_anonymous === true;
  const params = await searchParams;
  const sessionId = param(params.session_id);
  const returned: ReturnInfo =
    param(params.ok) === "1" ? await confirmCheckoutReturn(sessionId, user.id) : { state: null };
  const returnState = returned.state;
  const paymentError = param(params.error) === "pago";
  const waiverError = param(params.error) === "desistimiento";

  const supabase = await createServerClient();
  const ledger = await getLedger(user.id, supabase as unknown as LedgerClient);
  const paymentsEnabled = isStripeConfigured();

  return (
    <>
      <Box as="header" borderBottomWidth="1px" borderColor="border">
        <Container maxW="5xl" px={{ base: 4, md: 8 }}>
          <Flex h="16" align="center" justify="space-between">
            <NextLink href="/panel">
              <Text fontFamily="heading" fontSize="xl" fontWeight="500">
                {PRODUCT_NAME}
              </Text>
            </NextLink>
            <Button asChild size="sm" variant="ghost" colorPalette="ink">
              <NextLink href="/panel">Your pieces</NextLink>
            </Button>
          </Flex>
        </Container>
      </Box>

      <Container as="main" maxW="5xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Stack gap={{ base: 10, md: 14 }}>
          <Stack gap="4">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Credits
            </Heading>
            {returnState === "paid" ? (
              <>
                <Notice tone="success">Payment received. Your credits are now in your balance.</Notice>
                <TrackEvent
                  event="purchase"
                  onceKey={`purchase:${sessionId}`}
                  params={{ value: returned.value, currency: "EUR", transactionId: sessionId }}
                />
              </>
            ) : null}
            {returnState === "pending" ? (
              <Notice tone="success">
                Payment pending confirmation. We&apos;ll add your credits as soon as your bank confirms it.
              </Notice>
            ) : null}
            {paymentError ? (
              <Notice tone="error">We couldn&apos;t open the payment page. Please try again in a few minutes.</Notice>
            ) : null}
            {waiverError ? (
              <Notice tone="error">To buy, tick the box about immediate delivery of the digital content.</Notice>
            ) : null}
            <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p={{ base: 6, md: 8 }}>
              <Text color="fg.muted">Your balance</Text>
              <Flex align="baseline" gap="3" mt="1">
                <Text
                  data-testid="credit-balance"
                  fontFamily="heading"
                  fontSize={{ base: "6xl", md: "7xl" }}
                  lineHeight="1"
                >
                  {formatCount(ledger.balance)}
                </Text>
                <Text fontSize="lg" color="fg.muted">
                  {ledger.balance === 1 ? "credit" : "credits"}
                </Text>
              </Flex>
              <Text mt="3" color="fg.muted" fontSize="sm">
                1 credit = 1 downloaded piece (GLB with 2K textures and USDZ).
              </Text>
            </Box>
          </Stack>

          <Stack as="section" gap="6" aria-labelledby="buy">
            <Heading as="h2" id="buy" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              Buy credits
            </Heading>
            {/* One form: each "Buy" submits its pack; the waiver checkbox is required (native validation, checked again on the server). */}
            {anonymous ? (
              <SaveAccountCard
                next="/creditos"
                title="Save your account to buy credits"
                body="Credits, receipts and invoices go to your email. Your pieces stay as they are."
              />
            ) : (
              <Stack asChild gap="6">
                <form action={startCheckout}>
                  <Grid
                    templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }}
                    gap={{ base: 4, md: 6 }}
                    alignItems="stretch"
                  >
                    {PACKS.map((pack) => (
                      <PackCard key={pack.id} pack={pack} paymentsEnabled={paymentsEnabled} />
                    ))}
                  </Grid>
                  {paymentsEnabled ? (
                    <Flex asChild gap="3" align="flex-start" fontSize="sm" cursor="pointer">
                      <label>
                        <input
                          type="checkbox"
                          name="waiver"
                          required
                          data-testid="waiver"
                          style={{
                            marginTop: "0.2rem",
                            width: "1rem",
                            height: "1rem",
                            accentColor: "#9A5132",
                            flexShrink: 0,
                          }}
                        />
                        <Text as="span">{WAIVER_TEXT}</Text>
                      </label>
                    </Flex>
                  ) : null}
                </form>
              </Stack>
            )}
            <Text fontSize="sm" color="fg.muted" textWrap="pretty">
              VAT included. Used credits are non-refundable · unused credits never expire. That&apos;s why you see every
              piece in full, with its dimensions and in augmented reality, before you spend a credit.
            </Text>
          </Stack>

          <Stack as="section" gap="4" aria-labelledby="history">
            <Heading as="h2" id="history" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              History
            </Heading>
            {ledger.entries.length === 0 ? (
              <Text color="fg.muted">No activity yet.</Text>
            ) : (
              <Stack
                as="ul"
                listStyleType="none"
                gap="0"
                borderTopWidth="1px"
                borderColor="border"
                data-testid="ledger"
              >
                {ledger.entries.map((entry) => (
                  <Flex
                    as="li"
                    key={entry.id}
                    data-testid="ledger-entry"
                    py="3"
                    borderBottomWidth="1px"
                    borderColor="border"
                    justify="space-between"
                    align="center"
                    gap="4"
                  >
                    <Stack gap="0.5">
                      <Text fontWeight="600">
                        {entry.label}
                        {entry.pieceName ? (
                          <Text as="span" fontWeight="400" color="fg.muted">
                            {" "}
                            · {entry.pieceName}
                          </Text>
                        ) : null}
                      </Text>
                      <Text fontSize="sm" color="fg.muted">
                        <time dateTime={entry.createdAt}>{DATE_FORMAT.format(new Date(entry.createdAt))}</time>
                      </Text>
                    </Stack>
                    <Text
                      fontWeight="600"
                      fontVariantNumeric="tabular-nums"
                      color={entry.delta > 0 ? "clay.fg" : "fg"}
                      aria-label={formatCredits(entry.delta)}
                    >
                      {formatCreditDelta(entry.delta)}
                    </Text>
                  </Flex>
                ))}
              </Stack>
            )}
          </Stack>
        </Stack>
      </Container>
    </>
  );
}

function PackCard({ pack, paymentsEnabled }: { pack: Pack; paymentsEnabled: boolean }) {
  return (
    <Stack
      as="article"
      data-testid={`pack-${pack.id}`}
      bg="bg.panel"
      rounded="xl"
      borderWidth={pack.highlighted ? "2px" : "1px"}
      borderColor={pack.highlighted ? "clay.solid" : "border"}
      p={{ base: 6, md: 8 }}
      gap="4"
      position="relative"
    >
      {pack.highlighted ? (
        <Badge position="absolute" top="-3" left="6" colorPalette="clay" variant="solid" rounded="full" px="3">
          {HIGHLIGHT_LABEL}
        </Badge>
      ) : null}
      <Text fontWeight="600" fontSize="lg">
        {pack.label}
      </Text>
      <Text fontFamily="heading" fontSize="5xl" lineHeight="1" whiteSpace="nowrap">
        {formatEur(pack.priceCents)}
      </Text>
      <Text color="fg.muted" fontSize="sm">
        {pack.credits === 1 ? "One downloaded piece" : `${formatEur(pack.perPieceCents)} per piece`}
      </Text>
      <Box flex="1" />
      {paymentsEnabled ? (
        <Button
          type="submit"
          name="pack"
          value={pack.id}
          width="full"
          colorPalette={pack.highlighted ? "clay" : "ink"}
          variant={pack.highlighted ? "solid" : "outline"}
          rounded="full"
        >
          Buy
        </Button>
      ) : (
        <Button disabled width="full" variant="outline" colorPalette="ink" rounded="full">
          Payments not configured
        </Button>
      )}
    </Stack>
  );
}

function Notice({ tone, children }: { tone: "success" | "error"; children: React.ReactNode }) {
  return (
    <Box
      role={tone === "error" ? "alert" : "status"}
      rounded="lg"
      px="4"
      py="3"
      bg={tone === "error" ? "red.subtle" : "clay.subtle"}
      color={tone === "error" ? "red.fg" : "clay.fg"}
    >
      {children}
    </Box>
  );
}
