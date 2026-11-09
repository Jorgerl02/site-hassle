"use client";

import { Box, Text } from "@chakra-ui/react";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

interface LazyModelProps {
  glb: string;
  poster: string;
  alt: string;
}

/**
 * Shows the poster until the card nears the viewport, then loads
 * model-viewer (and three.js) on demand. `ar-scale="fixed"` keeps the real
 * size in AR, which is the whole point of the product. No `ios-src`: Quick Look
 * gets a USDZ that model-viewer generates from the GLB.
 */
export function LazyModel({ glb, poster, alt }: LazyModelProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        observer.disconnect();
        import("@google/model-viewer").then(() => setActive(true)).catch(() => {});
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <Box ref={ref} position="relative" aspectRatio="1" rounded="lg" overflow="hidden" bg="white">
      {active ? (
        <model-viewer
          src={glb}
          poster={poster}
          alt={alt}
          camera-controls
          ar
          ar-modes="webxr scene-viewer quick-look"
          ar-scale="fixed"
          shadow-intensity="1"
          touch-action="pan-y"
          interaction-prompt="none"
          style={{ width: "100%", height: "100%", backgroundColor: "white" }}
        />
      ) : (
        <Image src={poster} alt={alt} fill sizes="(max-width: 768px) 45vw, 240px" style={{ objectFit: "contain" }} />
      )}
      <Text
        position="absolute"
        top="2"
        left="2"
        fontSize="xs"
        fontWeight="600"
        bg="clay.subtle"
        color="clay.fg"
        px="2"
        py="0.5"
        rounded="full"
        pointerEvents="none"
      >
        Gíralo
      </Text>
    </Box>
  );
}
