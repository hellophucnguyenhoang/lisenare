import json

import fakeredis
from google import genai
from ollama import chat

from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

r = fakeredis.FakeRedis()
SESSION_EXPIRY = 3600  # 60 minutes in seconds


def generate_response_stream(user_message: str):
    response = client.models.generate_content_stream(
        model="gemini-2.5-flash-lite",
        contents=[user_message],
    )
    for chunk in response:
        yield chunk.text


def generate_chat_stream(session_id: str, user_message: str):
    session_key = f"chat:{session_id}"

    # 1. Retrieve history from Redis
    raw_history = r.get(session_key)
    # If no history exists, start with a system prompt
    messages = (
        json.loads(raw_history) if raw_history else []
    )  # [] or [{"role": "system", "content": "You are a helpful assistant."}]

    # 2. Add the new user message
    messages.append({"role": "user", "content": user_message})

    # 3. Stream from Ollama
    stream = chat(model="gemma3:1b", messages=messages, stream=True)

    full_response = ""
    for chunk in stream:
        content = chunk["message"]["content"]
        full_response += content
        yield content

    # 4. Add the assistant's response to history and save
    messages.append({"role": "assistant", "content": full_response})

    # resets the countdown every time a message is sent
    r.setex(session_key, SESSION_EXPIRY, json.dumps(messages))


def generate_response_stream_fake(user_message: str):
    response = """The sky is blue due to a phenomenon called **Rayleigh scattering**. It's all about how sunlight interacts with the Earth's atmosphere.

Here's a breakdown:

1.  **Sunlight is made of many colors:** Sunlight, which appears white to us, is actually a spectrum of all the colors of the rainbow. These colors have different wavelengths. Blue and violet light have shorter, smaller wavelengths, while red and orange light have longer, larger wavelengths.

2.  **The Earth's atmosphere:** Our atmosphere is made up of tiny molecules of gases, primarily nitrogen (about 78%) and oxygen (about 21%), along with smaller amounts of other gases and particles.

3.  **Scattering occurs:** When sunlight enters the Earth's atmosphere, it collides with these gas molecules. This collision causes the light to scatter, meaning it bounces off in all directions.

4.  **Wavelength matters:** Rayleigh scattering is more effective at scattering shorter wavelengths of light than longer ones. This is why blue and violet light are scattered much more than red and orange light.

5.  **Why blue, not violet?** Violet light is scattered even more than blue light, so you might wonder why the sky isn't violet. There are two main reasons:
    *   **Our eyes are more sensitive to blue:** Human eyes are more sensitive to blue light than to violet light.
    *   **Less violet light in sunlight:** The sun emits slightly less violet light than blue light.

**In summary:**

When sunlight hits the atmosphere, the blue wavelengths are scattered in all directions by the tiny gas molecules. This scattered blue light reaches our eyes from all parts of the sky, making it appear blue. The other colors, with their longer wavelengths, pass through the atmosphere more directly, and that's why they are more visible during sunrise and sunset when the light has to travel through more of the atmosphere."""
    for chunk in response:
        yield chunk
