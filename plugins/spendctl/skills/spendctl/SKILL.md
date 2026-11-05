---
name: spendctl
description: Pay for HTTP APIs that answer 402 (x402, MPP) through the spendctl sidecar the user runs, using the `pay`, `await_approval`, `withdraw_approval`, `check_budget` and `list_receipts` tools. Use when a task needs a paid API call, when a `pay` call was refused or held for approval, or when the user asks what was spent.
---

# Paying through spendctl

The user runs a spendctl sidecar (`npx spendctl start`). It holds the wallet, the budget and the allowlist; this session never sees a key. Five MCP tools talk to it:

- `pay` fetches a URL that may cost money. Free responses come back as is; a 402 is paid by the sidecar if the user's policy allows, and the response says what was paid.
- `await_approval` waits for a human to decide a payment that `pay` reported as held, without paying again.
- `withdraw_approval` takes a held payment back when the task no longer needs it, so a late approval pays nothing.
- `check_budget` shows the limits for this agent, what is spent in each window and what is left.
- `list_receipts` lists the newest payment attempts: paid, refused, waiting for approval, withdrawn.

## How to behave

1. **Before a paid loop, check the budget once.** Call `check_budget` before calling a paid endpoint many times or when a single call may be expensive. Do not call it before every single request.
2. **Pass an `idempotencyKey` when you retry.** Reuse the same key for the same logical call (for example `"report-42"`) so a retry can never pay twice.
3. **Use `dryRun: true` to find out what would happen** without paying, when the user asks "would this be allowed?" or when you are unsure a host is allowed.
4. **A refusal is final for this session.** When `pay` answers that spendctl denied the call (budget, allowlist, recipient, price jump, first-payment cap), report the reason to the user in one sentence and stop. Do not retry, do not vary the URL or host to get around the policy, and do not ask for a bigger budget unless the user raises it.
5. **An approval request is a pause, not an error.** When `pay` returns an approval id, nothing was paid. Tell the user exactly what is waiting (URL, amount, the id, the deadline) and that a human runs `spendctl approve <id>` (or approves through the review link or in the dashboard). Then call `await_approval` with the id: it waits up to 25 seconds per call and answers `pending` (call it again, or report that the payment is waiting), `approved`, `denied`, `expired` or `withdrawn`. Once it is `approved`, call `pay` again with the same URL, the same `idempotencyKey` and `approvalId` set to the id; that completes the payment. `denied` and `expired` are final, like a refusal.
6. **Withdraw what the task no longer needs.** If the user cancels the task, or the plan changes so the held payment is no longer needed, call `withdraw_approval` with the id and a short note (for example `"task cancelled"`). A late approval then pays nothing. Do not withdraw a payment the task still needs, and never withdraw to get around a denial; if it is needed after all, a new `pay` call opens a fresh approval.
7. **Report spend when a task is done.** After a task with paid calls, summarise what was paid (count and total) from `list_receipts`; receipts carry the transaction hash.
8. **If the sidecar is unreachable**, say so and ask the user to run `spendctl start`. Do not fall back to calling the paid API directly.

Never ask the user for wallet keys, the admin token, or the licence key. The sidecar is designed so that you never need them.

## What the answers look like

- Paid: `HTTP 200 · paid $0.01 (settled) · receipt att_…` followed by the response body.
- Free: `HTTP 200 · no payment needed`.
- Waiting: the message names the approval id, the amount and the decision deadline.
- Withdrawn: `await_approval` and `withdraw_approval` say the approval was withdrawn by this agent and nothing was paid.
- Refused: the sidecar's reason (for example `host not in allowlist`, `daily budget exceeded`), with the ledger id.

Docs: https://spendctl.dev/docs/integrations/ and https://spendctl.dev/docs/policy/.
