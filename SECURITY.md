# Security policy

## Reporting

Email **security@spendctl.dev**. Do not open a public issue for a vulnerability.

Include what you found, how to reproduce it, and the version (`@spendctl/client` version and, if relevant, the sidecar version from `spendctl --version`). We acknowledge within 3 business days and keep you informed until a fix ships. Please give us a reasonable window before public disclosure; we credit reporters in the changelog unless they ask otherwise.

## Scope

This repository: the clients and their published packages. The sidecar, CLI, MCP server and the hosted control plane are covered by the policy at <https://spendctl.dev/docs/security/>; the same mailbox handles both.

## What the clients hold

`@spendctl/client` has no runtime dependencies. On the agent side it carries at most a per-agent token and never a wallet key; the admin client carries the admin token you pass it. Neither is logged or persisted by the client.
