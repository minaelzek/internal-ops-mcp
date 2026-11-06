"""SQLite store seeded from local fixtures. Seeding is safe to run more than once."""

import json
import os
import re
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "ops.db"
DOCS_DIR = PROJECT_ROOT / "fixtures" / "docs"
TICKETS_PATH = PROJECT_ROOT / "fixtures" / "tickets.json"

PRODUCTS = ("billing", "accounts", "shipping")
PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("open", "pending", "resolved")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,}$")


def is_valid_email(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 254:
        return False
    return EMAIL_RE.fullmatch(value) is not None


def db_path() -> Path:
    raw = os.environ.get("OPS_DB_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_DB


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    _seed(conn)
    conn.commit()
    return conn


def ensure_db() -> None:
    conn = connect()
    conn.close()


def search_documents(query: str, product: str | None, limit: int) -> list[dict]:
    terms = [term for term in query.split() if term]
    where = []
    params: list[object] = []
    if product is not None:
        where.append("product = ?")
        params.append(product)
    for term in terms:
        where.append("(lower(title) LIKE ? ESCAPE '\\' OR lower(body) LIKE ? ESCAPE '\\')")
        pattern = _like(term)
        params.extend([pattern, pattern])
    sql = (
        "SELECT id, title, product, body FROM docs "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY id LIMIT ?"
    )
    params.append(limit)
    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "product": row["product"],
            "snippet": _snippet(row["body"], terms),
        }
        for row in rows
    ]


def get_document(doc_id: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, title, product, body FROM docs WHERE id = ?",
            (doc_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "product": row["product"],
        "body": row["body"],
    }


def list_open_tickets(priority: str | None, limit: int) -> list[dict]:
    sql = (
        "SELECT id, title, priority, status, requester FROM tickets "
        "WHERE status = 'open' "
    )
    params: list[object] = []
    if priority is not None:
        sql += "AND priority = ? "
        params.append(priority)
    sql += "ORDER BY id LIMIT ?"
    params.append(limit)
    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "priority": row["priority"],
            "status": row["status"],
            "requester": row["requester"],
        }
        for row in rows
    ]


def get_ticket(ticket_id: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT id, title, description, priority, status, requester, last_note
            FROM tickets WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _ticket_dict(row)


def create_ticket(title: str, body: str, priority: str, requester_email: str) -> dict:
    conn = connect()
    try:
        new_id = _next_ticket_id(conn)
        conn.execute(
            """
            INSERT INTO tickets (id, title, description, priority, status, requester, last_note)
            VALUES (?, ?, ?, ?, 'open', ?, NULL)
            """,
            (new_id, title, body, priority, requester_email),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, title, description, priority, status, requester, last_note
            FROM tickets WHERE id = ?
            """,
            (new_id,),
        ).fetchone()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _ticket_dict(row)


def collect_stats() -> dict:
    conn = connect()
    try:
        doc_count = conn.execute("SELECT COUNT(*) AS n FROM docs").fetchone()["n"]
        open_count = conn.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE status = 'open'"
        ).fetchone()["n"]
    finally:
        conn.close()
    return {"doc_count": doc_count, "open_ticket_count": open_count}


def _ticket_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],
        "status": row["status"],
        "requester": row["requester"],
        "last_note": row["last_note"],
    }


def _next_ticket_id(conn: sqlite3.Connection) -> str:
    rows = conn.execute("SELECT id FROM tickets").fetchall()
    highest = 1000
    for row in rows:
        ticket_id = row["id"]
        if isinstance(ticket_id, str) and ticket_id.startswith("TCK-"):
            suffix = ticket_id[4:]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
    return f"TCK-{highest + 1}"


def _like(term: str) -> str:
    escaped = term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _snippet(body: str, terms: list[str]) -> str:
    text = " ".join(body.split())
    haystack = text.lower()
    index = -1
    for term in terms:
        index = haystack.find(term.lower())
        if index >= 0:
            break
    if index < 0:
        clipped = text[:160]
        return clipped if len(text) <= 160 else clipped + "..."
    start = max(0, index - 50)
    end = min(len(text), index + 110)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS docs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            product TEXT NOT NULL,
            body TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            requester TEXT NOT NULL,
            last_note TEXT
        );
        """
    )


def _seed(conn: sqlite3.Connection) -> None:
    docs = _load_docs()
    tickets = _load_tickets()
    conn.executemany(
        """
        INSERT INTO docs (id, title, product, body) VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            product = excluded.product,
            body = excluded.body
        """,
        [(doc["id"], doc["title"], doc["product"], doc["body"]) for doc in docs],
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO tickets
            (id, title, description, priority, status, requester, last_note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                ticket["id"],
                ticket["title"],
                ticket["description"],
                ticket["priority"],
                ticket["status"],
                ticket["requester"],
                ticket["last_note"],
            )
            for ticket in tickets
        ],
    )


def _load_docs() -> list[dict]:
    paths = sorted(DOCS_DIR.glob("*.md"))
    if len(paths) < 6:
        raise RuntimeError(f"Expected at least 6 articles in {DOCS_DIR}, found {len(paths)}.")
    loaded = []
    seen: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8").lstrip("\ufeff").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            raise RuntimeError(f"{path.name} is missing frontmatter.")
        _marker, front, body = text.split("---", 2)
        meta: dict[str, str] = {}
        for line in front.strip().splitlines():
            if not line.strip():
                continue
            if ":" not in line:
                raise RuntimeError(f"{path.name} has a bad frontmatter line: {line}")
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        for key in ("id", "title", "product"):
            if not meta.get(key):
                raise RuntimeError(f"{path.name} frontmatter needs {key}.")
        if meta["product"] not in PRODUCTS:
            raise RuntimeError(f"{path.name} product must be one of {', '.join(PRODUCTS)}.")
        if meta["id"] in seen:
            raise RuntimeError(f"Duplicate doc id {meta['id']}.")
        seen.add(meta["id"])
        article = body.strip()
        loaded.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "product": meta["product"],
                "body": article + "\n",
            }
        )
    return loaded


def _load_tickets() -> list[dict]:
    if not TICKETS_PATH.is_file():
        raise RuntimeError(f"Missing ticket fixture {TICKETS_PATH}.")
    data = json.loads(TICKETS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) < 6:
        raise RuntimeError("fixtures/tickets.json must contain at least 6 tickets.")
    loaded = []
    seen: set[str] = set()
    required = ("id", "title", "description", "priority", "status", "requester", "last_note")
    for index, ticket in enumerate(data):
        if not isinstance(ticket, dict):
            raise RuntimeError(f"Ticket at index {index} must be an object.")
        for key in required:
            if key not in ticket:
                raise RuntimeError(f"Ticket at index {index} is missing {key}.")
        ticket_id = ticket["id"]
        if not isinstance(ticket_id, str) or not ticket_id.startswith("TCK-"):
            raise RuntimeError(f"Ticket id {ticket_id!r} must look like TCK-1001.")
        if ticket_id in seen:
            raise RuntimeError(f"Duplicate ticket id {ticket_id}.")
        seen.add(ticket_id)
        if ticket["priority"] not in PRIORITIES:
            raise RuntimeError(f"{ticket_id} has an unknown priority.")
        if ticket["status"] not in STATUSES:
            raise RuntimeError(f"{ticket_id} has an unknown status.")
        if not is_valid_email(ticket["requester"]):
            raise RuntimeError(f"{ticket_id} requester is not an email address.")
        if not str(ticket["title"]).strip() or not str(ticket["description"]).strip():
            raise RuntimeError(f"{ticket_id} needs a title and a description.")
        loaded.append(
            {
                "id": ticket_id,
                "title": str(ticket["title"]).strip(),
                "description": str(ticket["description"]).strip(),
                "priority": ticket["priority"],
                "status": ticket["status"],
                "requester": ticket["requester"],
                "last_note": None if ticket["last_note"] is None else str(ticket["last_note"]),
            }
        )
    return loaded
