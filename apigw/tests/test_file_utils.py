import asyncio
import io
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile

from constants import (
    ASSETS_DIR,
    GENERATED_AUDIOS_DIR,
    LEARNER_AUDIOS_DIR,
)
from utils.file_utils import save_file_bytes, save_upload_file


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
