"use client";

import { Box, CloseButton, Flex, SimpleGrid, Stack, Text, chakra } from "@chakra-ui/react";
import { useEffect, useRef, useState, type Dispatch, type DragEvent, type SetStateAction } from "react";
import { MAX_PHOTOS, PHOTO_TYPES } from "@/lib/validation";

export interface SelectedPhoto {
  key: string;
  file: File;
  url: string;
  width?: number;
  height?: number;
}

interface PhotoDropzoneProps {
  photos: SelectedPhoto[];
  onChange: Dispatch<SetStateAction<SelectedPhoto[]>>;
  invalid?: boolean;
  disabled?: boolean;
}

async function measure(file: File): Promise<{ width?: number; height?: number }> {
  try {
    const bitmap = await createImageBitmap(file);
    const size = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return size;
  } catch {
    // Not decodable here (HEIC, PDF…): validation rejects it by type.
    return {};
  }
}

/** Drag-and-drop or tap to choose 1–4 photos, with previews. Validation lives in the form. */
export function PhotoDropzone({ photos, onChange, invalid, disabled }: PhotoDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const latest = useRef(photos);
  useEffect(() => {
    latest.current = photos;
  }, [photos]);

  // Free the object URLs when the component goes away.
  useEffect(() => () => latest.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  async function add(files: FileList | File[]) {
    const added = await Promise.all(
      Array.from(files).map(async (file) => ({
        key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        url: URL.createObjectURL(file),
        ...(await measure(file)),
      })),
    );
    onChange((prev) => [...prev, ...added]);
  }

  function remove(key: string) {
    const photo = photos.find((p) => p.key === key);
    if (photo) URL.revokeObjectURL(photo.url);
    onChange((prev) => prev.filter((p) => p.key !== key));
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (!disabled && event.dataTransfer.files.length) void add(event.dataTransfer.files);
  }

  const full = photos.length >= MAX_PHOTOS;

  return (
    <Stack gap="3">
      <Flex
        as="label"
        direction="column"
        align="center"
        justify="center"
        gap="1"
        minH="32"
        px="4"
        py="6"
        textAlign="center"
        rounded="xl"
        borderWidth="2px"
        borderStyle="dashed"
        borderColor={invalid ? "border.error" : dragging ? "clay.solid" : "border.emphasized"}
        bg={dragging ? "clay.subtle" : "bg.panel"}
        cursor={disabled || full ? "not-allowed" : "pointer"}
        opacity={disabled ? 0.6 : 1}
        transition="background 0.15s, border-color 0.15s"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <Text fontWeight="600">{full ? "You have 4 photos" : "Drop your photos here or tap to choose them"}</Text>
        <Text fontSize="sm" color="fg.muted">
          1 to 4 photos · JPG, PNG or WebP · up to 20 MB each
        </Text>
        <chakra.input
          ref={inputRef}
          type="file"
          multiple
          accept={PHOTO_TYPES.join(",")}
          aria-label="Add photos"
          disabled={disabled || full}
          srOnly
          onChange={(e) => {
            if (e.target.files?.length) void add(e.target.files);
            e.target.value = "";
          }}
        />
      </Flex>

      {photos.length > 0 ? (
        <SimpleGrid as="ul" listStyleType="none" columns={{ base: 2, sm: 4 }} gap="3" aria-label="Chosen photos">
          {photos.map((photo, i) => (
            <Box as="li" key={photo.key} position="relative" rounded="lg" overflow="hidden" borderWidth="1px" bg="white">
              {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
              <img
                src={photo.url}
                alt={`Photo ${i + 1}: ${photo.file.name}`}
                style={{ width: "100%", aspectRatio: "1", objectFit: "contain", display: "block" }}
              />
              <CloseButton
                size="xs"
                position="absolute"
                top="1"
                right="1"
                bg="white"
                rounded="full"
                aria-label={`Remove ${photo.file.name}`}
                disabled={disabled}
                onClick={() => remove(photo.key)}
              />
              {i === 0 ? (
                <Text position="absolute" bottom="1" left="1" fontSize="xs" bg="white" px="1.5" rounded="sm">
                  Main
                </Text>
              ) : null}
            </Box>
          ))}
        </SimpleGrid>
      ) : null}
    </Stack>
  );
}
