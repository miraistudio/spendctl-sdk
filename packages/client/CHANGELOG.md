# @spendctl/client

## Unreleased

## 0.1.1

- `AdminClient.pending()` returns `PendingApproval[]` (exported): the whole approval record, including the terms a retry must match on sidecar 0.4 and later (`network`, `asset`, `assetSymbol`, `amountAtomic`, `payTo`), `reasons[].code`, `attemptId`, `status` and the decision fields.

## 0.1.0

Initial public release, extracted from the spendctl monorepo.

- `wrapFetch()`: route absolute `http(s)` requests through the sidecar with `x-spendctl-target`, `x-spendctl-agent`, `x-spendctl-token`.
- `readRefusal()`: parse `spendctl_denied`, `spendctl_approval_required`, `spendctl_dry_run` bodies.
- `AgentClient`: `budget()`, `receipts()`, `approval()`.
- `AdminClient`: `pending()`, `approve()`, `deny()`, `ledger()`, `export()`, `trace()`, `summary()`, `resolve()`.
