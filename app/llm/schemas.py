from pydantic import BaseModel
from typing import Optional


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 512


class LLMResponse(BaseModel):
    content: str
