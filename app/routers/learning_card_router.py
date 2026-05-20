from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import LearningCardStats, LearningTimeSeries
from app.services import auth_service, learning_card_service

router = APIRouter(prefix="/learning-cards", tags=["Learning Cards"])


@router.get(
    "/stats",
    response_model=LearningCardStats,
    summary="Get learner statistics",
    description="Retrieve stats for a specific period. Use 'days=0' for today's data based on your timezone.",
)
def get_learning_stats(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    tz_name: Annotated[
        str,
        Query(
            description="Your IANA timezone string (e.g., 'Asia/Ho_Chi_Minh')"
        ),
    ] = "Asia/Ho_Chi_Minh",
    days: Annotated[
        int | None,
        Query(
            description="Number of days to look back calendar-based. 0 = Today (since local midnight), None = All time.",
            ge=0,
        ),
    ] = None,
):
    return learning_card_service.get_learning_stats(
        session, learner.id, tz_name, days
    )


@router.get(
    "/stats/timeseries",
    response_model=LearningTimeSeries,
)
def get_learning_timeseries(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    tz_name: str = "Asia/Ho_Chi_Minh",
    days: int | None = Query(default=None, ge=0),
    metric: str = Query(
        default="total_learning",
        description="Metric type: total_learning | reviews",
    ),
):
    result = LearningTimeSeries(
        **learning_card_service.get_learning_timeseries(
            session,
            learner.id,
            tz_name,
            days,
            metric,
        )
    )
    result.data = learning_card_service.fill_missing_days(
        result.data,
        days,
        fill_strategy="zero" if metric == "reviews" else "carry",
    )
    result.data = learning_card_service.downsample_points(result.data)
    return result
