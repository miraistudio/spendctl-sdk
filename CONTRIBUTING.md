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

Python client (`packages/python`, [uv](https://docs.astral.sh/uv/)):

```sh
cd packages/python
uv sync                      # creates .venv with the dev group (pytest, httpx, requests, ruff)
uv run ruff format . && uv run ruff check .
uv run pytest                # in-process fake sidecar, same rule: no network
uv build                     # wheel + sdist into dist/
```

Python 3.10 or newer; `uv.lock` is committed and CI runs with `--locked`.

## Pull requests

- One change per PR, with a test.
- Commit messages and code comments in English; Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`) keep the changelog easy to write.
- Keep the clients dependency-free. A new runtime dependency needs a strong reason in the PR.
- Public API changes need a line in the package's `CHANGELOG.md` under "Unreleased" (`packages/client/CHANGELOG.md`, `packages/python/CHANGELOG.md`).

## Licence of contributions

By submitting a contribution you agree that it is licensed under the Apache License 2.0, the same licence as the repository (inbound = outbound, Apache-2.0 §5). There is no CLA to sign.

## Releasing (maintainers)

1. Move "Unreleased" in `packages/client/CHANGELOG.md` to the new version and bump `version` in `packages/client/package.json`.
2. `pnpm clean && pnpm install --frozen-lockfile && pnpm lint && pnpm build && pnpm test`.
3. `cd packages/client && pnpm pack` and inspect the tarball (dist, README, LICENSE, NOTICE).
4. Commit, then tag and push: `git tag -a client-v<version> -m "@spendctl/client <version>" && git push origin main --follow-tags`.
5. The `Publish` workflow (`.github/workflows/publish.yml`) runs on the tag: it re-runs lint, build and tests, checks that the tag matches `package.json`, and publishes with npm trusted publishing (OIDC, provenance attached). No token and no 2FA prompt. If a check fails, nothing was published; fix and re-tag with a new version (never move a tag). If only the publish step fails with `ENEEDAUTH`, use the manual fallback below.

The trusted publisher is registered on npmjs.com under the package settings: repository `miraistudio/spendctl-sdk`, workflow `publish.yml`. Changing either name there or here breaks publishing.

Manual fallback: on `main` at the tag, `pnpm build`, then `npm publish --access public` from `packages/client` in an interactive terminal; the npm account uses a passkey, so npm opens the browser to confirm, and a non-TTY shell fails with `EOTP`. Then re-run the failed `Publish` job: it sees the version on npm, skips the publish step and finishes green. This is the normal path while [npm/cli#9969](https://github.com/npm/cli/issues/9969) is open: this repository was created after GitHub's 2026-07-15 switch to immutable OIDC subject claims, which npm's trusted publishing does not accept yet, so the publish step fails with `ENEEDAUTH`. A manual publish carries no provenance attestation.

### Python (`spendctl-sdk`)

1. Move "Unreleased" in `packages/python/CHANGELOG.md` to the new version and bump `version` in `packages/python/pyproject.toml` and `__version__` in `src/spendctl_sdk/__init__.py` (the test `test_package_surface` pins it).
2. `cd packages/python && uv sync --locked && uv run ruff format --check . && uv run ruff check . && uv run pytest && uv build`, then inspect `dist/`.
3. Commit, then tag and push: `git tag -a python-v<version> -m "spendctl-sdk <version>" && git push origin main --follow-tags`.
4. The `Publish (PyPI)` workflow (`.github/workflows/publish-python.yml`) re-runs the checks, verifies the tag matches `pyproject.toml`, builds, and publishes from the GitHub environment `pypi` with PyPI trusted publishing (OIDC, no token).

The trusted publisher is registered on pypi.org (for the first release as a *pending publisher* under the account's "Publishing" page, before the project exists): project `spendctl-sdk`, owner `miraistudio`, repository `spendctl-sdk`, workflow `publish-python.yml`, environment `pypi`. The GitHub environment `pypi` is created on first use. Changing any of these names breaks publishing.

Manual fallback: `uv publish` with a PyPI API token scoped to the project, from an interactive terminal; never store the token in the repository.
