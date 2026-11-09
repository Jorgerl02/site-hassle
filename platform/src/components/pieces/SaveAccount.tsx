"use client";

import { Box, Button, Field, Input, Stack, Text } from "@chakra-ui/react";
import { useActionState } from "react";
import { saveAccount, type SaveAccountState } from "@/app/account/actions";
import { GoogleButton } from "./GoogleButton";

interface SaveAccountFormProps {
  /** Where the confirmation link brings the customer back (same-site path). */
  next: string;
  submitLabel?: string;
}

/**
 * Google first (when enabled), email below. Converts the anonymous trial
 * into an account keeping the same user and pieces.
 */
export function SaveAccountForm({ next, submitLabel = "Email me a link" }: SaveAccountFormProps) {
  const [state, formAction, pending] = useActionState<SaveAccountState, FormData>(saveAccount, { status: "idle" });
  if (state.status === "sent") {
    return (
      <Stack gap="2" role="status" data-testid="save-account-sent">
        <Text fontWeight="600">Check your email</Text>
        {state.existing ? (
          <Text color="fg.muted">
            <strong>{state.email}</strong> already has an account. We&apos;ve sent you a sign-in link: open it in this
            browser and we&apos;ll move this piece to your account.
          </Text>
        ) : (
          <Text color="fg.muted">
            We&apos;ve sent a link to <strong>{state.email}</strong>. Open it on this device, in this browser, so your
            piece stays with your account.
          </Text>
        )}
      </Stack>
    );
  }

  const error = state.status === "error" ? state.message : null;
  return (
    <Stack gap="3">
      <GoogleButton next={next} link />
      <form action={formAction} noValidate>
        <input type="hidden" name="next" value={next} />
        <Stack gap="3">
          <Field.Root invalid={Boolean(error)}>
            <Field.Label>Email</Field.Label>
            <Input
              name="email"
              type="email"
              autoComplete="email"
              inputMode="email"
              placeholder="you@yourstore.com"
              bg="bg.panel"
              defaultValue={state.status === "error" ? state.email : undefined}
            />
            {error ? <Field.ErrorText>{error}</Field.ErrorText> : null}
          </Field.Root>
          <Button type="submit" colorPalette="clay" rounded="full" loading={pending} loadingText="Sending…">
            {submitLabel}
          </Button>
        </Stack>
      </form>
    </Stack>
  );
}

/** Optional card shown to an anonymous customer while the piece is generating. */
export function SaveAccountCard({ next, title, body }: { next: string; title: string; body: string }) {
  return (
    <Box bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p={{ base: 4, md: 5 }} data-testid="save-account-card">
      <Stack gap="3">
        <Stack gap="1">
          <Text fontWeight="600">{title}</Text>
          <Text fontSize="sm" color="fg.muted">
            {body}
          </Text>
        </Stack>
        <SaveAccountForm next={next} />
      </Stack>
    </Box>
  );
}
