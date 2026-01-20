from kokoro import KPipeline
import soundfile as sf
import io
from datetime import datetime, timezone

class TTSService:
    def __init__(self):
        self.pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
        self.sample_rate = 24000

    def tts_stream(self, text: str):
        generator = self.pipeline(text, voice="af_heart", speed=1)

        for _, _, audio in generator:
            buffer = io.BytesIO()
            sf.write(
                buffer,
                audio.cpu().numpy(),
                self.sample_rate,
                format="WAV",
                subtype="PCM_16",
            )
            yield buffer.getvalue()
    
    async def synthesize_to_file(self, text: str) -> str:
        saved_file_path = f'temp_{datetime.now(timezone.utc)}.wav'
        generator = self.pipeline(text, voice="af_heart", speed=1)
        for _, _, audio in generator:
            sf.write(saved_file_path, audio, self.sample_rate) # save each audio file
        return saved_file_path

# Instantiate as a singleton to be used in the router
tts_service = TTSService()
