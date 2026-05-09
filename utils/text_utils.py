import math
import re
from difflib import get_close_matches

import enchant
import nltk
import spacy
from nltk.stem import LancasterStemmer
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
