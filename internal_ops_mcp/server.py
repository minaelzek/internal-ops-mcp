"""stdio MCP server for the fictional Northline Goods support desk."""

import json
import os
import sys
import traceback
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from internal_ops_mcp.auth import require_access
from internal_ops_mcp.db import (
    PRIORITIES,
    PRODUCTS,
    collect_stats,
    create_ticket as insert_ticket,
    ensure_db,
    get_document,
    get_ticket as fetch_ticket,
    is_valid_email,
    list_open_tickets as query_open_tickets,
    search_documents,
)

mcp = FastMCP(
    "internal-ops",
    instructions=(
        "Northline Goods is a fictional company. These tools read a local help center "
        "and ticket queue. Quote the article id you used. When the server process has "
        "OPS_MCP_TOKEN set, pass that same value as access_token on every tool call."
    ),
)

Product = Literal["billing", "accounts", "shipping"]
Priority = Literal["low", "medium", "high", "critical"]
_ACCESS_TOKEN = Field(
    description=(
        "Shared secret. Required only when OPS_MCP_TOKEN is set on the server. "
        "Omit it for local stdio when that variable is unset."
    )
)


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _internal(tool_name: str) -> str:
    traceback.print_exc(file=sys.stderr)
    return _error(
        f"{tool_name} hit an internal error. Check that OPS_DB_PATH is writable and the fixtures are intact, then retry."
    )


def _check_limit(limit: int, low: int, high: int) -> str | None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        return _error(f"limit must be an integer from {low} to {high}.")
    if limit < low or limit > high:
        return _error(f"limit must be an integer from {low} to {high}.")
    return None


@mcp.tool()
def search_docs(
    query: Annotated[str, Field(description="Words to find in an article title or body.")],
    product: Annotated[
        Product | None,
        Field(description="Optional product filter: billing, accounts, or shipping."),
    ] = None,
    limit: Annotated[
        int,
        Field(ge=1, le=20, description="Maximum number of articles to return, from 1 to 20."),
    ] = 5,
    access_token: Annotated[str | None, _ACCESS_TOKEN] = None,
) -> str:
    """Search Northline help-center articles by keyword."""
    denied = require_access(access_token)
    if denied:
        return denied
    cleaned = query.strip() if isinstance(query, str) else ""
    if not cleaned:
        return _error("query is required. Pass words from the question, for example 'refund window'.")
    if product is not None and product not in PRODUCTS:
        return _error("product must be billing, accounts, or shipping. Omit it to search every product.")
    limit_error = _check_limit(limit, 1, 20)
    if limit_error:
        return limit_error
    try:
        results = search_documents(cleaned, product, limit)
    except Exception:
        return _internal("search_docs")
    return _dump({"results": results})


@mcp.tool()
def get_doc(
    doc_id: Annotated[str, Field(description="Article id returned by search_docs, such as refund-window.")],
    access_token: Annotated[str | None, _ACCESS_TOKEN] = None,
) -> str:
    """Fetch one help-center article, including its full markdown body."""
    denied = require_access(access_token)
    if denied:
        return denied
    cleaned = doc_id.strip() if isinstance(doc_id, str) else ""
    if not cleaned:
        return _error("doc_id is required. Call search_docs and use one of the returned ids.")
    try:
        document = get_document(cleaned)
    except Exception:
        return _internal("get_doc")
    if document is None:
        return _error(
            f"Help-center article {cleaned!r} was not found. Call search_docs and use a returned id."
        )
    return _dump(document)


@mcp.tool()
def list_open_tickets(
    priority: Annotated[
        Priority | None,
        Field(description="Optional priority filter: low, medium, high, or critical."),
    ] = None,
    limit: Annotated[
        int,
        Field(ge=1, le=50, description="Maximum number of open tickets to return, from 1 to 50."),
    ] = 20,
    access_token: Annotated[str | None, _ACCESS_TOKEN] = None,
) -> str:
    """List tickets that are still open. Resolved and pending tickets are omitted."""
    denied = require_access(access_token)
    if denied:
        return denied
    if priority is not None and priority not in PRIORITIES:
        return _error("priority must be low, medium, high, or critical. Omit it to list every open ticket.")
    limit_error = _check_limit(limit, 1, 50)
    if limit_error:
        return limit_error
    try:
        tickets = query_open_tickets(priority, limit)
    except Exception:
        return _internal("list_open_tickets")
    return _dump({"tickets": tickets})


@mcp.tool()
def get_ticket(
    ticket_id: Annotated[str, Field(description="Ticket id, such as TCK-1001.")],
    access_token: Annotated[str | None, _ACCESS_TOKEN] = None,
) -> str:
    """Fetch one ticket, including its description and latest note."""
    denied = require_access(access_token)
    if denied:
        return denied
    cleaned = ticket_id.strip() if isinstance(ticket_id, str) else ""
    if not cleaned:
        return _error("ticket_id is required. Call list_open_tickets or use the id returned by create_ticket.")
    try:
        ticket = fetch_ticket(cleaned)
    except Exception:
        return _internal("get_ticket")
    if ticket is None:
        return _error(
            f"Ticket {cleaned!r} was not found. Call list_open_tickets to see open ids."
        )
    return _dump(ticket)


@mcp.tool()
def create_ticket(
    title: Annotated[str, Field(description="Short summary of the customer issue.")],
    body: Annotated[str, Field(description="What happened and what the agent already checked.")],
    priority: Annotated[Priority, Field(description="Ticket priority: low, medium, high, or critical.")],
    requester_email: Annotated[str, Field(description="Email address of the person who asked for help.")],
    access_token: Annotated[str | None, _ACCESS_TOKEN] = None,
) -> str:
    """Open a new ticket. The ticket is stored with status open."""
    denied = require_access(access_token)
    if denied:
        return denied
    cleaned_title = title.strip() if isinstance(title, str) else ""
    cleaned_body = body.strip() if isinstance(body, str) else ""
    if not cleaned_title:
        return _error("title is required.")
    if len(cleaned_title) > 200:
        return _error("title must be 200 characters or fewer.")
    if not cleaned_body:
        return _error("body is required. Describe the issue so the next agent can act on it.")
    if len(cleaned_body) > 5000:
        return _error("body must be 5000 characters or fewer.")
    if priority not in PRIORITIES:
        return _error("priority must be one of low, medium, high, critical.")
    if not is_valid_email(requester_email):
        return _error("requester_email must look like name@domain.tld. Example: priya@northline.example.")
    try:
        ticket = insert_ticket(cleaned_title, cleaned_body, priority, requester_email)
    except Exception:
        return _internal("create_ticket")
    return _dump(ticket)


@mcp.resource("ops://stats", mime_type="application/json")
def ops_stats() -> str:
    """JSON counts of help-center articles and open tickets."""
    try:
        return _dump(collect_stats())
    except Exception:
        return _internal("ops_stats")


def main() -> None:
    """Seed the local database and serve the MCP server over stdio."""
    if not os.environ.get("OPS_MCP_TOKEN"):
        print(
            "internal-ops: OPS_MCP_TOKEN is unset, so local stdio calls are allowed. "
            "Operators should set OPS_MCP_TOKEN before sharing this server. "
            "When it is set, each tool call must pass the same value as access_token.",
            file=sys.stderr,
        )
    try:
        ensure_db()
    except Exception as exc:
        print(f"internal-ops: could not seed the database: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    mcp.run(transport="stdio")
