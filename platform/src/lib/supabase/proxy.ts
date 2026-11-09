import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import type { Database } from "@/lib/database.types";
import { supabaseAnonKey, supabaseUrl } from "./env";

/**
 * Refreshes the Supabase session cookies (pattern from the Supabase Next.js
 * guide). Returns the response that carries the refreshed cookies; callers
 * must return it (or copy its cookies) or the user is signed out.
 */
export interface SessionInfo {
  response: NextResponse;
  /** Signed-in user (verified JWT claims), or null. */
  user: { id: string; isAnonymous: boolean } | null;
}

export async function updateSession(request: NextRequest): Promise<SessionInfo> {
  let response = NextResponse.next({ request });

  const supabase = createServerClient<Database>(supabaseUrl(), supabaseAnonKey(), {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        for (const [key, value] of Object.entries(headers ?? {})) {
          response.headers.set(key, value);
        }
      },
    },
  });

  // Do not run code between createServerClient and getClaims (Supabase guide).
  const { data } = await supabase.auth.getClaims();
  const claims = data?.claims;

  return {
    response,
    user: claims?.sub ? { id: claims.sub, isAnonymous: claims.is_anonymous === true } : null,
  };
}
