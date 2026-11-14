# Changelog

## 0.2.1

- `read_refusal()` (and `SidecarResponse.refusal`) returns only a body the sidecar wrote. A seller's answer to a paid request passes through the sidecar with the `x-spendctl-*` headers on it, so a seller that took the payment and answered an error shaped like a refusal (`{"error": "spendctl_approval_required", …}`) was returned as one, and a caller would read "nothing was paid". The body's `error` now has to start with `spendctl_`, and once `x-spendctl-decision` says a payment was signed (`reserved`, `settled`, `unknown`, `failed`) only the body the sidecar writes for that decision counts (`spendctl_upstream_error`, or `spendctl_signing_failed` under `failed`). On any other error response, read `x-spendctl-decision`: `unknown` means the payment was sent and its outcome is not confirmed.

## 0.2.0

Catches up with sidecar 0.6 and 0.7, like `@spendctl/client` 0.2.0. Against an older sidecar the new fields are absent, `wait` is ignored and `withdraw()` raises.

- `AgentClient.approval(id, wait=...)`: long-poll for a decision (the sidecar caps `wait` at 25 s; waiting never pays). The HTTP timeout of that call is raised to `wait` plus 5 s. The returned dict adds `attempt`, `decidedAt`, `note` (0.6) and `decidedBy` (0.7: `cli`, `admin-api`, `review-link`, `timeout` or `agent:<name>`); `status` can be `withdrawn`.
- `AgentClient.withdraw(id, note=None)`: the agent takes back its own pending approval when the task no longer needs the payment, so a late approve cannot pay for it (0.7). Returns the approval, now `withdrawn`. Raises `SpendctlError` with status 409, and the outcome in `.body["approval"]`, if a human already decided or it expired.
- `Refusal` adds `approval_expires_at` (0.6), `hint`, the echoed `idempotency_key` and `request_id` (0.5), and the dry-run `would_be`.
- `AgentClient.budget()` documents `endpoints`, the `endpointBudget` windows (0.6).
- Agent API errors that only carry `not_found` now say which approval is unknown instead of `spendctl: not_found`.

## 0.1.0

First release, tracking sidecar 0.3: `pay()` (standard library), `SidecarTransport` / `AsyncSidecarTransport` / `httpx_client` / `async_httpx_client` for httpx, `SidecarAdapter` / `requests_session` for requests, `read_refusal()`, `sidecar_headers()`, `AgentClient` (budget, receipts, approval, pay) and `AdminClient` (pending, approve, deny, ledger, export, trace, summary, resolve). No runtime dependencies; Python 3.10+.
