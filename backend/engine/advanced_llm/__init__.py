"""Advanced LLM module cho rule discovery và generation."""

from backend.engine.advanced_llm.client import LLMClient, LLMConfig
from backend.engine.advanced_llm.router import AdvancedRuleRouter, RouterError
from backend.engine.advanced_llm.base_generator import BaseRuleGenerator
from backend.engine.advanced_llm.cross_column_generator import (
    CrossColumnGenerator,
    GeneratorError,
)
from backend.engine.advanced_llm.conditional_dependency_generator import (
    ConditionalDependencyGenerator,
)
from backend.engine.advanced_llm.temporal_generator import TemporalGenerator

# Re-export models từ contracts để tiện import
from backend.contracts import (
    AdvancedRuleType,
    RouterCandidate,
    RouterResult,
    GeneratedRule,
    GeneratorResult,
)

__all__ = [
    # Client & Config
    "LLMClient",
    "LLMConfig",
    # Router
    "AdvancedRuleRouter",
    "RouterError",
    # Generators
    "BaseRuleGenerator",
    "CrossColumnGenerator",
    "ConditionalDependencyGenerator",
    "TemporalGenerator",
    "GeneratorError",
    # Models
    "AdvancedRuleType",
    "RouterCandidate",
    "RouterResult",
    "GeneratedRule",
    "GeneratorResult",
]
