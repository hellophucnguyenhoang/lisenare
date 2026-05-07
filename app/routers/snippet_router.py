from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
)
from sqlmodel import Session

from app.config import settings
from app.database import Learner, get_session
from app.schemas import SnippetPage, SnippetRead
from app.services import auth_service, snippet_like_service, snippet_service
from utils import file_utils

router = APIRouter(prefix="/snippets", tags=["Snippets"])


@router.get("/random")
def get_random_snippets(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    page_size: int = 5,
) -> SnippetPage:
    snippets = snippet_service.get_random_snippets(session, page_size)
    learner_id = learner.id if learner else None
    snippets = snippet_like_service.attach_reactions(
        session, snippets, learner_id
    )
    snippet_page = SnippetPage(items=snippets, total=len(snippets))
    return snippet_page


@router.get("/recommended/{session_id}")
def get_recommended_snippets(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    session_id: str,
    page_size: int = 5,
) -> SnippetPage:
    snippets = snippet_service.get_recommended_snippets(
        session, session_id, page_size
    )

    total_page = len(snippets)
    if total_page < page_size:
        additional_snippets = snippet_service.get_random_snippets(
            session, limit=page_size - total_page
        )
        snippets.extend(additional_snippets)

    learner_id = learner.id if learner else None
    snippets = snippet_like_service.attach_reactions(
        session, snippets, learner_id
    )
    snippet_page = SnippetPage(items=snippets, total=total_page)
    print(f"{snippet_page.total = }")
    return snippet_page


@router.post("", response_model=SnippetRead)
async def create_snippet(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    audio_file: Annotated[UploadFile, File()],
    snippet_content: Annotated[str, Form()],
    snippet_translation: Annotated[str | None, Form()] = None,
):
    learner_audio_path, _ = await file_utils.save_upload_file(
        file=audio_file,
        base_dir=settings.snippets_folder,
        sub_dir="learner_upload_audios",
        filename_prefix=f"ln{learner.id}rec",
    )
    snippet = snippet_service.create_snippet(
        session=session,
        content=snippet_content,
        audio_path=learner_audio_path,
        creator_id=learner.id,
        translation=snippet_translation,
    )
    return snippet
