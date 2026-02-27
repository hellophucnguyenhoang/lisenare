import difflib
from jiwer import cer # Character Error Rate (works for phoneme sequences)

class PhonemeRecognitionService:
    def evaluate_pronunciation(self, teacher_ipa: str, learner_ipa: str):
        # 1. Clean strings (remove extra spaces)
        t_seq = teacher_ipa.strip().split()
        l_seq = learner_ipa.strip().split()
        
        # 2. Calculate Accuracy Score 
        # We treat phonemes as "characters" for the CER metric
        error_rate = cer(" ".join(t_seq), " ".join(l_seq))
        score = max(0, 1 - error_rate)

        # 3. Identify specific differences
        matcher = difflib.SequenceMatcher(None, t_seq, l_seq)
        analysis = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for i in range(i1, i2):
                    analysis.append({"phoneme": t_seq[i], "status": "correct"})
            elif tag == 'replace':
                for i in range(i1, i2):
                    analysis.append({"phoneme": t_seq[i], "status": "mispronounced", "heard": l_seq[j1 + (i-i1)] if (j1 + (i-i1)) < j2 else None})
            elif tag == 'delete':
                for i in range(i1, i2):
                    analysis.append({"phoneme": t_seq[i], "status": "missing"})
            elif tag == 'insert':
                for j in range(j1, j2):
                    analysis.append({"phoneme": l_seq[j], "status": "extra"})

        return {
            "score": round(score, 4),
            "analysis": analysis
        }
    
phoneme_recognition_service = PhonemeRecognitionService()

t = "b iː h aɪ n d"
l = "b i h aɪ d"
r = phoneme_recognition_service.evaluate_pronunciation(t, l)

print(r['score'])
for a in r['analysis']:
    print(a)