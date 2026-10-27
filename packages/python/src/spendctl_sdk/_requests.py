"""requests integration: an adapter that routes absolute http(s) requests through the sidecar."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter

from ._core import HEADER_AGENT, HEADER_TARGET, HEADER_TOKEN, _resolve, routes_through_sidecar


class SidecarAdapter(HTTPAdapter):
    """Mount on ``http://`` and ``https://``: ``session.mount("https://", SidecarAdapter(agent=...))``.

    Absolute requests are sent to the sidecar with the real destination in ``x-spendctl-target``;
    requests already aimed at the sidecar pass through. The sidecar's answer (the paid response,
    or a 402 refusal) is returned as the response.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        agent: str | None = None,
        token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._cfg = _resolve(url, agent, token)

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        target = request.url or ""
        if not routes_through_sidecar(target, self._cfg.url):
            return super().send(request, **kwargs)
        rewritten = request.copy()
        rewritten.url = f"{self._cfg.url}/"
        rewritten.headers.pop("Host", None)
        rewritten.headers[HEADER_TARGET] = target
        if self._cfg.agent:
            rewritten.headers[HEADER_AGENT] = self._cfg.agent
        if self._cfg.token:
            rewritten.headers[HEADER_TOKEN] = self._cfg.token
        return super().send(rewritten, **kwargs)


def requests_session(
    *, url: str | None = None, agent: str | None = None, token: str | None = None, **kwargs: Any
) -> requests.Session:
    """A ``requests.Session`` whose every absolute request goes through the sidecar."""
    session = requests.Session()
    adapter = SidecarAdapter(url=url, agent=agent, token=token, **kwargs)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
