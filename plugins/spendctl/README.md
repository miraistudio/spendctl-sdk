# spendctl plugin

Connects Claude Code or Cursor to the [spendctl](https://spendctl.dev) sidecar you run, so every paid HTTP call (x402, MPP) the agent makes is checked against your policy, held for approval above your thresholds, and written to the ledger. The plugin is a thin wrapper: an MCP server config that starts `spendctl mcp` (tools `pay`, `check_budget`, `list_receipts`) and a skill that tells the agent how to behave around budgets, refusals and approvals.

The sidecar itself ships on npm as `spendctl` (proprietary licence, Free tier included); only this wrapper is Apache-2.0. Nothing here holds keys, funds or the admin token.

## Before installing

```sh
npx spendctl init        # writes spendctl.yaml (agent "researcher") and .spendctl/
npx spendctl start       # the sidecar, http://127.0.0.1:8402
```

Docs: <https://spendctl.dev/docs/quickstart/>.

## Claude Code

```sh
claude plugin marketplace add miraistudio/spendctl-sdk
claude plugin install spendctl@spendctl
```

Claude Code asks for the agent name (as defined under `agents:` in `spendctl.yaml`, default `researcher`) and the sidecar URL, then runs `npx -y spendctl@latest mcp` with them. Change either later in `/config`.

## Cursor

Add the repository as a marketplace (Dashboard → Plugins & MCPs → Add Marketplace → Import from Repo, `https://github.com/miraistudio/spendctl-sdk`) and install `spendctl`, or copy this directory to `~/.cursor/plugins/local/spendctl` and reload. Set the variables `SPENDCTL_AGENT` (default `researcher`) and `SPENDCTL_URL` (default `http://127.0.0.1:8402`).

## Layout

```text
spendctl/
├── .claude-plugin/plugin.json   # Claude Code manifest (userConfig: agent, sidecar_url)
├── .cursor-plugin/plugin.json   # Cursor manifest (variables: SPENDCTL_AGENT, SPENDCTL_URL)
├── .mcp.json                    # Claude Code: npx -y spendctl@latest mcp
├── mcp.json                     # Cursor / Agent Plugins: the same server
├── skills/spendctl/SKILL.md     # how the agent should pay, retry, report
└── logo.png
```
