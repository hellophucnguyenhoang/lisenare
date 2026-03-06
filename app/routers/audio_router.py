from fastapi import APIRouter, UploadFile, Depends
from sqlmodel import Session
from phonemizer import phonemize
from phonemizer.separator import Separator

from schemas.audio import STTResponse
from app.database import get_session, Learner
from app.schemas import PronunciationAnalysisResponse, ReviewCreate
from app.services.text_service import text_service
from app.services import (
    auth_service,
    brick_service,
    review_service,
    learning_card_service,
)
import app.http_client as http_client


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
    target_brick_id: int,
    learner_file: UploadFile,
    learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session),
):
    """
    About this approach:\n
    Good: short words, very precise when we know the transcript
        because we don't have noise.
    Bad: sentences, the sound still might be understandable
        to got a right transcript but the pronunciation is not right.
    """
    target_brick = brick_service.get_brick(session, target_brick_id)
    sep = Separator(phone=" ", word="  ")
    teacher_ipa = phonemize(target_brick.target_text, separator=sep)

    learner_files = {
        "file": (
            learner_file.filename,
            await learner_file.read(),
            learner_file.content_type,
        )
    }
    learner_result = await http_client.client.post(
        "/audio/transcripts", files=learner_files
    )
    learner_ipa = phonemize(learner_result.json()["transcript"], separator=sep)
    print(f"learner_transcript:{learner_result.json()["transcript"]}")
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
