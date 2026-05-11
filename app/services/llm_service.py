from google import genai
from typing import Generator
import os
os.environ["GEMINI_API_KEY"] = ""
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
def call_llm(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-3-flash-preview", contents=prompt
    )
    return response.text

def call_llm_stream(prompt: str, model: str = "gemini-2.5-flash") -> Generator[str, None, None]:
    response = client.models.generate_content_stream(
        model=model,
        contents=prompt
    )
    for chunk in response:
        if chunk.text is not None:
            yield chunk.text
