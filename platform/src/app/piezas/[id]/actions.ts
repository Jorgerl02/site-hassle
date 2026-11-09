"use server";

import { revalidatePath } from "next/cache";
import { getCurrentUser } from "@/lib/auth";
import { isUuid, sqlErrorCode } from "@/lib/pieces";
import { createServerClient } from "@/lib/supabase/server";

export type ActionCode =
  | "insufficient_credits"
  | "invalid_state"
  | "max_versions"
  | "not_found"
  | "not_authenticated"
  | "unknown";

export type ActionResult<T = object> = ({ ok: true } & T) | { ok: false; code: ActionCode; message: string };

const MESSAGES: Record<ActionCode, string> = {
  insufficient_credits: "Necesitas 1 crédito para descargar esta pieza.",
  invalid_state: "Esta pieza ha cambiado de estado. Recarga la página.",
  // An admin «Regenerar» also uses an attempt: never claim the customer asked for them.
  max_versions: "No quedan más versiones de esta pieza.",

  not_found: "No encontramos esta pieza.",
  not_authenticated: "Tu sesión ha caducado. Vuelve a entrar.",
  unknown: "Algo ha fallado. Vuelve a intentarlo en unos minutos.",
};

function fail(code: ActionCode): { ok: false; code: ActionCode; message: string } {
  return { ok: false, code, message: MESSAGES[code] };
}

function codeOf(error: { message: string }): ActionCode {
  const code = sqlErrorCode(error);
  if (code === "forbidden") return "not_found";
  return code && code in MESSAGES ? (code as ActionCode) : "unknown";
}

function refresh(id: string) {
  revalidatePath(`/piezas/${id}`);
  revalidatePath("/panel");
}

/**
 * Spends 1 credit (once: `approve_piece` is idempotent). The page then shows
 * the signed GLB and USDZ links (1 h), signed on every visit.
 */
export async function downloadPiece(id: string): Promise<ActionResult> {
  if (!isUuid(id)) return fail("not_found");
  if (!(await getCurrentUser())) return fail("not_authenticated");
  const supabase = await createServerClient();

  const { error } = await supabase.rpc("approve_piece", { p_piece_id: id });
  if (error) return fail(codeOf(error));
  refresh(id);
  return { ok: true };
}

/** Back to the queue for a new attempt, free (at most 2 extra versions). */
export async function requestNewVersion(id: string): Promise<ActionResult> {
  if (!isUuid(id)) return fail("not_found");
  const supabase = await createServerClient();
  const { error } = await supabase.rpc("request_new_version", { p_piece_id: id });
  if (error) return fail(codeOf(error));
  refresh(id);
  return { ok: true };
}

/** «No me sirve»: closes the piece with the customer's reason, free. */
export async function rejectPiece(id: string, reason: string): Promise<ActionResult> {
  if (!isUuid(id)) return fail("not_found");
  const supabase = await createServerClient();
  const { error } = await supabase.rpc("reject_piece", { p_piece_id: id, p_reason: reason.trim().slice(0, 500) });
  if (error) return fail(codeOf(error));
  refresh(id);
  return { ok: true };
}
