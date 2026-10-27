"""httpx integration: a transport that routes absolute http(s) requests through the sidecar."""

from __future__ import annotations

from typing import Any

import httpx

from ._core import HEADER_AGENT, HEADER_TARGET, HEADER_TOKEN, _resolve, routes_through_sidecar

_HOP_HEADERS = ("host", "content-length")


def _rewrite(request: httpx.Request, cfg, content: bytes) -> httpx.Request:  # noqa: ANN001
    headers = [(k, v) for k, v in request.headers.raw if k.decode().lower() not in _HOP_HEADERS]
    headers.append((HEADER_TARGET.encode(), str(request.url).encode()))
    if cfg.agent:
        headers.append((HEADER_AGENT.encode(), cfg.agent.encode()))
    if cfg.token:
        headers.append((HEADER_TOKEN.encode(), cfg.token.encode()))
    rewritten = httpx.Request(request.method, f"{cfg.url}/", headers=headers, content=content)
    rewritten.extensions = dict(request.extensions)
    return rewritten


class SidecarTransport(httpx.BaseTransport):
    """``httpx.Client(transport=SidecarTransport(agent="researcher"))``.

    Absolute ``http(s)`` requests go to the sidecar with the real destination in
    ``x-spendctl-target``; requests already aimed at the sidecar pass through. The sidecar's
    answer (the paid response, or a 402 refusal) is returned as the response. ``transport``
    is the underlying transport (default ``httpx.HTTPTransport()``).
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        agent: str | None = None,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._cfg = _resolve(url, agent, token)
        self._inner = transport or httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if not routes_through_sidecar(str(request.url), self._cfg.url):
            return self._inner.handle_request(request)
        return self._inner.handle_request(_rewrite(request, self._cfg, request.read()))

    def close(self) -> None:
        self._inner.close()


class AsyncSidecarTransport(httpx.AsyncBaseTransport):
    """``httpx.AsyncClient(transport=AsyncSidecarTransport(agent="researcher"))``."""

    def __init__(
        self,
        *,
        url: str | None = None,
        agent: str | None = None,
        token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._cfg = _resolve(url, agent, token)
        self._inner = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not routes_through_sidecar(str(request.url), self._cfg.url):
            return await self._inner.handle_async_request(request)
        return await self._inner.handle_async_request(_rewrite(request, self._cfg, await request.aread()))

    async def aclose(self) -> None:
        await self._inner.aclose()


def httpx_client(
    *, url: str | None = None, agent: str | None = None, token: str | None = None, **kwargs: Any
) -> httpx.Client:
    """An ``httpx.Client`` whose every absolute request goes through the sidecar."""
    kwargs.setdefault("transport", SidecarTransport(url=url, agent=agent, token=token))
    return httpx.Client(**kwargs)


def async_httpx_client(
    *, url: str | None = None, agent: str | None = None, token: str | None = None, **kwargs: Any
) -> httpx.AsyncClient:
    """An ``httpx.AsyncClient`` whose every absolute request goes through the sidecar."""
    kwargs.setdefault("transport", AsyncSidecarTransport(url=url, agent=agent, token=token))
    return httpx.AsyncClient(**kwargs)
