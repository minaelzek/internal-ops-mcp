"""Access check for local stdio. No network call and no stored secret."""

import hmac
import json
import os


def require_access(access_token: str | None) -> str | None:
    """Allow the call when OPS_MCP_TOKEN is unset.

    When OPS_MCP_TOKEN is set, access_token must match it. A mismatch returns
    a JSON error string and does not raise.
    """
    expected = os.environ.get("OPS_MCP_TOKEN")
    if expected is None or expected == "":
        return None
    if not isinstance(access_token, str) or access_token == "":
        return _denied(
            "Access denied. OPS_MCP_TOKEN is set on the server, so pass access_token with the same value."
        )
    token_bytes = access_token.encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if len(token_bytes) != len(expected_bytes) or not hmac.compare_digest(token_bytes, expected_bytes):
        return _denied("Access denied. access_token does not match OPS_MCP_TOKEN.")
    return None


def _denied(message: str) -> str:
    return json.dumps({"error": message})
