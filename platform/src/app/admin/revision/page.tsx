import { Badge, Box, Container, Flex, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { AdminHeader } from "@/components/admin/AdminHeader";
import { ContactSheet } from "@/components/admin/ContactSheet";
import { FailedActions } from "@/components/admin/FailedActions";
import { WithdrawButton } from "@/components/admin/WithdrawButton";
import { AUTO_PUBLISHED_HOURS, listAutoPublished, listFailedPieces, listReviewQueue, requireAdmin } from "@/lib/admin";

export const metadata: Metadata = {
  title: "Revisión interna",
  robots: { index: false, follow: false },
};

export default async function ReviewQueuePage() {
  // 404 before anything streams for non-admins.
  await requireAdmin();
  const [items, failed, published] = await Promise.all([listReviewQueue(), listFailedPieces(), listAutoPublished()]);

  return (
    <>
      <AdminHeader />
      <Container as="main" maxW="6xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Flex justify="space-between" align="baseline" gap="4" wrap="wrap" mb="8">
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            Cola de revisión
          </Heading>
          <Text color="fg.muted">
            {items.length === 1 ? "1 pieza esperando" : `${items.length} piezas esperando`}
          </Text>
        </Flex>

        {items.length === 0 ? (
          <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p="8" textAlign="center">
            <Text fontWeight="600">No hay piezas por revisar</Text>
            <Text color="fg.muted" mt="1">
              Cuando el worker termine una pieza aparecerá aquí.
            </Text>
          </Box>
        ) : (
          <Stack as="ol" listStyleType="none" gap="4">
            {items.map((item) => (
              <Box
                as="li"
                key={item.id}
                data-testid="queue-item"
                bg="bg.panel"
                borderWidth="1px"
                borderColor="border"
                rounded="xl"
                p={{ base: 4, md: 5 }}
              >
                <NextLink href={`/admin/revision/${item.id}`}>
                  <Stack gap="3">
                    <Flex justify="space-between" align="baseline" gap="3" wrap="wrap">
                      <Text fontWeight="600" fontSize="lg">
                        {item.name}
                      </Text>
                      <Text fontSize="sm" color="fg.muted" fontVariantNumeric="tabular-nums">
                        Esperando {item.waiting}
                      </Text>
                    </Flex>
                    <ContactSheet url={item.contactUrl} alt={`Hoja de contacto de ${item.name}`} />
                    <Flex gap="2" wrap="wrap" fontSize="sm" color="fg.muted" align="center">
                      <Text>{item.kindLabel}</Text>
                      <Text aria-hidden>·</Text>
                      <Text fontVariantNumeric="tabular-nums">{item.dimensions}</Text>
                      <Text aria-hidden>·</Text>
                      <Text>Intento {item.attempt}</Text>
                      <Text aria-hidden>·</Text>
                      <Text>{item.provider}</Text>
                      <Badge colorPalette={item.maxErrorHigh ? "red" : "gray"} fontVariantNumeric="tabular-nums">
                        Error máx. {item.maxError}
                      </Badge>
                      {item.email ? (
                        <Text ms="auto" color="fg.subtle">
                          {item.email}
                        </Text>
                      ) : null}
                    </Flex>
                  </Stack>
                </NextLink>
              </Box>
            ))}
          </Stack>
        )}

        <Stack as="section" gap="4" mt="14" aria-labelledby="publicadas">
          <Flex justify="space-between" align="baseline" gap="4" wrap="wrap">
            <Heading as="h2" id="publicadas" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              Publicadas automáticamente (últimas {AUTO_PUBLISHED_HOURS} h)
            </Heading>
            <Text color="fg.muted">{published.length === 1 ? "1 pieza" : `${published.length} piezas`}</Text>
          </Flex>
          {published.length === 0 ? (
            <Text color="fg.muted">Ninguna pieza publicada sin revisión en las últimas {AUTO_PUBLISHED_HOURS} h.</Text>
          ) : (
            <Stack as="ol" listStyleType="none" gap="4">
              {published.map((item) => (
                <Box
                  as="li"
                  key={item.id}
                  data-testid="auto-published-item"
                  bg="bg.panel"
                  borderWidth="1px"
                  borderColor="border"
                  rounded="xl"
                  p={{ base: 4, md: 5 }}
                >
                  <Stack gap="3">
                    <Flex justify="space-between" align="baseline" gap="3" wrap="wrap">
                      <NextLink href={`/admin/revision/${item.id}`}>
                        <Text fontWeight="600" fontSize="lg">
                          {item.name}
                        </Text>
                      </NextLink>
                      <Text fontSize="sm" color="fg.muted" fontVariantNumeric="tabular-nums">
                        Publicada hace {item.publishedAgo}
                      </Text>
                    </Flex>
                    <ContactSheet url={item.contactUrl} alt={`Hoja de contacto de ${item.name}`} />
                    <Flex gap="2" wrap="wrap" fontSize="sm" color="fg.muted" align="center">
                      <Text>{item.kindLabel}</Text>
                      <Text aria-hidden>·</Text>
                      <Text fontVariantNumeric="tabular-nums">{item.dimensions}</Text>
                      <Text aria-hidden>·</Text>
                      <Text>Intento {item.attempt}</Text>
                      {item.route ? (
                        <>
                          <Text aria-hidden>·</Text>
                          <Text>Ruta {item.route}</Text>
                        </>
                      ) : null}
                      <Badge colorPalette="gray" fontVariantNumeric="tabular-nums">
                        Error máx. {item.maxError}
                      </Badge>
                      <Badge colorPalette={item.canWithdraw ? "green" : "gray"}>{item.statusLabel}</Badge>
                      {item.email ? (
                        <Text ms="auto" color="fg.subtle">
                          {item.email}
                        </Text>
                      ) : null}
                    </Flex>
                    <Box fontSize="sm" data-testid="auto-published-reasons">
                      <Text color="fg.muted">Decisión por {item.gate}:</Text>
                      <Stack as="ul" gap="0.5" ps="4" listStyleType="disc">
                        {item.reasons.map((reason) => (
                          <Text as="li" key={reason}>
                            {reason}
                          </Text>
                        ))}
                      </Stack>
                    </Box>
                    {item.canWithdraw ? <WithdrawButton pieceId={item.id} /> : null}
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Stack>

        <Stack as="section" gap="4" mt="14" aria-labelledby="fallidas">
          <Flex justify="space-between" align="baseline" gap="4" wrap="wrap">
            <Heading as="h2" id="fallidas" fontSize={{ base: "2xl", md: "3xl" }} fontWeight="500">
              Fallidas
            </Heading>
            <Text color="fg.muted">{failed.length === 1 ? "1 pieza" : `${failed.length} piezas`}</Text>
          </Flex>
          {failed.length === 0 ? (
            <Text color="fg.muted">No hay piezas fallidas.</Text>
          ) : (
            <Stack as="ol" listStyleType="none" gap="4">
              {failed.map((item) => (
                <Box
                  as="li"
                  key={item.id}
                  data-testid="failed-item"
                  bg="bg.panel"
                  borderWidth="1px"
                  borderColor="border"
                  rounded="xl"
                  p={{ base: 4, md: 5 }}
                >
                  <Stack gap="3">
                    <Flex justify="space-between" align="baseline" gap="3" wrap="wrap">
                      <Text fontWeight="600" fontSize="lg">
                        {item.name}
                      </Text>
                      <Text fontSize="sm" color="fg.muted" fontVariantNumeric="tabular-nums">
                        Falló hace {item.waiting}
                      </Text>
                    </Flex>
                    <Flex gap="2" wrap="wrap" fontSize="sm" color="fg.muted">
                      <Text>{item.kindLabel}</Text>
                      <Text aria-hidden>·</Text>
                      <Text fontVariantNumeric="tabular-nums">{item.dimensions}</Text>
                      <Text aria-hidden>·</Text>
                      <Text>Intento {item.attempt}</Text>
                      {item.route ? (
                        <>
                          <Text aria-hidden>·</Text>
                          <Text>Ruta {item.route}</Text>
                        </>
                      ) : null}
                      {item.email ? (
                        <Text ms="auto" color="fg.subtle">
                          {item.email}
                        </Text>
                      ) : null}
                    </Flex>
                    <Box
                      as="pre"
                      data-testid="failed-error"
                      bg="bg.subtle"
                      rounded="md"
                      p="3"
                      fontSize="xs"
                      whiteSpace="pre-wrap"
                      wordBreak="break-word"
                    >
                      {item.error ?? "Sin detalle del error."}
                    </Box>
                    <FailedActions pieceId={item.id} shape={item.shape} />
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Stack>
      </Container>

    </>
  );
}
