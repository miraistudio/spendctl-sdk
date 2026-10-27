---
name: spendctl
description: Pay for HTTP APIs that answer 402 (x402, MPP) through the spendctl sidecar the user runs, using the `pay`, `check_budget` and `list_receipts` tools. Use when a task needs a paid API call, when a `pay` call was refused or held for approval, or when the user asks what was spent.
---

# Paying through spendctl

The user runs a spendctl sidecar (`npx spendctl start`). It holds the wallet, the budget and the allowlist; this session never sees a key. Three MCP tools talk to it:

- `pay` fetches a URL that may cost money. Free responses come back as is; a 402 is paid by the sidecar if the user's policy allows, and the response says what was paid.
- `check_budget` shows the limits for this agent, what is spent in each window and what is left.
- `list_receipts` lists the newest payment attempts: paid, refused, waiting for approval.

## How to behave

1. **Before a paid loop, check the budget once.** Call `check_budget` before calling a paid endpoint many times or when a single call may be expensive. Do not call it before every single request.
2. **Pass an `idempotencyKey` when you retry.** Reuse the same key for the same logical call (for example `"report-42"`) so a retry can never pay twice.
3. **Use `dryRun: true` to find out what would happen** without paying, when the user asks "would this be allowed?" or when you are unsure a host is allowed.
4. **A refusal is final for this session.** When `pay` answers that spendctl denied the call (budget, allowlist, recipient, price jump, first-payment cap), report the reason to the user in one sentence and stop. Do not retry, do not vary the URL or host to get around the policy, and do not ask for a bigger budget unless the user raises it.
5. **An approval request is a pause, not an error.** When `pay` returns an approval id, tell the user exactly what is waiting (URL, amount, the id) and that a human runs `spendctl approve <id>` (or approves in the dashboard or chat). Do not retry until the user says it is approved; then call `pay` again with the same `idempotencyKey`. The sidecar attaches the approval to that retry.
6. **Report spend when a task is done.** After a task with paid calls, summarise what was paid (count and total) from `list_receipts`; receipts carry the transaction hash.
7. **If the sidecar is unreachable**, say so and ask the user to run `spendctl start`. Do not fall back to calling the paid API directly.

Never ask the user for wallet keys, the admin token, or the licence key. The sidecar is designed so that you never need them.

## What the answers look like

- Paid: `HTTP 200 · paid $0.01 (settled) · receipt att_…` followed by the response body.
- Free: `HTTP 200 · no payment needed`.
- Waiting: the message names the approval id and the amount.
- Refused: the sidecar's reason (for example `host not in allowlist`, `daily budget exceeded`), with the ledger id.

Docs: https://spendctl.dev/docs/integrations/ and https://spendctl.dev/docs/policy/.
