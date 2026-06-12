from collections.abc import Generator

from google import genai
from google.genai import types

from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)


def call_llm(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt
    )
    return response.text


def call_llm_stream(
    prompt: str, model: str = "gemini-2.5-flash"
) -> Generator[str, None, None]:
    response = client.models.generate_content_stream(
        model=model, contents=prompt
    )
    for chunk in response:
        if chunk.text is not None:
            yield chunk.text


def call_llm_with_tools(
    contents: list,
    tools: list[types.Tool],
    system_instruction: str | None = None,
    model: str = "gemini-2.5-flash-lite",
):
    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=system_instruction,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    )
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
