"""Wire protocol of the spendctl sidecar, standard library only."""

from __future__ import annotations

import json as _json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8402"

HEADER_TARGET = "x-spendctl-target"
HEADER_AGENT = "x-spendctl-agent"
HEADER_TOKEN = "x-spendctl-token"
HEADER_APPROVAL = "x-spendctl-approval"
HEADER_DECISION = "x-spendctl-decision"
HEADER_ATTEMPT = "x-spendctl-attempt"
HEADER_AMOUNT = "x-spendctl-amount"


class SpendctlError(Exception):
    """The sidecar answered an error, or could not be reached."""

    def __init__(self, message: str, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass(frozen=True)
class Reason:
    code: str
    message: str


@dataclass(frozen=True)
class Refusal:
    """Body the sidecar returns when it refuses, needs approval, or is in dry-run."""

    error: str
    """``spendctl_denied``, ``spendctl_approval_required`` or ``spendctl_dry_run``."""
    message: str
    attempt: str | None = None
    decision: str | None = None
    amount: str | None = None
    approval: str | None = None
    """Approval id to poll with :meth:`AgentClient.approval` and to send back as ``x-spendctl-approval``."""
    reasons: tuple[Reason, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def needs_approval(self) -> bool:
        return self.error == "spendctl_approval_required"

    @property
    def denied(self) -> bool:
        return self.error == "spendctl_denied"

    @property
    def dry_run(self) -> bool:
        return self.error == "spendctl_dry_run"

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> Refusal:
        reasons = tuple(
            Reason(code=str(r.get("code", "")), message=str(r.get("message", "")))
            for r in body.get("reasons") or ()
            if isinstance(r, Mapping)
        )
        return cls(
            error=str(body.get("error", "")),
            message=str(body.get("message", "")),
            attempt=_opt_str(body.get("attempt")),
            decision=_opt_str(body.get("decision")),
            amount=_opt_str(body.get("amount")),
            approval=_opt_str(body.get("approval")),
            reasons=reasons,
            raw=dict(body),
        )


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class _Config:
    url: str
    agent: str | None
    token: str | None


def _resolve(url: str | None, agent: str | None, token: str | None) -> _Config:
    base = (url or os.environ.get("SPENDCTL_URL") or DEFAULT_URL).rstrip("/")
    return _Config(
        url=base,
        agent=agent or os.environ.get("SPENDCTL_AGENT") or None,
        token=token or os.environ.get("SPENDCTL_AGENT_TOKEN") or None,
    )


def sidecar_headers(
    target: str,
    *,
    agent: str | None = None,
    token: str | None = None,
    approval: str | None = None,
) -> dict[str, str]:
    """Headers that send a request for ``target`` through the sidecar.

    Useful with any HTTP library: send the request to the sidecar's base URL
    (``/``) with these headers added, and the sidecar forwards it to ``target``.
    ``agent`` and ``token`` fall back to ``SPENDCTL_AGENT`` and ``SPENDCTL_AGENT_TOKEN``.
    """
    cfg = _resolve(None, agent, token)
    headers = {HEADER_TARGET: target}
    if cfg.agent:
        headers[HEADER_AGENT] = cfg.agent
    if cfg.token:
        headers[HEADER_TOKEN] = cfg.token
    if approval:
        headers[HEADER_APPROVAL] = approval
    return headers


def routes_through_sidecar(url: str, sidecar_url: str) -> bool:
    """True when ``url`` is an absolute http(s) URL that is not the sidecar itself."""
    lowered = url.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return False
    return not (url == sidecar_url or url.startswith(sidecar_url + "/"))


# ---- a small response type for the standard-library path ---------------------------


class _CaseInsensitiveHeaders(Mapping[str, str]):
    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = {k.lower(): v for k, v in items}

    def __getitem__(self, key: str) -> str:
        return self._items[key.lower()]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


@dataclass
class SidecarResponse:
    """What :func:`pay` returns: the seller's response as relayed by the sidecar, or a refusal."""

    status: int
    headers: Mapping[str, str]
    content: bytes
    url: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return _json.loads(self.content or b"null")

    @property
    def decision(self) -> str | None:
        """``settled``, ``denied``, ``pending_approval``, ``failed``, ``expired`` or ``dry-run``."""
        return self.headers.get(HEADER_DECISION)

    @property
    def attempt(self) -> str | None:
        return self.headers.get(HEADER_ATTEMPT)

    @property
    def amount(self) -> str | None:
        """Amount paid, formatted in USD, when the sidecar paid."""
        return self.headers.get(HEADER_AMOUNT)

    @property
    def refusal(self) -> Refusal | None:
        return read_refusal(self)

    # requests/httpx-compatible alias so one helper works for all three response types
    @property
    def status_code(self) -> int:
        return self.status


def read_refusal(response: Any) -> Refusal | None:
    """Returns the sidecar's refusal if ``response`` is one, else ``None``.

    Works with :class:`SidecarResponse`, ``httpx.Response`` and ``requests.Response``:
    anything with ``status_code`` (or ``status``), case-insensitive ``headers`` and
    ``json()``. A paid response, or one that did not come from spendctl, gives ``None``.
    """
    status = getattr(response, "status_code", None)
    if status is None:
        status = getattr(response, "status", None)
    if status is None or 200 <= int(status) < 400:
        return None
    headers = getattr(response, "headers", None) or {}
    decision = _header(headers, HEADER_DECISION)
    content_type = _header(headers, "content-type") or ""
    if decision is None or "json" not in content_type:
        return None
    try:
        body = response.json()
    except Exception:  # noqa: BLE001 - any parse failure means "not a refusal we understand"
        return None
    if not isinstance(body, Mapping) or "error" not in body:
        return None
    return Refusal.from_dict(body)


def _header(headers: Any, name: str) -> str | None:
    try:
        value = headers.get(name)
    except AttributeError:
        return None
    if value is None and hasattr(headers, "items"):
        lowered = name.lower()
        for key, candidate in headers.items():
            if str(key).lower() == lowered:
                return str(candidate)
    return None if value is None else str(value)


# ---- standard-library transport -----------------------------------------------------


class _NoRaise(urllib.request.HTTPErrorProcessor):
    """Return 4xx/5xx responses instead of raising: a 402 is an answer, not an error."""

    def http_response(self, request, response):  # noqa: ANN001, ANN201
        return response

    https_response = http_response


def _opener() -> urllib.request.OpenerDirector:
    # No redirect handler on purpose: a redirect from the seller comes back to the caller,
    # who can send the next request through the sidecar again (same as fetch's redirect: "manual").
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
        _NoRaise(),
    ):
        opener.add_handler(handler)
    return opener


def _send(
    url: str,
    *,
    method: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout: float,
    sidecar_url: str,
) -> SidecarResponse:
    request = urllib.request.Request(url, data=body, method=method.upper())
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with _opener().open(request, timeout=timeout) as response:
            content = response.read()
            return SidecarResponse(
                status=int(response.status),
                headers=_CaseInsensitiveHeaders(list(response.headers.items())),
                content=content,
                url=url,
            )
    except urllib.error.URLError as error:
        raise SpendctlError(
            f"Cannot reach the spendctl sidecar at {sidecar_url} ({error.reason}). "
            "Is `spendctl start` running?"
        ) from error


def pay(
    target: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    data: bytes | str | None = None,
    json: Any = None,
    approval: str | None = None,
    timeout: float = 30.0,
    url: str | None = None,
    agent: str | None = None,
    token: str | None = None,
) -> SidecarResponse:
    """Send one request for ``target`` through the sidecar, with the standard library only.

    If the seller answers 402, the sidecar applies your policy, asks a human when needed,
    pays, and returns the paid response; otherwise it returns a 402 explaining why it refused
    (``response.refusal``). ``approval`` attaches an approval id to a retry. ``url``,
    ``agent`` and ``token`` fall back to ``SPENDCTL_URL``, ``SPENDCTL_AGENT`` and
    ``SPENDCTL_AGENT_TOKEN``. URLs that already point at the sidecar go through untouched.
    """
    cfg = _resolve(url, agent, token)
    merged: dict[str, str] = dict(headers or {})
    body: bytes | None
    if json is not None:
        body = _json.dumps(json).encode("utf-8")
        merged.setdefault("content-type", "application/json")
    elif isinstance(data, str):
        body = data.encode("utf-8")
    else:
        body = data
    if not routes_through_sidecar(target, cfg.url):
        return _send(target, method=method, headers=merged, body=body, timeout=timeout, sidecar_url=cfg.url)
    merged.update(sidecar_headers(target, agent=cfg.agent, token=cfg.token, approval=approval))
    return _send(
        f"{cfg.url}/", method=method, headers=merged, body=body, timeout=timeout, sidecar_url=cfg.url
    )


# ---- agent and admin APIs -----------------------------------------------------------


def _parse(response: SidecarResponse) -> Any:
    content_type = response.headers.get("content-type") or ""
    if "json" in content_type:
        try:
            return response.json()
        except ValueError:
            return response.text
    return response.text


def _raise_for(response: SidecarResponse, what: str) -> None:
    if response.ok:
        return
    body = _parse(response)
    detail = None
    if isinstance(body, Mapping):
        detail = body.get("message") or body.get("error")
    raise SpendctlError(
        f"spendctl: {detail or f'{what} failed with {response.status}'}", response.status, body
    )


class AgentClient:
    """Read-only view of one agent's budget, receipts and approvals (no admin token needed)."""

    def __init__(
        self,
        *,
        url: str | None = None,
        agent: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._cfg = _resolve(url, agent, token)
        self._timeout = timeout

    @property
    def url(self) -> str:
        return self._cfg.url

    def pay(self, target: str, **kwargs: Any) -> SidecarResponse:
        """:func:`pay` with this client's url, agent and token."""
        kwargs.setdefault("url", self._cfg.url)
        kwargs.setdefault("agent", self._cfg.agent)
        kwargs.setdefault("token", self._cfg.token)
        return pay(target, **kwargs)

    def _get(self, path: str) -> Any:
        headers: dict[str, str] = {}
        if self._cfg.agent:
            headers[HEADER_AGENT] = self._cfg.agent
        if self._cfg.token:
            headers[HEADER_TOKEN] = self._cfg.token
        response = _send(
            f"{self._cfg.url}/_spendctl/agent/{path}",
            method="GET",
            headers=headers,
            body=None,
            timeout=self._timeout,
            sidecar_url=self._cfg.url,
        )
        _raise_for(response, path)
        return _parse(response)

    def budget(self) -> dict[str, Any]:
        """``{agent, mode, perRequest, requireApprovalAbove, onBudgetExceeded, allow, windows}``."""
        return self._get("budget")

    def receipts(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(self._get(f"receipts?limit={int(limit)}").get("receipts", []))

    def approval(self, approval_id: str) -> dict[str, Any]:
        """``{id, status, expiresAt}`` for an approval the sidecar asked a human for."""
        return self._get(f"approvals/{urllib.parse.quote(approval_id, safe='')}")


class AdminClient:
    """Approvals, ledger, export and trace, with the admin token from ``.spendctl/admin.token``."""

    def __init__(self, token: str, *, url: str | None = None, timeout: float = 30.0) -> None:
        if not token:
            raise ValueError("AdminClient needs the admin token (.spendctl/admin.token)")
        self._url = (url or os.environ.get("SPENDCTL_URL") or DEFAULT_URL).rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def url(self) -> str:
        return self._url

    def request(self, path: str, *, method: str = "GET", json: Any = None) -> Any:
        """Raw call to ``/_spendctl/admin/<path>``; returns the parsed JSON or the text body."""
        headers = {"authorization": f"Bearer {self._token}", "content-type": "application/json"}
        body = None if json is None else _json.dumps(json).encode("utf-8")
        response = _send(
            f"{self._url}/_spendctl/admin/{path}",
            method=method,
            headers=headers,
            body=body,
            timeout=self._timeout,
            sidecar_url=self._url,
        )
        _raise_for(response, path)
        return _parse(response)

    def pending(self) -> list[dict[str, Any]]:
        return list(self.request("pending").get("pending", []))

    def approve(self, approval_id: str, note: str | None = None) -> dict[str, Any]:
        return self.request(
            f"approvals/{urllib.parse.quote(approval_id, safe='')}/approve",
            method="POST",
            json={"note": note, "by": "cli"},
        )

    def deny(self, approval_id: str, note: str | None = None) -> dict[str, Any]:
        return self.request(
            f"approvals/{urllib.parse.quote(approval_id, safe='')}/deny",
            method="POST",
            json={"note": note, "by": "cli"},
        )

    def ledger(self, *, agent: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        query: dict[str, str] = {}
        if agent:
            query["agent"] = agent
        if limit:
            query["limit"] = str(int(limit))
        return list(self.request(f"ledger?{urllib.parse.urlencode(query)}").get("attempts", []))

    def export(self, format: str, *, agent: str | None = None, since: str | None = None) -> Any:
        """CSV text for ``format="csv"``, a list for ``format="json"``."""
        query = {"format": format}
        if agent:
            query["agent"] = agent
        if since:
            query["since"] = since
        return self.request(f"export?{urllib.parse.urlencode(query)}")

    def trace(self, attempt_id: str) -> dict[str, Any]:
        """``{root, text}``: the agent-to-agent payment chain as text."""
        return self.request(f"trace/{urllib.parse.quote(attempt_id, safe='')}")

    def summary(self) -> dict[str, Any]:
        return self.request("summary")

    def resolve(self, attempt_id: str, status: str, tx_hash: str | None = None) -> Any:
        """Mark an ``unknown`` attempt ``settled`` or ``failed`` after checking the chain yourself."""
        return self.request(
            f"ledger/{urllib.parse.quote(attempt_id, safe='')}/resolve",
            method="POST",
            json={"status": status, "txHash": tx_hash},
        )
