from transformers import pipeline


class ReadMePPService:
    LABEL2CEFR = {
        "LABEL_0": "A1",
        "LABEL_1": "A2",
        "LABEL_2": "B1",
        "LABEL_3": "B2",
        "LABEL_4": "C1",
        "LABEL_5": "C2",
    }
    CEFR2INDEX = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}

    def __init__(self, model_name: str = "tareknaous/readabert-en"):
        # top_k=None returns all labels;
        # top_k=1 would return only the highest
        self.pipe = pipeline("text-classification", model=model_name, top_k=1)
        print(f"Model {model_name} loaded successfully.")

    def predict(self, english_sentence: str, return_index: bool = True):
        # pred will be a list of dicts like:
        # [{'label': 'LABEL_0', 'score': 0.9}, ...]
        # only get the result of the first (only one) sample
        # and the first (only) label prediction
        pred = self.pipe(english_sentence)[0][0]

        # Convert LABEL_X to CEFR (e.g., A1, B2)
        final_cefr = self.LABEL2CEFR[pred["label"]]

        if return_index:
            return self.CEFR2INDEX[final_cefr]
        return final_cefr


readmepp_service = ReadMePPService()
