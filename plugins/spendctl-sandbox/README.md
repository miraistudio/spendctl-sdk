# spendctl sandbox plugin

Connects Claude Code or Cursor to the login-free [spendctl](https://spendctl.dev) sandbox at `https://mcp.spendctl.dev/mcp`: a throwaway copy of the spendctl sidecar with a mock wallet, a mock x402 facilitator and two mock paid APIs. Nothing to install on your side, no account, no real funds; each sandbox expires two hours after its last call.

Tools: `sandbox_create`, `sandbox_pay`, `check_budget`, `list_receipts`, `get_policy`, `approve`. The skill walks the agent through the three presets (`default`, `strict`, `approvals`) and the hold → approve → retry loop. Docs: <https://spendctl.dev/docs/sandbox/>.

## Claude Code

```sh
claude plugin marketplace add miraistudio/spendctl-sdk
claude plugin install spendctl-sandbox@spendctl
```

Then ask: "Create a spendctl sandbox with the approvals preset and show me a held payment."

## Cursor

Add the repository as a marketplace (Dashboard → Plugins & MCPs → Add Marketplace → Import from Repo, `https://github.com/miraistudio/spendctl-sdk`) and install `spendctl-sandbox`, or copy this directory to `~/.cursor/plugins/local/spendctl-sandbox` and reload. The MCP server needs no variables.

## Layout

```text
spendctl-sandbox/
├── .claude-plugin/plugin.json          # Claude Code manifest
├── .cursor-plugin/plugin.json          # Cursor manifest
├── .mcp.json                           # Claude Code: https://mcp.spendctl.dev/mcp
├── mcp.json                            # Cursor / Agent Plugins: the same server
├── skills/spendctl-sandbox/SKILL.md    # the walkthrough
└── logo.png
```

What the sandbox records and for how long: <https://spendctl.dev/docs/privacy/>.
