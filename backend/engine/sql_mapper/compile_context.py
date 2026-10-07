"""Compile Context cho SQL Mapper.

Quản lý việc binding parameters để tránh SQL injection.
Literal values được thay thế bằng placeholders (:param_name).
"""

from __future__ import annotations

from typing import Any


class CompileContext:
    """Context cho việc compile rule thành SQL.

    Quản lý parameters và counter để tạo unique parameter names.
    """

    def __init__(self) -> None:
        """Khởi tạo compile context."""
        self.params: dict[str, Any] = {}
        self._counter: int = 0

    def add_param(self, value: Any) -> str:
        """Thêm một literal value vào params, trả về placeholder.

        Args:
            value: Giá trị cần bind (string, number, etc.)

        Returns:
            Parameter placeholder string, ví dụ ":rule_param_1"

        Example:
            >>> ctx = CompileContext()
            >>> placeholder = ctx.add_param("USD")
            >>> placeholder
            ':rule_param_1'
            >>> ctx.params
            {'rule_param_1': 'USD'}
        """
        self._counter += 1
        key = f"rule_param_{self._counter}"
        self.params[key] = value
        return f":{key}"

    def reset(self) -> None:
        """Reset context để tái sử dụng."""
        self.params = {}
        self._counter = 0

    @property
    def param_count(self) -> int:
        """Số lượng parameters hiện tại."""
        return len(self.params)

    def __repr__(self) -> str:
        return f"CompileContext(params={self.params}, counter={self._counter})"
