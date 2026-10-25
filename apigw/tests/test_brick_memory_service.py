from unittest.mock import MagicMock, patch

from database import BrickMemory, LearnerSetting
from services import brick_memory_service
from shared_schemas.fsrs import FSRSOptimizeResponse


def test_optimize_learner_scheduler_aborts_when_under_100_logs():
    session = MagicMock()
    # Mock only 50 reviews
    session.exec.return_value.all.return_value = [
        MagicMock(fsrs_log_dict={"rating": 3}) for _ in range(50)
    ]

    with patch("services.brick_memory_service.Session") as mock_session_cls:
        mock_session_cls.return_value.__enter__.return_value = session
        with patch("http_client.get_client") as mock_get_client:
            brick_memory_service.optimize_learner_scheduler(learner_id=1)
            mock_get_client.assert_not_called()


def test_optimize_learner_scheduler_success():
    session = MagicMock()
    # Mock 120 reviews with valid logs
    reviews = [
        MagicMock(
            brick_id=i % 10,
            fsrs_log_dict={
                "card_id": 100 + (i % 10),
                "rating": 3,
                "review_datetime": "2026-10-25T00:00:00Z",
                "review_duration": None,
            },
        )
        for i in range(120)
    ]
    db_card = BrickMemory(
        learner_id=1,
        brick_id=0,
        fsrs_card_dict={
            "card_id": 100,
            "step": 0,
            "state": 1,
            "stability": 2.0,
            "difficulty": 5.0,
            "due": "2026-10-26T00:00:00Z",
            "last_review": "2026-10-25T00:00:00Z",
        },
    )

    def fake_exec(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "brickreview" in stmt_str or "brick_review" in stmt_str:
            mock_res.all.return_value = reviews
        else:
            mock_res.all.return_value = [db_card]
        return mock_res

    session.exec.side_effect = fake_exec
    setting = LearnerSetting(learner_id=1)
    session.get.return_value = setting

    valid_params = [
        0.212,
        1.2931,
        2.3065,
        8.2956,
        6.4133,
        0.8334,
        3.0194,
        0.001,
        1.8722,
        0.1666,
        0.796,
        1.4835,
        0.0614,
        0.2629,
        1.6483,
        0.6014,
        1.8729,
        0.5425,
        0.0912,
        0.0658,
        0.1542,
    ]
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = FSRSOptimizeResponse(
        optimal_params=valid_params,
        optimal_retention=0.88,
    ).model_dump(mode="json")
    mock_client.post.return_value = mock_response

    with (
        patch("services.brick_memory_service.Session") as mock_session_cls,
        patch("http_client.get_client", return_value=mock_client),
    ):
        mock_session_cls.return_value.__enter__.return_value = session
        brick_memory_service.optimize_learner_scheduler(learner_id=1)

    mock_client.post.assert_called_once()
    assert setting.fsrs_weights == valid_params
    assert setting.target_retention == 0.88
    session.commit.assert_called_once()
