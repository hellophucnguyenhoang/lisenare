import io
import soundfile as sf
from kokoro import KPipeline

pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
sample_rate = 24000
text = "What is going on?"
generator = pipeline(text, voice="af_heart", speed=1, split_pattern=r'\n+')
for i, (gs, ps, audio) in enumerate(generator):
    sf.write(f'{i}.wav', audio, 24000) # save each audio file
