from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from phonemizer import phonemize
from phonemizer.separator import Separator
from sqlmodel import Session

import app.http_client as http_client
from app.database import Learner, get_session
from app.schemas import PronunciationAnalysisResponse, ReviewCreate
from app.services import (
    auth_service,
    brick_service,
    learning_card_service,
    review_service,
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
    r = await http_client.client.post("/audio/transcripts", files=files)
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
    r = await http_client.client.post("/audio/phonemes", files=files)
    return r.json()


@router.post("/ipa-evaluation", response_model=PronunciationAnalysisResponse)
async def evaluate_audio(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
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
        base_dir="learner_audio",
        sub_dir=f"user_{learner.id}",
        filename_prefix=f"brick_{target_brick_id}",
    )

    learner_files = {
        "file": (
            learner_file.filename,
            learner_audio_bytes,
            learner_file.content_type,
        )
    }
    learner_result = await http_client.client.post(
        "/audio/transcripts", files=learner_files
    )

    sep = Separator(phone=" ", word="  ")
    teacher_text, learner_text = text_utils.normalize_for_pronunciation(
        target_brick.target_text, learner_result.json()["transcript"]
    )
    teacher_ipa = phonemize(teacher_text, separator=sep)
    learner_ipa = phonemize(learner_text, separator=sep)
    print(f"{teacher_text = }")
    print(f"{learner_text = }")
    print(f"teacher_ipa:{teacher_ipa}")
    print(f"learner_ipa:{learner_ipa}")

    result = text_service.evaluate_ipa_pronunciation(
        teacher_ipa=teacher_ipa, learner_ipa=learner_ipa
    )
    if (
        not review_service.review_exists(
            session, learner_id=learner.id, brick_id=target_brick_id
        )
        and result["accuracy_score"] >= 0.7
    ):
        is_answer_revealed_assumed = True
        review_create = ReviewCreate(
            brick_id=target_brick_id,
            is_answer_revealed=is_answer_revealed_assumed,
            first_score=result["accuracy_score"],
            user_target_text=learner_text,
            user_target_audio_uri=learner_audio_path,
        )
        review_service.save_review(
            session=session,
            learner_id=learner.id,
            review_create=review_create,
        )
        learning_card_service.update_learning_card(
            session=session,
            learner_id=learner.id,
            brick_id=target_brick_id,
            score=result["accuracy_score"],
            is_answer_revealed=is_answer_revealed_assumed,
        )
        print("Learn saved!")

    return result
