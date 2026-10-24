import pytest
from zerowall.settings import Settings
from zerowall.api import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def app(tmp_path):
    settings = Settings(tmp_path)
    settings.api_key = "test-key-never-network"
    settings.openrouter_enabled = (
        True  # Exercise historical provider compatibility with transport doubles.
    )
    settings.direct_keys = {}  # A test fixture never inherits real direct-provider credentials.
    settings.direct_free_confirmed = False
    settings.tavily_api_key = (
        ""  # Offline tests never inherit the real search credential.
    )
    settings.native_research_providers = set()
    return create_app(settings, run_worker=False)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        client.headers["X-ZeroWall-Director"] = "1"
        client.post(
            "/api/session", json={"token": app.state.research.settings.director_token}
        )
        yield client


@pytest.fixture
def pg():
    """Only an explicitly supplied disposable database; never use app secrets."""
    import os
    from zerowall.postgres import PostgresStore

    dsn = os.environ.get("ZEROWALL_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Dedicated Postgres integration database not configured")
    store = PostgresStore(dsn)
    with store.tx() as c:
        for table in (
            "records",
            "events",
            "reservations",
            "jobs",
            "settings",
            "idempotency",
            "blob_files",
            "source_fts",
        ):
            c.execute("DELETE FROM " + table)
    yield store
    store.close()
