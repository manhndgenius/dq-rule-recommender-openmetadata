"""Regression tests for compact JSON sent to advanced LLM calls."""

import json

import pytest

from backend.engine.advanced_llm.conditional_dependency_generator import (
    ConditionalDependencyGenerator,
)
from backend.engine.advanced_llm.cross_column_generator import CrossColumnGenerator
from backend.engine.advanced_llm.temporal_generator import TemporalGenerator


@pytest.mark.parametrize(
    "builder",
    [
        TemporalGenerator._build_user_prompt,
        CrossColumnGenerator._build_user_prompt,
        ConditionalDependencyGenerator._build_user_prompt,
    ],
)
def test_generator_user_prompts_are_compact_utf8_json(builder):
    context = {"table": {"description": "dữ liệu y tế"}, "columns": ["income"]}

    prompt = builder(None, context)

    assert json.loads(prompt) == context
    assert "\n" not in prompt
    assert ": " not in prompt
    assert "dữ liệu y tế" in prompt
