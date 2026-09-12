import io
import string

import soundfile as sf
import torch
from kokoro import KPipeline
from sentence_transformers import SentenceTransformer, util
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from inference.config import logger
from schemas.sentence import Language


class TextService:
    def __init__(self):
        # Determine device (GPU if available, else CPU)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # 1. Load Similarity Model (all-mpnet-base-v2)
        self.similarity_model = SentenceTransformer(
            "all-mpnet-base-v2", device=self.device
        )

        # 2. Load Translation Model (VietAI/envit5-translation)
        self.trans_model_name = "VietAI/envit5-translation"
        self.trans_tokenizer = AutoTokenizer.from_pretrained(
            self.trans_model_name
        )
        self.trans_model = AutoModelForSeq2SeqLM.from_pretrained(
            self.trans_model_name
        ).to(self.device)

        # 3. Load text to speech model
        self.tts_pipeline_en = KPipeline(
            lang_code="a", repo_id="hexgrad/Kokoro-82M", device=self.device
        )
        self.tts_pipeline_jp = KPipeline(
            lang_code="ja", repo_id="hexgrad/Kokoro-82M", device=self.device
        )
        logger.info(f"Running Kokoro on: {self.device}")

    def get_similarity(self, s1: str, s2: str) -> float:
        """Computes semantic similarity score between two sentences."""
        # Create a translation table that maps all punctuation to None
        translator = str.maketrans("", "", string.punctuation)

        # Remove punctuation from both strings
        s1_clean = s1.translate(translator)
        s2_clean = s2.translate(translator)

        # Process cleaned strings
        embeddings = self.similarity_model.encode(
            [s1_clean, s2_clean], convert_to_tensor=True
        )
        score = util.cos_sim(embeddings[0], embeddings[1])
        return float(score.item())

    def translate(self, text: str, target_lang: Language) -> str:
        """
        Translates a single sentence.
        target_lang: "vi" for En->Vi, "en" for Vi->En
        """
        # Prefix is required by EnViT5: "en: " or "vi: "
        prefix = "en" if target_lang is Language.vi else "vi"
        input_text = f"{prefix}: {text}"
        inputs = self.trans_tokenizer(
            input_text, return_tensors="pt", padding=True
        ).to(self.device)
        with torch.no_grad():
            outputs = self.trans_model.generate(
                inputs.input_ids, max_length=512
            )
        decoded = self.trans_tokenizer.decode(
            outputs[0], skip_special_tokens=True
        )
        return decoded[4:], (
            Language.en if decoded[:2] == Language.en.value else Language.vi
        )

    def generate_tts_wav(
        self, text: str | list[str], voice: str = "af_heart"
    ) -> bytes | list[bytes]:
        """Generate WAV audio bytes from input text (str or list of str) using Kokoro TTS model."""
        if not text:
            return [] if isinstance(text, list) else b""

        pipeline = (
            self.tts_pipeline_jp
            if voice.startswith("j")
            else self.tts_pipeline_en
        )
        generator = pipeline(text, voice=voice)
        audio_files = []
        for _, _, audio in generator:
            buffer = io.BytesIO()
            sf.write(buffer, audio, 24000, format="WAV")
            audio_files.append(buffer.getvalue())

        if isinstance(text, list):
            return audio_files
        return audio_files[0] if audio_files else b""


text_service = TextService()
