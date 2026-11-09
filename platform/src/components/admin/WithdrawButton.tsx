"use client";

import { Button, Stack, Text } from "@chakra-ui/react";
import { useActionState } from "react";
import { submitWithdraw, type ReviewActionResult } from "@/app/admin/revision/actions";

const initialState: ReviewActionResult = { ok: true };

/** «Retirar» an automatically published piece (back to `review`). */
export function WithdrawButton({ pieceId }: { pieceId: string }) {
  const [state, formAction, pending] = useActionState(submitWithdraw, initialState);
  return (
    <form action={formAction}>
      <input type="hidden" name="pieceId" value={pieceId} />
      <Stack gap="1" align="flex-start">
        <Button type="submit" variant="outline" colorPalette="red" rounded="full" size="sm" loading={pending}>
          Retirar
        </Button>
        {state.message ? (
          <Text role={state.ok ? "status" : "alert"} data-testid="withdraw-message" fontSize="sm" color={state.ok ? "fg.muted" : "red.600"}>
            {state.message}
          </Text>
        ) : null}
      </Stack>
    </form>
  );
}
