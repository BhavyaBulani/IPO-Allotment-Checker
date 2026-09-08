"""API tests for login and the auth gate.

These never touch the database: the login and verify endpoints are pure, and
the protected-route test relies on the ``require_auth`` router dependency
rejecting the request before ``get_db`` ever runs.
"""

import pytest

from api import security


@pytest.fixture(autouse=True)
def _reset_login_state():
    """The in-memory login throttle is module-global; clear it between tests."""
    security._login_attempts.clear()
    yield
    security._login_attempts.clear()


def test_login_success_returns_a_valid_token(app_client):
    res = app_client.post("/api/auth/login", json={"password": security.APP_PASSWORD})

    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert security.verify_access_token(body["token"])


def test_login_wrong_password_is_401(app_client):
    res = app_client.post("/api/auth/login", json={"password": "definitely-wrong"})

    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid password."


def test_login_missing_password_is_rejected(app_client):
    res = app_client.post("/api/auth/login", json={})

    assert res.status_code == 422


def test_login_throttle_blocks_after_max_attempts(app_client):
    for _ in range(security._LOGIN_MAX_ATTEMPTS):
        res = app_client.post("/api/auth/login", json={"password": "bad"})
        assert res.status_code == 401

    # Even the correct password is refused once the per-IP window is exhausted.
    res = app_client.post("/api/auth/login", json={"password": security.APP_PASSWORD})
    assert res.status_code == 429


def test_verify_without_token_is_401(app_client):
    res = app_client.get("/api/auth/verify")

    assert res.status_code == 401


def test_verify_with_valid_token_succeeds(app_client):
    token = security.create_access_token()
    res = app_client.get(
        "/api/auth/verify", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"authenticated": True}


def test_verify_with_garbage_token_is_401(app_client):
    res = app_client.get(
        "/api/auth/verify", headers={"Authorization": "Bearer not.a.token"}
    )

    assert res.status_code == 401


def test_protected_route_requires_a_bearer_token(app_client):
    """Client-identifying routes must 401 before any DB work happens."""
    res = app_client.get("/api/results/batch/1/summary")

    assert res.status_code == 401
