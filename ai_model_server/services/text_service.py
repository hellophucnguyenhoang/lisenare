import torch
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from schemas.sentence import Language
import string

class TextService:
    def __init__(self):
        # Determine device (GPU if available, else CPU)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 1. Load Similarity Model (all-mpnet-base-v2)
        self.similarity_model = SentenceTransformer('all-mpnet-base-v2', device=self.device)
        
        # 2. Load Translation Model (VietAI/envit5-translation)
        self.trans_model_name = "VietAI/envit5-translation"
        self.trans_tokenizer = AutoTokenizer.from_pretrained(self.trans_model_name)
        self.trans_model = AutoModelForSeq2SeqLM.from_pretrained(self.trans_model_name).to(self.device)

    def get_similarity(self, s1: str, s2: str) -> float:
        """Computes semantic similarity score between two sentences."""
        # Create a translation table that maps all punctuation to None
        translator = str.maketrans('', '', string.punctuation)
        
        # Remove punctuation from both strings
        s1_clean = s1.translate(translator)
        s2_clean = s2.translate(translator)
        
        # Process cleaned strings
        embeddings = self.similarity_model.encode([s1_clean, s2_clean], convert_to_tensor=True)
        score = util.cos_sim(embeddings[0], embeddings[1])
        return float(score.item())


    def translate(self, text: str, target_lang: Language) -> str:
        """
        Translates a single sentence.
        target_lang: 'vi' for En->Vi, 'en' for Vi->En
        """
        # Prefix is required by EnViT5: "en: " or "vi: "
        prefix = "en: " if target_lang is Language.vi else "vi: "
        input_text = f"{prefix}{text}"
        inputs = self.trans_tokenizer(input_text, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.trans_model.generate(inputs.input_ids, max_length=512)
        decoded = self.trans_tokenizer.decode(outputs[0], skip_special_tokens=True)
        return decoded[4:], Language.en if decoded[:2] == Language.en.value else Language.vi

# Initialize a single instance to be imported by your API routes
text_service = TextService()
