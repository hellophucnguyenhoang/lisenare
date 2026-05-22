import math
import re
from difflib import get_close_matches

import enchant
import nltk
import spacy
from nltk.stem import LancasterStemmer
from phonemizer import phonemize
from phonemizer.separator import Separator
from wordfreq import word_frequency

dict_checker = enchant.Dict("en_US")
nltk.download("punkt")
nlp = spacy.load("en_core_web_sm")


def log_frequency(text: str, lang="en") -> float:
    # Tokenize the sentence and get the frequency of every token,
    # then aggregate them using the Harmonic Mean
    # Formula: 1 / (1/f1 + 1/f2 + ...)
    content_freq = word_frequency(text, lang)
    return math.log10(content_freq + 1e-9)


def calculate_rarity(text: str, lang="en") -> float:
    """
    Calculate lexical rarity score of a text.

    Returns:
        float in range [0, 1]
        Higher means less common / rarer.
    """
    log_freq = log_frequency(text, lang)
    return -log_freq / 9


def lemmatize_to_set(text: str) -> set[str]:
    """
    Convert text into a set of normalized lemmas.
    """
    doc = nlp(text)

    lemmas = {token.lemma_.lower() for token in doc if token.is_alpha}

    return lemmas


def get_lenient_stems(text: str) -> set[str]:
    """
    Uses the aggressive Lancaster Stemmer to ensure UK/US and
    tense variations match correctly.
    """
    stemmer = LancasterStemmer()

    # Tokenize: lowercase and keep only words
    words = re.findall(r"\b\w+\b", text.lower())

    # Apply aggressive stemming
    return {stemmer.stem(word) for word in words}


def normalize_target_term(word: str) -> tuple[str, bool]:
    word = word.strip()

    # 1. Perfect match
    if dict_checker.check(word):
        return word, True

    # 2. Fix typos
    suggestions = dict_checker.suggest(word)
    if suggestions:
        matches = get_close_matches(word, suggestions, n=1, cutoff=0.7)
        if matches:
            # FIX: matches is a list, so return the string matches[0]
            return matches[0], True

    # 3. Not English
    return word, False


def is_valid_english(text: str) -> bool:
    return dict_checker.check(text)


def refined_spell_fix(sentence: str) -> str:
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
        if dict_checker.check(lower_word):
            corrected_words.append(word)
            continue

        # Get suggestions for English-only typos
        suggestions = dict_checker.suggest(lower_word)

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


def analyze_phoneme(
    target_text: str, learner_text: str
) -> tuple[str, str, str, str]:
    sep = Separator(phone=" ", word="  ")
    normalized_teacher_text, normalized_learner_text = (
        normalize_for_pronunciation(target_text, learner_text)
    )
    teacher_ipa = phonemize(normalized_teacher_text, separator=sep)
    learner_ipa = phonemize(normalized_learner_text, separator=sep)
    print(f"{normalized_teacher_text = }")
    print(f"{normalized_learner_text = }")
    print(f"teacher_ipa:{teacher_ipa}")
    print(f"learner_ipa:{learner_ipa}")
    return (
        teacher_ipa,
        learner_ipa,
        normalized_teacher_text,
        normalized_learner_text,
    )
