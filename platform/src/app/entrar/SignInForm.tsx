"use client";

import { Button, Field, Input, Link, Stack, Text } from "@chakra-ui/react";
import NextLink from "next/link";
import { useSearchParams } from "next/navigation";
import { useActionState } from "react";
import { GoogleButton } from "@/components/pieces/GoogleButton";
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
    <Stack gap="3">
      <GoogleButton next="/panel" link={false} />
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
            Email me a login link
          </Button>
          <Text fontSize="sm" color="fg.subtle">
            New here? You don&apos;t need an account to start:{" "}
            <Link asChild color="clay.fg" fontWeight="600">
              <NextLink href="/piezas/nueva?source=login_page">turn a photo into a 3D model</NextLink>
            </Link>
            .
          </Text>
        </Stack>
      </form>
    </Stack>
  );
}
