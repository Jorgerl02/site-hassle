"use client";

import { Button, Stack, Text } from "@chakra-ui/react";
import { useState } from "react";
import { prepareGoogleLink } from "@/app/account/actions";
import { googleAuthEnabled, oauthRedirect } from "@/lib/google-auth";
import { createClient } from "@/lib/supabase/client";

/**
 * «Continue with Google», above the email field. `link` (save card, sign-up
 * modal of an anonymous trial): `linkIdentity`, so the same user and its
 * pieces get Google; if that Google account already belongs to someone, the
 * callback signs in to it and moves the trial's pieces there. Otherwise
 * (`/entrar`): plain Google sign-in, and an anonymous trial in this browser
 * also hands its pieces over. Both rely on the claim cookie set by
 * `prepareGoogleLink`. Renders nothing without the build flag.
 */
export function GoogleButton({ next, link }: { next: string; link: boolean }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  if (!googleAuthEnabled()) return null;

  async function onClick() {
    setError(null);
    setPending(true);
    const origin = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "") || window.location.origin;
    const supabase = createClient();
    await prepareGoogleLink();
    const { error: oauthError } = link
      ? await supabase.auth.linkIdentity({ provider: "google", options: { redirectTo: oauthRedirect(origin, next, true) } })
      : await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: oauthRedirect(origin, next) } });
    if (oauthError) {
      setPending(false);
      setError("We couldn't connect to Google. Use your email instead.");
    }
  }

  return (
    <Stack gap="2">
      <Button type="button" size="lg" bg="black" color="white" rounded="full" onClick={onClick} loading={pending} data-testid="google-button">
        Continue with Google
      </Button>
      {error ? (
        <Text fontSize="sm" color="red.fg" role="alert">
          {error}
        </Text>
      ) : null}
      <Text fontSize="sm" color="fg.subtle" textAlign="center">
        or
      </Text>
    </Stack>
  );
}
