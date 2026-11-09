import { Box, Container, Flex, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { PRODUCT_NAME } from "@/lib/site";

export function AdminHeader() {
  return (
    <Box as="header" borderBottomWidth="1px" borderColor="border">
      <Container maxW="6xl" px={{ base: 4, md: 8 }}>
        <Flex h="16" align="center" justify="space-between" gap="4">
          <Text fontFamily="heading" fontSize="xl" fontWeight="500">
            {PRODUCT_NAME} · Revisión
          </Text>
          <NextLink href="/admin/revision">
            <Text fontSize="sm" color="fg.muted">
              Cola
            </Text>
          </NextLink>
        </Flex>
      </Container>
    </Box>
  );
}
