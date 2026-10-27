from __future__ import annotations

import httpx
import pytest
import requests
from conftest import ADMIN, AGENT_TOKEN, FakeSidecar

import spendctl_sdk
from spendctl_sdk import (
    AdminClient,
    AgentClient,
    AsyncSidecarTransport,
    Refusal,
    SidecarAdapter,
    SidecarTransport,
    SpendctlError,
    async_httpx_client,
    httpx_client,
    pay,
    read_refusal,
    requests_session,
    sidecar_headers,
)

# ---- standard-library path ----------------------------------------------------------


def test_pay_routes_through_the_sidecar(sidecar: FakeSidecar) -> None:
    res = pay(
        "https://api.example.com/paid?x=1",
        method="POST",
        json={"q": "tokyo"},
        url=sidecar.url,
        agent="researcher",
        token=AGENT_TOKEN,
    )
    assert res.ok and res.status == 200
    assert res.decision == "settled" and res.amount == "$0.01" and res.attempt == "att_paid"
    assert res.refusal is None
    body = res.json()
    assert body["target"] == "https://api.example.com/paid?x=1"
    assert body["method"] == "POST" and body["agent"] == "researcher" and body["token"] == AGENT_TOKEN
    assert body["content_type"] == "application/json" and body["body"] == '{"q": "tokyo"}'
    assert sidecar.last.path == "/"
    assert sidecar.last.headers["host"] == sidecar.url.removeprefix("http://")


def test_pay_reads_env(sidecar: FakeSidecar, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPENDCTL_URL", sidecar.url + "/")
    monkeypatch.setenv("SPENDCTL_AGENT", "env-agent")
    monkeypatch.setenv("SPENDCTL_AGENT_TOKEN", AGENT_TOKEN)
    res = pay("https://api.example.com/paid")
    assert res.json()["agent"] == "env-agent"


def test_pay_denied_and_held(sidecar: FakeSidecar) -> None:
    denied = pay("https://api.example.com/deny", url=sidecar.url, agent="bot")
    assert denied.status == 402 and not denied.ok
    refusal = denied.refusal
    assert isinstance(refusal, Refusal) and refusal.denied and not refusal.needs_approval
    assert refusal.reasons[0].code == "host_not_allowed"

    held = pay("https://api.example.com/hold", url=sidecar.url, agent="bot")
    assert held.refusal is not None and held.refusal.needs_approval
    assert held.refusal.approval == "apr_1" and held.refusal.amount == "$1.00"

    retried = pay("https://api.example.com/hold", url=sidecar.url, agent="bot", approval="apr_1")
    assert retried.ok and retried.json()["approval"] == "apr_1"


def test_pay_passes_sidecar_urls_through_and_does_not_follow_redirects(sidecar: FakeSidecar) -> None:
    # A URL on the sidecar itself is sent as is: no gateway headers are added, so pass the token explicitly.
    direct = pay(
        f"{sidecar.url}/_spendctl/agent/budget",
        url=sidecar.url,
        agent="bot",
        headers={"x-spendctl-token": AGENT_TOKEN},
    )
    assert direct.ok and sidecar.last.path == "/_spendctl/agent/budget"
    assert "x-spendctl-target" not in sidecar.last.headers

    redirect = pay("https://api.example.com/redirect", url=sidecar.url)
    assert redirect.status == 302 and redirect.headers["location"].endswith("/paid")


def test_pay_unreachable_sidecar_explains() -> None:
    with pytest.raises(SpendctlError, match="spendctl start"):
        pay("https://api.example.com/paid", url="http://127.0.0.1:9", timeout=2)


def test_sidecar_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPENDCTL_AGENT", "env-agent")
    headers = sidecar_headers("https://api.example.com/x", approval="apr_9")
    assert headers == {
        "x-spendctl-target": "https://api.example.com/x",
        "x-spendctl-agent": "env-agent",
        "x-spendctl-approval": "apr_9",
    }


# ---- httpx -----------------------------------------------------------------------------


def test_httpx_transport(sidecar: FakeSidecar) -> None:
    with httpx_client(url=sidecar.url, agent="researcher", token=AGENT_TOKEN) as client:
        res = client.post("https://api.example.com/paid", json={"q": 1}, headers={"x-custom": "yes"})
        assert res.status_code == 200 and read_refusal(res) is None
        body = res.json()
        assert body["target"] == "https://api.example.com/paid" and body["agent"] == "researcher"
        assert body["body"] == '{"q":1}' or body["body"] == '{"q": 1}'
        assert sidecar.last.headers["x-custom"] == "yes"
        assert sidecar.last.headers["host"] == sidecar.url.removeprefix("http://")

        held = client.get("https://api.example.com/hold")
        refusal = read_refusal(held)
        assert refusal is not None and refusal.needs_approval and refusal.approval == "apr_1"

        passthrough = client.get(
            f"{sidecar.url}/_spendctl/agent/budget", headers={"x-spendctl-token": AGENT_TOKEN}
        )
        assert passthrough.status_code == 200 and "x-spendctl-target" not in sidecar.last.headers


async def test_httpx_async_transport(sidecar: FakeSidecar) -> None:
    async with async_httpx_client(url=sidecar.url, agent="async-bot") as client:
        res = await client.get("https://api.example.com/paid")
        assert res.status_code == 200 and res.json()["agent"] == "async-bot"
        denied = await client.get("https://api.example.com/deny")
        assert read_refusal(denied) is not None and read_refusal(denied).denied


def test_httpx_transport_wraps_a_custom_transport(sidecar: FakeSidecar) -> None:
    inner = httpx.HTTPTransport()
    transport = SidecarTransport(url=sidecar.url, agent="bot", transport=inner)
    with httpx.Client(transport=transport) as client:
        assert client.get("https://api.example.com/paid").json()["agent"] == "bot"
    assert isinstance(AsyncSidecarTransport(url=sidecar.url), httpx.AsyncBaseTransport)


# ---- requests ----------------------------------------------------------------------------


def test_requests_adapter(sidecar: FakeSidecar) -> None:
    session = requests_session(url=sidecar.url, agent="researcher", token=AGENT_TOKEN)
    res = session.post("https://api.example.com/paid", json={"q": 1}, headers={"x-custom": "yes"})
    assert res.status_code == 200 and read_refusal(res) is None
    body = res.json()
    assert body["target"] == "https://api.example.com/paid" and body["agent"] == "researcher"
    assert body["token"] == AGENT_TOKEN and body["body"] == '{"q": 1}'
    assert sidecar.last.headers["x-custom"] == "yes"
    assert sidecar.last.headers["host"] == sidecar.url.removeprefix("http://")

    denied = session.get("https://api.example.com/deny")
    refusal = read_refusal(denied)
    assert refusal is not None and refusal.denied and refusal.attempt == "att_denied"

    passthrough = session.get(
        f"{sidecar.url}/_spendctl/agent/budget", headers={"x-spendctl-token": AGENT_TOKEN}
    )
    assert passthrough.status_code == 200 and "x-spendctl-target" not in sidecar.last.headers

    bare = requests.Session()
    bare.mount("https://", SidecarAdapter(url=sidecar.url, agent="mounted"))
    assert bare.get("https://api.example.com/paid").json()["agent"] == "mounted"


# ---- agent and admin clients ----------------------------------------------------------------


def test_agent_client(sidecar: FakeSidecar) -> None:
    me = AgentClient(url=sidecar.url, agent="researcher", token=AGENT_TOKEN)
    budget = me.budget()
    assert budget["agent"] == "researcher" and budget["windows"][0]["remaining"] == "$0.99"
    receipts = me.receipts(5)
    assert receipts == [{"id": "att_1", "status": "settled", "limit": "5"}]
    assert me.approval("apr/1")["id"] == "apr%2F1"
    assert me.pay("https://api.example.com/paid").json()["agent"] == "researcher"

    anonymous = AgentClient(url=sidecar.url, agent="researcher")
    with pytest.raises(SpendctlError) as info:
        anonymous.budget()
    assert info.value.status == 401 and "Agent token required" in str(info.value)


def test_admin_client(sidecar: FakeSidecar) -> None:
    admin = AdminClient(ADMIN, url=sidecar.url)
    pending = admin.pending()
    assert pending[0]["id"] == "apr_1"
    assert admin.approve("apr_1", "looks right")["approval"] == {
        "id": "apr_1",
        "status": "approved",
        "note": "looks right",
        "by": "cli",
    }
    assert admin.deny("apr_1")["approval"]["status"] == "denied"
    assert admin.ledger(agent="bot", limit=3) == [{"id": "att_1", "agent": "bot", "limit": "3"}]
    csv = admin.export("csv", agent="bot", since="2026-01-01")
    assert csv == "id,agent,since\natt_1,bot,2026-01-01\n"
    assert admin.export("json") == [{"id": "att_1", "agent": None}]
    assert admin.trace("att_9") == {"root": "att_9", "text": "bot -> sub-bot: $0.01"}
    assert admin.summary()["pending"] == 1
    assert admin.resolve("att_9", "settled", "0xabc") == {"ok": True, "status": "settled", "txHash": "0xabc"}
    assert sidecar.last.headers["authorization"] == f"Bearer {ADMIN}"

    with pytest.raises(SpendctlError, match="Admin token required"):
        AdminClient("wrong", url=sidecar.url).pending()
    with pytest.raises(ValueError):
        AdminClient("")
    with pytest.raises(SpendctlError, match="spendctl start"):
        AdminClient(ADMIN, url="http://127.0.0.1:9", timeout=2).pending()


def test_read_refusal_ignores_non_spendctl_responses() -> None:
    assert read_refusal(httpx.Response(404, json={"error": "nope"})) is None
    assert (
        read_refusal(httpx.Response(402, headers={"x-spendctl-decision": "denied"}, text="not json")) is None
    )
    assert read_refusal(httpx.Response(200, headers={"x-spendctl-decision": "settled"}, json={})) is None


def test_package_surface() -> None:
    assert spendctl_sdk.__version__ == "0.1.0"
    assert spendctl_sdk.DEFAULT_URL == "http://127.0.0.1:8402"
    with pytest.raises(AttributeError):
        _ = spendctl_sdk.nope
