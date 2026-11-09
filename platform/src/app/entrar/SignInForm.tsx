"use client";

import { Button, Field, Input, Stack, Text } from "@chakra-ui/react";
import { useSearchParams } from "next/navigation";
import { useActionState } from "react";
import { sendMagicLink, type SignInState } from "./actions";

const CALLBACK_ERRORS: Record<string, string> = {
  enlace: "El enlace ha caducado o ya se ha usado. Pide otro y ábrelo en este mismo dispositivo.",
};

export function SignInForm() {
  const [state, formAction, pending] = useActionState<SignInState, FormData>(sendMagicLink, { status: "idle" });
  const callbackError = CALLBACK_ERRORS[useSearchParams().get("error") ?? ""];

  if (state.status === "sent") {
    return (
      <Stack gap="2" role="status" bg="bg.panel" borderWidth="1px" borderColor="border" rounded="xl" p="6">
        <Text fontWeight="600">Revisa tu correo</Text>
        <Text color="fg.muted">
          Te hemos enviado un enlace a <strong>{state.email}</strong>. Ábrelo en este mismo navegador para entrar.
        </Text>
      </Stack>
    );
  }

  const error = state.status === "error" ? state.message : callbackError;

  return (
    <form action={formAction} noValidate>
      <Stack gap="4">
        <Field.Root invalid={Boolean(error)}>
          <Field.Label>Correo electrónico</Field.Label>
          <Input
            name="email"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder="tu@tienda.es"
            required
            size="lg"
            bg="bg.panel"
            defaultValue={state.status === "error" ? state.email : undefined}
          />
          {error ? <Field.ErrorText>{error}</Field.ErrorText> : null}
        </Field.Root>
        <Button type="submit" size="lg" colorPalette="clay" rounded="full" loading={pending} loadingText="Enviando…">
          Enviarme el enlace
        </Button>
        <Text fontSize="sm" color="fg.subtle">
          Sin contraseña: te mandamos un enlace para entrar. Si es tu primera vez, se crea tu cuenta.
        </Text>
      </Stack>
    </form>
  );
}
