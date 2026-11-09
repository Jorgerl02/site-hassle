"use client";

import { Alert, Button, Dialog, Field, Flex, Portal, Stack, Text, Textarea } from "@chakra-ui/react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition, type ReactNode } from "react";
import { trackOnce } from "@/lib/analytics";
import { downloadPiece, rejectPiece, requestNewVersion, type ActionResult } from "@/app/piezas/[id]/actions";
import { PacksDialog } from "./PacksDialog";
import { SaveAccountForm } from "./SaveAccount";

type DialogKind = "download" | "version" | "reject" | "signup" | null;

interface ResultActionsProps {
  pieceId: string;
  /** Null when the balance could not be read (or for an anonymous trial); the server decides anyway. */
  balance: number | null;
  /** Extra versions the customer can still ask for (0–2). */
  versionsLeft: number;
  /** Anonymous trial: downloading asks for an account first (same user, same pieces). */
  anonymous: boolean;
  /** `?download=1`: the customer already asked to download (before signing up or buying). */
  autoDownload: boolean;
  paymentsEnabled: boolean;
  source: string;
}

export function ResultActions({
  pieceId,
  balance,
  versionsLeft,
  anonymous,
  autoDownload,
  paymentsEnabled,
  source,
}: ResultActionsProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState<DialogKind>(null);
  const [packsOpen, setPacksOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const autoStarted = useRef(false);

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
      if (result.code === "insufficient_credits") setPacksOpen(true);
      else setError(result.message);
    });
  }

  function download() {
    run(
      () => downloadPiece(pieceId),
      () => {
        trackOnce("piece_approved", `piece_approved:${pieceId}`, { source });
        // The approved page starts the GLB download by itself.
        router.replace(`${pathname}?download=1`);
      },
    );
  }

  /** Where the download goes next: account first, then credits, then confirm (or straight on when asked before). */
  function startDownload(confirmFirst: boolean) {
    if (anonymous) return setOpen("signup");
    if (balance !== null && balance < 1) return setPacksOpen(true);
    if (confirmFirst) return setOpen("download");
    download();
  }

  // Back from sign-up or Checkout with `?download=1`: continue without another click.
  useEffect(() => {
    if (!autoDownload || autoStarted.current) return;
    autoStarted.current = true;
    startDownload(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, [autoDownload]);

  function onDownloadClick() {
    trackOnce("download_clicked", `download_clicked:${pieceId}`, { source });
    startDownload(true);
  }

  const dialog: { title: string; body: ReactNode; confirm?: string; onConfirm?: () => void } | null = (() => {
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
          onConfirm: download,
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
          title: "Not what I need",
          body: (
            <Stack gap="3">
              <Text>We&apos;ll close the piece at no cost. Tell us what&apos;s wrong and we&apos;ll use it to improve.</Text>
              <Field.Root>
                <Field.Label>Reason</Field.Label>
                <Textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} rows={3} />
              </Field.Root>
            </Stack>
          ),
          confirm: "Close this piece",
          onConfirm: () => run(() => rejectPiece(pieceId, reason)),
        };
      case "signup":
        return {
          title: "Save your piece to download it",
          body: (
            <Stack gap="4" data-testid="signup-dialog">
              <Text color="fg.muted">
                Create your free account to download the files. Your piece and its preview stay exactly as they are;
                you&apos;ll come straight back here.
              </Text>
              <SaveAccountForm next={`/piezas/${pieceId}?download=1`} submitLabel="Create my account" />
            </Stack>
          ),
        };
      default:
        return null;
    }
  })();

  return (
    <Stack gap="4">
      <Flex direction={{ base: "column", sm: "row" }} wrap="wrap" gap="3">
        <Button colorPalette="clay" rounded="full" size="lg" onClick={onDownloadClick} disabled={pending}>
          Download GLB + USDZ (1 credit)
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
          Not what I need
        </Button>
      </Flex>
      <Text fontSize="sm" color="fg.subtle">
        {versionsLeft < 1 ? "There are no more versions left for this piece. " : ""}Requesting another version or
        closing the piece costs nothing.
      </Text>

      {error ? (
        <Alert.Root status="error" rounded="xl" role="alert">
          <Alert.Indicator />
          <Alert.Title>{error}</Alert.Title>
        </Alert.Root>
      ) : null}

      <PacksDialog open={packsOpen} onClose={() => setPacksOpen(false)} pieceId={pieceId} paymentsEnabled={paymentsEnabled} />

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
                  {dialog?.confirm ? "Cancel" : "Not now"}
                </Button>
                {dialog?.confirm ? (
                  <Button colorPalette="clay" rounded="full" loading={pending} onClick={dialog.onConfirm}>
                    {dialog.confirm}
                  </Button>
                ) : null}
              </Dialog.Footer>
            </Dialog.Content>
          </Dialog.Positioner>
        </Portal>
      </Dialog.Root>
    </Stack>
  );
}
