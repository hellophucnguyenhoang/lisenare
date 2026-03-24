from ollama import AsyncClient

client = AsyncClient()


async def generate_ollama_stream(chat_history: list[dict]):
    # Pass the entire list of messages to the model
    async for chunk in await client.chat(
        model="gemma3:270m", messages=chat_history, stream=True
    ):
        content = chunk["message"]["content"]
        if content:
            yield content
