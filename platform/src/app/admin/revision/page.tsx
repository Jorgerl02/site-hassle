import { Badge, Box, Container, Flex, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import NextLink from "next/link";
import { AdminHeader } from "@/components/admin/AdminHeader";
import { ContactSheet } from "@/components/admin/ContactSheet";
import { listReviewQueue, requireAdmin } from "@/lib/admin";

export const metadata: Metadata = {
  title: "Revisión interna",
  robots: { index: false, follow: false },
};

export default async function ReviewQueuePage() {
  // 404 before anything streams for non-admins.
  await requireAdmin();
  const items = await listReviewQueue();

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
      </Container>
    </>
  );
}
