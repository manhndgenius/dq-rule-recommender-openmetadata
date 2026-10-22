"""LLM client độc lập với provider, hỗ trợ structured output."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Type

import httpx
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
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
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "1"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1024"))
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
            "max_tokens": self.config.max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await self._call_with_retry(client, payload)
            return self._parse_response(response, response_model)

    async def _call_with_retry(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Gọi API với retry logic."""
        url = self._build_base_url()
        headers = self._build_headers()

        logger.debug(f"LLM call to {url} với model {self.config.model}")

        # max_retries is the number of retries after the initial request.
        total_attempts = max(1, self.config.max_retries + 1)
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.HTTPStatusError)
            ),
            stop=stop_after_attempt(total_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

        response: httpx.Response | None = None
        async for attempt in retrying:
            with attempt:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

        if response is None:  # Defensive guard; AsyncRetrying always attempts once.
            raise LLMResponseError("LLM request did not produce a response")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        return self._clean_and_parse_json(content)

    @staticmethod
    def _clean_and_parse_json(content: str) -> dict[str, Any]:
        """Làm sạch output và parse JSON an toàn (loại bỏ thinking tags, markdown fences)."""
        import json
        import re

        cleaned = (content or "").strip()

        # 1. Loại bỏ các thẻ suy nghĩ <thought>...</thought> hoặc <think>...</think>
        if "<thought>" in cleaned or "<think>" in cleaned:
            logger.warning("[GUARDRAIL CAN THIỆP] Phát hiện và đã bóc tách thẻ suy nghĩ (<thought>/<think>) từ LLM output")
        cleaned = re.sub(r"<thought>.*?</thought>", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)

        # 2. Loại bỏ markdown code blocks ```json ... ``` hoặc ``` ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()

        # 3. Thử parse trực tiếp
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 4. Tìm khối JSON { ... } lớn nhất nếu có text thừa xung quanh
        match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if match:
            candidate_json = match.group(1).strip()
            try:
                return json.loads(candidate_json)
            except json.JSONDecodeError:
                pass

        logger.warning(f"Invalid JSON từ LLM: {content[:200]}")
        raise LLMResponseError(f"Invalid JSON response: {content[:200]}")

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
