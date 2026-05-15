import os
import google.generativeai as genai

from app.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):

    provider_name = "gemini"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment variables")

        genai.configure(api_key=api_key)

        # You can switch model anytime here
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a SQL generation assistant.",
        temperature: float = 0.2,
        max_tokens: int = 512,
        model: str = "gemini-1.5-flash",
        **kwargs
    ):
        full_prompt = f"""
{system_prompt}

Task:
{prompt}

Return only SQL query.
"""

        response = self.model.generate_content(full_prompt)

        return {
            "text": response.text,
            "provider": self.provider_name
        }
