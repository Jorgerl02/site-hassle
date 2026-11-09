"use client";

import { Text } from "@chakra-ui/react";
import { useEffect, useRef } from "react";

/**
 * Starts the GLB download once when the page comes back with `?download=1`
 * (after sign-up or after buying credits), then drops the flag from the URL so
 * a reload does not download again. The USDZ stays one click away below.
 */
export function AutoDownload({ href }: { href: string }) {
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const link = document.createElement("a");
    link.href = href;
    link.download = "";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    const url = new URL(window.location.href);
    url.searchParams.delete("download");
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }, [href]);
  return (
    <Text fontSize="sm" color="fg.muted" role="status" data-testid="auto-download">
      Your GLB download has started. The USDZ is just below.
    </Text>
  );
}
