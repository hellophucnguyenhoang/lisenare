import librosa
import torch
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

# 1. Load model and processor
model_id = "facebook/wav2vec2-lv-60-espeak-cv-ft"
processor = Wav2Vec2Processor.from_pretrained(model_id)
model = Wav2Vec2ForCTC.from_pretrained(model_id)


# 2. Function to process local files
def transcribe_phonemes(file_path):
    # Load audio and automatically resample to 16,000Hz
    audio_input, _ = librosa.load(file_path, sr=16000)

    # Tokenize the audio array
    input_values = processor(
        audio_input, sampling_rate=16000, return_tensors="pt"
    ).input_values

    # Perform inference
    with torch.no_grad():
        logits = model(input_values).logits

    # Decode predicted phonemes
    predicted_ids = torch.argmax(logits, dim=-1)
    transcription = processor.batch_decode(predicted_ids)
    return transcription[0]


teacher_phonemes = transcribe_phonemes("test_audios/teacher_shoe.wav")
# learner_phonemes = transcribe_phonemes("learner.wav")

print(f"Teacher: {teacher_phonemes}")
# print(f"Learner: {learner_phonemes}")
