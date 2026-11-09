import { Box, Container, Heading, Link, List, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ResetConsentButton } from "@/components/CookieConsent";
import { SiteFooter, SiteHeader } from "@/components/landing/SiteHeader";
import { PRODUCT_NAME } from "@/lib/site";

export const metadata: Metadata = {
  title: "Privacy and cookies",
  description: `What data ${PRODUCT_NAME} processes, why, who it shares it with and which cookies it uses.`,
  alternates: { canonical: "/privacy" },
};

// TODO(Jorge): legal name and tax id of the owner once the company is set.
const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || null;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Stack as="section" gap="3">
      <Heading as="h2" fontSize={{ base: "xl", md: "2xl" }} fontWeight="500">
        {title}
      </Heading>
      {children}
    </Stack>
  );
}

function Contact() {
  return CONTACT_EMAIL ? (
    <Link href={`mailto:${CONTACT_EMAIL}`} color="clay.fg" fontWeight="600">
      {CONTACT_EMAIL}
    </Link>
  ) : (
    <>the contact email on this website</>
  );
}

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />
      <Container as="main" maxW="3xl" px={{ base: 4, md: 8 }} py={{ base: 10, md: 16 }}>
        <Stack gap="10" lineHeight="1.7">
          <Stack gap="3">
            <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
              Privacy and cookies
            </Heading>
            <Text color="fg.muted">
              The essentials, with no small print. If you have any questions, write to us at <Contact />.
            </Text>
          </Stack>

          <Section title="What data we process and why">
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Your email address</strong>, to create your account and send you the sign-in link and updates
                about your pieces (for example, when a piece is ready).
              </List.Item>
              <List.Item>
                <strong>The photos, dimensions and notes of your furniture</strong>, to generate the 3D model, check it
                before showing it to you and deliver it.
              </List.Item>
              <List.Item>
                <strong>Your purchases and credits</strong>: pack, amount and balance history. We never see or store
                your card details; payments are handled by Stripe.
              </List.Item>
              <List.Item>
                <strong>How you found us</strong> (campaign or link parameters, such as <code>utm_source</code>), to
                learn which ads work. It is saved with your account when you sign up.
              </List.Item>
            </List.Root>
            <Text>
              The legal bases are the contract (providing the service you ask for), our legitimate interest in knowing
              where our customers come from and, for measurement cookies, your consent. We do not sell your data.
            </Text>
          </Section>

          <Section title="Who we share it with">
            <Text>Only with the providers we need to run the service, who process the data on our behalf:</Text>
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Supabase</strong>: accounts, database and files, on servers in the European Union (Ireland).
              </List.Item>
              <List.Item>
                <strong>Stripe</strong>: payment for credit packs.
              </List.Item>
              <List.Item>
                <strong>Resend</strong>: sending notification emails.
              </List.Item>
              <List.Item>
                <strong>3D generation of pieces that aren&apos;t straight</strong> (sofas, armchairs, vases…): we send
                only the piece&apos;s main photo, without your email or name, to <strong>fal.ai</strong> (United States)
                or <strong>Tripo</strong> (China), depending on the provider we have active. The transfer relies on the
                European Commission&apos;s standard contractual clauses (Article 46 GDPR) and, for the United States,
                also on the EU-US Data Privacy Framework where the provider is certified.
              </List.Item>
              <List.Item>
                <strong>Vercel</strong>: website hosting.
              </List.Item>
              <List.Item>
                <strong>Meta and Google</strong>, only if you accept measurement cookies (see below).
              </List.Item>
            </List.Root>
            <Text>
              Some of these providers may process data outside the European Union with the safeguards the GDPR requires
              (standard contractual clauses or adequacy frameworks).
            </Text>
          </Section>

          <Section title="How long we keep it">
            <Text>
              For as long as you have an account. If you ask us to delete it, we delete your account, photos and
              models; purchase records are kept for as long as tax law requires.
            </Text>
          </Section>

          <Section title="Cookies">
            <List.Root gap="2" ps="5">
              <List.Item>
                <strong>Necessary</strong> (always on): the session that keeps you signed in, and
                <code> sh_attr</code>, which remembers for 90 days which campaign or link brought you here. They are
                our own and are not shared.
              </List.Item>
              <List.Item>
                <strong>Measurement</strong> (only if you accept them): Meta Pixel and Google Analytics, to learn
                whether our ads bring in people who create and buy pieces. If you reject them, neither is loaded.
              </List.Item>
            </List.Root>
            <Text>Your choice is saved in this browser for 180 days. You can change it at any time.</Text>
            <Box>
              <ResetConsentButton />
            </Box>
          </Section>

          <Section title="Your rights">
            <Text>
              You can ask for access, correction, deletion, restriction or portability of your data, or object to its
              processing, by writing to <Contact />. If you think we haven&apos;t handled your request properly, you
              can complain to the Spanish Data Protection Agency (AEPD, aepd.es) or to the authority in your country.
            </Text>
          </Section>
        </Stack>
      </Container>
      <SiteFooter />
    </>
  );
}
