# @spendctl/client

## Unreleased

## 0.2.0

Catches up with sidecar 0.6 and 0.7. Against an older sidecar the new fields are absent, `wait` is ignored and `withdraw()` throws.

- `AgentClient.approval(id, { wait, signal })`: long-poll for a decision (the sidecar caps `wait` at 25 s; waiting never pays). Returns `AgentApproval` (exported): `id`, `status`, `expiresAt`, plus `attempt`, `decidedAt`, `note` (0.6) and `decidedBy` (0.7: `cli`, `admin-api`, `review-link`, `timeout` or `agent:<name>`).
- `AgentClient.withdraw(id, note?)`: the agent takes back its own pending approval when the task no longer needs the payment, so a late approve cannot pay for it (0.7). Throws with the sidecar's message if a human already decided or it expired.
- `ApprovalStatus` (exported) adds `withdrawn`, distinct from a human's `denied`; `PendingApproval.status` uses it.
- `Budget.endpoints`: the `endpointBudget` windows (`EndpointWindow`: `pattern`, `window`, `limit`, `spent`, `remaining`; 0.6). `BudgetWindow` is exported.
- `SpendctlRefusal` types `approvalExpiresAt` (0.6), `hint`, the echoed `idempotencyKey` and `requestId` (0.5), and the dry-run fields `dryRun` and `wouldBe`.
- Type change: `approval()` used to return `{ id; status: string; expiresAt }`. `status` is now the `ApprovalStatus` union, so comparing it with a string outside the union no longer type-checks.
- Agent API errors that only carry `not_found` now say which approval is unknown instead of `spendctl … failed with 404`.

## 0.1.1

- `AdminClient.pending()` returns `PendingApproval[]` (exported): the whole approval record, including the terms a retry must match on sidecar 0.4 and later (`network`, `asset`, `assetSymbol`, `amountAtomic`, `payTo`), `reasons[].code`, `attemptId`, `status` and the decision fields.

## 0.1.0

Initial public release, extracted from the spendctl monorepo.

- `wrapFetch()`: route absolute `http(s)` requests through the sidecar with `x-spendctl-target`, `x-spendctl-agent`, `x-spendctl-token`.
- `readRefusal()`: parse `spendctl_denied`, `spendctl_approval_required`, `spendctl_dry_run` bodies.
- `AgentClient`: `budget()`, `receipts()`, `approval()`.
- `AdminClient`: `pending()`, `approve()`, `deny()`, `ledger()`, `export()`, `trace()`, `summary()`, `resolve()`.
