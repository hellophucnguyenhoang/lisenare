import torch
import ffmpeg
import numpy as np
import librosa
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from fastapi import UploadFile


async def preprocess_upload_file(file: UploadFile) -> np.ndarray:
    audio_bytes = await file.read()
    out, _ = (
        ffmpeg.input("pipe:0")
        .output("pipe:1", format="f32le", acodec="pcm_f32le", ac=1, ar="16000")
        .run(input=audio_bytes, capture_stdout=True, capture_stderr=True)
    )
    audio_data = np.frombuffer(out, np.float32)
    return audio_data


class TranscriptionService:
    def __init__(self):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.torch_dtype = (
            torch.float16 if torch.cuda.is_available() else torch.float32
        )
        self.model_id = "distil-whisper/distil-small.en"

        # Load model and processor once
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        ).to(self.device)
        # Clear the old setting to stop the warning
        self.model.generation_config.forced_decoder_ids = None
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

    async def transcribe(self, audio_data: np.ndarray) -> str:
        result = self.pipe(audio_data)
        return result["text"]


class PhonemeRecognitionService:
    def __init__(self, model_id="facebook/wav2vec2-lv-60-espeak-cv-ft"):
        # Determine if GPU is available
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        print(f"Loading {model_id} to {self.device}...")

        # Initialize processor and model
        self.processor = Wav2Vec2Processor.from_pretrained(model_id)
        self.model = Wav2Vec2ForCTC.from_pretrained(model_id).to(self.device)
        self.model.eval()  # Set to evaluation mode

    def get_phonemes(self, file_path):
        """Transcribes a local wav file into IPA phonemes."""
        # 1. Load and resample
        audio_input, _ = librosa.load(file_path, sr=16000)

        # 2. Preprocess
        inputs = self.processor(
            audio_input, sampling_rate=16000, return_tensors="pt"
        ).to(self.device)

        # 3. Inference
        with torch.no_grad():
            logits = self.model(inputs.input_values).logits

        # 4. Decode
        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = self.processor.batch_decode(predicted_ids)

        return transcription[0]

    async def get_phonemes_from_array(self, audio_data: np.ndarray):
        """Processes a numpy array directly instead of a file path."""
        inputs = self.processor(
            audio_data, sampling_rate=16000, return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(inputs.input_values).logits

        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = self.processor.batch_decode(predicted_ids)
        return transcription[0]  # Return the first string in the batch


transcription_service = TranscriptionService()
phoneme_recognition_service = PhonemeRecognitionService()
