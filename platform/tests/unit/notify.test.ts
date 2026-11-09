import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The route and the default piece loader reach server-only modules; the tests inject their own.
vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase/admin", () => ({
  createAdminClient: () => {
    throw new Error("the admin client must not be reached in unit tests");
  },
}));

import { POST } from "@/app/api/internal/notify/route";
import {
  RESEND_ENDPOINT,
  notifyBudgetExhausted,
  notifyPieceFailed,
  notifyPieceInReview,
  notifyPieceReady,
  sendEmail,
  type NotifyDeps,
  type PieceContact,
} from "@/lib/notify";

const PIECE_ID = "0b5e1c1e-8a3f-4c1e-9d55-2f1a6c0d9e71";
const CONTACT: PieceContact = { id: PIECE_ID, name: "Cabecero Rigole", email: "cliente@example.com" };

function okFetch(id = "email_123") {
  return vi.fn(async () => new Response(JSON.stringify({ id }), { status: 200, headers: { "content-type": "application/json" } }));
}

function deps(overrides: Partial<NotifyDeps> = {}): NotifyDeps {
  return {
    apiKey: "re_test_key",
    from: "Pieza 3D <avisos@example.com>",
    adminEmail: "jorge@example.com",
    siteUrl: "https://pieza3d.example",
    fetch: okFetch(),
    loadPiece: async () => CONTACT,
    log: vi.fn(),
    ...overrides,
  };
}

describe("sendEmail", () => {
  it("is a logged no-op without RESEND_API_KEY", async () => {
    const fetch = okFetch();
    const log = vi.fn();
    const result = await sendEmail(
      { to: "a@example.com", subject: "Hola", html: "<p>Hola</p>", text: "Hola" },
      deps({ apiKey: undefined, fetch, log }),
    );
    expect(result).toEqual({ sent: false, reason: "not_configured" });
    expect(fetch).not.toHaveBeenCalled();
    expect(log).toHaveBeenCalledOnce();
  });

  it("posts the message to Resend with the key and an idempotency key", async () => {
    const fetch = okFetch("email_abc");
    const result = await sendEmail(
      { to: "a@example.com", subject: "Hola", html: "<p>Hola</p>", text: "Hola", idempotencyKey: "piece-ready/1" },
      deps({ fetch }),
    );
    expect(result).toEqual({ sent: true, id: "email_abc" });
    expect(fetch).toHaveBeenCalledOnce();
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(RESEND_ENDPOINT);
    expect(init.method).toBe("POST");
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBe("Bearer re_test_key");
    expect(headers.get("content-type")).toBe("application/json");
    expect(headers.get("idempotency-key")).toBe("piece-ready/1");
    expect(JSON.parse(init.body as string)).toEqual({
      from: "Pieza 3D <avisos@example.com>",
      to: ["a@example.com"],
      subject: "Hola",
      html: "<p>Hola</p>",
      text: "Hola",
    });
  });

  it("never throws: an API error comes back as sent false", async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ message: "invalid from" }), { status: 422 }));
    const log = vi.fn();
    const result = await sendEmail({ to: "a@example.com", subject: "s", html: "h", text: "t" }, deps({ fetch, log }));
    expect(result).toMatchObject({ sent: false, reason: "error" });
    expect(log).toHaveBeenCalled();

    const broken = vi.fn(async () => {
      throw new Error("network down");
    });
    expect(await sendEmail({ to: "a@example.com", subject: "s", html: "h", text: "t" }, deps({ fetch: broken }))).toMatchObject({
      sent: false,
      reason: "error",
    });
  });
});

describe("notifyPieceReady", () => {
  it("returns sent false without a key and does not look the piece up", async () => {
    const loadPiece = vi.fn(async () => CONTACT);
    expect(await notifyPieceReady(PIECE_ID, deps({ apiKey: undefined, loadPiece }))).toEqual({
      sent: false,
      reason: "not_configured",
    });
    expect(loadPiece).not.toHaveBeenCalled();
  });

  it("emails the customer with the piece name and its link", async () => {
    const fetch = okFetch();
    const result = await notifyPieceReady(PIECE_ID, deps({ fetch }));
    expect(result).toEqual({ sent: true, id: "email_123" });
    const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.to).toEqual(["cliente@example.com"]);
    expect(body.subject).toBe("Tu pieza «Cabecero Rigole» está lista");
    expect(body.text).toContain(`https://pieza3d.example/piezas/${PIECE_ID}`);
    expect(body.html).toContain(`href="https://pieza3d.example/piezas/${PIECE_ID}"`);
    expect(new Headers(init.headers).get("idempotency-key")).toBe(`piece-ready/${PIECE_ID}`);
  });

  it("escapes the piece name in the HTML", async () => {
    const fetch = okFetch();
    await notifyPieceReady(PIECE_ID, deps({ fetch, loadPiece: async () => ({ ...CONTACT, name: "<b>Mesa</b> & co" }) }));
    const body = JSON.parse((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.html).toContain("&lt;b&gt;Mesa&lt;/b&gt; &amp; co");
    expect(body.html).not.toContain("<b>Mesa</b>");
  });

  it("reports a missing piece without sending", async () => {
    const fetch = okFetch();
    expect(await notifyPieceReady(PIECE_ID, deps({ fetch, loadPiece: async () => null }))).toEqual({
      sent: false,
      reason: "not_found",
    });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("notifyPieceInReview", () => {
  it("emails the admin with the review link", async () => {
    const fetch = okFetch();
    await notifyPieceInReview(PIECE_ID, deps({ fetch }));
    const body = JSON.parse((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.to).toEqual(["jorge@example.com"]);
    expect(body.subject).toBe("Pieza en revisión: «Cabecero Rigole»");
    expect(body.text).toContain(`https://pieza3d.example/admin/revision/${PIECE_ID}`);
  });

  it("needs ADMIN_NOTIFY_EMAIL", async () => {
    const fetch = okFetch();
    expect(await notifyPieceInReview(PIECE_ID, deps({ fetch, adminEmail: undefined }))).toEqual({
      sent: false,
      reason: "no_recipient",
    });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("admin alerts (failed, budget)", () => {
  it("emails the admin when a piece fails", async () => {
    const fetch = okFetch();
    await notifyPieceFailed(PIECE_ID, deps({ fetch }));
    const body = JSON.parse((fetch.mock.calls[0] as unknown as [string, RequestInit])[1].body as string);
    expect(body.to).toEqual(["jorge@example.com"]);
    expect(body.subject).toBe("Pieza fallida: «Cabecero Rigole»");
    expect(body.text).toContain("https://pieza3d.example/admin/revision");
  });

  it("emails the admin once a day when the budget runs out", async () => {
    const fetch = okFetch();
    await notifyBudgetExhausted(PIECE_ID, deps({ fetch }));
    const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string).subject).toBe("Presupuesto diario del proveedor agotado");
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^budget\/\d{4}-\d{2}-\d{2}$/);
  });

  it("needs ADMIN_NOTIFY_EMAIL", async () => {
    const fetch = okFetch();
    expect(await notifyPieceFailed(PIECE_ID, deps({ fetch, adminEmail: undefined }))).toEqual({
      sent: false,
      reason: "no_recipient",
    });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("POST /api/internal/notify", () => {
  const SECRET = "worker-secret-for-tests";
  const request = (body: unknown, auth?: string) =>
    new Request("http://localhost/api/internal/notify", {
      method: "POST",
      headers: { "content-type": "application/json", ...(auth ? { authorization: auth } : {}) },
      body: JSON.stringify(body),
    });

  beforeEach(() => {
    vi.stubEnv("WORKER_SHARED_SECRET", SECRET);
    vi.stubEnv("RESEND_API_KEY", "");
    vi.spyOn(console, "info").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("is disabled without WORKER_SHARED_SECRET", async () => {
    vi.stubEnv("WORKER_SHARED_SECRET", "");
    const response = await POST(request({ pieceId: PIECE_ID, status: "review" }, `Bearer ${SECRET}`));
    expect(response.status).toBe(503);
  });

  it("refuses a missing or wrong secret", async () => {
    expect((await POST(request({ pieceId: PIECE_ID, status: "review" }))).status).toBe(401);
    expect((await POST(request({ pieceId: PIECE_ID, status: "review" }, "Bearer nope"))).status).toBe(401);
  });

  it("validates the body", async () => {
    const auth = `Bearer ${SECRET}`;
    expect((await POST(request({ pieceId: "not-a-uuid", status: "review" }, auth))).status).toBe(400);
    expect((await POST(request({ pieceId: PIECE_ID, status: "approved" }, auth))).status).toBe(400);
  });

  it("answers sent false when email is not configured", async () => {
    const response = await POST(request({ pieceId: PIECE_ID, status: "review" }, `Bearer ${SECRET}`));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true, sent: false, reason: "not_configured" });
  });

  it("accepts the failed and budget notices", async () => {
    for (const status of ["failed", "budget"]) {
      const response = await POST(request({ pieceId: PIECE_ID, status }, `Bearer ${SECRET}`));
      expect(response.status).toBe(200);
    }
    expect((await POST(request({ pieceId: PIECE_ID, status: "toString" }, `Bearer ${SECRET}`))).status).toBe(400);
  });

});
