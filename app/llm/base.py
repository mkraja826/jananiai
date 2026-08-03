from typing import Protocol

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    approved_context: list[str] = Field(default_factory=list, max_length=20)
    language: str = Field(default="en", pattern="^(en|te)$")
    synthetic_data_only: bool = True


class LLMResponse(BaseModel):
    message: str
    citations: list[str]
    provider: str
    model: str
    synthetic_only: bool


class LLMProvider(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a typed response from approved context."""
        ...
