# base.py

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    """

    provider_name: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        """
        pass
