"use client";

import { Box, Text, chakra } from "@chakra-ui/react";
import { useEffect, useState } from "react";

interface ModelViewerProps {
  /** Public preview GLB. */
  src: string;
  alt: string;
  poster?: string;
  /** Headboards and panels go on the wall in AR. */
  placement?: "floor" | "wall";
}

/**
 * Free preview with AR at real size (`ar-scale="fixed"`). No `ios-src`:
 * Quick Look builds the USDZ on the fly from the preview GLB, so the paid
 * USDZ never leaves the private bucket before the download.
 */
export function ModelViewer({ src, alt, poster, placement = "floor" }: ModelViewerProps) {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    import("@google/model-viewer")
      .then(() => alive && setLoaded(true))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Box position="relative" aspectRatio={{ base: "1", md: "4 / 3" }} rounded="xl" overflow="hidden" bg="white" borderWidth="1px">
      <model-viewer
        src={src}
        poster={poster}
        alt={alt}
        camera-controls
        ar
        ar-modes="webxr scene-viewer quick-look"
        ar-scale="fixed"
        ar-placement={placement}
        shadow-intensity="1"
        touch-action="pan-y"
        style={{ width: "100%", height: "100%", backgroundColor: "white" }}
      >
        <chakra.button
          slot="ar-button"
          position="absolute"
          bottom="3"
          left="50%"
          transform="translateX(-50%)"
          bg="clay.solid"
          color="clay.contrast"
          fontWeight="600"
          fontSize="sm"
          px="4"
          py="2"
          rounded="full"
          boxShadow="md"
        >
          View in your room
        </chakra.button>
      </model-viewer>
      {!loaded ? (
        <Text position="absolute" inset="0" display="flex" alignItems="center" justifyContent="center" color="fg.muted">
          Loading the model…
        </Text>
      ) : null}
    </Box>
  );
}
