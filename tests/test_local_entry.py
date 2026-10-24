import pytest
from fastapi.testclient import TestClient


def test_fresh_local_browser_opens_without_a_token_and_keeps_billing_locked(app):
    with TestClient(app, client=("127.0.0.1", 50000)) as browser:
        assert browser.get("/api/chats/bootstrap").status_code == 401
        response = browser.post(
            "/api/session/local",
            json={},
            headers={
                "X-ZeroWall-Director": "1",
                "Origin": "http://testserver",
                "Sec-Fetch-Site": "same-origin",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"authenticated": True}
        assert app.state.research.settings.director_token not in response.text
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert browser.get("/api/chats/bootstrap").status_code == 200
        bootstrap = browser.get("/api/bootstrap").json()
        assert bootstrap["live_ready"] is False
        assert bootstrap["budget"]["attempts"] == 0


@pytest.mark.parametrize(
    "client_host,headers",
    [
        ("203.0.113.9", {"X-ZeroWall-Director": "1"}),
        ("10.0.0.1", {"X-ZeroWall-Director": "1"}),
        ("127.0.0.1", {}),
        (
            "127.0.0.1",
            {"X-ZeroWall-Director": "1", "Origin": "https://foreign.example"},
        ),
        (
            "127.0.0.1",
            {"X-ZeroWall-Director": "1", "Sec-Fetch-Site": "cross-site"},
        ),
    ],
)
def test_local_entry_rejects_remote_or_cross_site_requests(app, client_host, headers):
    with TestClient(app, client=(client_host, 50000)) as browser:
        response = browser.post("/api/session/local", json={}, headers=headers)
        assert response.status_code == 403
        assert "zw_session" not in browser.cookies
        assert browser.get("/api/chats/bootstrap").status_code == 401
