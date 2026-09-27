import asyncio
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import UploadFile

from constants import (
    ASSETS_DIR,
    GENERATED_AUDIOS_DIR,
    LEARNER_AUDIOS_DIR,
)
from utils.file_utils import (
    save_file_bytes,
    save_file_bytes_to_cloud,
    save_upload_file,
    save_upload_file_to_cloud,
)


def test_constants():
    assert ASSETS_DIR == Path("lisenare-assets")
    assert LEARNER_AUDIOS_DIR == Path("learner-audios")
    assert GENERATED_AUDIOS_DIR == Path("generated-audios")


def test_save_file_bytes(tmp_path):
    with patch("utils.file_utils.ASSETS_DIR", tmp_path):
        data = b"RIFFfake_wav_data"
        rel_path = save_file_bytes(
            content=data,
            relative_path=GENERATED_AUDIOS_DIR,
            filename_prefix="tts",
            extension=".wav",
        )

        assert rel_path.startswith("generated-audios/tts-")
        assert rel_path.endswith(".wav")

        full_path = tmp_path / rel_path
        assert full_path.exists()
        assert full_path.read_bytes() == data


def test_save_file_bytes_collision_handling(tmp_path):
    with patch("utils.file_utils.ASSETS_DIR", tmp_path):
        data = b"some_bytes"
        rel_path1 = save_file_bytes(
            content=data,
            relative_path="test-folder",
            filename_prefix="sample",
            extension=".wav",
        )
        rel_path2 = save_file_bytes(
            content=data,
            relative_path="test-folder",
            filename_prefix="sample",
            extension=".wav",
        )

        assert rel_path1 != rel_path2
        assert (tmp_path / rel_path1).exists()
        assert (tmp_path / rel_path2).exists()


def test_save_upload_file(tmp_path):
    async def _test():
        with patch("utils.file_utils.ASSETS_DIR", tmp_path):
            file_content = b"audio_upload_content"
            upload = UploadFile(
                file=io.BytesIO(file_content),
                filename="user_recording.mp3",
            )

            rel_path, returned_bytes = await save_upload_file(
                file=upload,
                relative_path=LEARNER_AUDIOS_DIR / "learner-42",
                filename_prefix="brick",
            )

            assert rel_path.startswith("learner-audios/learner-42/brick-")
            assert rel_path.endswith(".mp3")
            assert returned_bytes == file_content

            full_path = tmp_path / rel_path
            assert full_path.exists()
            assert full_path.read_bytes() == file_content

    asyncio.run(_test())


def test_save_file_bytes_to_cloud():
    mock_upload = MagicMock()
    with patch("cloud_storage_client.upload_bytes", mock_upload):
        data = b"RIFFcloud_wav_data"
        s3_key = save_file_bytes_to_cloud(
            content=data,
            relative_path=GENERATED_AUDIOS_DIR,
            filename_prefix="tts",
            extension=".wav",
        )

        assert s3_key.startswith("generated-audios/tts-")
        assert s3_key.endswith(".wav")

        mock_upload.assert_called_once_with(
            content=data,
            s3_key=s3_key,
            content_type="audio/wav",
        )


def test_save_upload_file_to_cloud():
    async def _test():
        mock_upload = MagicMock()
        with patch("cloud_storage_client.upload_bytes", mock_upload):
            file_content = b"cloud_upload_audio"
            upload = UploadFile(
                file=io.BytesIO(file_content),
                filename="learner_audio.mp3",
                headers={"content-type": "audio/mpeg"},
            )

            s3_key, returned_bytes = await save_upload_file_to_cloud(
                file=upload,
                relative_path=LEARNER_AUDIOS_DIR / "learner-99",
                filename_prefix="brick",
            )

            assert s3_key.startswith("learner-audios/learner-99/brick-")
            assert s3_key.endswith(".mp3")
            assert returned_bytes == file_content

            mock_upload.assert_called_once_with(
                content=file_content,
                s3_key=s3_key,
                content_type="audio/mpeg",
            )

    asyncio.run(_test())
