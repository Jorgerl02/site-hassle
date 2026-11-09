"use client";

import { Alert, Button, Dialog, Flex, Field, Link, Portal, Stack, Text, Textarea } from "@chakra-ui/react";
import NextLink from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
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
        <Alert.Title>Necesitas 1 crédito para descargar esta pieza.</Alert.Title>
        <Alert.Description>
          Verla en 3D y en tu casa sigue siendo gratis.{" "}
          <Link asChild color="clay.fg" fontWeight="600">
            <NextLink href="/creditos">Comprar créditos</NextLink>
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

  function run(action: () => Promise<ActionResult<object>>) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (result.ok) {
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
          title: "Descargar la pieza",
          body: (
            <Text>
              Usarás 1 crédito y te llevas el modelo en GLB (texturas 2K) y USDZ, a escala real.
              {balance !== null ? ` Te quedarán ${balance - 1}.` : ""}
            </Text>
          ),
          confirm: "Usar 1 crédito y descargar",
          onConfirm: () => run(() => downloadPiece(pieceId)),
        };
      case "version":
        return {
          title: "Pedir otra versión",
          body: (
            <Text>
              La volvemos a generar desde cero, sin coste. Te {versionsLeft === 1 ? "queda" : "quedan"} {versionsLeft}{" "}
              {versionsLeft === 1 ? "versión" : "versiones"} extra para esta pieza.
            </Text>
          ),
          confirm: "Pedir otra versión",
          onConfirm: () => run(() => requestNewVersion(pieceId)),
        };
      case "reject":
        return {
          title: "No me sirve",
          body: (
            <Stack gap="3">
              <Text>Cerramos la pieza sin coste. Cuéntanos qué falla y lo usamos para mejorar.</Text>
              <Field.Root>
                <Field.Label>Motivo</Field.Label>
                <Textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} rows={3} />
              </Field.Root>
            </Stack>
          ),
          confirm: "Cerrar la pieza",
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
          Descargar (1 crédito)
        </Button>
        <Button
          variant="outline"
          colorPalette="ink"
          rounded="full"
          size="lg"
          onClick={() => setOpen("version")}
          disabled={pending || versionsLeft < 1}
        >
          Pedir otra versión
        </Button>
        <Button variant="ghost" colorPalette="ink" rounded="full" size="lg" onClick={() => setOpen("reject")} disabled={pending}>
          No me sirve
        </Button>
      </Flex>
      <Text fontSize="sm" color="fg.subtle">
        {versionsLeft < 1 ? "Ya has usado las 2 versiones extra. " : ""}Pedir otra versión o cerrar la pieza no cuesta
        nada.
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
                  Cancelar
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
