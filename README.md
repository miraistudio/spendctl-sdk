# spendctl SDK

Open-source clients for the [spendctl](https://spendctl.dev) sidecar.

spendctl is the spend-policy control plane for AI agents: budgets, approvals, receipts and chain tracing across every wallet and every HTTP 402 protocol — enforced in a sidecar you run, never by holding your keys or funds.

This repository holds the thin clients that talk to that sidecar. They are Apache-2.0 and expose only the wire protocol. The sidecar, CLI and MCP server themselves are proprietary and ship on npm as `spendctl`; their docs live at <https://spendctl.dev/docs/>.

**Status:** `@spendctl/client` is on npm (`npm i @spendctl/client`); `spendctl-sdk` for Python is in this repository and goes to PyPI with its first tag. The sidecar they talk to ships as `spendctl` on npm; the hosted control plane is in private beta (<https://spendctl.dev>).

## Packages

| Package | Language | Registry | Status |
| --- | --- | --- | --- |
| [`@spendctl/client`](packages/client) | TypeScript, zero dependencies | npm | available |
| [`spendctl-sdk`](packages/python) | Python 3.10+, zero dependencies (optional `httpx` / `requests` integrations); import name `spendctl_sdk` | PyPI | first release pending |
| Claude Code / Cursor plugin wrappers | — | marketplaces | planned |

## How it fits together

1. Run the spendctl sidecar next to your agents: `npx spendctl init && npx spendctl start`.
2. Point agents at it — the gateway URL from any language, this `fetch` wrapper, or the MCP server.
3. Every HTTP 402 is checked against your policy, held for approval above your thresholds, and written to the ledger.

```ts
import { wrapFetch, readRefusal } from "@spendctl/client";

const pay = wrapFetch({ agent: "researcher" }); // reads SPENDCTL_URL / SPENDCTL_AGENT by default
const res = await pay("https://api.example.com/paid");
const refusal = await readRefusal(res); // undefined when paid; otherwise why spendctl refused or is waiting for a human
```

```python
from spendctl_sdk import httpx_client, read_refusal

with httpx_client(agent="researcher") as http:  # same env vars; requests_session() and pay() also exist
    res = http.get("https://api.example.com/paid")
    refusal = read_refusal(res)  # None when paid
```

Signing happens in the sidecar you run, against a wallet you own — a Coinbase CDP server wallet or your own key. spendctl never holds keys or funds.

## Wire protocol

The clients are small because the protocol is small. Anyone can write one in another language from this table.

**Gateway (agent → sidecar).** Send the request you would have sent to the seller to the sidecar's base URL (default `http://127.0.0.1:8402/`) and put the real destination in a header.

| Header | Direction | Meaning |
| --- | --- | --- |
| `x-spendctl-target` | request | Absolute URL of the seller endpoint |
| `x-spendctl-agent` | request | Agent name as defined in `spendctl.yaml` |
| `x-spendctl-token` | request | Per-agent token, when the sidecar runs with `agentAuth: token` |
| `x-spendctl-approval` | request | Approval id to attach to a retry after a human approved |
| `x-spendctl-decision` | response | Outcome of the attempt: `settled`, `denied`, `pending_approval`, `failed`, `expired` or `dry-run` |
| `x-spendctl-attempt` | response | Ledger id of the attempt |
| `x-spendctl-amount` | response | Amount paid, formatted in USD |

When the sidecar refuses, needs approval, or is in dry-run it answers `402` with a JSON body `{ error, message, attempt?, decision?, amount?, approval?, reasons? }` where `error` is one of `spendctl_denied`, `spendctl_approval_required`, `spendctl_dry_run`. A paid response is the seller's response with the `x-spendctl-*` headers added.

**Agent API (read-only, identified by `x-spendctl-agent` / `x-spendctl-token`).** `GET /_spendctl/agent/budget`, `GET /_spendctl/agent/receipts?limit=`, `GET /_spendctl/agent/approvals/:id`.

**Admin API (`Authorization: Bearer <admin token>` from `.spendctl/admin.token`).** `GET /_spendctl/admin/pending`, `POST /_spendctl/admin/approvals/:id/approve|deny`, `GET /_spendctl/admin/ledger`, `GET /_spendctl/admin/export?format=csv|json`, `GET /_spendctl/admin/trace/:id`, `GET /_spendctl/admin/summary`, `POST /_spendctl/admin/ledger/:id/resolve`.

The protocol is versioned with the sidecar; this README tracks sidecar v0.1.

## Contributing and security

Issues and pull requests are welcome here — see [CONTRIBUTING.md](CONTRIBUTING.md). Contributions are accepted under Apache-2.0 (inbound = outbound); no CLA.

Security reports for the clients or the sidecar: **security@spendctl.dev**, not a public issue. See [SECURITY.md](SECURITY.md).

## Licence and trademark

Code in this repository is licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE).

"spendctl" and the spendctl logo are trademarks of Mirai Studio, Inc. The licence does not grant permission to use the name for forks or derived services; call yours something else and say it is compatible with spendctl.

© Mirai Studio, Inc. (株式会社みらいスタジオ), Tokyo.
