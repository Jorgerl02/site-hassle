import { Badge, Box, Button, Container, Flex, Grid, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { TrackEvent } from "@/components/Analytics";
import { requireUser } from "@/lib/auth";
import { formatCount, formatCreditDelta, formatCredits, getLedger, supabaseFulfillmentDeps, type LedgerClient } from "@/lib/credits";
import { formatEur, HIGHLIGHT_LABEL, PACKS, WAIVER_TEXT, type Pack } from "@/lib/pricing";

import { PRODUCT_NAME } from "@/lib/site";
import { fulfillCheckoutSession, getStripe, isStripeConfigured } from "@/lib/stripe";
import { createAdminClient } from "@/lib/supabase/admin";
import { createServerClient } from "@/lib/supabase/server";
import { startCheckout } from "./actions";


export const metadata: Metadata = {
  title: "Créditos",
  robots: { index: false },
};

const DATE_FORMAT = new Intl.DateTimeFormat("es-ES", {
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

type ReturnState = "paid" | "pending" | null;

interface ReturnInfo {
  state: ReturnState;
  /** Amount actually paid in euros, for the `purchase` conversion. */
  value?: number;
}

/**
 * Back from Checkout the webhook may not have arrived yet: fulfil from the
 * session itself (idempotent with the webhook), only for the signed-in owner.
 * Returns null unless the session was retrieved and belongs to the user.
 */
async function confirmReturn(sessionId: string | undefined, userId: string): Promise<ReturnInfo> {
  const stripe = getStripe();
  if (!stripe || !sessionId?.startsWith("cs_")) return { state: null };
  try {
    const session = await stripe.checkout.sessions.retrieve(sessionId);
    if (session.client_reference_id !== userId) return { state: null };
    if (session.payment_status === "unpaid") return { state: "pending" };
    const result = await fulfillCheckoutSession(
      session,
      supabaseFulfillmentDeps(() => createAdminClient() as unknown as LedgerClient),
    );
    if (!result.handled) return { state: null };
    return { state: "paid", value: session.amount_total != null ? session.amount_total / 100 : undefined };
  } catch (error) {
    console.error("[stripe] return confirmation failed", error);
    return { state: null };
  }
}

export default async function CreditsPage({ searchParams }: { searchParams: SearchParams }) {
  // Redirects to /entrar before anything streams when there is no session.
  const { user } = await requireUser();
  const params = await searchParams;
  const sessionId = param(params.session_id);
  const returned: ReturnInfo = param(params.ok) === "1" ? await confirmReturn(sessionId, user.id) : { state: null };
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
              <NextLink href="/panel">Tus piezas</NextLink>
            </Button>
          </Flex>
        </Container>
      </Box>

      <Container as="main" maxW="5xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Stack gap={{ base: 10, md: 14 }}>
          <Stack gap="4">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Créditos
            </Heading>
            {returnState === "paid" ? (
              <>
                <Notice tone="success">Pago recibido. Tus créditos ya están en tu saldo.</Notice>
                <TrackEvent
                  event="purchase"
                  onceKey={`purchase:${sessionId}`}
                  params={{ value: returned.value, currency: "EUR", transactionId: sessionId }}
                />
              </>
            ) : null}
            {returnState === "pending" ? (
              <Notice tone="success">
                Pago pendiente de confirmación. Sumaremos tus créditos en cuanto el banco lo confirme.
              </Notice>
            ) : null}
            {paymentError ? (
              <Notice tone="error">No hemos podido abrir el pago. Inténtalo de nuevo en unos minutos.</Notice>
            ) : null}
            {waiverError ? (
              <Notice tone="error">Para comprar, marca la casilla de entrega inmediata del contenido digital.</Notice>
            ) : null}
            <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p={{ base: 6, md: 8 }}>
              <Text color="fg.muted">Tu saldo</Text>
              <Flex align="baseline" gap="3" mt="1">
                <Text data-testid="credit-balance" fontFamily="heading" fontSize={{ base: "6xl", md: "7xl" }} lineHeight="1">
                  {formatCount(ledger.balance)}
                </Text>
                <Text fontSize="lg" color="fg.muted">
                  {ledger.balance === 1 ? "crédito" : "créditos"}
                </Text>
              </Flex>
              <Text mt="3" color="fg.muted" fontSize="sm">
                1 crédito = 1 pieza descargada (GLB con texturas 2K y USDZ).
              </Text>
            </Box>
          </Stack>

          <Stack as="section" gap="6" aria-labelledby="comprar">
            <Heading as="h2" id="comprar" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              Comprar créditos
            </Heading>
            {/* One form: each «Comprar» submits its pack; the waiver checkbox is required (native validation, checked again on the server). */}
            <Stack asChild gap="6">
              <form action={startCheckout}>
                <Grid templateColumns={{ base: "1fr", md: "repeat(3, 1fr)" }} gap={{ base: 4, md: 6 }} alignItems="stretch">
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
                        style={{ marginTop: "0.2rem", width: "1rem", height: "1rem", accentColor: "#9A5132", flexShrink: 0 }}
                      />
                      <Text as="span">{WAIVER_TEXT}</Text>
                    </label>
                  </Flex>
                ) : null}
              </form>
            </Stack>
            <Text fontSize="sm" color="fg.muted" textWrap="pretty">
              IVA incluido. Los créditos comprados no caducan. Sin reembolsos: por eso ves cada pieza entera, con sus
              medidas y en realidad aumentada, antes de gastar un crédito.
            </Text>
          </Stack>

          <Stack as="section" gap="4" aria-labelledby="movimientos">
            <Heading as="h2" id="movimientos" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              Movimientos
            </Heading>
            {ledger.entries.length === 0 ? (
              <Text color="fg.muted">Todavía no hay movimientos.</Text>
            ) : (
              <Stack as="ul" listStyleType="none" gap="0" borderTopWidth="1px" borderColor="border" data-testid="ledger">
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
                            {" "}· {entry.pieceName}
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
        {pack.credits === 1 ? "Una pieza descargada" : `${formatEur(pack.perPieceCents)} por pieza`}
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
          Comprar
        </Button>
      ) : (
        <Button disabled width="full" variant="outline" colorPalette="ink" rounded="full">
          Pagos no configurados
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
