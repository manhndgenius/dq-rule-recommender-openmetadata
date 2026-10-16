"""Metadata-only NT governance rule evaluators."""

from backend.engine.nt_rules.registry import NT_RULE_REGISTRY, evaluate_nt_rule

__all__ = ["NT_RULE_REGISTRY", "evaluate_nt_rule"]
