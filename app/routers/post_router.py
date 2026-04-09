import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas.post import PostPage
from app.services import (
    auth_service,
    bandit_service,
    post_interaction_service,
    post_service,
)

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("/random", response_model=PostPage)
def list_random_posts(
    session: Annotated[Session, Depends(get_session)],
    page_size: int = 5,
):
    posts = post_service.get_random_posts(session, page_size)
    return {"items": posts, "total": len(posts)}


@router.get("/recommended", response_model=PostPage)
def get_recommended_posts(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    page_size: int = 5,
):
    learner_history = post_interaction_service.get_learner_history(
        session, learner.id
    )
    seen_post_ids = [interaction[0] for interaction in learner_history]
    candidate_posts = post_service.get_candidate_pool(
        session,
        limit=100,
        exclude_ids=seen_post_ids,
    )
    candidate_post_ids = [post.id for post in candidate_posts]
    recommended_post_ids, chosen_arm_features = bandit_service.rank_posts(
        learner_history, candidate_post_ids, top_k=page_size
    )

    # Presave the interactions with no rewards
    for post_id, feature_vector in zip(
        recommended_post_ids, chosen_arm_features
    ):
        post_interaction_service.create_or_update_interaction(
            session=session,
            learner_id=learner.id,
            post_id=post_id,
            arm_feature=json.dumps(feature_vector.tolist()),
        )

    recommended_posts = post_service.get_posts_by_ids(
        session, recommended_post_ids
    )
    return {
        "items": recommended_posts,
        "total": len(recommended_posts),
    }


@router.get("/audio/{filename}")
def get_post_audio(filename: str):
    return StreamingResponse(
        post_service.iter_audio_path(filename), media_type="audio/mp3"
    )


@router.get("/files/{file_path:path}")
async def read_file(file_path: str):
    return {"file_path": file_path}
