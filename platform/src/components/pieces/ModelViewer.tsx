"use client";

import { Box, Text, chakra } from "@chakra-ui/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { trackOnce } from "@/lib/analytics";

interface ModelViewerProps {
  /** Public preview GLB. */
  src: string;
  alt: string;
  poster?: string;
  /** Headboards and panels go on the wall in AR. */
  placement?: "floor" | "wall";
  /**
   * Public preview USDZ for iOS Quick Look (`previews/{piece}/{attempt}/model_preview.usdz`),
   * when the worker uploaded one. Without it model-viewer converts the GLB on the
   * fly, which awaits and loses the tap's user activation: AR does not open on iPhone.
   */
  iosSrc?: string;
  /** For the `preview_opened` / `ar_opened` funnel events. */
  pieceId: string;
  source: string;
}

type ModelViewerElement = HTMLElement & { canActivateAR?: boolean; activateAR?: () => Promise<void> };

/**
 * Free preview with AR at real size (`ar-scale="fixed"`). The paid GLB/USDZ
 * never leave the private bucket before the download: AR uses the preview
 * files. «View in your room» is our own button that calls `activateAR()`
 * synchronously inside the tap (iOS Quick Look needs the user activation);
 * model-viewer's default AR button is replaced by an empty slot.
 */
export function ModelViewer({ src, alt, poster, placement = "floor", iosSrc, pieceId, source }: ModelViewerProps) {
  const [loaded, setLoaded] = useState(false);
  const [arAvailable, setArAvailable] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const viewer = box.current?.querySelector<ModelViewerElement>("model-viewer");
    if (!viewer) return;
    const onLoad = () => {
      trackOnce("preview_opened", `preview_opened:${pieceId}`, { source });
      setArAvailable(Boolean(viewer.canActivateAR));
      // canActivateAR may settle a beat after load.
      window.setTimeout(() => setArAvailable(Boolean(viewer.canActivateAR)), 600);
    };
    // WebXR / Scene Viewer report a session; Quick Look only the button press.
    const onAr = (event: Event) => {
      const status = (event as CustomEvent<{ status?: string }>).detail?.status;
      if (status === "session-started") trackOnce("ar_opened", `ar_opened:${pieceId}`, { source });
    };
    viewer.addEventListener("load", onLoad);
    viewer.addEventListener("ar-status", onAr);
    return () => {
      viewer.removeEventListener("load", onLoad);
      viewer.removeEventListener("ar-status", onAr);
    };
  }, [pieceId, source, loaded]);

  const enterAr = useCallback(() => {
    const viewer = box.current?.querySelector<ModelViewerElement>("model-viewer");
    trackOnce("ar_opened", `ar_opened:${pieceId}`, { source });
    try {
      // Synchronously in the click handler: no await before activateAR.
      if (viewer?.canActivateAR && typeof viewer.activateAR === "function") {
        Promise.resolve(viewer.activateAR()).catch(() => {});
      }
    } catch {
      // Some devices throw synchronously; the 3D preview keeps working.
    }
  }, [pieceId, source]);

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
    <Box ref={box} position="relative" aspectRatio={{ base: "1", md: "4 / 3" }} rounded="xl" overflow="hidden" bg="white" borderWidth="1px">
      <model-viewer
        src={src}
        {...(iosSrc ? { "ios-src": iosSrc } : {})}
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
        {/* Empty slot: hides model-viewer's own AR button (ours is below). */}
        <span slot="ar-button" hidden />
      </model-viewer>
      {arAvailable ? (
        <chakra.button
          type="button"
          onClick={enterAr}
          data-testid="ar-button"
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
      ) : null}
      {!loaded ? (
        <Text position="absolute" inset="0" display="flex" alignItems="center" justifyContent="center" color="fg.muted">
          Loading the model…
        </Text>
      ) : null}
    </Box>
  );
}
