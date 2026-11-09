/**
 * Email notices sent through Resend's REST API (no SDK needed).
 *
 * Optional by design: without `RESEND_API_KEY` every notice is a logged no-op
 * that returns `{ sent: false, reason: "not_configured" }`, so the app and the
 * worker run the same way with or without email. A notice never throws: a
 * failed email must not undo a state change that already happened.
 */
import { PRODUCT_NAME, siteUrl } from "@/lib/site";

export const RESEND_ENDPOINT = "https://api.resend.com/emails";
/** Resend's shared test sender: only delivers to the account owner until a domain is verified. */
export const DEFAULT_FROM = `${PRODUCT_NAME} <onboarding@resend.dev>`;

export type NotifyResult =
  | { sent: true; id: string }
  | { sent: false; reason: "not_configured" | "no_recipient" | "not_found" | "error"; detail?: string };

export interface EmailMessage {
  to: string;
  subject: string;
  html: string;
  text: string;
  /** Resend drops a repeated key for 24 h: the same notice is never sent twice. */
  idempotencyKey?: string;
}

export interface PieceContact {
  id: string;
  name: string;
  email: string | null;
}

export interface NotifyDeps {
  apiKey?: string;
  from: string;
  adminEmail?: string;
  siteUrl: string;
  fetch: typeof fetch;
  loadPiece: (pieceId: string) => Promise<PieceContact | null>;
  log: (message: string, detail?: unknown) => void;
}

function blankToUndefined(value: string | undefined): string | undefined {
  return value?.trim() ? value.trim() : undefined;
}

/** Piece name + owner email with the service role (server only, imported lazily). */
async function loadPieceWithServiceRole(pieceId: string): Promise<PieceContact | null> {
  const { createAdminClient } = await import("@/lib/supabase/admin");
  const db = createAdminClient();
  const { data: piece, error } = await db.from("pieces").select("id, name, user_id").eq("id", pieceId).maybeSingle();
  if (error) throw new Error(`pieces: ${error.message}`);
  if (!piece) return null;
  const { data: profile } = await db.from("profiles").select("email").eq("id", piece.user_id).maybeSingle();
  return { id: piece.id, name: piece.name, email: profile?.email ?? null };
}

export function envDeps(): NotifyDeps {
  return {
    apiKey: blankToUndefined(process.env.RESEND_API_KEY),
    from: blankToUndefined(process.env.NOTIFY_FROM_EMAIL) ?? DEFAULT_FROM,
    adminEmail: blankToUndefined(process.env.ADMIN_NOTIFY_EMAIL),
    siteUrl: siteUrl(),
    fetch: (...args) => fetch(...args),
    loadPiece: loadPieceWithServiceRole,
    log: (message, detail) => (detail === undefined ? console.info(message) : console.info(message, detail)),
  };
}

export async function sendEmail(message: EmailMessage, deps: NotifyDeps = envDeps()): Promise<NotifyResult> {
  if (!deps.apiKey) {
    deps.log(`[notify] RESEND_API_KEY sin configurar: no se envía «${message.subject}» a ${message.to}`);
    return { sent: false, reason: "not_configured" };
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${deps.apiKey}`,
    "Content-Type": "application/json",
  };
  if (message.idempotencyKey) headers["Idempotency-Key"] = message.idempotencyKey;
  try {
    const response = await deps.fetch(RESEND_ENDPOINT, {
      method: "POST",
      headers,
      body: JSON.stringify({
        from: deps.from,
        to: [message.to],
        subject: message.subject,
        html: message.html,
        text: message.text,
      }),
    });
    const payload = (await response.json().catch(() => null)) as { id?: string; message?: string } | null;
    if (!response.ok || !payload?.id) {
      const detail = `${response.status} ${payload?.message ?? ""}`.trim();
      deps.log(`[notify] Resend rechazó «${message.subject}»`, detail);
      return { sent: false, reason: "error", detail };
    }
    return { sent: true, id: payload.id };
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    deps.log(`[notify] no se pudo enviar «${message.subject}»`, detail);
    return { sent: false, reason: "error", detail };
  }
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

function layout(paragraphs: string[], link: { href: string; label: string }): string {
  const body = paragraphs.map((p) => `<p style="margin:0 0 16px">${p}</p>`).join("");
  return (
    `<div style="font-family:Inter,Arial,sans-serif;font-size:16px;line-height:1.5;color:#2b2621;max-width:520px">` +
    body +
    `<p style="margin:24px 0"><a href="${escapeHtml(link.href)}" style="background:#b4532a;color:#fff;` +
    `padding:12px 20px;border-radius:999px;text-decoration:none;font-weight:600">${link.label}</a></p>` +
    `<p style="margin:0;color:#7a7067;font-size:14px">${PRODUCT_NAME}</p></div>`
  );
}

async function notifyAbout(
  pieceId: string,
  deps: NotifyDeps,
  build: (piece: PieceContact) => EmailMessage | null,
): Promise<NotifyResult> {
  // Without a key there is nothing to send: skip the lookup too.
  if (!deps.apiKey) {
    deps.log(`[notify] RESEND_API_KEY sin configurar: sin aviso para la pieza ${pieceId}`);
    return { sent: false, reason: "not_configured" };
  }
  let piece: PieceContact | null;
  try {
    piece = await deps.loadPiece(pieceId);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    deps.log(`[notify] no se pudo leer la pieza ${pieceId}`, detail);
    return { sent: false, reason: "error", detail };
  }
  if (!piece) return { sent: false, reason: "not_found" };
  const message = build(piece);
  if (!message) return { sent: false, reason: "no_recipient" };
  return sendEmail(message, deps);
}

/** Customer notice: the reviewed piece is `ready` to see (free) and to download (1 credit). */
export async function notifyPieceReady(pieceId: string, deps: NotifyDeps = envDeps()): Promise<NotifyResult> {
  return notifyAbout(pieceId, deps, (piece) => {
    if (!piece.email) return null;
    const href = `${deps.siteUrl}/piezas/${piece.id}`;
    const name = escapeHtml(piece.name);
    return {
      to: piece.email,
      subject: `Tu pieza «${piece.name}» está lista`,
      idempotencyKey: `piece-ready/${piece.id}`,
      text:
        `Tu pieza «${piece.name}» ya tiene su modelo 3D a escala real.\n\n` +
        `Míralo gratis, con sus medidas y en realidad aumentada, y descárgalo si te convence: ${href}\n\n` +
        PRODUCT_NAME,
      html: layout(
        [
          `Tu pieza «${name}» ya tiene su modelo 3D a escala real.`,
          "Míralo gratis, con sus medidas y en realidad aumentada, y descárgalo si te convence.",
        ],
        { href, label: "Ver mi pieza" },
      ),
    };
  });
}

/** Internal heads-up: the worker left a piece in `review`. Needs `ADMIN_NOTIFY_EMAIL`. */
export async function notifyPieceInReview(pieceId: string, deps: NotifyDeps = envDeps()): Promise<NotifyResult> {
  if (deps.apiKey && !deps.adminEmail) {
    deps.log(`[notify] ADMIN_NOTIFY_EMAIL sin configurar: sin aviso de revisión para ${pieceId}`);
    return { sent: false, reason: "no_recipient" };
  }
  return notifyAbout(pieceId, deps, (piece) => {
    if (!deps.adminEmail) return null;
    const href = `${deps.siteUrl}/admin/revision/${piece.id}`;
    return {
      to: deps.adminEmail,
      subject: `Pieza en revisión: «${piece.name}»`,
      text: `El worker ha terminado «${piece.name}» y espera revisión: ${href}`,
      html: layout([`El worker ha terminado «${escapeHtml(piece.name)}» y espera revisión.`], {
        href,
        label: "Revisar",
      }),
    };
  });
}
