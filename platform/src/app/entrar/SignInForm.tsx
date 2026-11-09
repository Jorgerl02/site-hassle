"use client";

import { Button, Field, Input, Stack, Text } from "@chakra-ui/react";
import { useSearchParams } from "next/navigation";
import { useActionState } from "react";
import { sendMagicLink, type SignInState } from "./actions";

const CALLBACK_ERRORS: Record<string, string> = {
  enlace: "This link has expired or has already been used. Request a new one and open it on this device.",
};

export function SignInForm() {
  const [state, formAction, pending] = useActionState<SignInState, FormData>(sendMagicLink, { status: "idle" });
  const callbackError = CALLBACK_ERRORS[useSearchParams().get("error") ?? ""];

  if (state.status === "sent") {
    return (
      <Stack gap="2" role="status" bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p="6">
        <Text fontWeight="600">Check your email</Text>
        <Text color="fg.muted">
          We&apos;ve sent a link to <strong>{state.email}</strong>. Open it in this browser to sign in.
        </Text>
      </Stack>
    );
  }

  const error = state.status === "error" ? state.message : callbackError;

  return (
    <form action={formAction} noValidate>
      <Stack gap="4">
        <Field.Root invalid={Boolean(error)}>
          <Field.Label>Email</Field.Label>
          <Input
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder="you@yourstore.com"
            required
            size="lg"
            bg="bg.panel"
            defaultValue={state.status === "error" ? state.email : undefined}
          />
          {error ? <Field.ErrorText>{error}</Field.ErrorText> : null}
        </Field.Root>
        <Button type="submit" size="lg" colorPalette="clay" rounded="full" loading={pending} loadingText="Sending…">
          Email me a sign-in link
        </Button>
        <Text fontSize="sm" color="fg.subtle">
          No password needed: we email you a link to sign in. If it&apos;s your first time, we&apos;ll create your account.
        </Text>
      </Stack>
    </form>
  );
}
