from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def preflight(origin: str):
    """What a browser sends before a cross-origin JSON POST."""
    return client.options(
        "/expenses",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
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
