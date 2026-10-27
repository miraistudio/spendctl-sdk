"""Python client for the spendctl sidecar.

The sidecar runs next to your agents and applies your spend policy to every HTTP 402
(x402, MPP): budgets, allowlists, human approvals, receipts. This package only speaks
its wire protocol; the agent side never holds a wallet key or the admin token.

- :func:`pay` sends one request through the sidecar with the standard library only.
- :class:`SidecarTransport` / :func:`httpx_client` route an ``httpx`` client through it.
- :class:`SidecarAdapter` / :func:`requests_session` do the same for ``requests``.
- :func:`read_refusal` explains a 402 the sidecar answered instead of the seller.
- :class:`AgentClient` reads the agent's own budget, receipts and approvals.
- :class:`AdminClient` approves, denies, lists the ledger and exports (admin token).

Configuration falls back to the environment: ``SPENDCTL_URL`` (default
``http://127.0.0.1:8402``), ``SPENDCTL_AGENT`` and ``SPENDCTL_AGENT_TOKEN``.
"""

from ._core import (
    DEFAULT_URL,
    AdminClient,
    AgentClient,
    Reason,
    Refusal,
    SidecarResponse,
    SpendctlError,
    pay,
    read_refusal,
    sidecar_headers,
)

__all__ = [
    "DEFAULT_URL",
    "AdminClient",
    "AgentClient",
    "AsyncSidecarTransport",
    "Reason",
    "Refusal",
    "SidecarAdapter",
    "SidecarResponse",
    "SidecarTransport",
    "SpendctlError",
    "async_httpx_client",
    "httpx_client",
    "pay",
    "read_refusal",
    "requests_session",
    "sidecar_headers",
]

__version__ = "0.1.0"


def __getattr__(name: str):  # noqa: ANN202 - lazy optional integrations
    # httpx and requests are optional: import their adapters only when asked for.
    if name in {"SidecarTransport", "AsyncSidecarTransport", "httpx_client", "async_httpx_client"}:
        from . import _httpx

        return getattr(_httpx, name)
    if name in {"SidecarAdapter", "requests_session"}:
        from . import _requests

        return getattr(_requests, name)
    raise AttributeError(f"module 'spendctl_sdk' has no attribute {name!r}")
