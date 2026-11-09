import { timingSafeEqual } from "node:crypto";
import { notifyPieceInReview, notifyPieceReady } from "@/lib/notify";

/**
 * Worker → web notices. The worker (`src/platform_worker/pipeline.py`) calls it
 * when `NOTIFY_URL` and `WORKER_SHARED_SECRET` are set, with
 * `Authorization: Bearer <WORKER_SHARED_SECRET>` and `{ pieceId, status }`.
 * `review` warns the admin; `ready` emails the customer (the admin action
 * calls `notifyPieceReady` directly, the route accepts it for manual retries).
 */
export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const STATUSES = new Set(["review", "ready"]);

function sameSecret(given: string, expected: string): boolean {
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export async function POST(request: Request): Promise<Response> {
  const secret = process.env.WORKER_SHARED_SECRET?.trim();
  if (!secret) return Response.json({ error: "notify_disabled" }, { status: 503 });

  const auth = request.headers.get("authorization") ?? "";
  const given = auth.startsWith("Bearer ") ? auth.slice("Bearer ".length) : "";
  if (!given || !sameSecret(given, secret)) return Response.json({ error: "unauthorized" }, { status: 401 });

  const body = (await request.json().catch(() => null)) as { pieceId?: unknown; status?: unknown } | null;
  const pieceId = typeof body?.pieceId === "string" ? body.pieceId : "";
  const status = typeof body?.status === "string" ? body.status : "";
  if (!UUID.test(pieceId) || !STATUSES.has(status)) {
    return Response.json({ error: "invalid_body" }, { status: 400 });
  }

  const result = status === "ready" ? await notifyPieceReady(pieceId) : await notifyPieceInReview(pieceId);
  return Response.json({ ok: true, ...result });
}
