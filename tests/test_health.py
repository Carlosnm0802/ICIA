from fastapi.testclient import TestClient

from app.core.config import APP_NAME
from app.main import app

client = TestClient(app)


def test_home_shows_icia() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert APP_NAME in response.text


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": APP_NAME}
