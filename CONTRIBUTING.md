# Contributing

Thanks for helping improve `internal-ops-mcp`.

## Ground rules

* Be kind. The [Code of Conduct](CODE_OF_CONDUCT.md) applies to issues, pull requests, and discussions.
* Open an issue before a large change so we can agree on the approach.
* Keep pull requests focused. One behavior change per pull request is easier to review.

## Development setup

Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Tests

```bash
python -m pytest
```

Tests use a temporary database through `OPS_DB_PATH`. They do not read `data/ops.db`. GitHub Actions runs this on every pull request against Python 3.11, 3.12, and 3.13.

## Pull requests

Use the pull request template. If you change a tool name, argument, or return shape, update the README in the same pull request.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file a public issue for a vulnerability.
