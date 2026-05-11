from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_data():
    assert 1 == 1
