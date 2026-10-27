---
name: spendctl-sandbox
description: Try spendctl's spend policy for AI agents (budgets, allowlists, human approvals, receipts) against mock paid APIs in a login-free sandbox, using the sandbox_create, sandbox_pay, check_budget, list_receipts, get_policy and approve tools. Use when the user wants to see what spendctl does, test a policy preset, or walk through a refusal and an approval without real funds.
---

# The spendctl sandbox

A hosted, throwaway copy of the spendctl sidecar: a mock wallet, a mock x402 facilitator and two mock paid APIs. Nothing here moves real money, and each sandbox disappears two hours after its last call. The tools are the same ones an agent uses with a real sidecar, plus `sandbox_create` and `approve`.

## Walkthrough

1. **Create one sandbox per conversation** with `sandbox_create`. The result gives the `sandbox_id` every other tool needs and lists the paid endpoints and the preset's limits. Pick the preset for what the user wants to see:
   - `default`: comfortable caps, both endpoints allowed; shows the happy path.
   - `strict`: tiny per-request and daily caps, weather only; shows refusals (an allowlist refusal for the search API, a budget refusal on the fourth weather call).
   - `approvals`: payments at or above the threshold wait for a human; shows the hold → approve → retry loop.
2. **Pay** with `sandbox_pay` using an endpoint the create result listed (for example `https://weather.sandbox.spendctl.dev/weather?city=Kyoto`). Give each logical call an `idempotencyKey` so a retry never pays twice. Use `dryRun: true` to show the decision without paying.
3. **Read the outcome.** A paid call reports the amount and a receipt id; a refusal names the rule that fired; a hold returns an approval id.
4. **For a hold**, explain to the user that in the real product a human approves (`spendctl approve <id>`, the dashboard, or Slack). In the sandbox you play the approver: call `approve` with the approval id (or `decision: "deny"` to show a denial), then call `sandbox_pay` again with the same URL, the same `idempotencyKey` and `approvalId` set, which completes the held payment.
5. **Explain with evidence.** `check_budget` shows what each window has left, `list_receipts` the attempts so far, `get_policy` the sandbox's `spendctl.yaml`. Quote them instead of guessing why something was refused.

## Rules

- Never try to get around a refusal by changing the URL; show the user why it was refused and, if useful, create another sandbox with a different preset.
- Do not create sandboxes in a loop; one serves the whole conversation. Creation is rate-limited per address.
- Keep the user's expectations straight: the sandbox demonstrates policy enforcement; real payments need the sidecar the user runs (`npx spendctl init && npx spendctl start`) and the `spendctl` plugin.

Docs: https://spendctl.dev/docs/sandbox/ and https://spendctl.dev/docs/policy/.
