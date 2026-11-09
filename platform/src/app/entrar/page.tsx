import { Container, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { getCurrentUser } from "@/lib/auth";
import { SignInForm } from "./SignInForm";

export const metadata: Metadata = {
  title: "Log in",
  description: "Log in to your Pieza 3D account with your email.",
  robots: { index: false },
  alternates: { canonical: "/entrar" },
};

export default async function SignInPage() {
  // Already signed in to an account: nothing to do here. An anonymous trial may
  // log in to an existing account (its pieces move there, see `sendMagicLink`).
  const current = await getCurrentUser();
  if (current && !current.user.is_anonymous) redirect("/panel");

  return (
    <>
      <SiteHeader />
      <Container as="main" maxW="md" px={{ base: 4, md: 8 }} py={{ base: 12, md: 20 }}>
        <Stack gap="8">
          <Stack gap="3">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Log in with your email
            </Heading>
            <Text color="fg.muted">We&apos;ll email you a link to log in. No password needed.</Text>
          </Stack>
          {/* useSearchParams needs a boundary to keep the page in the static shell. */}
          <Suspense fallback={null}>
            <SignInForm />
          </Suspense>
        </Stack>
      </Container>
    </>
  );
}
