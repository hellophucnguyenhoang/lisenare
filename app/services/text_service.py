import difflib
import math

from jiwer import cer
from wordfreq import word_frequency


def log_frequency(text: str, lang="en") -> float:
    content_freq = word_frequency(text, lang)
    return math.log10(content_freq + 1e-9)


class TextService:
    def evaluate_ipa_pronunciation(self, teacher_ipa: str, learner_ipa: str):
        # Split IPA strings into sequences of phonemes
        # Example: "k æ t" -> ["k", "æ", "t"]
        t_seq = teacher_ipa.strip().split()
        l_seq = learner_ipa.strip().split()

        # --- ACCURACY CALCULATION ---
        # We compute Character Error Rate (CER),
        # but we treat each phoneme as a "character"
        # So we join phonemes back into a string like: "k æ t"
        # CER measures how many edits (insert/delete/replace) are needed
        error_rate = cer(" ".join(t_seq), " ".join(l_seq))

        # Convert error rate into accuracy score
        # Example: error_rate = 0.3 -> accuracy = 0.7
        # max(0, ...) ensures score never goes negative
        accuracy_score = max(0, 1 - error_rate)

        # --- ALIGNMENT (CORE LOGIC) ---
        # SequenceMatcher finds the best alignment between
        # teacher and learner phoneme sequences
        # It tells us where they match and where they differ
        matcher = difflib.SequenceMatcher(None, t_seq, l_seq)

        # This will store detailed phoneme-by-phoneme analysis
        analysis = []

        """
        Opcode tags meaning:

        Tag        Meaning            Interpretation in pronunciation
        -------------------------------------------------------------
        equal      same              learner pronounced correctly
        replace    different         learner mispronounced the phoneme
        delete     missing           learner skipped this phoneme
        insert     extra             learner added an extra phoneme
        """

        # Iterate over all alignment operations between teacher and learner
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            # --- CASE 1: CORRECT PHONEMES ---
            # These phonemes match exactly between teacher and learner
            if tag == "equal":
                for i in range(i1, i2):
                    analysis.append(
                        {
                            "phoneme": t_seq[i],  # the correct phoneme
                            "status": "correct",  # learner said it correctly
                        }
                    )

            # --- CASE 2: MISPRONOUNCED PHONEMES ---
            # Teacher phoneme was replaced by a different learner phoneme
            elif tag == "replace":
                for i in range(i1, i2):
                    analysis.append(
                        {
                            "phoneme": t_seq[i],  # expected phoneme (teacher)
                            "status": "mispronounced",
                            # What the system actually heard from learner
                            # We align positions using (i - i1)
                            # Example:
                            # teacher: æ t
                            # learner: ɛ d
                            # maps: æ->ɛ, t->d
                            "heard": (
                                l_seq[j1 + (i - i1)]
                                # Safety check to avoid index out-of-range
                                if (j1 + (i - i1)) < j2
                                else None
                            ),
                        }
                    )

            # --- CASE 3: MISSING PHONEMES ---
            # These phonemes exist in teacher but NOT in learner
            # -> learner skipped them
            elif tag == "delete":
                for i in range(i1, i2):
                    analysis.append(
                        {
                            "phoneme": t_seq[i],  # expected phoneme
                            "status": "missing",  # learner did not say it
                        }
                    )

            # --- CASE 4: EXTRA PHONEMES ---
            # These phonemes exist in learner but NOT in teacher
            # -> learner added extra sounds
            elif tag == "insert":
                for j in range(j1, j2):
                    analysis.append(
                        {
                            "phoneme": l_seq[j],  # extra phoneme from learner
                            "status": "extra",
                        }
                    )

        # --- FINAL RESULT ---
        return {
            # Rounded accuracy score for cleaner UI display
            "accuracy_score": round(accuracy_score, 4),
            # Detailed phoneme-by-phoneme evaluation
            "analysis": analysis,
            # Raw learner phoneme sequence (useful for UI display)
            "learner_phonemes": l_seq,
        }


text_service = TextService()
