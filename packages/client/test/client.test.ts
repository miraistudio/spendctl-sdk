/**
 * Tests run against an in-process fake of the spendctl sidecar's wire protocol
 * (gateway headers, agent API, admin API). No real sidecar, wallet or network.
 */
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";
import { AdminClient, AgentClient, readRefusal, wrapFetch } from "@spendctl/client";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const ADMIN = "test-admin-token";
const AGENT_TOKEN = "test-agent-token";

interface Seen {
  method: string;
  url: string;
  headers: IncomingMessage["headers"];
  body: string;
}
const seen: Seen[] = [];

async function readBody(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

function send(res: ServerResponse, status: number, body: unknown, headers: Record<string, string> = {}): void {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  res.writeHead(status, {
    "content-type": typeof body === "string" ? "text/csv; charset=utf-8" : "application/json",
    ...headers,
  });
  res.end(text);
}

function fakeSidecar(): Server {
  return createServer(async (req, res) => {
    const url = new URL(req.url ?? "/", "http://sidecar");
    const body = await readBody(req);
    seen.push({ method: req.method ?? "", url: req.url ?? "", headers: req.headers, body });
    const path = url.pathname;

    if (path.startsWith("/_spendctl/agent/")) {
      if (req.headers["x-spendctl-token"] !== AGENT_TOKEN) {
        return send(res, 401, { error: "spendctl_unauthorized", message: "Agent token required." });
      }
      if (path === "/_spendctl/agent/budget") {
        return send(res, 200, {
          agent: req.headers["x-spendctl-agent"],
          mode: "enforce",
          perRequest: "$0.05",
          requireApprovalAbove: null,
          onBudgetExceeded: "deny",
          allow: ["*"],
          windows: [{ window: "daily", limit: "$1.00", spent: "$0.01", remaining: "$0.99" }],
        });
      }
      if (path === "/_spendctl/agent/receipts") {
        return send(res, 200, {
          agent: "bot",
          receipts: [{ id: "att_1", status: "settled", limit: url.searchParams.get("limit") }],
        });
      }
      const approval = /^\/_spendctl\/agent\/approvals\/([\w-]+)$/.exec(path);
      if (approval)
        return send(res, 200, { id: approval[1], status: "pending", expiresAt: "2026-01-01T00:00:00.000Z" });
      return send(res, 404, { error: "not_found" });
    }

    if (path.startsWith("/_spendctl/admin/")) {
      if (req.headers.authorization !== `Bearer ${ADMIN}`) {
        return send(res, 401, { error: "spendctl_admin_only", message: "Admin token required." });
      }
      if (path === "/_spendctl/admin/pending") {
        return send(res, 200, {
          pending: [
            {
              id: "apr_1",
              attemptId: "att_1",
              agent: "bot",
              status: "pending",
              createdAt: 0,
              expiresAt: 0,
              host: "api.example.com",
              path: "/expensive",
              usdMicros: "250000",
              network: "eip155:8453",
              asset: "0xusdc",
              assetSymbol: "USDC",
              amountAtomic: "250000",
              payTo: "0xseller",
              reasons: [{ code: "approval_required", message: "over threshold" }],
            },
          ],
        });
      }
      const decide = /^\/_spendctl\/admin\/approvals\/([\w-]+)\/(approve|deny)$/.exec(path);
      if (decide && req.method === "POST") {
        return send(res, 200, {
          approval: { id: decide[1], status: decide[2] === "approve" ? "approved" : "denied" },
          received: JSON.parse(body),
        });
      }
      if (path === "/_spendctl/admin/export") {
        return url.searchParams.get("format") === "json"
          ? send(res, 200, [{ id: "att_1", since: url.searchParams.get("since") }])
          : send(res, 200, "id,agent,tx_hash\natt_1,bot,0xabc\n");
      }
      if (path === "/_spendctl/admin/ledger") {
        return send(res, 200, { attempts: [], query: Object.fromEntries(url.searchParams) });
      }
      if (path === "/_spendctl/admin/summary")
        return send(res, 200, { agents: [], pending: 0, recent: [], dryRun: false });
      return send(res, 404, { error: "not_found" });
    }

    // Gateway: the agent's request, with the real destination in x-spendctl-target.
    const target = req.headers["x-spendctl-target"];
    if (typeof target === "string" && target.includes("/expensive")) {
      return send(
        res,
        402,
        {
          error: "spendctl_approval_required",
          message: "Needs a human.",
          attempt: "att_2",
          approval: "apr_1",
          reasons: [{ code: "threshold", message: "over threshold" }],
        },
        { "x-spendctl-attempt": "att_2", "x-spendctl-decision": "pending_approval" },
      );
    }
    if (typeof target === "string" && target.includes("/forbidden")) {
      return send(
        res,
        402,
        {
          error: "spendctl_denied",
          message: "Host not allowed.",
          reasons: [{ code: "host", message: "not in allow list" }],
        },
        { "x-spendctl-attempt": "att_3", "x-spendctl-decision": "denied" },
      );
    }
    return send(
      res,
      200,
      {
        target: target ?? null,
        agent: req.headers["x-spendctl-agent"] ?? null,
        token: req.headers["x-spendctl-token"] ?? null,
        method: req.method,
        body,
      },
      { "x-spendctl-amount": "$0.01", "x-spendctl-decision": "settled", "x-spendctl-attempt": "att_1" },
    );
  });
}

let server: Server;
let base = "";

beforeAll(async () => {
  server = fakeSidecar();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((resolve, reject) => server.close((err) => (err ? reject(err) : resolve()))));

beforeEach(() => {
  seen.length = 0;
});

describe("wrapFetch", () => {
  it("routes absolute URLs through the sidecar with target, agent and token headers", async () => {
    const pay = wrapFetch({ url: base, agent: "bot", token: AGENT_TOKEN });
    const res = await pay("https://api.example.com/paid?city=Kyoto", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ q: 1 }),
    });
    expect(res.status).toBe(200);
    expect(res.headers.get("x-spendctl-amount")).toBe("$0.01");
    expect(await res.json()).toMatchObject({
      target: "https://api.example.com/paid?city=Kyoto",
      agent: "bot",
      token: AGENT_TOKEN,
      method: "POST",
      body: '{"q":1}',
    });
    expect(seen[0]?.url).toBe("/");
    expect(seen[0]?.headers["content-type"]).toBe("application/json");
  });

  it("sends GET without a body and tolerates a trailing slash in the sidecar URL", async () => {
    const pay = wrapFetch({ url: `${base}/`, agent: "bot" });
    const res = await pay("https://api.example.com/free");
    expect(await res.json()).toMatchObject({ method: "GET", body: "", token: null });
  });

  it("passes requests already addressed to the sidecar straight through", async () => {
    const pay = wrapFetch({ url: base, agent: "bot" });
    const res = await pay(`${base}/_spendctl/agent/budget`, { headers: { "x-spendctl-token": AGENT_TOKEN } });
    expect(res.status).toBe(200);
    expect(seen[0]?.url).toBe("/_spendctl/agent/budget");
    expect(seen[0]?.headers["x-spendctl-target"]).toBeUndefined();
  });

  it("reads defaults from SPENDCTL_URL, SPENDCTL_AGENT and SPENDCTL_AGENT_TOKEN", async () => {
    vi.stubEnv("SPENDCTL_URL", base);
    vi.stubEnv("SPENDCTL_AGENT", "env-bot");
    vi.stubEnv("SPENDCTL_AGENT_TOKEN", AGENT_TOKEN);
    try {
      const res = await wrapFetch()("https://api.example.com/x");
      expect(await res.json()).toMatchObject({ agent: "env-bot", token: AGENT_TOKEN });
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("uses the injected fetch and forwards the approval header on a retry", async () => {
    const calls: Array<{ url: string; headers: Headers }> = [];
    const fake: typeof fetch = async (input, init) => {
      calls.push({ url: String(input), headers: new Headers(init?.headers) });
      return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    };
    const pay = wrapFetch({ url: base, agent: "bot", fetch: fake });
    await pay("https://api.example.com/expensive", { headers: { "x-spendctl-approval": "apr_1" } });
    expect(calls[0]?.url).toBe(`${base}/`);
    expect(calls[0]?.headers.get("x-spendctl-target")).toBe("https://api.example.com/expensive");
    expect(calls[0]?.headers.get("x-spendctl-approval")).toBe("apr_1");
  });
});

describe("readRefusal", () => {
  it("parses an approval request", async () => {
    const res = await wrapFetch({ url: base, agent: "bot" })("https://api.example.com/expensive");
    expect(res.status).toBe(402);
    const refusal = await readRefusal(res);
    expect(refusal).toMatchObject({ error: "spendctl_approval_required", approval: "apr_1" });
    expect(refusal?.reasons?.[0]?.code).toBe("threshold");
  });

  it("parses a denial and leaves the body readable", async () => {
    const res = await wrapFetch({ url: base, agent: "bot" })("https://api.example.com/forbidden");
    const refusal = await readRefusal(res);
    expect(refusal?.error).toBe("spendctl_denied");
    expect(refusal?.message).toBe("Host not allowed.");
    expect(((await res.json()) as { error: string }).error).toBe("spendctl_denied");
  });

  it("returns undefined for a paid response", async () => {
    const res = await wrapFetch({ url: base, agent: "bot" })("https://api.example.com/paid");
    expect(await readRefusal(res)).toBeUndefined();
  });

  it("returns undefined for errors that did not come from spendctl", async () => {
    expect(await readRefusal(new Response("upstream down", { status: 503 }))).toBeUndefined();
    const notJson = new Response("denied", { status: 402, headers: { "x-spendctl-decision": "denied" } });
    expect(await readRefusal(notJson)).toBeUndefined();
  });
});

describe("AgentClient", () => {
  const agent = () => new AgentClient({ url: base, agent: "bot", token: AGENT_TOKEN });

  it("reads the budget", async () => {
    const budget = await agent().budget();
    expect(budget.agent).toBe("bot");
    expect(budget.windows[0]).toMatchObject({ window: "daily", remaining: "$0.99" });
  });

  it("lists receipts with a limit", async () => {
    const receipts = await agent().receipts(5);
    expect(receipts[0]?.status).toBe("settled");
    expect(seen[0]?.url).toBe("/_spendctl/agent/receipts?limit=5");
  });

  it("reads an approval and encodes its id", async () => {
    const approval = await agent().approval("apr_1");
    expect(approval).toMatchObject({ id: "apr_1", status: "pending" });
  });

  it("exposes the wrapped fetch and surfaces API errors", async () => {
    expect(typeof agent().fetch).toBe("function");
    await expect(new AgentClient({ url: base, agent: "bot", token: "wrong" }).budget()).rejects.toThrow(
      /Agent token required/,
    );
  });
});

describe("AdminClient", () => {
  const admin = () => new AdminClient({ url: base, token: ADMIN });

  it("lists pending approvals with the terms the human is shown", async () => {
    const { pending } = await admin().pending();
    expect(pending[0]).toMatchObject({ id: "apr_1", agent: "bot", host: "api.example.com" });
    // Typed fields, not just present in the JSON.
    const terms: Array<string | undefined> = [
      pending[0]?.payTo,
      pending[0]?.network,
      pending[0]?.assetSymbol,
      pending[0]?.amountAtomic,
    ];
    expect(terms).toEqual(["0xseller", "eip155:8453", "USDC", "250000"]);
    expect(pending[0]?.reasons[0]?.code).toBe("approval_required");
    expect(seen[0]?.headers.authorization).toBe(`Bearer ${ADMIN}`);
  });

  it("approves and denies with a note", async () => {
    const approved = await admin().approve("apr_1", "fine");
    expect(approved.approval).toEqual({ id: "apr_1", status: "approved" });
    expect(JSON.parse(seen[0]?.body ?? "{}")).toEqual({ note: "fine", by: "cli" });
    const denied = await admin().deny("apr_1");
    expect(denied.approval.status).toBe("denied");
  });

  it("exports CSV as text and JSON as data", async () => {
    const csv = (await admin().export("csv")) as string;
    expect(csv.split("\n")[0]).toBe("id,agent,tx_hash");
    const rows = (await admin().export("json", { since: "2026-01-01" })) as Array<{ since: string }>;
    expect(rows[0]?.since).toBe("2026-01-01");
  });

  it("passes ledger filters as query parameters", async () => {
    const { query } = (await admin().ledger({ agent: "bot", limit: 5 })) as { query: Record<string, string> };
    expect(query).toEqual({ agent: "bot", limit: "5" });
  });

  it("reads the summary", async () => {
    expect(await admin().summary()).toMatchObject({ pending: 0, dryRun: false });
  });

  it("rejects a wrong token with the sidecar's message", async () => {
    await expect(new AdminClient({ url: base, token: "wrong" }).pending()).rejects.toThrow(/Admin token required/);
  });

  it("explains an unreachable sidecar", async () => {
    const closed = createServer();
    await new Promise<void>((resolve) => closed.listen(0, "127.0.0.1", () => resolve()));
    const port = (closed.address() as AddressInfo).port;
    await new Promise<void>((resolve) => closed.close(() => resolve()));
    await expect(new AdminClient({ url: `http://127.0.0.1:${port}`, token: ADMIN }).pending()).rejects.toThrow(
      /Cannot reach the spendctl sidecar .* Is `spendctl start` running\?/,
    );
  });
});
