import { Alert, Button, Container, Heading, Link, Stack, Text } from "@chakra-ui/react";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import NextLink from "next/link";
import { AppHeader } from "@/components/pieces/AppHeader";
import { PieceForm, type PieceFormDefaults } from "@/components/pieces/PieceForm";
import { cleanSource } from "@/lib/analytics";
import { ATTRIBUTION_COOKIE, readAttributionCookie, sourceOf } from "@/lib/attribution";
import { getCurrentUser } from "@/lib/auth";
import { formatCm } from "@/lib/format";
import { dailyLimitMessage, findPieceForUser } from "@/lib/pieces";
import { ANONYMOUS_DAILY_PIECE_LIMIT, DAILY_PIECE_LIMIT } from "@/lib/pricing";
import { createServerClient } from "@/lib/supabase/server";
import { rectilinearAnswer, supportAnswer } from "@/lib/validation";

export const metadata: Metadata = {
  title: "Turn a photo into a 3D model",
  robots: { index: false },
};

/** "Fix photos": `?desde=<id>` starts the form with that piece's data. */
async function defaultsFrom(id: string | undefined): Promise<PieceFormDefaults | null> {
  if (!id) return null;
  const piece = await findPieceForUser(id);
  if (!piece) return null;
  return {
    name: piece.name,
    kind: piece.kind,
    widthCm: formatCm(piece.width_cm),
    heightCm: formatCm(piece.height_cm),
    depthCm: formatCm(piece.depth_cm),
    rectilinear: rectilinearAnswer(piece.rectilinear),
    support: supportAnswer(piece.support),

    notes: piece.notes ?? "",
  };
}

/**
 * Open to everyone: the landing CTAs land here with `?source=`. Without a
 * session the form signs the visitor in anonymously right before uploading
 * (no email); anonymous trials get 1 piece a day, accounts 3.
 */
export default async function NewPiecePage({ searchParams }: { searchParams: Promise<{ desde?: string; source?: string }> }) {
  const current = await getCurrentUser();
  const user = current?.user ?? null;
  const anonymous = user?.is_anonymous === true;
  const params = await searchParams;
  const supabase = await createServerClient();
  const [createdToday, source] = await Promise.all([
    user ? supabase.rpc("pieces_created_today", { p_user: user.id }).then((r) => r.data) : Promise.resolve(0),
    user ? defaultsFrom(params.desde) : Promise.resolve(null),
  ]);
  const limit = anonymous ? ANONYMOUS_DAILY_PIECE_LIMIT : DAILY_PIECE_LIMIT;
  const limitReached = typeof createdToday === "number" && createdToday >= limit;
  // Funnel source: this CTA's `?source=`, else the one stored with the profile, else the ad's utm_source.
  const cookieAttribution = readAttributionCookie((await cookies()).get(ATTRIBUTION_COOKIE)?.value);
  const funnelSource =
    cleanSource(params.source) ?? (current?.profile ? sourceOf(current.profile.attribution) : sourceOf(cookieAttribution));

  return (
    <>
      <AppHeader />
      <Container as="main" maxW="3xl" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
        <Stack gap="2" mb="8">
          {user ? (
            <Link asChild fontSize="sm" color="fg.muted">
              <NextLink href="/panel">← Your pieces</NextLink>
            </Link>
          ) : null}
          <Heading as="h1" fontSize={{ base: "3xl", md: "4xl" }} fontWeight="500">
            {source ? "Fix photos" : "Turn a photo into a 3D model"}
          </Heading>
          <Text color="fg.muted">
            {source
              ? "We've copied your piece's details. Upload new photos and we'll generate it again."
              : "A catalogue photo and the real dimensions. No account or credit card needed: you see the model for free."}
          </Text>
        </Stack>

        {limitReached ? (
          <Alert.Root status="info" rounded="xl" role="alert">
            <Alert.Indicator />
            <Alert.Content>
              <Alert.Title>{dailyLimitMessage(anonymous)}</Alert.Title>
              <Alert.Description>
                <Button asChild variant="plain" colorPalette="clay" px="0">
                  <NextLink href={anonymous ? "/entrar" : "/panel"}>{anonymous ? "Log in" : "Back to your pieces"}</NextLink>
                </Button>
              </Alert.Description>
            </Alert.Content>
          </Alert.Root>
        ) : (
          <PieceForm
            userId={user?.id ?? null}
            defaults={source ?? undefined}
            source={funnelSource}
            attribution={{ ...(cookieAttribution ?? {}), source: funnelSource }}
          />
        )}
      </Container>
    </>
  );
}
