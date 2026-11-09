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
  DEFAULT_KIND,
  DEFAULT_RECTILINEAR,
  DEFAULT_SUPPORT,
  KIND_LABEL,
  PIECE_KINDS,
  RECTILINEAR_OPTIONS,
  SUPPORT_OPTIONS,
  looksExcluded,
  nameFromFileName,
  validatePieceInput,
  type PieceField,
  type RectilinearAnswer,
  type SupportAnswer,
} from "@/lib/validation";
import { PhotoDropzone, type SelectedPhoto } from "./PhotoDropzone";

export interface PieceFormDefaults {
  name: string;
  kind: string;
  widthCm: string;
  heightCm: string;
  depthCm: string;
  rectilinear: RectilinearAnswer;
  support: SupportAnswer;
  notes: string;
}

const EMPTY_PIECE: PieceFormDefaults = {
  name: "",
  kind: DEFAULT_KIND,
  widthCm: "",
  heightCm: "",
  depthCm: "",
  rectilinear: DEFAULT_RECTILINEAR,
  support: DEFAULT_SUPPORT,
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
  { name: "widthCm", label: "Width" },
  { name: "heightCm", label: "Height" },
  { name: "depthCm", label: "Depth" },
] as const;

/**
 * New-piece form. The customer only has to give photos, the real dimensions
 * and a name (suggested from the first photo's file name). Type, the
 * straight-piece question, the support and the notes sit in a closed
 * `<details>`: its fields stay in the DOM, so the defaults (`otro`, "Not
 * sure", "Not sure") are submitted when nobody opens it.
 */
export function PieceForm({ userId, defaults = EMPTY_PIECE }: { userId: string; defaults?: PieceFormDefaults }) {
  const [photos, setPhotos] = useState<SelectedPhoto[]>([]);
  const [errors, setErrors] = useState<Partial<Record<PieceField, string>>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [kind, setKind] = useState(defaults.kind);
  const [rectilinear, setRectilinear] = useState<string>(defaults.rectilinear);
  // Until the customer types a name (or one is copied from an earlier piece),
  // it follows the first photo's file name.
  const [typedName, setTypedName] = useState<string | null>(defaults.name || null);
  const name = typedName ?? (photos[0] ? nameFromFileName(photos[0].file.name) : "");
  const [notes, setNotes] = useState(defaults.notes);
  const [pending, startTransition] = useTransition();

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const field = (key: string) => String(formData.get(key) ?? "");
    const result = validatePieceInput({
      name: field("name"),
      kind: field("kind"),
      widthCm: field("widthCm"),
      heightCm: field("heightCm"),
      depthCm: field("depthCm"),
      rectilinear: field("rectilinear"),
      support: field("support"),
      notes: field("notes"),
      photos: photos.map((p) => ({ name: p.file.name, type: p.file.type, size: p.file.size, width: p.width, height: p.height })),
    });
    setMessage(null);
    if (!result.ok) {
      setErrors(result.errors);
      setMessage("Please check the highlighted fields.");
      // Errors inside the optional details must not stay hidden.
      if (result.errors.kind || result.errors.rectilinear || result.errors.support || result.errors.notes) {
        const details = event.currentTarget.querySelector("details");
        if (details) details.open = true;
      }
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
        setProgress(`Uploading photos (${i + 1} of ${photos.length})…`);
        const path = `${folder}/${i + 1}.${EXTENSION[photo.file.type] ?? "jpg"}`;
        const { error } = await supabase.storage
          .from("photos")
          .upload(path, photo.file, { contentType: photo.file.type, upsert: false });
        if (error) {
          await cleanup();
          setProgress(null);
          setMessage("We couldn't upload your photos. Check your connection and try again.");
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

      setProgress("Creating your piece…");
      formData.set("id", pieceId);
      // Redirects to /piezas/[id] on success; returns only on failure.
      let failure: Awaited<ReturnType<typeof createPiece>> | undefined;
      try {
        failure = await createPiece(formData);
      } catch (error) {
        if (isNavigation(error)) throw error;
        failure = { ok: false, message: "We couldn't create the piece. Please try again in a few minutes." };
      }
      if (!failure) return;
      await cleanup();
      setProgress(null);
      setErrors(failure.errors ?? {});
      setMessage(failure.message);
    });
  }

  const warnExcluded = looksExcluded(kind, notes, name);

  return (
    <form onSubmit={onSubmit} noValidate>
      <Stack gap="8">
        <Field.Root invalid={Boolean(errors.photos)}>
          <Field.Label>Photos</Field.Label>
          <Field.HelperText mb="2">
            A front or three-quarter view on a light background with no other furniture, the whole piece in the
            frame and at least 1,000 px on the long side. The first photo is the main one.
          </Field.HelperText>
          <Box w="full">
            <PhotoDropzone photos={photos} onChange={setPhotos} invalid={Boolean(errors.photos)} disabled={pending} />
          </Box>
          <Field.ErrorText>{errors.photos}</Field.ErrorText>
        </Field.Root>

        <Fieldset.Root>
          <Fieldset.Legend fontWeight="500">Real dimensions</Fieldset.Legend>
          <Fieldset.HelperText>From the catalogue, in centimetres. The model will be built at exactly this scale.</Fieldset.HelperText>
          <SimpleGrid columns={{ base: 1, sm: 3 }} gap="4" mt="2">
            {DIMENSIONS.map(({ name: dimension, label }) => (
              <Field.Root key={dimension} invalid={Boolean(errors[dimension])} required>
                <Field.Label>{label}</Field.Label>
                <InputGroup endElement={<Text color="fg.muted">cm</Text>}>
                  <Input name={dimension} defaultValue={defaults[dimension]} inputMode="decimal" placeholder="0" bg="bg.panel" />
                </InputGroup>
                <Field.ErrorText>{errors[dimension]}</Field.ErrorText>
              </Field.Root>
            ))}
          </SimpleGrid>
        </Fieldset.Root>

        <Field.Root invalid={Boolean(errors.name)} required>
          <Field.Label>Name</Field.Label>
          <Input
            name="name"
            value={name}
            placeholder="Upholstered headboard Rigole"
            maxLength={80}
            bg="bg.panel"
            autoComplete="off"
            onChange={(e) => setTypedName(e.target.value)}
          />
          <Field.HelperText>We fill it in from the first photo&apos;s file name; change it if you like.</Field.HelperText>
          <Field.ErrorText>{errors.name}</Field.ErrorText>
        </Field.Root>

        <Box
          as="details"
          data-testid="optional-details"
          bg="bg.subtle"
          rounded="xl"
          px="4"
          py="3"
          css={{ "& > summary::-webkit-details-marker": { display: "none" } }}
        >
          <Box as="summary" cursor="pointer" fontWeight="600" listStyleType="none" display="flex" justifyContent="space-between" gap="4">
            Optional details (helps us get the shape right)
            <Text as="span" color="fg.subtle" aria-hidden>
              +
            </Text>
          </Box>
          <Stack gap="5" mt="4">
            <Field.Root invalid={Boolean(errors.kind)}>
              <Field.Label>Type</Field.Label>
              <NativeSelect.Root bg="bg.panel">
                <NativeSelect.Field name="kind" defaultValue={defaults.kind} onChange={(e) => setKind(e.target.value)}>
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

            <Fieldset.Root invalid={Boolean(errors.rectilinear)}>
              <Fieldset.Legend fontWeight="500">Is it a straight piece, like a box, a panel or a headboard?</Fieldset.Legend>
              <RadioGroup.Root
                name="rectilinear"
                defaultValue={defaults.rectilinear}
                onValueChange={(e) => setRectilinear(e.value ?? DEFAULT_RECTILINEAR)}
                colorPalette="clay"
                mt="2"
              >
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

            {rectilinear !== "no" ? (
              <Fieldset.Root invalid={Boolean(errors.support)}>
                <Fieldset.Legend fontWeight="500">How does it stand?</Fieldset.Legend>
                <Fieldset.HelperText>Helps us rebuild the base exactly as it is.</Fieldset.HelperText>
                <RadioGroup.Root name="support" defaultValue={defaults.support} colorPalette="clay" mt="2">
                  <Stack direction={{ base: "column", sm: "row" }} gap={{ base: 3, sm: 6 }} wrap="wrap">
                    {SUPPORT_OPTIONS.map((option) => (
                      <RadioGroup.Item key={option.value} value={option.value}>
                        <RadioGroup.ItemHiddenInput />
                        <RadioGroup.ItemIndicator />
                        <RadioGroup.ItemText>{option.label}</RadioGroup.ItemText>
                      </RadioGroup.Item>
                    ))}
                  </Stack>
                </RadioGroup.Root>
                <Fieldset.ErrorText>{errors.support}</Fieldset.ErrorText>
              </Fieldset.Root>
            ) : null}

            <Field.Root invalid={Boolean(errors.notes)}>
              <Field.Label>Notes</Field.Label>
              <Textarea
                name="notes"
                defaultValue={defaults.notes}
                maxLength={500}
                rows={3}
                bg="bg.panel"
                placeholder="Materials, finishes or any detail the photo doesn't show."
                onChange={(e) => setNotes(e.target.value)}
              />
              <Field.ErrorText>{errors.notes}</Field.ErrorText>
            </Field.Root>
          </Stack>
        </Box>

        <Box bg="bg.subtle" rounded="xl" p="4" fontSize="sm">
          <Text fontWeight="600">What we don&apos;t do yet</Text>
          <Text color="fg.muted" mt="1">
            Metal, chrome or glass pieces, or pieces with thin tubes or legs: the 3D generators lose the reflections and
            proportions and can&apos;t reach the scale we promise (±3% per axis).
          </Text>
        </Box>

        {warnExcluded ? (
          <Alert.Root status="warning" rounded="xl">
            <Alert.Indicator />
            <Alert.Title>
              This looks like a metal or glass piece. If it is, we&apos;ll decline it at no cost, but it will count
              towards your daily limit.
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
          <Button type="submit" size="lg" colorPalette="clay" rounded="full" loading={pending} loadingText={progress ?? "Sending…"}>
            Create piece
          </Button>
          <Text fontSize="sm" color="fg.subtle">
            Viewing the result in 3D and in augmented reality is free. You only pay if you download it.
          </Text>
        </Stack>
      </Stack>
    </form>
  );
}
