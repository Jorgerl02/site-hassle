import { Badge, Box, Flex, Image, SimpleGrid, Stack, Text } from "@chakra-ui/react";
import type { CandidateView } from "@/lib/admin";
import { ModelPreview } from "./ModelPreview";

interface ReviewCardProps {
  candidate: CandidateView;
  /** Radio group name; the radio sits inside the review form. */
  name: string;
  checked: boolean;
  disabled?: boolean;
  onSelect?: () => void;
}

/** One generated candidate: radio, renders, 3D preview and scale error per axis. */
export function ReviewCard({ candidate, name, checked, disabled, onSelect }: ReviewCardProps) {
  const inputId = `candidate-${candidate.id}`;
  const usable = candidate.modelUrl !== null && !candidate.error;
  return (
    <Box
      as="article"
      data-testid="candidate"
      bg="bg.panel"
      borderWidth="2px"
      borderColor={checked ? "clay.solid" : "border"}
      rounded="xl"
      p={{ base: 4, md: 5 }}
    >
      <Flex asChild align="center" gap="3" mb="4" cursor={disabled ? "default" : "pointer"}>
        <label htmlFor={inputId}>
        <input
          id={inputId}
          type="radio"
          name={name}
          value={candidate.id}
          checked={checked}
          disabled={disabled || !usable}
          onChange={onSelect}
          style={{ width: 18, height: 18, accentColor: "var(--chakra-colors-clay-solid)" }}
        />
        <Text fontWeight="600">Candidato {candidate.candidate}</Text>
        <Text color="fg.muted" fontSize="sm">
          {candidate.provider}
        </Text>
        {candidate.selected ? <Badge colorPalette="clay">Elegido por el worker</Badge> : null}
        </label>
      </Flex>

      {candidate.error ? (
        <Text color="red.600" fontSize="sm" mb="3">
          Falló: {candidate.error}
        </Text>
      ) : null}

      <SimpleGrid columns={{ base: 1, md: 3 }} gap="4">
        <Box gridColumn={{ md: "span 2" }}>
          <SimpleGrid columns={2} gap="2">
            {candidate.renders.map((render) =>
              render.url ? (
                <Image
                  key={render.view}
                  src={render.url}
                  alt={`${render.label}, candidato ${candidate.candidate}`}
                  aspectRatio="1"
                  objectFit="contain"
                  bg="white"
                  rounded="md"
                  borderWidth="1px"
                  borderColor="border"
                  loading="lazy"
                />
              ) : (
                <Box key={render.view} aspectRatio="1" bg="bg.subtle" rounded="md" display="grid" placeItems="center">
                  <Text fontSize="xs" color="fg.muted">
                    {render.label}: sin render
                  </Text>
                </Box>
              ),
            )}
          </SimpleGrid>
        </Box>
        <Stack gap="3">
          <ModelPreview src={candidate.modelUrl} alt={`Modelo del candidato ${candidate.candidate}`} />
          <Box>
            <Text fontSize="sm" fontWeight="600" mb="1">
              Error de escala
            </Text>
            <Stack as="dl" gap="0.5" fontSize="sm" data-testid="scale-errors">
              {candidate.axisErrors.map((axis) => (
                <Flex key={axis.axis} justify="space-between" gap="2">
                  <Text as="dt" color="fg.muted">
                    {axis.label}
                  </Text>
                  <Text as="dd" fontVariantNumeric="tabular-nums" color={axis.high ? "red.600" : undefined}>
                    {axis.value}
                    {axis.beforeFit ? (
                      <Text as="span" color="fg.subtle">
                        {" "}
                        (antes del ajuste {axis.beforeFit})
                      </Text>
                    ) : null}
                  </Text>
                </Flex>
              ))}
              <Flex justify="space-between" gap="2" borderTopWidth="1px" borderColor="border" pt="1">
                <Text as="dt" color="fg.muted">
                  Máximo
                </Text>
                <Text
                  as="dd"
                  fontWeight="600"
                  fontVariantNumeric="tabular-nums"
                  color={candidate.maxErrorHigh ? "red.600" : undefined}
                >
                  {candidate.maxError}
                </Text>
              </Flex>
            </Stack>
            <Text fontSize="xs" color="fg.subtle" mt="2">
              {candidate.fitBoxApplied ? "Ajustado a la caja de medidas." : "Sin ajuste a caja."}
              {candidate.costUsd ? ` Coste del proveedor: ${candidate.costUsd}.` : null}
            </Text>
          </Box>
        </Stack>
      </SimpleGrid>
    </Box>
  );
}
