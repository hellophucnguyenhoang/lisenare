# Use a pipeline as a high-level helper
from transformers import pipeline
import spacy
from collections import defaultdict

# Load spaCy once
nlp = spacy.load("en_core_web_sm")

# Load Hugging Face model once
pipe = pipeline("text-classification", model="tareknaous/readabert-en", top_k=None)

LABEL2CEFR = {
    "LABEL_0": "A1",
    "LABEL_1": "A2",
    "LABEL_2": "B1",
    "LABEL_3": "B2",
    "LABEL_4": "C1",
    "LABEL_5": "C2",
}


CEFR2INDEX = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
INDEX2CEFR = {i: level for level, i in CEFR2INDEX.items()}


def weighted_label(predictions, return_index=True):
    score_dict = defaultdict(float)

    for pred in predictions:            # pred is [[ {...}, {...}, ... ]]]
        items = pred[0]                 # list of dicts

        for item in items:              # each dict = {'label': 'LABEL_1', 'score': 0.3}
            cefr = LABEL2CEFR[item["label"]]
            score_dict[cefr] += float(item["score"])

    # pick highest accumulated softmax score
    final_cefr = max(score_dict, key=score_dict.get)

    if return_index:
        return CEFR2INDEX[final_cefr]
    return final_cefr


def predict_cefr(text, return_index=True):
    doc = nlp(text)
    preds = [pipe(sent.text) for sent in doc.sents]
    return weighted_label(preds, return_index=return_index)

