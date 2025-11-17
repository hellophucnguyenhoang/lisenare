from transformers import AutoTokenizer, T5ForConditionalGeneration
import spacy



# Load model once at startup
tokenizer = AutoTokenizer.from_pretrained("grammarly/coedit-large")
model = T5ForConditionalGeneration.from_pretrained("grammarly/coedit-large")
MAX_TOKENS = 256
nlp = spacy.load("en_core_web_sm")

def run_sentence(instruction: str, text: str):
    # CoEdit expects input like:
    #   <instruction>: <text>
    prompt = f"{instruction}: {text}"

    input_ids = tokenizer(prompt, return_tensors="pt").input_ids
    outputs = model.generate(input_ids, max_length=MAX_TOKENS)
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return result

def run_paragraph(instruction: str, text: str):
    doc = nlp(text)
    edited_sentences = [run_sentence(instruction, sent.text) for sent in doc.sents]
    corrected = " ".join(edited_sentences)
    return corrected, len(edited_sentences)