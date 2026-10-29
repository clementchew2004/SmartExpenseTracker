import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def preflight(origin: str, method: str = "POST"):
    """What a browser sends before a cross-origin JSON request."""
    return client.options(
        "/expenses",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Content-Type",
        },
    )


def test_frontend_origin_is_allowed():
    response = preflight("http://localhost:5173")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_other_websites_are_not_allowed():
    response = preflight("https://evil.example")

    assert "access-control-allow-origin" not in response.headers


def test_normal_responses_carry_the_header_for_the_frontend():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# Every method the frontend uses. PUT was missing once: the browser blocked the
# budget saves and the app could only say "can't reach the server".
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_every_method_the_app_uses_is_allowed(method):
    response = preflight("http://localhost:5173", method)

    assert response.status_code == 200
