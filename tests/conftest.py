import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("OPS_DB_PATH", str(tmp_path / "ops.db"))
    monkeypatch.delenv("OPS_MCP_TOKEN", raising=False)
