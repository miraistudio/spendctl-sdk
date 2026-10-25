# Contributing

Thanks for helping. This repository holds the open-source clients for the spendctl sidecar. The sidecar, CLI and MCP server are developed elsewhere and are not open source; bug reports about them are welcome at <https://spendctl.dev/docs/> (support) or as issues here when a client is involved.

## Scope

In scope: `@spendctl/client`, future clients in other languages, plugin wrappers, and docs for the wire protocol. Out of scope: anything that would require the sidecar to change — open an issue describing the need and we take it to the sidecar team.

## Development

```sh
pnpm install
pnpm lint      # biome
pnpm build     # tsc -b
pnpm test      # vitest, runs against an in-process fake sidecar
```

Node 22.13 or newer. Tests must not need a real sidecar, a wallet or network access.

## Pull requests

- One change per PR, with a test.
- Commit messages and code comments in English; Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`) keep the changelog easy to write.
- Keep the clients dependency-free. A new runtime dependency needs a strong reason in the PR.
- Public API changes need a line in `packages/client/CHANGELOG.md` under "Unreleased".

## Licence of contributions

By submitting a contribution you agree that it is licensed under the Apache License 2.0, the same licence as the repository (inbound = outbound, Apache-2.0 §5). There is no CLA to sign.

## Releasing (maintainers)

1. Move "Unreleased" in `packages/client/CHANGELOG.md` to the new version and bump `version` in `packages/client/package.json`.
2. `pnpm clean && pnpm install --frozen-lockfile && pnpm lint && pnpm build && pnpm test`.
3. `cd packages/client && pnpm pack` and inspect the tarball (dist, README, LICENSE, NOTICE).
4. `pnpm publish --access public` from `packages/client`, then tag `client-v<version>` and push the tag.
5. Remove the "build from source" status line from the root README on the first publish.

npm trusted publishing from GitHub Actions is planned once the package exists on npm.
