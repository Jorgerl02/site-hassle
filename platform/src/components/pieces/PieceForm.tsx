"use client";

import {
  Alert,
  Box,
  Button,
  Field,
  Fieldset,
  Input,
  InputGroup,
  NativeSelect,
  RadioGroup,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { useState, useTransition, type FormEvent } from "react";
import { createPiece } from "@/app/piezas/nueva/actions";
import { createClient } from "@/lib/supabase/client";
import {
  KIND_LABEL,
  PIECE_KINDS,
  RECTILINEAR_OPTIONS,
  looksExcluded,
  validatePieceInput,
  type PieceField,
  type RectilinearAnswer,
} from "@/lib/validation";
import { PhotoDropzone, type SelectedPhoto } from "./PhotoDropzone";

export interface PieceFormDefaults {
  name: string;
  kind: string;
  widthCm: string;
  heightCm: string;
  depthCm: string;
  rectilinear: RectilinearAnswer;
  notes: string;
}

const EMPTY_PIECE: PieceFormDefaults = {
  name: "",
  kind: "",
  widthCm: "",
  heightCm: "",
  depthCm: "",
  rectilinear: "no_se",
  notes: "",
};

const EXTENSION: Record<string, string> = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };

/** Small JPEG for the panel list (the originals can weigh 20 MB). Best effort. */
async function thumbnail(file: File): Promise<Blob | null> {
  try {
    const bitmap = await createImageBitmap(file, { resizeWidth: 480, resizeQuality: "medium" });
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0);
    bitmap.close();
    return await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
  } catch {
    return null;
  }
}

/** Next's redirect/notFound signals must keep propagating. */
function isNavigation(error: unknown): boolean {
  const digest = (error as { digest?: unknown } | null)?.digest;
  return typeof digest === "string" && (digest.startsWith("NEXT_REDIRECT") || digest.startsWith("NEXT_HTTP_ERROR_FALLBACK"));
}

const DIMENSIONS = [
  { name: "widthCm", label: "Ancho" },
  { name: "heightCm", label: "Alto" },
  { name: "depthCm", label: "Fondo" },
] as const;

export function PieceForm({ userId, defaults = EMPTY_PIECE }: { userId: string; defaults?: PieceFormDefaults }) {
  const [photos, setPhotos] = useState<SelectedPhoto[]>([]);
  const [errors, setErrors] = useState<Partial<Record<PieceField, string>>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [kind, setKind] = useState(defaults.kind);
  const [text, setText] = useState({ name: defaults.name, notes: defaults.notes });
  const [pending, startTransition] = useTransition();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const field = (name: string) => String(formData.get(name) ?? "");
    const result = validatePieceInput({
      name: field("name"),
      kind: field("kind"),
      widthCm: field("widthCm"),
      heightCm: field("heightCm"),
      depthCm: field("depthCm"),
      rectilinear: field("rectilinear"),
      notes: field("notes"),
      photos: photos.map((p) => ({ name: p.file.name, type: p.file.type, size: p.file.size, width: p.width, height: p.height })),
    });
    setMessage(null);
    if (!result.ok) {
      setErrors(result.errors);
      setMessage("Revisa los campos marcados.");
      return;
    }
    setErrors({});

    startTransition(async () => {
      const supabase = createClient();
      const pieceId = crypto.randomUUID();
      const folder = `${userId}/${pieceId}`;
      const uploaded: string[] = [];
      const cleanup = () => (uploaded.length ? supabase.storage.from("photos").remove(uploaded) : null);

      for (const [i, photo] of photos.entries()) {
        setProgress(`Subiendo fotos (${i + 1} de ${photos.length})…`);
        const path = `${folder}/${i + 1}.${EXTENSION[photo.file.type] ?? "jpg"}`;
        const { error } = await supabase.storage
          .from("photos")
          .upload(path, photo.file, { contentType: photo.file.type, upsert: false });
        if (error) {
          await cleanup();
          setProgress(null);
          setMessage("No hemos podido subir las fotos. Comprueba tu conexión y vuelve a intentarlo.");
          return;
        }
        uploaded.push(path);
      }
      const thumb = await thumbnail(photos[0].file);
      if (thumb) {
        const path = `${folder}/thumb.jpg`;
        const { error } = await supabase.storage.from("photos").upload(path, thumb, { contentType: "image/jpeg" });
        if (!error) uploaded.push(path);
      }

      setProgress("Creando la pieza…");
      formData.set("id", pieceId);
      // Redirects to /piezas/[id] on success; returns only on failure.
      let failure: Awaited<ReturnType<typeof createPiece>> | undefined;
      try {
        failure = await createPiece(formData);
      } catch (error) {
        if (isNavigation(error)) throw error;
        failure = { ok: false, message: "No hemos podido crear la pieza. Vuelve a intentarlo en unos minutos." };
      }
      if (!failure) return;
      await cleanup();
      setProgress(null);
      setErrors(failure.errors ?? {});
      setMessage(failure.message);
    });
  }

  const warnExcluded = looksExcluded(kind, text.notes, text.name);

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack gap="8">
        <Stack gap="5">
          <Field.Root invalid={Boolean(errors.name)} required>
            <Field.Label>Nombre de la pieza</Field.Label>
            <Input
              name="name"
              defaultValue={defaults.name}
              placeholder="Cabecero tapizado Rigole"
              maxLength={80}
              bg="bg.panel"
              autoComplete="off"
              onChange={(e) => setText((t) => ({ ...t, name: e.target.value }))}
            />
            <Field.ErrorText>{errors.name}</Field.ErrorText>
          </Field.Root>

          <Field.Root invalid={Boolean(errors.kind)} required>
            <Field.Label>Tipo</Field.Label>
            <NativeSelect.Root bg="bg.panel">
              <NativeSelect.Field name="kind" defaultValue={defaults.kind} onChange={(e) => setKind(e.target.value)}>
                <option value="" disabled>
                  Elige el tipo
                </option>
                {PIECE_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABEL[k]}
                  </option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
            <Field.ErrorText>{errors.kind}</Field.ErrorText>
          </Field.Root>

          <Fieldset.Root>
            <Fieldset.Legend fontWeight="500">Medidas reales</Fieldset.Legend>
            <Fieldset.HelperText>Las del catálogo, en centímetros. El modelo saldrá exactamente a esta escala.</Fieldset.HelperText>
            <SimpleGrid columns={{ base: 1, sm: 3 }} gap="4" mt="2">
              {DIMENSIONS.map(({ name, label }) => (
                <Field.Root key={name} invalid={Boolean(errors[name])} required>
                  <Field.Label>{label}</Field.Label>
                  <InputGroup endElement={<Text color="fg.muted">cm</Text>}>
                    <Input name={name} defaultValue={defaults[name]} inputMode="decimal" placeholder="0" bg="bg.panel" />
                  </InputGroup>
                  <Field.ErrorText>{errors[name]}</Field.ErrorText>
                </Field.Root>
              ))}
            </SimpleGrid>
          </Fieldset.Root>

          <Fieldset.Root invalid={Boolean(errors.rectilinear)}>
            <Fieldset.Legend fontWeight="500">¿Es una pieza recta, como una caja, un panel o un cabecero?</Fieldset.Legend>
            <RadioGroup.Root name="rectilinear" defaultValue={defaults.rectilinear} colorPalette="clay" mt="2">
              <Stack direction="row" gap="6">
                {RECTILINEAR_OPTIONS.map((option) => (
                  <RadioGroup.Item key={option.value} value={option.value}>
                    <RadioGroup.ItemHiddenInput />
                    <RadioGroup.ItemIndicator />
                    <RadioGroup.ItemText>{option.label}</RadioGroup.ItemText>
                  </RadioGroup.Item>
                ))}
              </Stack>
            </RadioGroup.Root>
            <Fieldset.ErrorText>{errors.rectilinear}</Fieldset.ErrorText>
          </Fieldset.Root>
        </Stack>

        <Field.Root invalid={Boolean(errors.photos)}>
          <Field.Label>Fotos</Field.Label>
          <Field.HelperText mb="2">
            Vista frontal o de tres cuartos, fondo claro sin otros muebles, la pieza entera en el encuadre y al menos
            1.000 px en el lado mayor. La primera es la principal.
          </Field.HelperText>
          <Box w="full">
            <PhotoDropzone photos={photos} onChange={setPhotos} invalid={Boolean(errors.photos)} disabled={pending} />
          </Box>
          <Field.ErrorText>{errors.photos}</Field.ErrorText>
        </Field.Root>

        <Field.Root invalid={Boolean(errors.notes)}>
          <Field.Label>
            Notas{" "}
            <Text as="span" color="fg.muted" fontWeight="400">
              (opcional)
            </Text>
          </Field.Label>
          <Textarea
            name="notes"
            defaultValue={defaults.notes}
            maxLength={500}
            rows={3}
            bg="bg.panel"
            placeholder="Materiales, acabados o cualquier detalle que no se vea en la foto."
            onChange={(e) => setText((t) => ({ ...t, notes: e.target.value }))}
          />
          <Field.ErrorText>{errors.notes}</Field.ErrorText>
        </Field.Root>

        <Box bg="bg.subtle" rounded="xl" p="4" fontSize="sm">
          <Text fontWeight="600">Qué no hacemos todavía</Text>
          <Text color="fg.muted" mt="1">
            Piezas de metal, cromo o vidrio, ni con tubos o patas finas: los generadores pierden el reflejo y las
            proporciones, y no llegan a la escala que prometemos (±3 % por eje).
          </Text>
        </Box>

        {warnExcluded ? (
          <Alert.Root status="warning" rounded="xl">
            <Alert.Indicator />
            <Alert.Title>
              Parece una pieza de metal o vidrio. Si lo es, la rechazaremos sin coste, pero contará en tu límite diario.
            </Alert.Title>
          </Alert.Root>
        ) : null}

        {message ? (
          <Alert.Root status="error" rounded="xl" role="alert">
            <Alert.Indicator />
            <Alert.Title>{message}</Alert.Title>
          </Alert.Root>
        ) : null}

        <Stack gap="2" align={{ base: "stretch", sm: "flex-start" }}>
          <Button type="submit" size="lg" colorPalette="clay" rounded="full" loading={pending} loadingText={progress ?? "Enviando…"}>
            Crear pieza
          </Button>
          <Text fontSize="sm" color="fg.subtle">
            Ver el resultado en 3D y con realidad aumentada es gratis. Solo pagas si lo descargas.
          </Text>
        </Stack>
      </Stack>
    </form>
  );
}
