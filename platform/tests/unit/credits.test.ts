import { describe, expect, it } from "vitest";
import { formatCreditDelta, getLedger, LEDGER_REASON_LABEL, type LedgerClient } from "@/lib/credits";

const USER = "11111111-1111-1111-1111-111111111111";

/** Records the query the page makes and answers with canned rows. */
function fakeClient(rows: unknown[], balance: number | null, rpcError: unknown = null) {
  const calls: { table?: string; select?: string; eq?: [string, string]; order?: string; limit?: number } = {};
  const client = {
    rpc: async (fn: string, args: { p_user: string }) => {
      expect(fn).toBe("credit_balance");
      expect(args).toEqual({ p_user: USER });
      return { data: balance, error: rpcError };
    },
    from(table: string) {
      calls.table = table;
      const builder = {
        select(columns: string) {
          calls.select = columns;
          return builder;
        },
        eq(column: string, value: string) {
          calls.eq = [column, value];
          return builder;
        },
        order(column: string) {
          calls.order = column;
          return builder;
        },
        limit(n: number) {
          calls.limit = n;
          return Promise.resolve({ data: rows, error: null });
        },
      };
      return builder;
    },
  };
  return { client: client as unknown as LedgerClient, calls };
}

describe("getLedger", () => {
  it("returns the balance and the entries, newest first, with English labels", async () => {
    const { client, calls } = fakeClient(
      [
        { id: "b", delta: -1, reason: "consume", created_at: "2026-11-09T10:00:00Z", pieces: { name: "Aparador" } },
        { id: "a", delta: 10, reason: "purchase", created_at: "2026-11-08T09:00:00Z", pieces: null },
      ],
      9,
    );
    const ledger = await getLedger(USER, client);
    expect(calls.table).toBe("credit_ledger");
    expect(calls.eq).toEqual(["user_id", USER]);
    expect(calls.order).toBe("created_at");
    expect(ledger.balance).toBe(9);
    expect(ledger.entries).toEqual([
      { id: "b", delta: -1, reason: "consume", label: "Download", pieceName: "Aparador", createdAt: "2026-11-09T10:00:00Z" },
      { id: "a", delta: 10, reason: "purchase", label: "Purchase", pieceName: null, createdAt: "2026-11-08T09:00:00Z" },
    ]);
  });

  it("treats a missing balance as 0", async () => {
    const { client } = fakeClient([], null);
    expect(await getLedger(USER, client)).toEqual({ balance: 0, entries: [] });
  });

  it("throws when the balance cannot be read", async () => {
    const { client } = fakeClient([], null, { message: "boom" });
    await expect(getLedger(USER, client)).rejects.toThrow();
  });
});

describe("labels and formatting", () => {
  it("has an English label for every ledger reason", () => {
    expect(LEDGER_REASON_LABEL).toEqual({
      purchase: "Purchase",
      consume: "Download",
      grant: "Gift",
      refund: "Refund",
      plan: "Plan",
    });
  });

  it("signs the deltas with a true minus sign", () => {
    expect(formatCreditDelta(10)).toBe("+10");
    expect(formatCreditDelta(-1)).toBe("−1");
    expect(formatCreditDelta(1000)).toBe("+1,000");
  });
});

describe("counts", () => {
  it("groups thousands and pluralises", async () => {
    const { formatCount, formatCredits } = await import("@/lib/credits");
    expect(formatCount(1000)).toBe("1,000");
    expect(formatCount(0)).toBe("0");
    expect(formatCredits(1)).toBe("1 credit");
    expect(formatCredits(10)).toBe("10 credits");
    expect(formatCredits(-1)).toBe("−1 credit");
  });
});
