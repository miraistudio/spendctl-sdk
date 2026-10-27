"""An in-process fake of the spendctl sidecar's wire protocol (gateway, agent API, admin API).

No real sidecar, wallet or network: tests exercise the client's headers, bodies and parsing.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

ADMIN = "test-admin-token"
AGENT_TOKEN = "test-agent-token"


@dataclass
class Seen:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class FakeSidecar:
    url: str
    seen: list[Seen] = field(default_factory=list)

    @property
    def last(self) -> Seen:
        return self.seen[-1]


def _handler(state: FakeSidecar):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_: Any) -> None:  # keep pytest output quiet
            pass

        def _send(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header(
                "content-type", "text/csv; charset=utf-8" if isinstance(body, str) else "application/json"
            )
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length) if length else b""
            headers = {k.lower(): v for k, v in self.headers.items()}
            state.seen.append(Seen(self.command, self.path, headers, body))
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            path = parsed.path

            # ---- gateway -------------------------------------------------------------
            if path == "/":
                target = headers.get("x-spendctl-target")
                if not target:
                    return self._send(400, {"error": "bad_request", "message": "x-spendctl-target missing"})
                if "/deny" in target:
                    return self._send(
                        402,
                        {
                            "error": "spendctl_denied",
                            "message": "Denied by policy.",
                            "attempt": "att_denied",
                            "decision": "denied",
                            "reasons": [{"code": "host_not_allowed", "message": "host not in allowlist"}],
                        },
                        {"x-spendctl-decision": "denied", "x-spendctl-attempt": "att_denied"},
                    )
                if "/hold" in target and not headers.get("x-spendctl-approval"):
                    return self._send(
                        402,
                        {
                            "error": "spendctl_approval_required",
                            "message": "Waiting for a human.",
                            "attempt": "att_held",
                            "decision": "pending_approval",
                            "amount": "$1.00",
                            "approval": "apr_1",
                        },
                        {"x-spendctl-decision": "pending_approval", "x-spendctl-attempt": "att_held"},
                    )
                if "/redirect" in target:
                    self.send_response(302)
                    self.send_header("location", target.replace("/redirect", "/paid"))
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return None
                return self._send(
                    200,
                    {
                        "paid": True,
                        "target": target,
                        "method": self.command,
                        "agent": headers.get("x-spendctl-agent"),
                        "token": headers.get("x-spendctl-token"),
                        "approval": headers.get("x-spendctl-approval"),
                        "host": headers.get("host"),
                        "content_type": headers.get("content-type"),
                        "body": body.decode(),
                    },
                    {
                        "x-spendctl-decision": "settled",
                        "x-spendctl-attempt": "att_paid",
                        "x-spendctl-amount": "$0.01",
                    },
                )

            # ---- agent API -------------------------------------------------------------
            if path.startswith("/_spendctl/agent/"):
                if headers.get("x-spendctl-token") != AGENT_TOKEN:
                    return self._send(
                        401, {"error": "spendctl_unauthorized", "message": "Agent token required."}
                    )
                if path == "/_spendctl/agent/budget":
                    return self._send(
                        200,
                        {
                            "agent": headers.get("x-spendctl-agent"),
                            "mode": "enforce",
                            "perRequest": "$0.05",
                            "requireApprovalAbove": None,
                            "onBudgetExceeded": "deny",
                            "allow": ["*"],
                            "windows": [
                                {"window": "daily", "limit": "$1.00", "spent": "$0.01", "remaining": "$0.99"}
                            ],
                        },
                    )
                if path == "/_spendctl/agent/receipts":
                    return self._send(
                        200,
                        {
                            "agent": "bot",
                            "receipts": [{"id": "att_1", "status": "settled", "limit": query.get("limit")}],
                        },
                    )
                if path.startswith("/_spendctl/agent/approvals/"):
                    approval_id = path.rsplit("/", 1)[1]
                    return self._send(
                        200, {"id": approval_id, "status": "pending", "expiresAt": "2026-01-01T00:00:00.000Z"}
                    )
                return self._send(404, {"error": "not_found", "message": "No such agent route."})

            # ---- admin API -------------------------------------------------------------
            if path.startswith("/_spendctl/admin/"):
                if headers.get("authorization") != f"Bearer {ADMIN}":
                    return self._send(
                        401, {"error": "spendctl_admin_only", "message": "Admin token required."}
                    )
                route = path[len("/_spendctl/admin/") :]
                if route == "pending":
                    return self._send(
                        200,
                        {
                            "pending": [
                                {
                                    "id": "apr_1",
                                    "agent": "bot",
                                    "host": "api.example.com",
                                    "path": "/hold",
                                    "usdMicros": "1000000",
                                    "reasons": [{"message": "above threshold"}],
                                    "expiresAt": 1_900_000_000_000,
                                }
                            ]
                        },
                    )
                if route.startswith("approvals/") and route.endswith(("/approve", "/deny")):
                    approval_id, action = route[len("approvals/") :].split("/")
                    payload = json.loads(body or b"{}")
                    return self._send(
                        200,
                        {
                            "approval": {
                                "id": approval_id,
                                "status": "approved" if action == "approve" else "denied",
                                "note": payload.get("note"),
                                "by": payload.get("by"),
                            }
                        },
                    )
                if route.startswith("ledger/") and route.endswith("/resolve"):
                    payload = json.loads(body or b"{}")
                    return self._send(
                        200, {"ok": True, "status": payload.get("status"), "txHash": payload.get("txHash")}
                    )
                if route.startswith("ledger"):
                    return self._send(
                        200,
                        {
                            "attempts": [
                                {"id": "att_1", "agent": query.get("agent"), "limit": query.get("limit")}
                            ]
                        },
                    )
                if route.startswith("export"):
                    if query.get("format") == "csv":
                        return self._send(
                            200, f"id,agent,since\natt_1,{query.get('agent', '')},{query.get('since', '')}\n"
                        )
                    return self._send(200, [{"id": "att_1", "agent": query.get("agent")}])
                if route.startswith("trace/"):
                    return self._send(200, {"root": route[len("trace/") :], "text": "bot -> sub-bot: $0.01"})
                if route == "summary":
                    return self._send(200, {"agents": [], "pending": 1, "recent": [], "dryRun": False})
                return self._send(404, {"error": "not_found", "message": "No such admin route."})

            return self._send(404, {"error": "not_found", "message": "No such route."})

        def do_GET(self) -> None:  # noqa: N802
            self._handle()

        def do_POST(self) -> None:  # noqa: N802
            self._handle()

        def do_PUT(self) -> None:  # noqa: N802
            self._handle()

        def do_DELETE(self) -> None:  # noqa: N802
            self._handle()

    return Handler


@pytest.fixture
def sidecar():
    state = FakeSidecar(url="")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SPENDCTL_URL", "SPENDCTL_AGENT", "SPENDCTL_AGENT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
