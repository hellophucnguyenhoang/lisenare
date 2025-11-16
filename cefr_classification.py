from transformers import pipeline
import nltk

# Download NLTK sentence tokenizer
nltk.download('punkt')
nltk.download('punkt_tab')
from nltk.tokenize import sent_tokenize

# Mapping CEFR levels to numeric indices
LEVEL_IDX_MAPPER = {
    "A1": 0,
    "A2": 1,
    "B1": 2,
    "B2": 3,
    "C1": 4,
    "C2": 5
}

# Reverse mapping for numeric index → label
IDX_LEVEL_MAPPER = {v: k for k, v in LEVEL_IDX_MAPPER.items()}

# Load CEFR classifier pipeline
model_name = "AbdulSami/bert-base-cased-cefr"
cefr_classifier = pipeline("text-classification", model=model_name)

def text_to_cefr(text: str) -> tuple[float, str]:
    """
    Convert a long text to CEFR numeric index and closest CEFR label.
    
    Returns:
        avg_index (float): Average CEFR numeric index
        closest_label (str): Closest CEFR label
    """
    if not text.strip():
        raise ValueError("Input text is empty")
    
    sentences = sent_tokenize(text)
    indices = []
    
    for sent in sentences:
        result = cefr_classifier(sent)
        level_label = result[0]["label"]
        indices.append(LEVEL_IDX_MAPPER.get(level_label, 0))
    
    avg_index = sum(indices) / len(indices)
    
    # Round to nearest integer to get closest CEFR label
    closest_idx = round(avg_index)
    closest_label = IDX_LEVEL_MAPPER.get(closest_idx, "Unknown")
    
    return avg_index, closest_label

if __name__ == "__main__":
        
    # Example usage
    long_text = """I am learning English and I can write simple sentences. 
    Despite the storm, we completed our journey. The research findings were conclusive."""

    avg_index, closest_label = text_to_cefr(long_text)
    print(f"Average CEFR numeric index: {avg_index:.2f}")
    print(f"Closest CEFR label: {closest_label}")
