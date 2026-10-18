import os
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

SAMPLE_WAV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "brick-20261004_021255.wav"
)


def test_transcribe_audio_japanese():
    with open(SAMPLE_WAV_PATH, "rb") as f:
        response = client.post(
            "/audio/transcripts",
            params={"lang": "ja"},
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert data["transcript"] == "さようなら"


def test_transcribe_audio_english_default():
    with open(SAMPLE_WAV_PATH, "rb") as f:
        response = client.post(
            "/audio/transcripts",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert isinstance(data["transcript"], str)
