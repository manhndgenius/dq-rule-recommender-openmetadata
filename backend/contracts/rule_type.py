"""Enum định nghĩa các loại advanced rule được hỗ trợ."""

from enum import Enum


class AdvancedRuleType(str, Enum):
    """Các loại advanced rule được hỗ trợ cho rule discovery."""

    CROSS_COLUMN = "CROSS_COLUMN"
    """Quan hệ logic giữa hai hoặc nhiều cột.

    Ví dụ: total_amount = quantity * unit_price
    """

    CONDITIONAL_DEPENDENCY = "CONDITIONAL_DEPENDENCY"
    """Quan hệ IF-THEN giữa các cột.

    Ví dụ: IF status = 'completed' THEN completed_at IS NOT NULL
    """

    TEMPORAL = "TEMPORAL"
    """Quan hệ thứ tự thời gian giữa các cột ngày/giờ.

    Ví dụ: delivery_date >= order_date
    """
