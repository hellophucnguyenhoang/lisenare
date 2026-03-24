import difflib
from jiwer import cer


class TextService:
    def evaluate_ipa_pronunciation(self, teacher_ipa: str, learner_ipa: str):
        t_seq = teacher_ipa.strip().split()
        l_seq = learner_ipa.strip().split()

        # We treat phonemes as "characters" for the CER metric
        error_rate = cer(" ".join(t_seq), " ".join(l_seq))
        accuracy_score = max(0, 1 - error_rate)

        # Identify specific differences
        matcher = difflib.SequenceMatcher(None, t_seq, l_seq)
        analysis = []
        """ 
        Tag	        Logic	        What learner did
        equal	    correct	        said the sound perfectly.
        replace	    mispronounced	said a different sound.
        delete	    missing	        skipped a sound.
        insert	    extra	        added a sound.
        """
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    analysis.append({"phoneme": t_seq[i], "status": "correct"})
            elif tag == "replace":
                for i in range(i1, i2):
                    analysis.append(
                        {
                            "phoneme": t_seq[i],
                            "status": "mispronounced",
                            "heard": (
                                l_seq[j1 + (i - i1)]
                                if (j1 + (i - i1)) < j2
                                else None
                            ),
                        }
                    )
            elif tag == "delete":
                for i in range(i1, i2):
                    analysis.append({"phoneme": t_seq[i], "status": "missing"})
            elif tag == "insert":
                for j in range(j1, j2):
                    analysis.append({"phoneme": l_seq[j], "status": "extra"})

        return {
            "accuracy_score": round(accuracy_score, 4),
            "analysis": analysis,
        }


text_service = TextService()
