# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please do not open a public GitHub issue for a security problem.

Use [private vulnerability reporting](https://github.com/minaelzek/internal-ops-mcp/security/advisories/new), or email [minaaelzek@gmail.com](mailto:minaaelzek@gmail.com). Include the version, the tool you called, and a minimal way to reproduce the problem. You should get a reply within 7 days.

## Scope

This server is a local demo. It stores a fictional help center in SQLite. When `OPS_MCP_TOKEN` is set, every tool call must send that same value as `access_token`. Leave the variable unset only on your own machine.

Do not point this server at production customer data. Do not commit a real token.
