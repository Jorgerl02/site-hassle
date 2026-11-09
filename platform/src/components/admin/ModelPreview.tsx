"use client";

import { Box, Text } from "@chakra-ui/react";
import { useEffect, useState } from "react";

/** model-viewer loaded on demand; no AR here, only orbiting to inspect the mesh. */
export function ModelPreview({ src, alt }: { src: string | null; alt: string }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!src) return;
    let alive = true;
    import("@google/model-viewer").then(() => alive && setReady(true)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [src]);

  return (
    <Box aspectRatio="1" bg="white" rounded="md" borderWidth="1px" borderColor="border" overflow="hidden">
      {!src ? (
        <Box h="full" display="grid" placeItems="center">
          <Text fontSize="sm" color="fg.muted">
            Sin modelo
          </Text>
        </Box>
      ) : ready ? (
        <model-viewer
          src={src}
          alt={alt}
          camera-controls
          shadow-intensity="1"
          interaction-prompt="none"
          style={{ width: "100%", height: "100%", backgroundColor: "white" }}
        />
      ) : null}
    </Box>
  );
}
