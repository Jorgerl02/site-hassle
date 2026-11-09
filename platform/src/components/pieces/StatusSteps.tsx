"use client";

import { Box, Flex, Spinner, Stack, Text } from "@chakra-ui/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { StatusStep } from "@/lib/pieces";

export const POLL_MS = 10_000;

/** Re-renders the server page every 10 s while the piece is still moving. */
function useAutoRefresh(active: boolean) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, router]);
}

export function StatusSteps({ steps, poll }: { steps: StatusStep[]; poll: boolean }) {
  useAutoRefresh(poll);
  return (
    <Stack as="ol" listStyleType="none" gap="0" aria-label="Piece progress">
      {steps.map((step, i) => (
        <Flex as="li" key={step.key} gap="3" aria-current={step.state === "current" ? "step" : undefined}>
          <Flex direction="column" align="center">
            <Flex
              boxSize="7"
              rounded="full"
              align="center"
              justify="center"
              fontSize="sm"
              fontWeight="600"
              bg={step.state === "done" ? "clay.solid" : step.state === "current" ? "clay.muted" : "bg.muted"}
              color={step.state === "done" ? "clay.contrast" : step.state === "current" ? "clay.fg" : "fg.subtle"}
            >
              {step.state === "done" ? "✓" : step.state === "current" ? <Spinner size="xs" /> : i + 1}
            </Flex>
            {i < steps.length - 1 ? <Box w="2px" flex="1" minH="5" bg={step.state === "done" ? "clay.solid" : "border"} /> : null}
          </Flex>
          <Stack gap="0" pb="4">
            <Text fontWeight={step.state === "upcoming" ? "400" : "600"} color={step.state === "upcoming" ? "fg.muted" : "fg"}>
              {step.label}
            </Text>
            {step.state === "current" ? (
              <Text fontSize="sm" color="fg.muted">
                {step.hint}
              </Text>
            ) : null}
          </Stack>
        </Flex>
      ))}
    </Stack>
  );
}
