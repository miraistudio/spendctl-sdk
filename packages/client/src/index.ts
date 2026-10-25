/**
 * Client for the spendctl sidecar. No dependencies, works in Node, Bun, Deno and
 * edge runtimes. The agent side never holds keys or the admin token.
 */

const DEFAULT_URL = "http://127.0.0.1:8402";

function env(name: string): string | undefined {
  return typeof process !== "undefined" ? process.env?.[name] : undefined;
}

export interface AgentClientOptions {
  /** Sidecar base URL. Default: $SPENDCTL_URL or http://127.0.0.1:8402. */
  url?: string;
  /** Agent name as defined in spendctl.yaml. Default: $SPENDCTL_AGENT. */
  agent?: string;
  /** Per-agent token when the sidecar runs with `agentAuth: token`. Default: $SPENDCTL_AGENT_TOKEN. */
  token?: string;
  /** Underlying fetch. */
  fetch?: typeof fetch;
}

export interface Budget {
  agent: string;
  mode: string;
  perRequest: string | null;
  requireApprovalAbove: string | null;
  onBudgetExceeded: string;
  allow: string[];
  windows: Array<{ window: string; limit: string; spent: string; remaining: string }>;
}

export interface Receipt {
  id: string;
  created_at_utc: string;
  agent: string;
  status: string;
  method: string;
  host: string;
  path: string;
  usd_value: string;
  tx_hash: string;
  reasons: string;
  [key: string]: string | number;
}

/** Body spendctl returns when it refuses, needs approval, or is in dry-run. */
export interface SpendctlRefusal {
  error: "spendctl_denied" | "spendctl_approval_required" | "spendctl_dry_run" | string;
  message: string;
  attempt?: string;
  decision?: string;
  amount?: string;
  approval?: string;
  reasons?: Array<{ code: string; message: string }>;
}

function resolve(options: AgentClientOptions) {
  return {
    url: (options.url ?? env("SPENDCTL_URL") ?? DEFAULT_URL).replace(/\/$/, ""),
    agent: options.agent ?? env("SPENDCTL_AGENT"),
    token: options.token ?? env("SPENDCTL_AGENT_TOKEN"),
    fetch: options.fetch ?? globalThis.fetch.bind(globalThis),
  };
}

/**
 * Returns a `fetch` that sends absolute http(s) URLs through the spendctl sidecar.
 * If the seller answers 402, the sidecar applies policy, asks a human if needed,
 * pays, and returns the paid response — or a 402 explaining why it refused.
 */
export function wrapFetch(options: AgentClientOptions = {}): typeof fetch {
  const cfg = resolve(options);
  const wrapped = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const request = new Request(input, init);
    const target = request.url;
    if (!/^https?:\/\//i.test(target) || target.startsWith(`${cfg.url}/`)) return cfg.fetch(request);
    const headers = new Headers(request.headers);
    headers.set("x-spendctl-target", target);
    if (cfg.agent) headers.set("x-spendctl-agent", cfg.agent);
    if (cfg.token) headers.set("x-spendctl-token", cfg.token);
    const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
    return cfg.fetch(`${cfg.url}/`, {
      method: request.method,
      headers,
      body: body?.byteLength ? body : undefined,
      signal: request.signal,
      redirect: "manual",
    });
  };
  return wrapped as typeof fetch;
}

/** Parses a spendctl refusal body if `response` is one. */
export async function readRefusal(response: Response): Promise<SpendctlRefusal | undefined> {
  if (response.ok) return undefined;
  const type = response.headers.get("content-type") ?? "";
  if (!response.headers.has("x-spendctl-decision") || !type.includes("json")) return undefined;
  try {
    return (await response.clone().json()) as SpendctlRefusal;
  } catch {
    return undefined;
  }
}

export class AgentClient {
  readonly fetch: typeof fetch;
  private readonly cfg: ReturnType<typeof resolve>;

  constructor(options: AgentClientOptions = {}) {
    this.cfg = resolve(options);
    this.fetch = wrapFetch(options);
  }

  private async get<T>(path: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.cfg.agent) headers["x-spendctl-agent"] = this.cfg.agent;
    if (this.cfg.token) headers["x-spendctl-token"] = this.cfg.token;
    const response = await this.cfg.fetch(`${this.cfg.url}/_spendctl/agent/${path}`, { headers });
    const body = (await response.json()) as T & { message?: string };
    if (!response.ok) throw new Error(body.message ?? `spendctl ${path} failed with ${response.status}`);
    return body;
  }

  budget(): Promise<Budget> {
    return this.get<Budget>("budget");
  }

  async receipts(limit = 20): Promise<Receipt[]> {
    return (await this.get<{ receipts: Receipt[] }>(`receipts?limit=${limit}`)).receipts;
  }

  approval(id: string): Promise<{ id: string; status: string; expiresAt: string }> {
    return this.get(`approvals/${encodeURIComponent(id)}`);
  }
}

export interface AdminClientOptions {
  url?: string;
  /** Admin token (from .spendctl/admin.token). */
  token: string;
  fetch?: typeof fetch;
}

export class AdminClient {
  private readonly url: string;
  private readonly token: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: AdminClientOptions) {
    this.url = (options.url ?? env("SPENDCTL_URL") ?? DEFAULT_URL).replace(/\/$/, "");
    this.token = options.token;
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async request<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.url}/_spendctl/admin/${path}`, {
        ...init,
        headers: {
          authorization: `Bearer ${this.token}`,
          "content-type": "application/json",
          ...(init.headers as Record<string, string> | undefined),
        },
      });
    } catch (error) {
      throw new Error(
        `Cannot reach the spendctl sidecar at ${this.url} (${(error as Error).message}). Is \`spendctl start\` running?`,
      );
    }
    const text = await response.text();
    const body = (() => {
      try {
        return JSON.parse(text) as T & { message?: string; error?: string };
      } catch {
        return text as unknown as T & { message?: string; error?: string };
      }
    })();
    if (!response.ok) {
      const detail = typeof body === "object" && body ? (body.message ?? body.error) : text;
      throw new Error(`spendctl: ${detail ?? response.status}`);
    }
    return body;
  }

  pending() {
    return this.request<{
      pending: Array<
        Record<string, unknown> & {
          id: string;
          agent: string;
          host: string;
          path: string;
          usdMicros?: string;
          reasons: Array<{ message: string }>;
          expiresAt: number;
        }
      >;
    }>("pending");
  }

  approve(id: string, note?: string) {
    return this.request<{ approval: { id: string; status: string } }>(`approvals/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ note, by: "cli" }),
    });
  }

  deny(id: string, note?: string) {
    return this.request<{ approval: { id: string; status: string } }>(`approvals/${encodeURIComponent(id)}/deny`, {
      method: "POST",
      body: JSON.stringify({ note, by: "cli" }),
    });
  }

  ledger(options: { agent?: string; limit?: number } = {}) {
    const query = new URLSearchParams();
    if (options.agent) query.set("agent", options.agent);
    if (options.limit) query.set("limit", String(options.limit));
    return this.request<{ attempts: Receipt[] }>(`ledger?${query}`);
  }

  export(format: "csv" | "json", options: { agent?: string; since?: string } = {}) {
    const query = new URLSearchParams({ format });
    if (options.agent) query.set("agent", options.agent);
    if (options.since) query.set("since", options.since);
    return this.request<string | unknown[]>(`export?${query}`);
  }

  trace(id: string) {
    return this.request<{ root: string; text: string }>(`trace/${encodeURIComponent(id)}`);
  }

  summary() {
    return this.request<{ agents: Budget[]; pending: number; recent: Receipt[]; dryRun: boolean }>("summary");
  }

  resolve(id: string, status: "settled" | "failed", txHash?: string) {
    return this.request(`ledger/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ status, txHash }),
    });
  }
}
