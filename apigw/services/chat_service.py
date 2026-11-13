import json

from ollama import Client

from config import logger, settings
from redis_client import get_redis_client
from schemas.chat import ChatMessage

CHAT_SESSION_EXPIRY_SECONDS = 3600

ollama_client = Client(host=settings.ollama_host)


def generate_chat_stream(session_id: str, user_message: str):
    r = get_redis_client()
    session_key = f"chat:{session_id}"

    # 1. Retrieve history from Redis
    raw_history = r.get(session_key)

    # If no history exists, start with a system prompt
    messages = (
        json.loads(raw_history)
        if raw_history
        else [
            {
                "role": "system",
                "content": "You are a friendly English teacher who keeps responses concise, clear, and to the point.",
            }
        ]
    )

    # 2. Add the new user message
    messages.append({"role": "user", "content": user_message})

    # 3. Stream from Ollama
    stream = ollama_client.chat(
        model="gemma3:270m-it-qat",
        messages=messages,
        stream=True,
    )

    full_response = ""
    for chunk in stream:
        content = chunk["message"]["content"]
        full_response += content
        yield content

    # 4. Add the assistant's response to history and save
    messages.append({"role": "assistant", "content": full_response})

    # resets the countdown every time a message is sent
    r.setex(session_key, CHAT_SESSION_EXPIRY_SECONDS, json.dumps(messages))
    logger.info(f"Completed chat stream for session_id: {session_id}")


def get_chat_messages(session_id: str) -> list[ChatMessage]:
    r = get_redis_client()
    session_key = f"chat:{session_id}"
    raw_history = r.get(session_key)
    if not raw_history:
        return []
    try:
        messages = json.loads(raw_history)
        return [ChatMessage.model_validate(msg) for msg in messages]
    except Exception as e:
        logger.error(
            f"Failed to load chat messages for session_id {session_id}: {e}"
        )
        return []


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
