from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app as main_app
from inference.main import app as inference_app


def test_inference_to_speech_success():
    client = TestClient(inference_app)
    # Mock text_service.generate_tts_wav to return fake WAV bytes
    fake_wav_bytes = b"RIFFfake_wav_data_content"
    with patch(
        "inference.routers.text_router.text_service.generate_tts_wav",
        return_value=fake_wav_bytes,
    ) as mock_tts:
        response = client.post(
            "/text/to-speech",
            json={"text": "Hello world", "voice": "af_heart"},
        )
        assert response.status_code == 200
        assert response.content == fake_wav_bytes
        assert response.headers["content-type"] == "audio/wav"
        mock_tts.assert_called_once_with(text="Hello world", voice="af_heart")


def test_inference_to_speech_exceeds_max_length():
    client = TestClient(inference_app)
    max_chars = settings.brick_max_words * settings.brick_avg_word_len
    long_text = "a" * (max_chars + 1)
    response = client.post(
        "/text/to-speech",
        json={"text": long_text},
    )
    # Should be rejected due to length limit
    assert response.status_code in (400, 422)


def test_app_to_speech_success():
    client = TestClient(main_app)
    fake_wav = b"RIFFmocked_proxy_audio"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_wav

    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp

    with (
        patch("app.http_client.get_client", return_value=mock_client),
        patch(
            "utils.file_utils.save_file_bytes",
            return_value="brick-audios/tts-test.wav",
        ) as mock_save,
    ):
        response = client.post(
            "/text/to-speech",
            json={"text": "How are you today?"},
        )
        assert response.status_code == 200
        assert response.json() == "brick-audios/tts-test.wav"
        mock_client.post.assert_called_once_with(
            "/text/to-speech",
            json={"text": "How are you today?", "voice": "af_heart"},
        )
        mock_save.assert_called_once_with(
            content=fake_wav,
            base_dir=settings.brick_audios_folder,
            filename_prefix="tts",
            extension=".wav",
        )


def test_inference_to_speech_japanese_voice():
    client = TestClient(inference_app)
    fake_wav_bytes = b"RIFFfake_japanese_wav"
    with patch(
        "inference.routers.text_router.text_service.generate_tts_wav",
        return_value=fake_wav_bytes,
    ) as mock_tts:
        response = client.post(
            "/text/to-speech",
            json={"text": "こんにちは", "voice": "jf_alpha"},
        )
        assert response.status_code == 200
        assert response.content == fake_wav_bytes
        mock_tts.assert_called_once_with(text="こんにちは", voice="jf_alpha")


def test_app_to_speech_exceeds_max_length():
    client = TestClient(main_app)
    max_chars = settings.brick_max_words * settings.brick_avg_word_len
    long_text = "x" * (max_chars + 1)
    response = client.post(
        "/text/to-speech",
        json={"text": long_text},
    )
    assert response.status_code in (400, 422)


def test_generate_tts_wav_string():
    import numpy as np

    from inference.services.text_service import text_service

    dummy_audio = np.zeros(2400, dtype=np.float32)
    fake_generator = [("hello", "h_e_l_l_o", dummy_audio)]
    mock_pipeline = MagicMock(return_value=fake_generator)

    with patch.object(text_service, "tts_pipeline_en", mock_pipeline):
        result = text_service.generate_tts_wav("hello", voice="af_heart")
        mock_pipeline.assert_called_once_with("hello", voice="af_heart")
        assert isinstance(result, bytes)
        assert result.startswith(b"RIFF")


def test_generate_tts_wav_list_of_strings():
    import numpy as np

    from inference.services.text_service import text_service

    dummy_audio_1 = np.zeros(2400, dtype=np.float32)
    dummy_audio_2 = np.ones(2400, dtype=np.float32)
    fake_generator = [
        ("hello", "h_e_l_l_o", dummy_audio_1),
        ("world", "w_o_r_l_d", dummy_audio_2),
    ]
    mock_pipeline = MagicMock(return_value=fake_generator)

    with patch.object(text_service, "tts_pipeline_en", mock_pipeline):
        result = text_service.generate_tts_wav(
            ["hello", "world"], voice="af_heart"
        )
        mock_pipeline.assert_called_once_with(
            ["hello", "world"], voice="af_heart"
        )
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], bytes) and result[0].startswith(b"RIFF")
        assert isinstance(result[1], bytes) and result[1].startswith(b"RIFF")


def test_generate_tts_wav_empty():
    from inference.services.text_service import text_service

    assert text_service.generate_tts_wav("") == b""
    assert text_service.generate_tts_wav([]) == []
