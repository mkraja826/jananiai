from app.llm.base import LLMRequest, LLMResponse


class MockLLMProvider:
    """Free deterministic provider for tests. It must never process real patient data."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not request.synthetic_data_only:
            raise ValueError("Mock provider accepts synthetic data only")
        if not request.approved_context:
            return LLMResponse(
                message="[MOCK] No approved context was supplied, so no answer was generated.",
                citations=[],
                provider="mock",
                model="deterministic-mock-v1",
                synthetic_only=True,
            )
        return LLMResponse(
            message="[MOCK] A response would be generated only from the approved context.",
            citations=[f"context:{index}" for index, _ in enumerate(request.approved_context)],
            provider="mock",
            model="deterministic-mock-v1",
            synthetic_only=True,
        )
