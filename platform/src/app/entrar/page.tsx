import { Container, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { getCurrentUser } from "@/lib/auth";
import { SignInForm } from "./SignInForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in with your email to create your first 3D piece.",
  robots: { index: false },
  alternates: { canonical: "/entrar" },
};

export default async function SignInPage() {
  // Already signed in: nothing to do here.
  if (await getCurrentUser()) redirect("/panel");

  return (
    <>
      <SiteHeader />
      <Container as="main" maxW="md" px={{ base: 4, md: 8 }} py={{ base: 12, md: 20 }}>
        <Stack gap="8">
          <Stack gap="3">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Sign in with your email
            </Heading>
            <Text color="fg.muted">Create your first piece and see it in 3D for free.</Text>
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
