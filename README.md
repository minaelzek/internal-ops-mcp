# internal-ops-mcp

[![CI](https://github.com/minaelzek/internal-ops-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/minaelzek/internal-ops-mcp/actions/workflows/ci.yml)

MCP server that connects an agent to the internal support tools of **Northline Goods**, a fictional company. It exposes a local help center and a ticket queue stored in SQLite and seeded from [`fixtures/`](fixtures/). The process does not use the network and does not need an API key.

> [!NOTE]
> Northline Goods is fictional. This repository does not talk to a real help desk.

**Maintainer:** [Mina Elzek](https://github.com/minaelzek) · **Built:** January 2026

## About

| | |
| --- | --- |
| Server name | `internal-ops` |
| Entry point | `python -m internal_ops_mcp` |
| Transport | stdio |
| Store | SQLite. Default path `data/ops.db`. Override with `OPS_DB_PATH`. |
| Auth | Optional. When `OPS_MCP_TOKEN` is set, every tool call must pass that same value as `access_token`. |
| Python | 3.11+ |

Seeding reads [`fixtures/docs/`](fixtures/docs/) and [`fixtures/tickets.json`](fixtures/tickets.json). Running it again does not duplicate rows.

## Tools

Each tool returns a JSON string. A failure returns `{"error": "..."}` with a message the agent can act on. Stack traces are written to stderr, not returned to the caller.

| Tool | Purpose |
| --- | --- |
| `search_docs` | Find help-center articles. Arguments: `query`, optional `product` (`billing`, `accounts`, `shipping`), optional `limit` (1–20, default 5). Each result has `id`, `title`, `product`, and `snippet`. |
| `get_doc` | Load one article by `doc_id`, including the full markdown `body`. |
| `list_open_tickets` | List tickets with status `open`. Optional `priority` (`low`, `medium`, `high`, `critical`) and `limit`. Each row has `id`, `title`, `priority`, `status`, and `requester`. Resolved and pending tickets are omitted. |
| `get_ticket` | Load one ticket by `ticket_id`, including `description` and `last_note`. |
| `create_ticket` | Insert a ticket with status `open`. Arguments: `title`, `body`, `priority`, `requester_email`. The email must look like `name@domain.tld`. |

The resource `ops://stats` returns JSON with `doc_count` and `open_ticket_count`.

Every tool takes an optional `access_token`. If `OPS_MCP_TOKEN` is unset, local stdio calls are allowed without it. Set the variable before sharing the server. A missing or wrong token returns an error string and does not run the tool.

## Getting started

### Prerequisites

* Python 3.11 or newer
* An MCP client that can launch a stdio server

### Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` is the runtime set (`mcp` 1.x and pydantic). `requirements-dev.txt` adds pytest.

### Run

```bash
python -m internal_ops_mcp
```

The process speaks MCP over stdin and stdout. On startup it seeds the database. If `OPS_MCP_TOKEN` is missing it still starts, and it prints a stderr note telling you to set that variable before exposing the server.

### Client configuration

Point the client at a checkout of this repository. Replace the paths below.

```json
{
  "mcpServers": {
    "internal-ops": {
      "command": "python",
      "args": ["-m", "internal_ops_mcp"],
      "cwd": "/absolute/path/to/internal-ops-mcp"
    }
  }
}
```

Leave `OPS_MCP_TOKEN` unset for local use. To require a token, add it under `env` and pass that same value as `access_token` on every tool call. Do not commit a real token.

## Tests

```bash
python -m pytest
```

Tests set `OPS_DB_PATH` to a temporary database. They do not read `data/ops.db`.

## Project layout

```text
internal_ops_mcp/    server, auth, and SQLite access
fixtures/docs/       help-center articles
fixtures/tickets.json
tests/               pytest
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The [Code of Conduct](CODE_OF_CONDUCT.md) applies to this repository.

## Security

See [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Mina Elzek
