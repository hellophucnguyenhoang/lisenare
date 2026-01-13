# %%
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

# model_id = "distil-whisper/distil-large-v3.5"
# model_id = "distil-whisper/distil-medium.en"
model_id = "distil-whisper/distil-small.en"

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, 
    torch_dtype=torch_dtype, 
    low_cpu_mem_usage=True, 
    use_safetensors=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    max_new_tokens=128,
    dtype=torch_dtype,
    device=device,
)

# %%
import time

start = time.time()
result = pipe("_0J3v14ZjW4_sentence_014.wav")
print(result["text"])
end = time.time()
print(end - start)

start = time.time()
result = pipe("_0J3v14ZjW4_sentence_014.wav")
print(result["text"])
end = time.time()
print(end - start)

# %%
