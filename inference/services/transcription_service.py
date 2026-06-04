import io
import itertools
import re
from typing import Any

import ffmpeg
import numpy as np
import requests
import torch
import torchaudio
from fastapi import UploadFile
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    pipeline,
)

from inference.cv_finetune.loaders import (
    apply_lora_to_wav2vec2,
    load_lora_adapter,
    lora_mode,
)
from inference.schemas.audio import WordSegment


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
        print(f"{self.model_id} loaded with {self.device}")

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


class Point:
    """Helper for backtracking path."""

    def __init__(self, token_index: int, time_index: int, score: float):
        self.token_index = token_index
        self.time_index = time_index
        self.score = score


class PhonemeService:
    def __init__(
        self,
        bundle=torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H,
        lora_path: str | None = None,
        enable_lora: bool = True,
    ):
        # Determine if GPU is available
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        print(f"Loading torchaudio bundle to {self.device}...")
        self.bundle = bundle
        base_model = self.bundle.get_model().to(self.device)
        self.enable_lora = enable_lora
        if lora_path:
            print("📦 Extracting and loading LoRA adapter weights...")
            applied_model = apply_lora_to_wav2vec2(base_model).to(self.device)
            self.model = load_lora_adapter(applied_model, lora_path).to(
                self.device
            )
        else:
            self.model = base_model
            self.enable_lora = False
        self.model.eval()

        self.labels = self.bundle.get_labels()
        self.sample_rate = self.bundle.sample_rate
        self.l2i = {c: i for i, c in enumerate(self.labels)}
        self.blank_id = self.l2i["-"]

    def _decode_emissions(self, emission: torch.Tensor) -> str:
        """Helper to run greedy CTC decoding on model output frames."""
        # Find the highest-probability token index for each frame
        predicted_ids = torch.argmax(emission, dim=-1).tolist()

        # Group consecutive duplicate tokens (CTC mechanism)
        grouped_tokens = [key for key, _ in itertools.groupby(predicted_ids)]

        # Filter out the blank token ("-") and map IDs to characters
        transcript_list = [
            self.labels[idx]
            for idx in grouped_tokens
            if self.labels[idx] != "-"
        ]
        return "".join(transcript_list).replace("|", " ").strip()

    async def get_phonemes_from_array(self, audio_data: np.ndarray) -> str:
        """Processes a 1D or 2D numpy array directly instead of a file path."""
        waveform = torch.from_numpy(audio_data).float()

        # Ensure standard 2D shape [channels, time_steps]
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)

        waveform = waveform.to(self.device)

        with torch.inference_mode(), lora_mode(enabled=self.enable_lora):
            emissions, _ = self.model(waveform)
            emissions = torch.log_softmax(emissions, dim=-1)

        return self._decode_emissions(emissions[0])

    def download_url_to_ndarray(self, audio_url: str) -> np.ndarray:
        """Downloads an audio file from a URL and converts it to a NumPy array."""
        response = requests.get(audio_url)
        audio_file = io.BytesIO(response.content)

        waveform, sr = torchaudio.load(audio_file)
        if sr != self.sample_rate:
            waveform = torchaudio.functional.resample(
                waveform, sr, self.sample_rate
            )

        # Convert to mono if multi-channel and output as NumPy array
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        return waveform.squeeze(0).numpy()

    def _get_emission_from_url(
        self, audio_url: str
    ) -> tuple[torch.Tensor, int, int]:
        """Download remote audio, resample, and run inference to get log-softmax emissions."""
        response = requests.get(audio_url)
        audio_file = io.BytesIO(response.content)

        with torch.inference_mode(), lora_mode(enabled=self.enable_lora):
            waveform, sr = torchaudio.load(audio_file)
            if sr != self.sample_rate:
                waveform = torchaudio.functional.resample(
                    waveform, sr, self.sample_rate
                )
            emissions, _ = self.model(waveform.to(self.device))
            emissions = torch.log_softmax(emissions, dim=-1)

        # Move to CPU for memory-efficient backtracking/trellis logic
        return (
            emissions[0].cpu().detach(),
            waveform.shape[1],
            len(emissions[0]),
        )

    def _get_trellis(
        self, emission: torch.Tensor, tokens: list[int]
    ) -> torch.Tensor:
        """Build the dynamic programming trellis for forced alignment."""
        num_frame, num_tokens = emission.size(0), len(tokens)
        trellis = torch.zeros((num_frame, num_tokens))

        trellis[1:, 0] = torch.cumsum(emission[1:, self.blank_id], 0)
        trellis[0, 1:] = float("-inf")
        trellis[-num_tokens + 1 :, 0] = float("inf")

        for t in range(num_frame - 1):
            trellis[t + 1, 1:] = torch.maximum(
                trellis[t, 1:] + emission[t, self.blank_id],
                trellis[t, :-1] + emission[t, tokens[1:]],
            )
        return trellis

    def _backtrack(
        self, trellis: torch.Tensor, emission: torch.Tensor, tokens: list[int]
    ) -> list[Point]:
        """Backtrack through the trellis to find the optimal alignment path."""
        t, j = trellis.size(0) - 1, trellis.size(1) - 1
        path = [Point(j, t, emission[t, self.blank_id].exp().item())]

        while j > 0:
            assert t > 0
            p_stay = emission[t - 1, self.blank_id]
            p_change = emission[t - 1, tokens[j]]

            stayed = trellis[t - 1, j] + p_stay
            changed = trellis[t - 1, j - 1] + p_change

            t -= 1
            if changed > stayed:
                j -= 1
            prob = (p_change if changed > stayed else p_stay).exp().item()
            path.append(Point(j, t, prob))

        while t > 0:
            prob = emission[t - 1, self.blank_id].exp().item()
            path.append(Point(j, t - 1, prob))
            t -= 1

        return path[::-1]

    def _merge_repeats(
        self, path: list[Point], transcript: str
    ) -> list[dict[str, Any]]:
        """Merge consecutive frame repeats of identical tokens into characters."""
        segments = []
        i1 = i2 = 0
        while i1 < len(path):
            while (
                i2 < len(path) and path[i1].token_index == path[i2].token_index
            ):
                i2 += 1
            score = sum(p.score for p in path[i1:i2]) / (i2 - i1)
            segments.append(
                {
                    "label": transcript[path[i1].token_index],
                    "start": path[i1].time_index,
                    "end": path[i2 - 1].time_index + 1,
                    "score": score,
                }
            )
            i1 = i2
        return segments

    def _merge_words(
        self, segments: list[dict[str, Any]], separator: str = "|"
    ) -> list[WordSegment]:
        """Group raw character segments into structured WordSegment objects."""
        words = []
        i1 = i2 = 0
        while i1 < len(segments):
            if i2 >= len(segments) or segments[i2]["label"] == separator:
                if i1 != i2:
                    segs = segments[i1:i2]
                    word = "".join(s["label"] for s in segs)
                    total_length = sum(s["end"] - s["start"] for s in segs)
                    score = (
                        sum(s["score"] * (s["end"] - s["start"]) for s in segs)
                        / total_length
                    )
                    words.append(
                        WordSegment(
                            word=word,
                            start_frame=segments[i1]["start"],
                            end_frame=segments[i2 - 1]["end"],
                            score=score,
                        )
                    )
                i1 = i2 + 1
                i2 = i1
            else:
                i2 += 1
        return words

    def normalize_transcript(self, text: str) -> str:
        """Strip punctuation and format words with appropriate pipeline separators."""
        words = re.findall(r"[a-zA-Z']+", text)
        return "|" + "|".join(w.upper() for w in words) + "|"

    def align_audio_to_transcript(
        self, audio_url: str, raw_transcript: str
    ) -> tuple[list[WordSegment], float]:
        """Align audio from a URL with a raw transcript string.

        Returns:
            - A list of localized WordSegment models.
            - The sample frequency ratio (frames per second) for down-stream conversion.
        """
        emission, num_samples, num_frames = self._get_emission_from_url(
            audio_url
        )
        transcript = self.normalize_transcript(raw_transcript)

        tokens = [self.l2i[c] for c in transcript]

        trellis = self._get_trellis(emission, tokens)
        path = self._backtrack(trellis, emission, tokens)

        char_segments = self._merge_repeats(path, transcript)
        word_segments = self._merge_words(char_segments)

        frames_per_second = num_frames / (num_samples / self.sample_rate)
        return word_segments, frames_per_second


transcription_service = TranscriptionService()
phoneme_recognition_service = PhonemeService(
    lora_path="models/lora_adapter_epoch3_20260601_062920_loss0.2356.pt"
)
