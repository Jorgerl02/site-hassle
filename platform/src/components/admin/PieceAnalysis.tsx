import { Badge, Box, Flex, Heading, List, Stack, Text } from "@chakra-ui/react";
import type { PieceAnalysis as Analysis } from "@/lib/admin-labels";

function Section({ title, items, testId, tone }: { title: string; items: string[]; testId: string; tone?: "warn" }) {
  if (items.length === 0) return null;
  return (
    <Box data-testid={testId}>
      <Text fontWeight="600" fontSize="sm" mb="1" color={tone === "warn" ? "orange.700" : undefined}>
        {title}
      </Text>
      <List.Root fontSize="sm" ps="4" gap="0.5">
        {items.map((item) => (
          <List.Item key={item}>{item}</List.Item>
        ))}
      </List.Root>
    </Box>
  );
}

/**
 * What the worker decided for this attempt: the effective shape answers and
 * where each came from, the photo reading (confidence, reasons), conflicts with
 * the customer, dimension and delivery warnings, the material and the
 * automatic-publishing decision.
 */
export function PieceAnalysisPanel({ analysis }: { analysis: Analysis }) {
  const review = analysis.autoReview;
  return (
    <Box as="section" aria-labelledby="analisis" bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p={{ base: 4, md: 5 }} mb="10">
      <Flex justify="space-between" align="baseline" gap="3" wrap="wrap" mb="4">
        <Heading as="h2" id="analisis" fontSize="xl" fontWeight="500">
          Interpretación y decisión del worker
        </Heading>
        {review ? (
          <Badge colorPalette={review.auto ? "green" : "orange"} data-testid="auto-review-decision">
            {review.decision} ({review.gate})
          </Badge>
        ) : null}
      </Flex>
      <Stack gap="4">
        <Box as="dl" display="grid" gridTemplateColumns={{ base: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }} gap="3" data-testid="effective-answers">
          {analysis.answers.map((answer) => (
            <Box key={answer.label}>
              <Text as="dt" fontSize="sm" color="fg.muted">
                {answer.label}
              </Text>
              <Text as="dd" fontSize="sm">
                {answer.value}{" "}
                <Text as="span" color="fg.subtle">
                  ({answer.source})
                </Text>
              </Text>
            </Box>
          ))}
        </Box>
        <Text fontSize="sm" color="fg.muted" fontVariantNumeric="tabular-nums">
          Confianza de la foto: {analysis.confidence} (recta) · {analysis.supportConfidence} (apoyo)
          {analysis.material ? ` · Material: ${analysis.material}` : ""}
        </Text>
        <Section title="Conflictos con el cliente" items={analysis.conflicts} testId="analysis-conflicts" tone="warn" />
        <Section title="Avisos de medidas (los vería el cliente)" items={analysis.dimensionWarnings} testId="analysis-dimension-warnings" tone="warn" />
        <Section title="Avisos de generación y entrega" items={analysis.warnings} testId="analysis-warnings" tone="warn" />
        {review ? <Section title="Motivos de la decisión" items={[...review.reasons, ...(review.scores ? [`Notas del juez: ${review.scores}`] : [])]} testId="auto-review-reasons" /> : null}
        <Section title="Ruta" items={analysis.routeReasons} testId="analysis-route" />
        <Section title="Lectura de la foto (técnica)" items={analysis.reasons} testId="analysis-reasons" />
      </Stack>
    </Box>
  );
}
