"use client";

import { Field, NativeSelect, SimpleGrid } from "@chakra-ui/react";
import { useState } from "react";
import { KIND_LABEL, RECTILINEAR_CHOICES, SUPPORT_LABEL, type ShapeValues } from "@/lib/admin-labels";
import { PIECE_KINDS, SUPPORT_ANSWERS } from "@/lib/validation";

/**
 * Editable shape answers (tipo, ¿recta?, apoyo) inside a review form. Their
 * values travel with «Regenerar» / «Reintentar», which save them on the piece
 * before it goes back to the queue.
 */
export function ShapeFields({ idPrefix, defaults, disabled }: { idPrefix: string; defaults: ShapeValues; disabled?: boolean }) {
  const [rectilinear, setRectilinear] = useState(defaults.rectilinear);
  return (
    <SimpleGrid columns={{ base: 1, sm: 3 }} gap="3">
      <Field.Root disabled={disabled}>
        <Field.Label htmlFor={`${idPrefix}-kind`}>Tipo</Field.Label>
        <NativeSelect.Root size="sm" bg="white">
          <NativeSelect.Field id={`${idPrefix}-kind`} name="kind" defaultValue={defaults.kind}>
            {PIECE_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {KIND_LABEL[kind]}
              </option>
            ))}
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
      </Field.Root>
      <Field.Root disabled={disabled}>
        <Field.Label htmlFor={`${idPrefix}-rectilinear`}>¿Pieza recta?</Field.Label>
        <NativeSelect.Root size="sm" bg="white">
          <NativeSelect.Field
            id={`${idPrefix}-rectilinear`}
            name="rectilinear"
            value={rectilinear}
            onChange={(e) => setRectilinear(e.target.value as ShapeValues["rectilinear"])}
          >
            {RECTILINEAR_CHOICES.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.label}
              </option>
            ))}
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
      </Field.Root>
      <Field.Root disabled={disabled || rectilinear === "no"}>
        <Field.Label htmlFor={`${idPrefix}-support`}>¿Cómo se apoya?</Field.Label>
        <NativeSelect.Root size="sm" bg="white">
          <NativeSelect.Field id={`${idPrefix}-support`} name="support" defaultValue={defaults.support}>
            {SUPPORT_ANSWERS.map((support) => (
              <option key={support} value={support}>
                {SUPPORT_LABEL[support]}
              </option>
            ))}
          </NativeSelect.Field>
          <NativeSelect.Indicator />
        </NativeSelect.Root>
      </Field.Root>
    </SimpleGrid>
  );
}
