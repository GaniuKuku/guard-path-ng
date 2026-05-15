from app.llm.router import get_llm_provider


class LLMService:
    """
    GuardPath LLM abstraction layer.

    This isolates the application from any specific LLM provider
    (OpenAI, Gemini, Claude, etc.).
    """

    def __init__(self):
        # dynamically select provider (Gemini now, OpenAI later if needed)
        self.provider = get_llm_provider()

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.1
    ):
        """
        Generate SQL (or text) from LLM provider.

        Fully provider-agnostic.
        """

        response = await self.provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )

        return response
