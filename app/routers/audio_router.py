from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlmodel import Session

import app.http_client as http_client
from app.config import settings
from app.database import Learner, get_session
from app.schemas import (
    PronunciationAnalysisResponse,
    ReviewCreate,
    WordSegmentSecond,
)
from app.services import (
    auth_service,
    brick_memory_service,
    brick_review_service,
    brick_service,
)
from app.services.text_service import text_service
from schemas.audio import STTResponse
from utils import file_utils, text_utils

router = APIRouter(prefix="/audio", tags=["Audio"])


@router.post("/transcripts", response_model=STTResponse)
async def transcribe_audio(file: UploadFile):
    files = {
        "file": (
            file.filename,
            await file.read(),
            file.content_type,
        )
    }
    r = await http_client.get_client().post("/audio/transcripts", files=files)
    return r.json()


@router.post("/phonemes", response_model=STTResponse)
async def get_phonemes(file: UploadFile):
    files = {
        "file": (
            file.filename,
            await file.read(),
            file.content_type,
        )
    }
    r = await http_client.get_client().post("/audio/phonemes", files=files)
    return r.json()


@router.get("/forced-alignment/{audio_path:path}")
async def forced_align(
    session: Annotated[Session, Depends(get_session)], audio_path: str
) -> list[WordSegmentSecond]:
    """
    Fetches the brick text via audio path, sends it to the AI server on port 8001
    for forced alignment, and maps the results to seconds.
    """
    # Fetch the brick using the service method
    brick = brick_service.get_brick_by_audio_path(session, audio_path)

    # Build the payload for the port 8001 server
    payload = {
        "audio_url": f"{settings.asset_base_url}/{audio_path}",
        "transcript": brick.target_text,
    }

    # Request the alignment details from the port 8001 AI service
    http_response = await http_client.get_client().post(
        "/audio/align",
        json=payload,
    )
    alignment_data = http_response.json()

    # Map the fields directly back into the WordSegmentSecond list
    # Note: Port 8001 already calculates 'start_sec' and 'end_sec' for us!
    return [
        WordSegmentSecond(
            word=seg["word"],
            start_sec=seg["start_sec"],
            end_sec=seg["end_sec"],
        )
        for seg in alignment_data["segments"]
    ]


@router.post(
    "/ipa-evaluation",
    response_model=PronunciationAnalysisResponse,
    deprecated=True,
)
async def evaluate_audio(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    background_tasks: BackgroundTasks,
    target_brick_id: int,
    learner_file: UploadFile,
):
    """
    About this approach:\n
    Good: short words, very precise when we know the transcript
        because we don't have noise.\n
    Bad: sentences, the sound still might be understandable
        to got a right transcript but the pronunciation is not right.
    """
    target_brick = brick_service.get_brick(
        session, target_brick_id, learner.id
    )

    (
        learner_audio_path,
        learner_audio_bytes,
    ) = await file_utils.save_upload_file(
        file=learner_file,
        base_dir=settings.learner_audios_folder,
        sub_dir=f"learner_{learner.id}",
        filename_prefix=f"brick_{target_brick_id}",
    )

    learner_files = {
        "file": (
            learner_file.filename,
            learner_audio_bytes,
            learner_file.content_type,
        )
    }
    learner_result = await http_client.get_client().post(
        "/audio/transcripts", files=learner_files
    )

    teacher_ipa, learner_ipa, _, normalized_learner_text = (
        text_utils.analyze_phoneme(
            target_brick.target_text, learner_result.json()["transcript"]
        )
    )

    result = text_service.evaluate_ipa_pronunciation(
        teacher_ipa=teacher_ipa, learner_ipa=learner_ipa
    )
    if (
        not brick_review_service.review_exists(
            session, learner_id=learner.id, brick_id=target_brick_id
        )
        and result["accuracy_score"] >= 0.7
    ):
        is_answer_revealed_assumed = True
        review_create = ReviewCreate(
            brick_id=target_brick_id,
            is_answer_revealed=is_answer_revealed_assumed,
            first_score=result["accuracy_score"],
            learner_target_text=normalized_learner_text,
            learner_target_audio_path=learner_audio_path,
        )
        total_learner_reviews = brick_review_service.save_review(
            session=session,
            learner_id=learner.id,
            review_create=review_create,
        )
        print(f"Review saved, {total_learner_reviews=}")
        if total_learner_reviews > 100:
            interval = max(200, int(total_learner_reviews**0.5 * 20))
            if total_learner_reviews % interval == 0:
                background_tasks.add_task(
                    brick_memory_service.optimize_learner_scheduler,
                    learner.id,
                )
                print(
                    f"Triggering background optimization for learner {learner.id}"
                )

    return result


@router.post(
    "/pronunciation-evaluation", response_model=PronunciationAnalysisResponse
)
async def evaluate_pronunciation_audio(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    background_tasks: BackgroundTasks,
    target_brick_id: int,
    learner_file: UploadFile,
):
    target_brick = brick_service.get_brick(
        session, target_brick_id, learner.id
    )
    (
        learner_audio_path,
        learner_audio_bytes,
    ) = await file_utils.save_upload_file(
        file=learner_file,
        base_dir=settings.learner_audios_folder,
        sub_dir=f"learner_{learner.id}",
        filename_prefix=f"brick_{target_brick_id}",
    )

    learner_files = {
        "file": (
            learner_file.filename,
            learner_audio_bytes,
            learner_file.content_type,
        )
    }
    teacher_url = f"{settings.gcs_base_url}/{target_brick.target_audio_path}"

    learner_response = await http_client.get_client().post(
        "/audio/phonemes", files=learner_files
    )
    learner_phonemes = learner_response.json()["transcript"]

    teacher_response = await http_client.get_client().post(
        "/audio/phonemes", params={"audio_url": teacher_url}
    )
    teacher_phonemes = teacher_response.json()["transcript"]

    teacher_ipa, learner_ipa, _, normalized_learner_text = (
        text_utils.analyze_phoneme(teacher_phonemes, learner_phonemes)
    )

    result = text_service.evaluate_ipa_pronunciation(
        teacher_ipa=teacher_ipa, learner_ipa=learner_ipa
    )
    if (
        not brick_review_service.review_exists(
            session, learner_id=learner.id, brick_id=target_brick_id
        )
        and result["accuracy_score"] >= 0.7
    ):
        is_answer_revealed_assumed = True
        review_create = ReviewCreate(
            brick_id=target_brick_id,
            is_answer_revealed=is_answer_revealed_assumed,
            first_score=result["accuracy_score"],
            learner_target_text=normalized_learner_text,
            learner_target_audio_path=learner_audio_path,
        )
        total_learner_reviews = brick_review_service.save_review(
            session=session,
            learner_id=learner.id,
            review_create=review_create,
        )
        print(f"Review saved, {total_learner_reviews=}")
        if total_learner_reviews > 100:
            interval = max(200, int(total_learner_reviews**0.5 * 20))
            if total_learner_reviews % interval == 0:
                background_tasks.add_task(
                    brick_memory_service.optimize_learner_scheduler,
                    learner.id,
                )
                print(
                    f"Triggering background optimization for learner {learner.id}"
                )

    return result
