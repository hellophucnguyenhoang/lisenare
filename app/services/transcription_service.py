import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from fastapi import UploadFile
import ffmpeg
import numpy as np


class TranscriptionService:
    def __init__(self):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model_id = "distil-whisper/distil-small.en"
        
        # Load model and processor once
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id, dtype=self.torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
        ).to(self.device)
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            max_new_tokens=128,
            chunk_length_s=30,
            batch_size=16,
            dtype=self.torch_dtype,
            device=self.device,
        )

    async def transcribe(self, file: UploadFile) -> str:
        # Read file into memory and convert to 16kHz for Whisper
        audio_bytes = await file.read()
        # audio_data, _ = librosa.load(io.BytesIO(audio_bytes), sr=16000)
        out, _ = (
            ffmpeg
            .input('pipe:0')
            .output(
                'pipe:1',
                format='f32le',
                acodec='pcm_f32le',
                ac=1,
                ar='16000'
            )
            .run(
                input=audio_bytes,
                capture_stdout=True,
                capture_stderr=True
            )
        )
        audio_data = np.frombuffer(out, np.float32)

        result = self.pipe(audio_data)
        return result["text"]

# Instantiate as a singleton
transcription_service = TranscriptionService()
