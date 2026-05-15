import os
import google.generativeai as genai
from app.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):

    provider_name = "gemini"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-flash-lite-latest",
            system_instruction=None
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a SQL generation assistant.",
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs
    ):

        # 🔥 IMPORTANT FIX: separate system + user properly
        chat = self.model.start_chat()

        # system instruction goes FIRST message
        chat.send_message(system_prompt)

        # user prompt goes second
        response = chat.send_message(prompt)

        return {
            "text": response.text,
            "provider": self.provider_name
        }
