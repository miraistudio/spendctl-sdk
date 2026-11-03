# @spendctl/client

Zero-dependency client for the [spendctl](https://spendctl.dev) sidecar. Works in Node 22.13+, Bun, Deno and edge runtimes; ESM only.

spendctl is the spend-policy control plane for AI agents: budgets, approvals, receipts and chain tracing across every wallet and every HTTP 402 protocol — enforced in a sidecar you run, never by holding your keys or funds. This package is the thin client; the sidecar ships separately (`npx spendctl init && npx spendctl start`, docs at <https://spendctl.dev/docs/>).

```sh
npm i @spendctl/client
```

## For agents: `wrapFetch`

Returns a `fetch` that sends absolute `http(s)` URLs through the sidecar. If the seller answers `402`, the sidecar applies your policy, asks a human when needed, pays, and returns the paid response — or a `402` explaining why it refused.

```ts
import { wrapFetch, readRefusal } from "@spendctl/client";

const pay = wrapFetch({ agent: "researcher" });

const res = await pay("https://api.example.com/paid");
if (res.ok) {
  console.log(res.headers.get("x-spendctl-amount")); // "$0.01"
} else {
  const refusal = await readRefusal(res);
  if (refusal?.error === "spendctl_approval_required") {
    // A human was asked, and has until refusal.approvalExpiresAt. Wait with
    // `AgentClient.approval(refusal.approval, { wait: 25 })`, then retry with
    // { headers: { "x-spendctl-approval": refusal.approval } } once it is approved.
  }
}
```

Options (each falls back to an environment variable):

| Option | Env var | Default |
| --- | --- | --- |
| `url` | `SPENDCTL_URL` | `http://127.0.0.1:8402` |
| `agent` | `SPENDCTL_AGENT` | — |
| `token` | `SPENDCTL_AGENT_TOKEN` | — (only when the sidecar runs with `agentAuth: token`) |
| `fetch` | — | `globalThis.fetch` |

Requests that already point at the sidecar, or that are not absolute `http(s)` URLs, go through untouched. The agent side never holds a wallet key or the admin token.

`readRefusal(response)` returns the sidecar's refusal body (`spendctl_denied`, `spendctl_approval_required`, `spendctl_dry_run`) or `undefined` when the response was paid or did not come from spendctl. It clones the body, so the response stays readable. Besides `message` and `reasons`, it carries the approval id with its deadline (`approval`, `approvalExpiresAt`), a `hint` for the agent, and your own `Idempotency-Key` / `X-Request-Id` echoed back as `idempotencyKey` / `requestId`.

## For agents: `AgentClient`

The agent's own budget, receipts and approvals. It cannot approve anything.

```ts
import { AgentClient } from "@spendctl/client";

const me = new AgentClient({ agent: "researcher" });
const budget = await me.budget(); // { windows: [{ window: "daily", limit, spent, remaining }], endpoints: [{ pattern, window, … }], … }
const receipts = await me.receipts(20);

// Wait up to 25 s for a human to decide; returns early on a decision. Waiting never pays.
const approval = await me.approval("apr_…", { wait: 25 });
// { id, status: "pending" | "approved" | "denied" | "expired" | "withdrawn", expiresAt, attempt, decidedAt, decidedBy, note }

// The task no longer needs the payment: take the approval back so a late approve cannot pay for it.
await me.withdraw("apr_…", "task cancelled"); // status "withdrawn", decidedBy "agent:researcher"
me.fetch; // the same wrapped fetch as wrapFetch()
```

Which fields you get depends on the sidecar: `endpoints`, `wait`, `approvalExpiresAt` and the decision fields need 0.6 or later; `withdraw()`, `decidedBy` and the `withdrawn` status need 0.7 or later. An older sidecar leaves the fields out and ignores `wait`; `withdraw()` against one throws.

## For humans and tooling: `AdminClient`

Needs the admin token (`.spendctl/admin.token`). Approvals, ledger, export, trace.

```ts
import { AdminClient } from "@spendctl/client";

const admin = new AdminClient({ token: process.env.SPENDCTL_ADMIN_TOKEN! });
const { pending } = await admin.pending();
// Each entry carries the terms the human is shown: payTo, network, asset, assetSymbol,
// amountAtomic (sidecar 0.4 and later), plus the reasons it was held.
await admin.approve(pending[0].id, "looks right");
const csv = await admin.export("csv", { since: "2026-01-01" });
const { text } = await admin.trace("att_…"); // agent→agent chain as text
```

Errors are thrown as `Error` with the sidecar's message; an unreachable sidecar says so and reminds you to run `spendctl start`.

## Licence

Apache-2.0. Source and issues: <https://github.com/miraistudio/spendctl-sdk>. "spendctl" is a trademark of Mirai Studio, Inc.; the licence does not cover the name.
