/**
 * Ads measurement (Meta Pixel and GA4), both optional: with neither
 * `NEXT_PUBLIC_META_PIXEL_ID` nor `NEXT_PUBLIC_GA_ID` every call is a no-op and
 * no third-party script is loaded.
 *
 * Funnel events and how each platform receives them:
 *
 * | Event            | Meta Pixel                      | GA4              |
 * |------------------|---------------------------------|------------------|
 * | `signup`         | `CompleteRegistration`          | `sign_up`        |
 * | `piece_created`  | custom `PieceCreated`           | `piece_created`  |
 * | `piece_approved` | custom `PieceApproved`          | `piece_approved` |
 * | `purchase`       | `Purchase` (value, currency)    | `purchase`       |
 *
 * The vendors' queue stubs are created on first use, so events fired before
 * the scripts finish loading are kept and sent in order.
 */

export type AnalyticsEvent = "signup" | "piece_created" | "piece_approved" | "purchase";

export interface EventParams {
  value?: number;
  currency?: string;
  transactionId?: string;
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
  signup: { standard: true, name: "CompleteRegistration" },
  piece_created: { standard: false, name: "PieceCreated" },
  piece_approved: { standard: false, name: "PieceApproved" },
  purchase: { standard: true, name: "Purchase" },
};

const GA_EVENT: Record<AnalyticsEvent, string> = {
  signup: "sign_up",
  piece_created: "piece_created",
  piece_approved: "piece_approved",
  purchase: "purchase",
};

let initialised = false;

/** Same queue stubs as the vendors' snippets; idempotent. */
export function initAnalytics(): void {
  if (initialised || typeof window === "undefined") return;
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

export function analyticsEnabled(): boolean {
  return Boolean(META_PIXEL_ID || GA_ID);
}

export function trackPageView(path: string): void {
  if (!analyticsEnabled()) return;
  initAnalytics();
  window.fbq?.("track", "PageView");
  window.gtag?.("event", "page_view", { page_path: path, page_location: window.location.href });
}

export function track(event: AnalyticsEvent, params: EventParams = {}): void {
  if (!analyticsEnabled() || typeof window === "undefined") return;
  initAnalytics();
  const money = params.value !== undefined ? { value: params.value, currency: params.currency ?? "EUR" } : {};
  const meta = META_EVENT[event];
  window.fbq?.(meta.standard ? "track" : "trackCustom", meta.name, money);
  window.gtag?.("event", GA_EVENT[event], {
    ...money,
    ...(params.transactionId ? { transaction_id: params.transactionId } : {}),
  });
}

/** Fires `event` once per browser for `onceKey` (localStorage; best effort). */
export function trackOnce(event: AnalyticsEvent, onceKey: string, params?: EventParams): void {
  const key = `sh_tracked:${onceKey}`;
  try {
    if (window.localStorage.getItem(key)) return;
    window.localStorage.setItem(key, "1");
  } catch {
    // Storage blocked: send anyway (a duplicate beats a lost conversion).
  }
  track(event, params);
}

const PIECE_PAGE = /^\/piezas\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Funnel events inferred from a client navigation: creating a piece is the
 * only way from `/piezas/nueva` to a piece page (the form redirects there).
 */
export function eventForNavigation(from: string | null, to: string): AnalyticsEvent | null {
  if (from === "/piezas/nueva" && PIECE_PAGE.test(to)) return "piece_created";
  return null;
}

/**
 * First sign-in of a magic-link account: Supabase confirms the email on that
 * same verification, so `email_confirmed_at` and `last_sign_in_at` coincide.
 */
export function isFirstSignIn(user: { email_confirmed_at?: string | null; last_sign_in_at?: string | null } | null | undefined): boolean {
  if (!user?.email_confirmed_at || !user.last_sign_in_at) return false;
  const gap = Date.parse(user.last_sign_in_at) - Date.parse(user.email_confirmed_at);
  return Number.isFinite(gap) && Math.abs(gap) < 60_000;
}
