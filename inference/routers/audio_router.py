from fastapi import APIRouter, HTTPException, UploadFile, status
from inference.schemas.audio import (
    AlignmentRequest,
    AlignmentResponse,
    WordSegmentResponse,
)
from inference.services.transcription_service import (
    phoneme_recognition_service,
    preprocess_upload_file,
    transcription_service,
)

from schemas.audio import STTResponse

router = APIRouter(prefix="/audio", tags=["Audio Features"])


@router.post("/transcripts")
async def transcribe_audio(file: UploadFile) -> STTResponse:
    audio_data = await preprocess_upload_file(file)
    transcript = await transcription_service.transcribe(audio_data)
    return STTResponse(transcript=transcript)


@router.post("/phonemes")
async def get_phonemes(
    file: UploadFile | None = None, audio_url: str | None = None
) -> STTResponse:
    # Scenario A: User uploaded a raw file
    if file:
        audio_data = await preprocess_upload_file(file)

    # Scenario B: User provided a GCS or web URL instead
    elif audio_url:
        # We run this sync download in an internal executor or directly
        audio_data = phoneme_recognition_service.download_url_to_ndarray(
            audio_url
        )

    # Scenario C: User provided neither
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must provide either an uploaded 'file' or an 'audio_url'.",
        )

    phoneme_str = await phoneme_recognition_service.get_phonemes_from_array(
        audio_data
    )
    return STTResponse(transcript=phoneme_str)


@router.post("/align")
async def align_audio(body: AlignmentRequest) -> AlignmentResponse:
    """
    Align a remote audio file against an expected reference text transcript.
    Returns word tokens, frame placements, confidence scores, and timestamps in seconds.
    """
    # Run the synchronous alignment logic inside the service class
    word_segments, fps = phoneme_recognition_service.align_audio_to_transcript(
        audio_url=body.audio_url, raw_transcript=body.transcript
    )

    # Map structural WordSegments and compute secondary runtime metrics
    response_segments = []
    for segment in word_segments:
        start_sec, end_sec = segment.to_seconds(fps)
        response_segments.append(
            WordSegmentResponse(
                word=segment.word,
                start_frame=segment.start_frame,
                end_frame=segment.end_frame,
                score=segment.score,
                start_sec=round(start_sec, 3),
                end_sec=round(end_sec, 3),
            )
        )

    return AlignmentResponse(segments=response_segments, frames_per_second=fps)
