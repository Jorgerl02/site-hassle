"use client";

import { Button, Flex, Stack, Text, Textarea } from "@chakra-ui/react";
import { useActionState } from "react";
import { submitFailed, type ReviewActionResult } from "@/app/admin/revision/actions";
import type { ShapeValues } from "@/lib/admin-labels";
import { ShapeFields } from "./ShapeFields";

const initialState: ReviewActionResult = { ok: true };

/** «Reintentar» (same attempt, back to the queue, with the corrected shape) and «Rechazar» (reason for the customer). */
export function FailedActions({ pieceId, shape }: { pieceId: string; shape: ShapeValues }) {
  const [state, formAction, pending] = useActionState(submitFailed, initialState);
  const noteId = `failed-note-${pieceId}`;

  return (
    <form action={formAction}>
      <input type="hidden" name="pieceId" value={pieceId} />
      <Stack gap="2">
        <ShapeFields idPrefix={`failed-${pieceId}`} defaults={shape} disabled={pending} />
        <Text asChild fontSize="sm" color="fg.muted">
          <label htmlFor={noteId}>Motivo del rechazo (lo leerá el cliente)</label>
        </Text>
        <Textarea id={noteId} name="note" rows={2} maxLength={2000} bg="white" />
        {state.message ? (
          <Text role={state.ok ? "status" : "alert"} data-testid="failed-message" color={state.ok ? "fg.muted" : "red.600"}>
            {state.message}
          </Text>
        ) : null}
        <Flex gap="3" wrap="wrap">
          <Button type="submit" name="intent" value="retry" colorPalette="clay" rounded="full" size="sm" loading={pending}>
            Reintentar
          </Button>
          <Button
            type="submit"
            name="intent"
            value="reject"
            variant="outline"
            colorPalette="ink"
            rounded="full"
            size="sm"
            disabled={pending}
          >
            Rechazar
          </Button>
        </Flex>
      </Stack>
    </form>
  );
}
