"use client";

import { usePathname } from "next/navigation";
import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import {
  GA_ID,
  META_PIXEL_ID,
  analyticsEnabled,
  eventForNavigation,
  initAnalytics,
  measurementActive,
  trackOnce,
  trackPageView,
  type AnalyticsEvent,
  type EventParams,
} from "@/lib/analytics";
import { CONSENT_EVENT } from "@/lib/consent";

/** Whether measurement may run now: an id is set and `sh_consent` is `granted`. */
function useMeasurementAllowed(): boolean {
  const [allowed, setAllowed] = useState(false);
  useEffect(() => {
    const update = () => setAllowed(measurementActive());
    update();
    window.addEventListener(CONSENT_EVENT, update);
    window.addEventListener("storage", update);
    return () => {
      window.removeEventListener(CONSENT_EVENT, update);
      window.removeEventListener("storage", update);
    };
  }, []);
  return allowed;
}

/**
 * Meta Pixel and GA4, each only when its id is set (`NEXT_PUBLIC_META_PIXEL_ID`,
 * `NEXT_PUBLIC_GA_ID`). Lives in the root layout: sends a page view per client
 * navigation and `piece_created` when the form lands on the new piece.
 * Nothing loads until the visitor accepts in `CookieConsent` (or accepted on
 * an earlier visit); without ids it renders nothing and loads nothing.
 */
export function Analytics() {
  const pathname = usePathname();
  const previous = useRef<string | null>(null);
  const allowed = useMeasurementAllowed();

  useEffect(() => {
    // The navigation is remembered even without consent, so `piece_created`
    // is not misread after a later acceptance.
    const from = previous.current;
    previous.current = pathname;
    if (!allowed) return;
    initAnalytics();
    trackPageView(pathname);
    const event = eventForNavigation(from, pathname);
    if (event) trackOnce(event, `${event}:${pathname}`);
  }, [pathname, allowed]);

  if (!allowed || !analyticsEnabled()) return null;
  return (
    <>
      {META_PIXEL_ID ? (
        <Script id="meta-pixel" src="https://connect.facebook.net/en_US/fbevents.js" strategy="lazyOnload" />
      ) : null}
      {GA_ID ? (
        <Script
          id="ga4"
          src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_ID)}`}
          strategy="lazyOnload"
        />
      ) : null}
    </>
  );
}

/**
 * Fires one funnel event when rendered (once per browser for `onceKey`).
 * `cleanParam` removes a one-shot query flag (e.g. `?registro=1`) from the URL.
 */
export function TrackEvent({
  event,
  onceKey,
  params,
  cleanParam,
}: {
  event: AnalyticsEvent;
  onceKey: string;
  params?: EventParams;
  cleanParam?: string;
}) {
  const value = params?.value;
  const currency = params?.currency;
  const transactionId = params?.transactionId;
  useEffect(() => {
    trackOnce(event, onceKey, { value, currency, transactionId });
    if (cleanParam) {
      const url = new URL(window.location.href);
      if (url.searchParams.has(cleanParam)) {
        url.searchParams.delete(cleanParam);
        window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
      }
    }
  }, [event, onceKey, value, currency, transactionId, cleanParam]);
  return null;
}
