"use client";

import { Box, Button, Flex, Stack, Text, Textarea } from "@chakra-ui/react";
import { useActionState, useState } from "react";
import { submitReview, type ReviewActionResult } from "@/app/admin/revision/actions";
import type { CandidateView } from "@/lib/admin";
import { ReviewCard } from "./ReviewCard";

interface ReviewFormProps {
  pieceId: string;
  candidates: CandidateView[];
  canRegenerate: boolean;
}

const initialState: ReviewActionResult = { ok: true };

/** Candidate picker plus the three review decisions. */
export function ReviewForm({ pieceId, candidates, canRegenerate }: ReviewFormProps) {
  const [state, formAction, pending] = useActionState(submitReview, initialState);
  const initial = candidates.find((c) => c.selected) ?? candidates.find((c) => c.modelUrl && !c.error);
  const [modelId, setModelId] = useState(initial?.id ?? "");

  return (
    <form action={formAction}>
      <input type="hidden" name="pieceId" value={pieceId} />
      <Stack gap="6">
        <Stack gap="4" role="radiogroup" aria-label="Modelo que verá el cliente">
          {candidates.length === 0 ? (
            <Text color="fg.muted">Este intento no tiene modelos.</Text>
          ) : (
            candidates.map((candidate) => (
              <ReviewCard
                key={candidate.id}
                candidate={candidate}
                name="modelId"
                checked={modelId === candidate.id}
                disabled={pending}
                onSelect={() => setModelId(candidate.id)}
              />
            ))
          )}
        </Stack>

        <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p={{ base: 4, md: 5 }}>
          <Text asChild fontWeight="600" display="block" mb="1">
            <label htmlFor="review-note">Nota o motivo</label>
          </Text>
          <Text fontSize="sm" color="fg.muted" mb="2">
            Al regenerar es una nota interna. Al rechazar es el motivo que leerá el cliente.
          </Text>
          <Textarea id="review-note" name="note" rows={3} maxLength={2000} bg="white" />

          {state.message ? (
            <Text role="alert" data-testid="review-error" color="red.600" mt="3">
              {state.message}
            </Text>
          ) : null}

          <Flex gap="3" mt="4" wrap="wrap">
            <Button
              type="submit"
              name="intent"
              value="show"
              colorPalette="clay"
              rounded="full"
              disabled={pending || !modelId}
            >
              Mostrar al cliente
            </Button>
            <Button
              type="submit"
              name="intent"
              value="regenerate"
              variant="outline"
              colorPalette="ink"
              rounded="full"
              disabled={pending || !canRegenerate}
              title={canRegenerate ? undefined : "Ya va por el tercer intento"}
            >
              Regenerar
            </Button>
            <Button type="submit" name="intent" value="reject" variant="ghost" colorPalette="red" rounded="full" disabled={pending}>
              Rechazar
            </Button>
          </Flex>
        </Box>
      </Stack>
    </form>
  );
}
