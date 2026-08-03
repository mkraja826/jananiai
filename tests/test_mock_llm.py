import asyncio

import pytest

from app.llm import LLMRequest, MockLLMProvider


def test_mock_provider_requires_synthetic_data() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(
        query="Synthetic question",
        approved_context=["Synthetic approved context"],
        synthetic_data_only=False,
    )

    with pytest.raises(ValueError, match="synthetic data only"):
        asyncio.run(provider.generate(request))


def test_mock_provider_refuses_without_approved_context() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(query="Synthetic question")

    response = asyncio.run(provider.generate(request))

    assert response.provider == "mock"
    assert response.citations == []
    assert "No approved context" in response.message


def test_mock_provider_returns_traceable_context_references() -> None:
    provider = MockLLMProvider()
    request = LLMRequest(
        query="Synthetic question",
        approved_context=["First", "Second"],
    )

    response = asyncio.run(provider.generate(request))

    assert response.citations == ["context:0", "context:1"]
    assert response.synthetic_only is True
