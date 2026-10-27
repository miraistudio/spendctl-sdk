# spendctl-sdk

Zero-dependency Python client for the [spendctl](https://spendctl.dev) sidecar. Python 3.10+, typed, optional integrations for `httpx` and `requests`.

spendctl is the spend-policy control plane for AI agents: budgets, approvals, receipts and chain tracing across every wallet and every HTTP 402 protocol (x402, MPP), enforced in a sidecar you run, never by holding your keys or funds. This package is the thin client; the sidecar ships separately (`npx spendctl init && npx spendctl start`, docs at <https://spendctl.dev/docs/>).

```sh
pip install spendctl-sdk            # standard library only
pip install "spendctl-sdk[httpx]"   # + httpx transport
pip install "spendctl-sdk[requests]"
```

The import name is `spendctl_sdk` (the PyPI name `spendctl` belongs to an unrelated project).

## For agents

Every absolute `http(s)` request goes to the sidecar with the real destination in a header. If the seller answers `402`, the sidecar applies your policy, asks a human when needed, pays, and returns the paid response, or a `402` that says why it refused.

**httpx** (what the OpenAI SDK, LangChain and most agent frameworks use):

```python
from spendctl_sdk import httpx_client, read_refusal

with httpx_client(agent="researcher") as http:  # reads SPENDCTL_URL / SPENDCTL_AGENT by default
    res = http.get("https://api.example.com/paid")
    if res.status_code == 200:
        print(res.headers["x-spendctl-amount"])  # "$0.01"
    elif refusal := read_refusal(res):
        if refusal.needs_approval:
            # A human was asked. Poll AgentClient.approval(refusal.approval), then retry with
            # headers={"x-spendctl-approval": refusal.approval}.
            ...
```

`async_httpx_client(...)` is the `httpx.AsyncClient` version. To keep your own client configuration, mount the transport instead: `httpx.Client(transport=SidecarTransport(agent="researcher"))` / `AsyncSidecarTransport`.

**requests:**

```python
from spendctl_sdk import requests_session, read_refusal

http = requests_session(agent="researcher")
res = http.post("https://api.example.com/paid", json={"q": "tokyo"})
refusal = read_refusal(res)  # None when paid; otherwise why spendctl refused or is waiting for a human
```

Or mount `SidecarAdapter(agent=...)` on an existing `requests.Session` for `http://` and `https://`.

**Standard library only:**

```python
from spendctl_sdk import pay

res = pay("https://api.example.com/paid", agent="researcher")
res.status, res.amount, res.decision, res.json(), res.refusal
```

`pay()` follows no redirects and raises `SpendctlError` only when the sidecar cannot be reached; a refusal is a normal response with `res.refusal` set.

Options, each falling back to an environment variable:

| Option | Env var | Default |
| --- | --- | --- |
| `url` | `SPENDCTL_URL` | `http://127.0.0.1:8402` |
| `agent` | `SPENDCTL_AGENT` | — |
| `token` | `SPENDCTL_AGENT_TOKEN` | — (only when the sidecar runs with `agentAuth: token`) |

Requests that already point at the sidecar, or that are not absolute `http(s)` URLs, go through untouched. The agent side never holds a wallet key or the admin token. `sidecar_headers(target, ...)` returns the three headers for any other HTTP library.

`read_refusal(response)` accepts `httpx.Response`, `requests.Response` and the `SidecarResponse` from `pay()`; it returns a `Refusal` (`error`, `message`, `attempt`, `decision`, `amount`, `approval`, `reasons`; properties `denied`, `needs_approval`, `dry_run`) or `None` when the response was paid or did not come from spendctl.

## For agents: `AgentClient`

Read-only view of the agent's own budget and receipts.

```python
from spendctl_sdk import AgentClient

me = AgentClient(agent="researcher")
me.budget()  # {"windows": [{"window": "daily", "limit": ..., "spent": ..., "remaining": ...}], ...}
me.receipts(20)
me.approval("apr_…")  # {"id", "status", "expiresAt"}
me.pay("https://api.example.com/paid")  # pay() with this client's url, agent and token
```

## For humans and tooling: `AdminClient`

Needs the admin token (`.spendctl/admin.token`). Approvals, ledger, export, trace.

```python
import os
from spendctl_sdk import AdminClient

admin = AdminClient(os.environ["SPENDCTL_ADMIN_TOKEN"])
for approval in admin.pending():
    admin.approve(approval["id"], "looks right")
csv = admin.export("csv", since="2026-01-01")
admin.trace("att_…")["text"]  # agent-to-agent chain as text
```

Errors are raised as `SpendctlError` with the sidecar's message (`.status`, `.body`); an unreachable sidecar says so and reminds you to run `spendctl start`.

## Wire protocol

The client is small because the protocol is small; it is documented in the repository README so that anyone can write one in another language.

## Licence

Apache-2.0. Source and issues: <https://github.com/miraistudio/spendctl-sdk>. "spendctl" is a trademark of Mirai Studio, Inc.; the licence does not cover the name.
