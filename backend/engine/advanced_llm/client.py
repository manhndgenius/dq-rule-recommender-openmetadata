"""LLM client độc lập với provider, hỗ trợ structured output."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Type

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Cấu hình cho LLM client."""

    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    )
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API", ""))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-flash"))
    timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3"))
    )


class LLMClient:
    """LLM client tương thích OpenAI, hỗ trợ structured output."""

    def __init__(self, config: LLMConfig | None = None):
        """Khởi tạo LLM client.

        Args:
            config: Cấu hình LLM. Sử dụng environment variables nếu không truyền vào.
        """
        self.config = config or LLMConfig()

    def _build_headers(self) -> dict[str, str]:
        """Tạo headers cho request."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        return headers

    def _build_base_url(self) -> str:
        """Tạo base URL cho API calls."""
        base = self.config.base_url.rstrip("/")
        if not base.endswith("/chat/completions"):
            base = f"{base}/chat/completions"
        return base

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
    ) -> BaseModel:
        """Tạo structured response từ LLM.

        Args:
            system_prompt: System prompt để hướng dẫn model.
            user_prompt: User prompt chứa request.
            response_model: Pydantic model để parse response.

        Returns:
            Response đã được parse thành Pydantic model chỉ định.

        Raises:
            httpx.HTTPStatusError: Khi có lỗi HTTP.
            LLMResponseError: Khi có lỗi từ LLM.
        """
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await self._call_with_retry(client, payload)
            return self._parse_response(response, response_model)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _call_with_retry(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Gọi API với retry logic."""
        url = self._build_base_url()
        headers = self._build_headers()

        logger.debug(f"LLM call to {url} với model {self.config.model}")

        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        try:
            import json

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON từ LLM: {e}")
            raise LLMResponseError(f"Invalid JSON response: {e}")

    def _parse_response(
        self, data: dict[str, Any], response_model: Type[BaseModel]
    ) -> BaseModel:
        """Parse LLM response thành Pydantic model."""
        try:
            return response_model.model_validate(data)
        except Exception as e:
            logger.error(f"Parse response thất bại: {e}")
            raise LLMResponseError(f"Parse response thất bại: {e}")


class LLMResponseError(Exception):
    """Lỗi khi LLM trả về response không hợp lệ."""

    pass
