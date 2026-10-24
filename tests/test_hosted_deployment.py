import pytest
from fastapi.testclient import TestClient

from zerowall.api import create_app
from zerowall.hosting import Hosting
from zerowall.settings import Settings

HEADERS = {"X-ZeroWall-Director": "1", "Origin": "https://council.example"}
ACCESS_CODE = "offline-hosting-test-code-never-a-real-credential"


@pytest.fixture
def hosted_settings(tmp_path, monkeypatch):
    for key, value in {
        "ZEROWALL_MODE": "hosted",
        "ZEROWALL_PUBLIC_ORIGIN": "https://council.example",
        "ZEROWALL_DIRECTOR_TOKEN": ACCESS_CODE,
        "ZEROWALL_DATA_DIR": str(tmp_path),
        "ZEROWALL_PERSISTENT_STORAGE_CONFIRMED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    settings = Settings()
    settings.api_key = ""
    settings.openrouter_enabled = False
    settings.openrouter_api_key = ""
    settings.direct_keys = {}
    settings.tavily_api_key = ""
    return settings


@pytest.mark.parametrize(
    "origin",
    [
        "http://council.example",
        "https://*.example",
        "https://council.example/path",
        "https://user:password@council.example",
        "https://council.example?token=x",
        "https://council.example#token",
        "https://council.example:wrong",
    ],
)
def test_hosted_configuration_rejects_bad_origins(hosted_settings, monkeypatch, origin):
    monkeypatch.setenv("ZEROWALL_PUBLIC_ORIGIN", origin)
    with pytest.raises(ValueError):
        Hosting.from_env()


@pytest.mark.parametrize(
    "key,value",
    [
        ("ZEROWALL_MODE", "production-typo"),
        ("ZEROWALL_DIRECTOR_TOKEN", "short"),
        ("ZEROWALL_DIRECTOR_TOKEN", "x" * 201),
        ("ZEROWALL_DATA_DIR", "relative-data"),
        ("ZEROWALL_PERSISTENT_STORAGE_CONFIRMED", "false"),
    ],
)
def test_hosted_configuration_refuses_incomplete_setup(
    hosted_settings, monkeypatch, key, value
):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Hosting.from_env()


def test_hosted_login_is_explicit_even_behind_loopback_proxy(hosted_settings):
    app = create_app(hosted_settings, run_worker=False)
    with TestClient(
        app, base_url="https://council.example", client=("127.0.0.1", 50000)
    ) as browser:
        assert browser.get("/api/session").json() == {
            "authenticated": False,
            "local_entry": False,
        }
        assert browser.get("/api/chats/bootstrap").status_code == 401
        assert (
            browser.post("/api/session/local", json={}, headers=HEADERS).status_code
            == 403
        )
        assert "zw_session" not in browser.cookies
        assert (
            browser.post(
                "/api/session",
                json={"token": "wrong-code-that-is-long-enough-to-validate"},
                headers=HEADERS,
            ).status_code
            == 401
        )
        assert (
            browser.post(
                "/api/session", json={"token": "é" * 40}, headers=HEADERS
            ).status_code
            == 401
        )
        response = browser.post(
            "/api/session", json={"token": ACCESS_CODE}, headers=HEADERS
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert (
            "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        )
        assert ACCESS_CODE not in response.text
        assert browser.get("/api/session").json()["authenticated"] is True
        assert browser.get("/api/chats/bootstrap").status_code == 200


def test_hosted_origin_checks_work_behind_tls_termination(hosted_settings):
    app = create_app(hosted_settings, run_worker=False)
    # The proxy-to-app hop is HTTP, but the browser's real origin is HTTPS.
    with TestClient(app, base_url="http://council.example") as browser:
        response = browser.post(
            "/api/session", json={"token": ACCESS_CODE}, headers=HEADERS
        )
        assert response.status_code == 200
        for origin in (
            "https://foreign.example",
            "http://council.example",
            "http://localhost:5173",
        ):
            headers = {**HEADERS, "Origin": origin}
            assert (
                browser.post(
                    "/api/session", json={"token": ACCESS_CODE}, headers=headers
                ).status_code
                == 403
            )
        assert browser.get("https://untrusted.example/api/health").status_code == 400


def test_hosted_startup_rejects_missing_frontend(hosted_settings, tmp_path):
    hosted_settings.frontend = tmp_path / "missing-ui"
    with (
        pytest.raises(ValueError, match="Build the frontend"),
        TestClient(create_app(hosted_settings, run_worker=False)),
    ):
        pass


def test_hosted_readiness_tracks_worker_and_does_not_spend(hosted_settings):
    app = create_app(hosted_settings)
    with TestClient(app, base_url="https://council.example") as browser:
        assert browser.get("/api/ready").json() == {"status": "ready"}
        store = app.state.research.store
        with store.tx() as connection:
            assert (
                connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
                == 0
            )
            assert (
                connection.execute(
                    "SELECT COUNT(*) FROM records WHERE kind='call'"
                ).fetchone()[0]
                == 0
            )
        app.state.executor.stop.set()
        assert browser.get("/api/ready").status_code == 503
        assert browser.get("/api/health").status_code == 200


def test_hosted_session_and_state_survive_application_recreation(hosted_settings):
    app = create_app(hosted_settings)
    with TestClient(app, base_url="https://council.example") as first:
        first.post(
            "/api/session", json={"token": ACCESS_CODE}, headers=HEADERS
        ).raise_for_status()
        cookie = first.cookies.get("zw_session")
        with app.state.research.store.tx() as connection:
            app.state.research.store.set_setting(
                connection, "hosting-persistence-probe", {"saved": True}
            )
    assert not (hosted_settings.data / "director-token").exists()
    second_app = create_app(hosted_settings)
    with TestClient(second_app, base_url="https://council.example") as second:
        second.cookies.set("zw_session", cookie)
        assert second.get("/api/session").json()["authenticated"] is True
        with second_app.state.research.store.tx() as connection:
            assert second_app.state.research.store.setting(
                connection, "hosting-persistence-probe"
            ) == {"saved": True}
