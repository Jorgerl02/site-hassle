/**
 * Ads measurement (Meta Pixel and GA4), both optional: with neither
 * `NEXT_PUBLIC_META_PIXEL_ID` nor `NEXT_PUBLIC_GA_ID` every call is a no-op and
 * no third-party script is loaded.
 *
 * Funnel events and how each platform receives them:
 *
 * | Event              | Meta Pixel                      | GA4                |
 * |--------------------|---------------------------------|--------------------|
 * | `landing_view`     | custom `LandingView`            | `landing_view`     |
 * | `piece_started`    | custom `PieceStarted`           | `piece_started`    |
 * | `preview_opened`   | custom `PreviewOpened`          | `preview_opened`   |
 * | `ar_opened`        | custom `AROpened`               | `ar_opened`        |
 * | `download_clicked` | custom `DownloadClicked`        | `download_clicked` |
 * | `signup`           | `CompleteRegistration`          | `sign_up`          |
 * | `purchase`         | `Purchase` (value, currency)    | `purchase`         |
 * | `piece_approved`   | custom `PieceApproved`          | `piece_approved`   |
 *
 * Every event may carry `source` (the CTA or ad that started the trial, also
 * stored in `profiles.attribution.source`), sent as a custom parameter.
 *
 * The vendors' queue stubs are created on first use, so events fired before
 * the scripts finish loading are kept and sent in order. Nothing is created or
 * sent without a stored `granted` consent (`lib/consent.ts`): events before
 * the visitor accepts are dropped.
 */

import { measurementAllowed, readConsent } from "@/lib/consent";

export type AnalyticsEvent =
  | "landing_view"
  | "piece_started"
  | "preview_opened"
  | "ar_opened"
  | "download_clicked"
  | "signup"
  | "purchase"
  | "piece_approved";

export interface EventParams {
  value?: number;
  currency?: string;
  transactionId?: string;
  /** Funnel source (`?source=` of the CTA, else `utm_source`, else `direct`). */
  source?: string;
}

export const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID?.trim() || undefined;
export const GA_ID = process.env.NEXT_PUBLIC_GA_ID?.trim() || undefined;

type Fbq = ((...args: unknown[]) => void) & {
  callMethod?: (...args: unknown[]) => void;
  queue: unknown[];
  push: Fbq;
  loaded: boolean;
  version: string;
};

declare global {
  interface Window {
    fbq?: Fbq;
    _fbq?: Fbq;
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const META_EVENT: Record<AnalyticsEvent, { standard: boolean; name: string }> = {
  landing_view: { standard: false, name: "LandingView" },
  piece_started: { standard: false, name: "PieceStarted" },
  preview_opened: { standard: false, name: "PreviewOpened" },
  ar_opened: { standard: false, name: "AROpened" },
  download_clicked: { standard: false, name: "DownloadClicked" },
  signup: { standard: true, name: "CompleteRegistration" },
  purchase: { standard: true, name: "Purchase" },
  piece_approved: { standard: false, name: "PieceApproved" },
};

const GA_EVENT: Record<AnalyticsEvent, string> = {
  landing_view: "landing_view",
  piece_started: "piece_started",
  preview_opened: "preview_opened",
  ar_opened: "ar_opened",
  download_clicked: "download_clicked",
  signup: "sign_up",
  purchase: "purchase",
  piece_approved: "piece_approved",
};

/** `?source=` of the URL, else `utm_source`, else `direct` (letters, digits, `_-.` only, 60 chars). */
export function sourceFromSearch(search: string | URLSearchParams): string {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  return cleanSource(params.get("source")) ?? cleanSource(params.get("utm_source")) ?? "direct";
}

export function cleanSource(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const clean = value.trim().replace(/[^\w.-]/g, "").slice(0, 60);
  return clean || null;
}

let initialised = false;

/** Same queue stubs as the vendors' snippets; idempotent. */
export function initAnalytics(): void {
  if (initialised || !measurementActive()) return;
  initialised = true;
  if (META_PIXEL_ID && !window.fbq) {
    const fbq = function (...args: unknown[]) {
      if (fbq.callMethod) fbq.callMethod(...args);
      else fbq.queue.push(args);
    } as Fbq;
    fbq.push = fbq;
    fbq.loaded = true;
    fbq.version = "2.0";
    fbq.queue = [];
    window.fbq = fbq;
    window._fbq = window._fbq ?? fbq;
    fbq("init", META_PIXEL_ID);
  }
  if (GA_ID && !window.gtag) {
    window.dataLayer = window.dataLayer ?? [];
    window.gtag = function gtag() {
      // gtag.js reads the `arguments` object itself, not an array.
      // eslint-disable-next-line prefer-rest-params
      window.dataLayer!.push(arguments);
    };
    window.gtag("js", new Date());
    // Page views are sent by `trackPageView` on every client navigation.
    window.gtag("config", GA_ID, { send_page_view: false });
  }
}

/** Some measurement id is configured (the consent banner exists only then). */
export function analyticsEnabled(): boolean {
  return Boolean(META_PIXEL_ID || GA_ID);
}

/** An id is configured and the visitor accepted measurement cookies. */
export function measurementActive(): boolean {
  return typeof window !== "undefined" && measurementAllowed(analyticsEnabled(), readConsent());
}

export function trackPageView(path: string): void {
  if (!measurementActive()) return;
  initAnalytics();
  window.fbq?.("track", "PageView");
  // Origin + path only: no query string (it can carry session ids or e-mail links).
  window.gtag?.("event", "page_view", { page_path: path, page_location: `${window.location.origin}${path}` });
}

/** Sends one funnel event; returns whether it was sent (needs an id and consent). */
export function track(event: AnalyticsEvent, params: EventParams = {}): boolean {
  if (!measurementActive()) return false;
  initAnalytics();
  const money = params.value !== undefined ? { value: params.value, currency: params.currency ?? "EUR" } : {};
  const source = params.source ? { source: params.source } : {};
  const meta = META_EVENT[event];
  // eventID lets Meta deduplicate the purchase (e.g. against a future Conversions API call).
  const metaOptions = params.transactionId ? [{ eventID: params.transactionId }] : [];
  window.fbq?.(meta.standard ? "track" : "trackCustom", meta.name, { ...money, ...source }, ...metaOptions);
  window.gtag?.("event", GA_EVENT[event], {
    ...money,
    ...source,
    ...(params.transactionId ? { transaction_id: params.transactionId } : {}),
  });
  return true;
}

/**
 * Fires `event` once per browser for `onceKey` (localStorage; best effort).
 * Without an id or consent nothing is read or written: the key is marked only
 * after a real send, so an event dropped before consent can still fire later.
 */
export function trackOnce(event: AnalyticsEvent, onceKey: string, params?: EventParams): void {
  if (!measurementActive()) return;
  const key = `sh_tracked:${onceKey}`;
  let storage: Storage | null = null;
  try {
    storage = window.localStorage;
    if (storage.getItem(key)) return;
  } catch {
    storage = null; // storage blocked: send anyway (a duplicate beats a lost conversion)
  }
  if (!track(event, params)) return;
  try {
    storage?.setItem(key, "1");
  } catch {
    // ignore
  }
}

/**
 * First sign-in of a magic-link account: Supabase confirms the email on that
 * same verification, so `email_confirmed_at` and `last_sign_in_at` coincide.
 * An anonymous trial that adds its email confirms it on the link click, so the
 * conversion also counts (its `last_sign_in_at` is refreshed by the callback).
 */
export function isFirstSignIn(
  user: { email_confirmed_at?: string | null; last_sign_in_at?: string | null; is_anonymous?: boolean } | null | undefined,
): boolean {
  if (user?.is_anonymous) return false;
  if (!user?.email_confirmed_at || !user.last_sign_in_at) return false;
  const gap = Date.parse(user.last_sign_in_at) - Date.parse(user.email_confirmed_at);
  return Number.isFinite(gap) && Math.abs(gap) < 60_000;
}
