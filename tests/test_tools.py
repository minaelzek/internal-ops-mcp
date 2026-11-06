import json

from internal_ops_mcp.db import ensure_db
from internal_ops_mcp.server import (
    create_ticket,
    get_doc,
    get_ticket,
    list_open_tickets,
    mcp,
    ops_stats,
    search_docs,
)


def _load(payload: str) -> dict:
    return json.loads(payload)


def test_search_docs_finds_known_article():
    found = _load(search_docs(query="refund window"))
    assert "error" not in found
    match = next(row for row in found["results"] if row["id"] == "refund-window")
    assert match["title"] == "Refund window"
    assert match["product"] == "billing"
    assert "14 calendar days" in match["snippet"]
    assert set(match) == {"id", "title", "product", "snippet"}

    billing = _load(search_docs(query="refund window", product="billing", limit=5))
    assert [row["id"] for row in billing["results"]] == ["refund-window"]

    shipping = _load(search_docs(query="refund window", product="shipping"))
    assert shipping["results"] == []

    too_wide = _load(search_docs(query="refund window", limit=0))
    assert "limit" in too_wide["error"]


def test_get_doc_unknown_id_is_not_found():
    missing = _load(get_doc(doc_id="no-such-article"))
    assert "not found" in missing["error"].lower()
    assert "Traceback" not in missing["error"]

    article = _load(get_doc(doc_id="refund-window"))
    assert article["id"] == "refund-window"
    assert article["body"].startswith("# Refund window")
    assert "14 calendar days" in article["body"]


def test_list_open_tickets_excludes_resolved():
    payload = _load(list_open_tickets())
    ids = [ticket["id"] for ticket in payload["tickets"]]
    assert "TCK-1001" in ids
    assert "TCK-1005" not in ids
    assert "TCK-1006" not in ids
    assert "TCK-1007" not in ids
    assert ids == sorted(ids)
    assert all(ticket["status"] == "open" for ticket in payload["tickets"])
    assert all(set(ticket) == {"id", "title", "priority", "status", "requester"} for ticket in payload["tickets"])

    critical = _load(list_open_tickets(priority="critical"))
    assert [ticket["id"] for ticket in critical["tickets"]] == ["TCK-1003"]


def test_create_ticket_persists_and_rejects_bad_email():
    before = _load(list_open_tickets())["tickets"]
    rejected = _load(
        create_ticket(
            title="Bad contact",
            body="This should not be stored.",
            priority="low",
            requester_email="not-an-email",
        )
    )
    assert "email" in rejected["error"].lower()
    assert "Traceback" not in rejected["error"]
    after_reject = _load(list_open_tickets())["tickets"]
    assert [ticket["id"] for ticket in after_reject] == [ticket["id"] for ticket in before]

    created = _load(
        create_ticket(
            title="Need a copy of invoice INV-441",
            body="The customer cannot download the March invoice PDF.",
            priority="medium",
            requester_email="case@northline.example",
        )
    )
    assert "error" not in created
    assert created["status"] == "open"
    assert created["requester"] == "case@northline.example"
    assert created["description"] == "The customer cannot download the March invoice PDF."
    assert created["last_note"] is None

    stored = _load(get_ticket(ticket_id=created["id"]))
    assert stored["title"] == created["title"]
    assert stored["description"] == created["description"]
    assert stored["priority"] == "medium"
    assert stored["status"] == "open"

    listed = [ticket["id"] for ticket in _load(list_open_tickets())["tickets"]]
    assert created["id"] in listed


def test_stats_resource_counts():
    ensure_db()
    ensure_db()
    stats = _load(ops_stats())
    assert stats == {"doc_count": 8, "open_ticket_count": 4}

    create_ticket(
        title="Address hold",
        body="Please hold the parcel at the depot.",
        priority="low",
        requester_email="hold@northline.example",
    )
    updated = _load(ops_stats())
    assert updated["doc_count"] == 8
    assert updated["open_ticket_count"] == 5

    resources = mcp._resource_manager.list_resources()
    uris = {str(resource.uri) for resource in resources}
    assert "ops://stats" in uris


def test_access_token_when_env_is_set(monkeypatch):
    monkeypatch.setenv("OPS_MCP_TOKEN", "ops-test-token")

    wrong = _load(search_docs(query="refund window", access_token="wrong-token"))
    assert "access_token" in wrong["error"]
    assert "Traceback" not in wrong["error"]
    assert "results" not in wrong

    missing = _load(get_doc(doc_id="refund-window"))
    assert "error" in missing
    assert "OPS_MCP_TOKEN" in missing["error"]

    listed = _load(list_open_tickets(access_token="wrong-token"))
    assert "error" in listed

    right = _load(search_docs(query="refund window", access_token="ops-test-token"))
    assert [row["id"] for row in right["results"]] == ["refund-window"]

    article = _load(get_doc(doc_id="refund-window", access_token="ops-test-token"))
    assert "14 calendar days" in article["body"]

    created = _load(
        create_ticket(
            title="Token-gated ticket",
            body="Created only after the matching token was sent.",
            priority="low",
            requester_email="gated@northline.example",
            access_token="ops-test-token",
        )
    )
    assert created["status"] == "open"
    fetched = _load(get_ticket(ticket_id=created["id"], access_token="ops-test-token"))
    assert fetched["id"] == created["id"]
