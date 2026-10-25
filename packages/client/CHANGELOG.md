# @spendctl/client

## Unreleased

## 0.1.0

Initial public release, extracted from the spendctl monorepo.

- `wrapFetch()`: route absolute `http(s)` requests through the sidecar with `x-spendctl-target`, `x-spendctl-agent`, `x-spendctl-token`.
- `readRefusal()`: parse `spendctl_denied`, `spendctl_approval_required`, `spendctl_dry_run` bodies.
- `AgentClient`: `budget()`, `receipts()`, `approval()`.
- `AdminClient`: `pending()`, `approve()`, `deny()`, `ledger()`, `export()`, `trace()`, `summary()`, `resolve()`.
