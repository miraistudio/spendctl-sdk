# Plugins

Thin wrappers that connect an agent client to spendctl. Each directory is one plugin in both the Claude Code format (`.claude-plugin/plugin.json`, `.mcp.json`) and the Cursor format (`.cursor-plugin/plugin.json`, `mcp.json`); the skill under `skills/` is shared.

| Plugin | What it connects to | Needs |
| --- | --- | --- |
| [`spendctl-sandbox`](spendctl-sandbox) | the hosted, login-free sandbox at `https://mcp.spendctl.dev/mcp` | nothing |
| [`spendctl`](spendctl) | the sidecar you run (`npx spendctl start`) | Node.js, a `spendctl.yaml` |

The repository root is the marketplace for both: `.claude-plugin/marketplace.json` (Claude Code) and `.cursor-plugin/marketplace.json` (Cursor).

```sh
claude plugin marketplace add miraistudio/spendctl-sdk
claude plugin install spendctl-sandbox@spendctl     # try it: no sidecar, no funds
claude plugin install spendctl@spendctl             # the real thing, against your sidecar
```

Validate after editing: `claude plugin validate ./plugins/<name>` and `claude plugin validate .` for the marketplace.
