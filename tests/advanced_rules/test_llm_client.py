"""Unit tests cho LLM client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel

from backend.engine.advanced_llm.client import LLMClient, LLMConfig, LLMResponseError


class MockResponse(BaseModel):
    """Mock response model cho testing."""
    message: str
    status: str


class TestLLMConfig:
    """Tests cho LLMConfig."""

    def test_default_config(self):
        """Default config nên sử dụng environment variables."""
        config = LLMConfig()
        assert config.base_url is not None
        assert config.timeout_seconds > 0
        assert config.max_retries >= 0

    def test_custom_config(self):
        """Custom config nên override defaults."""
        config = LLMConfig(
            base_url="https://custom.api.com",
            model="gpt-4",
            timeout_seconds=60,
            max_retries=5,
        )
        assert config.base_url == "https://custom.api.com"
        assert config.model == "gpt-4"
        assert config.timeout_seconds == 60
        assert config.max_retries == 5


class TestLLMClient:
    """Tests cho LLMClient."""

    def test_build_headers(self):
        """Client nên build đúng headers."""
        config = LLMConfig(api_key="test-key")
        client = LLMClient(config)
        headers = client._build_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-key"

    def test_build_base_url(self):
        """Client nên build đúng base URL."""
        config = LLMConfig(base_url="https://api.example.com")
        client = LLMClient(config)
        url = client._build_base_url()
        assert url.endswith("/chat/completions")

    def test_build_base_url_already_complete(self):
        """Client nên xử lý URLs đã có /chat/completions."""
        config = LLMConfig(base_url="https://api.example.com/v1/chat/completions")
        client = LLMClient(config)
        url = client._build_base_url()
        assert url == "https://api.example.com/v1/chat/completions"

    def test_parse_response(self):
        """Client nên parse response thành Pydantic model."""
        config = LLMConfig()
        client = LLMClient(config)

        data = {"message": "hello", "status": "ok"}
        result = client._parse_response(data, MockResponse)

        assert isinstance(result, MockResponse)
        assert result.message == "hello"
        assert result.status == "ok"

    def test_parse_invalid_response(self):
        """Client nên raise error cho invalid response."""
        config = LLMConfig()
        client = LLMClient(config)

        with pytest.raises(LLMResponseError):
            client._parse_response({"invalid": "data"}, MockResponse)

    @pytest.mark.asyncio
    async def test_generate_structured_success(self):
        """Nên generate structured response thành công."""
        config = LLMConfig(api_key="test-key", model="gpt-4")
        client = LLMClient(config)

        mock_response_data = {"message": "success", "status": "ok"}

        with patch.object(client, "_call_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response_data

            result = await client.generate_structured(
                system_prompt="You are a test.",
                user_prompt="Test prompt",
                response_model=MockResponse,
            )

            assert isinstance(result, MockResponse)
            assert result.message == "success"

    @pytest.mark.asyncio
    async def test_generate_structured_invalid_json(self):
        """Nên raise error cho invalid JSON response."""
        config = LLMConfig(api_key="test-key")
        client = LLMClient(config)

        with patch.object(client, "_call_with_retry", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = LLMResponseError("Invalid JSON")

            with pytest.raises(LLMResponseError):
                await client.generate_structured(
                    system_prompt="Test",
                    user_prompt="Test",
                    response_model=MockResponse,
                )
