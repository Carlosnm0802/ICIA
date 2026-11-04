from fastapi.testclient import TestClient

from app.core.config import APP_NAME
from app.main import app

client = TestClient(app)


def test_home_redirects_to_login() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": APP_NAME}
