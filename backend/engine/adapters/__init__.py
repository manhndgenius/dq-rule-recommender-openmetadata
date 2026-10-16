"""Adapters exposing every recommendation engine through one contract."""

from backend.engine.adapters.advanced_adapter import AdvancedGenerationAdapter
from backend.engine.adapters.basic_adapter import BasicGenerationAdapter
from backend.engine.adapters.statistical_adapter import StatisticalGenerationAdapter

__all__ = [
    "AdvancedGenerationAdapter",
    "BasicGenerationAdapter",
    "StatisticalGenerationAdapter",
]
