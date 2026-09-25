import io
import re
import string

from difflib import get_close_matches

import enchant
import soundfile as sf
import torch
from kokoro import KPipeline
from nltk.stem import LancasterStemmer
from phonemizer import phonemize
from phonemizer.separator import Separator
from sentence_transformers import SentenceTransformer, util
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from config import logger
from shared_schemas.sentence import Language
from shared_schemas.text import PhonemeAnalysisResponse


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

        # 4. Dictionary checker for spell checking and word validation
        self.dict_checker = enchant.Dict("en_US")

        # 5. Lancaster Stemmer for aggressive linguistic stemming
        self.stemmer = LancasterStemmer()

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

    def analyze_phoneme(
        self, target_text: str, learner_text: str
    ) -> PhonemeAnalysisResponse:
        sep = Separator(phone=" ", word="  ")
        normalized_teacher_text, normalized_learner_text = (
            normalize_for_pronunciation(target_text, learner_text)
        )
        teacher_ipa = phonemize(normalized_teacher_text, separator=sep)
        learner_ipa = phonemize(normalized_learner_text, separator=sep)
        logger.info(f"{normalized_teacher_text = }")
        logger.info(f"{normalized_learner_text = }")
        logger.info(f"teacher_ipa: {teacher_ipa}")
        logger.info(f"learner_ipa: {learner_ipa}")
        return PhonemeAnalysisResponse(
            teacher_ipa=teacher_ipa,
            learner_ipa=learner_ipa,
            normalized_teacher_text=normalized_teacher_text,
            normalized_learner_text=normalized_learner_text,
        )

    def normalize_target_term(self, word: str) -> tuple[str, bool]:
        word = word.strip()

        # 1. Perfect match
        if self.dict_checker.check(word):
            return word, True

        # 2. Fix typos
        suggestions = self.dict_checker.suggest(word)
        if suggestions:
            matches = get_close_matches(word, suggestions, n=1, cutoff=0.7)
            if matches:
                return matches[0], True

        # 3. Not English
        return word, False

    def is_valid_english(self, text: str) -> bool:
        return self.dict_checker.check(text)

    def refined_spell_fix(self, sentence: str) -> str:
        words = sentence.split()
        corrected_words = []

        for word in words:
            # Clean the word (remove punctuation)
            clean_word = word.strip(".,!?;:()\"'")

            # Only process words that are strictly English characters
            # This will skip "Tôi", "tươi", or words with numbers/symbols
            if not re.fullmatch(r"[a-zA-Z]+", clean_word):
                corrected_words.append(word)
                continue

            lower_word = clean_word.lower()

            # If it's already a correct English word, keep it
            if self.dict_checker.check(lower_word):
                corrected_words.append(word)
                continue

            # Get suggestions for English-only typos
            suggestions = self.dict_checker.suggest(lower_word)

            if suggestions:
                # Filter suggestions, must be English letters only
                valid_suggestions = [
                    s for s in suggestions if re.fullmatch(r"[a-zA-Z]+", s)
                ]

                matches = get_close_matches(
                    lower_word, valid_suggestions, n=1, cutoff=0.8
                )

                if matches:
                    best_match = matches[0].lower()
                    # Match original capitalization
                    if word[0].isupper():
                        best_match = best_match.capitalize()
                    corrected_words.append(best_match)
                    continue

            # Fallback: Keep original
            corrected_words.append(word)

        return " ".join(corrected_words)

    def get_lenient_stems(self, text: str | list[str]) -> list[str]:
        """Uses aggressive Lancaster Stemmer to extract unique stems."""
        if not text:
            return []
        if isinstance(text, str):
            words = re.findall(r"\b\w+\b", text.lower())
        else:
            words = []
            for item in text:
                words.extend(re.findall(r"\b\w+\b", item.lower()))
        return list({self.stemmer.stem(word) for word in words})


def normalize_currency(text: str) -> str:
    # "$5" -> "5 dollars"
    return re.sub(r"\$(\d+)", r"\1 dollars", text)


def extract_number_sequences(text: str):
    """
    Extract sequences like:
    - 6.30
    - 6:30
    - 630
    """
    return re.findall(r"\d+(?:[.:]\d+)?", text)


def to_digit_signature(num_str: str) -> str:
    """
    Convert:
    - "6.30" -> "630"
    - "6:30" -> "630"
    - "630"  -> "630"
    """
    return re.sub(r"[^\d]", "", num_str)


def replace_numbers_by_teacher(teacher_text: str, learner_text: str) -> str:
    teacher_nums = extract_number_sequences(teacher_text)

    for t_num in teacher_nums:
        t_sig = to_digit_signature(t_num)

        # Find matching number in learner text
        matches = re.finditer(r"\d+(?:[.:]\d+)?", learner_text)

        for match in matches:
            l_num = match.group()
            l_sig = to_digit_signature(l_num)

            # Match exact digit order
            if l_sig == t_sig:
                # Replace ONLY this occurrence
                learner_text = (
                    learner_text[: match.start()]
                    + t_num
                    + learner_text[match.end() :]
                )
                break  # move to next teacher number

    return learner_text


def normalize_for_pronunciation(teacher_text: str, learner_text: str):
    # --- Step 1: normalize currency ---
    teacher_text = normalize_currency(teacher_text)
    learner_text = normalize_currency(learner_text)

    # --- Step 2: align numbers ---
    learner_text = replace_numbers_by_teacher(teacher_text, learner_text)

    return teacher_text, learner_text


text_service = TextService()
