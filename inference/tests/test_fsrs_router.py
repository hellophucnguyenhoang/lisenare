from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from fsrs import Card, Rating, Scheduler

from main import app
from shared_schemas.fsrs import FSRSOptimizeRequest, FSRSOptimizeResponse

client = TestClient(app)


def _generate_dummy_logs(count: int) -> list[dict]:
    s = Scheduler()
    c = Card()
    logs = []
    t = datetime.now(timezone.utc)
    for _ in range(count):
        t += timedelta(days=1)
        c, review_log = s.review_card(c, Rating.Good, review_datetime=t)
        logs.append(review_log.to_dict())
    return logs


def test_fsrs_optimize_not_enough_logs():
    req = FSRSOptimizeRequest(review_logs=_generate_dummy_logs(50))
    res = client.post("/fsrs/optimize", json=req.model_dump(mode="json"))
    assert res.status_code == 400
    assert "Not enough logs" in res.json()["detail"]


def test_fsrs_optimize_success():
    req = FSRSOptimizeRequest(review_logs=_generate_dummy_logs(110))
    res = client.post("/fsrs/optimize", json=req.model_dump(mode="json"))
    assert res.status_code == 200
    data = FSRSOptimizeResponse.model_validate(res.json())
    assert isinstance(data.optimal_params, list)
    assert len(data.optimal_params) > 0
    assert isinstance(data.optimal_retention, float)
