"use client";

import { Alert, Button, Dialog, Flex, Field, Link, Portal, Stack, Text, Textarea } from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { trackOnce } from "@/lib/analytics";
import { downloadPiece, rejectPiece, requestNewVersion, type ActionResult } from "@/app/piezas/[id]/actions";

type DialogKind = "download" | "version" | "reject" | null;

interface ResultActionsProps {
  pieceId: string;
  /** Null when the balance could not be read; the server decides anyway. */
  balance: number | null;
  /** Extra versions the customer can still ask for (0–2). */
  versionsLeft: number;
}

function NoCredits() {
  return (
    <Alert.Root status="warning" rounded="xl" role="alert">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>You need 1 credit to download this piece.</Alert.Title>
        <Alert.Description>
          Viewing it in 3D and in your room is still free.{" "}
          <Link asChild color="clay.fg" fontWeight="600">
            <NextLink href="/creditos">Buy credits</NextLink>
          </Link>
        </Alert.Description>
      </Alert.Content>
    </Alert.Root>
  );
}

export function ResultActions({ pieceId, balance, versionsLeft }: ResultActionsProps) {
  const router = useRouter();
  const [open, setOpen] = useState<DialogKind>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [noCredits, setNoCredits] = useState(false);
  const [pending, startTransition] = useTransition();

  function run(action: () => Promise<ActionResult<object>>, onSuccess?: () => void) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (result.ok) {
        onSuccess?.();
        setOpen(null);
        router.refresh();
        return;
      }
      setOpen(null);
      if (result.code === "insufficient_credits") setNoCredits(true);
      else setError(result.message);
    });
  }

  function onDownload() {
    if (balance !== null && balance < 1) {
      setNoCredits(true);
      return;
    }
    setOpen("download");
  }

  const dialog = (() => {
    switch (open) {
      case "download":
        return {
          title: "Download the piece",
          body: (
            <Text>
              This uses 1 credit and gets you the model as GLB (2K textures) and USDZ, at real scale.
              {balance !== null ? ` You'll have ${balance - 1} left.` : ""}
            </Text>
          ),
          confirm: "Use 1 credit and download",
          onConfirm: () =>
            run(
              () => downloadPiece(pieceId),
              () => trackOnce("piece_approved", `piece_approved:${pieceId}`),
            ),
        };
      case "version":
        return {
          title: "Request another version",
          body: (
            <Text>
              We&apos;ll generate it again from scratch, free of charge. You have {versionsLeft} extra{" "}
              {versionsLeft === 1 ? "version" : "versions"} left for this piece.
            </Text>
          ),
          confirm: "Request another version",
          onConfirm: () => run(() => requestNewVersion(pieceId)),
        };
      case "reject":
        return {
          title: "Not useful to me",
          body: (
            <Stack gap="3">
              <Text>We&apos;ll close the piece at no cost. Tell us what&apos;s wrong and we&apos;ll use it to improve.</Text>
              <Field.Root>
                <Field.Label>Reason</Field.Label>
                <Textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} rows={3} />
              </Field.Root>
            </Stack>
          ),
          confirm: "Close the piece",
          onConfirm: () => run(() => rejectPiece(pieceId, reason)),
        };
      default:
        return null;
    }
  })();

  return (
    <Stack gap="4">
      <Flex direction={{ base: "column", sm: "row" }} wrap="wrap" gap="3">
        <Button colorPalette="clay" rounded="full" size="lg" onClick={onDownload} disabled={pending}>
          Download (1 credit)
        </Button>
        <Button
          variant="outline"
          colorPalette="ink"
          rounded="full"
          size="lg"
          onClick={() => setOpen("version")}
          disabled={pending || versionsLeft < 1}
        >
          Request another version
        </Button>
        <Button variant="ghost" colorPalette="ink" rounded="full" size="lg" onClick={() => setOpen("reject")} disabled={pending}>
          Not useful to me
        </Button>
      </Flex>
      <Text fontSize="sm" color="fg.subtle">
        {versionsLeft < 1 ? "There are no more versions left for this piece. " : ""}Requesting another version or
        closing the piece costs nothing.
      </Text>

      {noCredits ? <NoCredits /> : null}
      {error ? (
        <Alert.Root status="error" rounded="xl" role="alert">
          <Alert.Indicator />
          <Alert.Title>{error}</Alert.Title>
        </Alert.Root>
      ) : null}

      <Dialog.Root
        open={dialog !== null}
        onOpenChange={(e) => {
          if (!e.open && !pending) setOpen(null);
        }}
        placement="center"
      >
        <Portal>
          <Dialog.Backdrop />
          <Dialog.Positioner px="4">
            <Dialog.Content rounded="2xl">
              <Dialog.Header>
                <Dialog.Title>{dialog?.title}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>{dialog?.body}</Dialog.Body>
              <Dialog.Footer>
                <Button variant="ghost" colorPalette="ink" onClick={() => setOpen(null)} disabled={pending}>
                  Cancel
                </Button>
                <Button colorPalette="clay" rounded="full" loading={pending} onClick={dialog?.onConfirm}>
                  {dialog?.confirm}
                </Button>
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </Stack>
  );
}
