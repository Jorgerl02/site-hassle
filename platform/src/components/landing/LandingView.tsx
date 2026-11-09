"use client";

import { useEffect } from "react";
import { sourceFromSearch, trackOnce } from "@/lib/analytics";

/** `landing_view` once per browser and day, with the source of the visit (`?source=`, `utm_source` or `direct`). */
export function LandingView() {
  useEffect(() => {
    const day = new Date().toISOString().slice(0, 10);
    trackOnce("landing_view", `landing_view:${day}`, { source: sourceFromSearch(window.location.search) });
  }, []);
  return null;
}
