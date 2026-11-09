import { Container, Heading, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { SiteHeader } from "@/components/landing/SiteHeader";
import { getCurrentUser } from "@/lib/auth";
import { SignInForm } from "./SignInForm";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Entra con tu correo para crear tu primera pieza en 3D.",
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
              Entra con tu correo
            </Heading>
            <Text color="fg.muted">Crea tu primera pieza y mírala en 3D gratis.</Text>
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
