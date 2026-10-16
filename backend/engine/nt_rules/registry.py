"""Registry and dispatch for NT rule evaluators."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from backend.contracts.nt_execution import (
    NTMetadataContext,
    NTRuleResult,
    NTTestDefinition,
)
from backend.engine.nt_rules.config import NTRuleConfigResolver
from backend.engine.nt_rules.evaluators import (
    evaluate_audit_columns,
    evaluate_boolean_naming,
    evaluate_business_key,
    evaluate_column_description,
    evaluate_column_naming,
    evaluate_datetime_columns,
    evaluate_domain_owner,
    evaluate_duplicate_table,
    evaluate_nullable_rate,
    evaluate_primary_key_missing,
    evaluate_primary_key_standard,
    evaluate_soft_delete,
    evaluate_table_comment,
    evaluate_table_naming,
    evaluate_table_too_wide,
)

NTEvaluator = Callable[[NTMetadataContext, Dict[str, Any]], NTRuleResult]

NT_RULE_REGISTRY: Dict[str, NTEvaluator] = {
    "NT1_TableNaming": evaluate_table_naming,
    "NT2_ColumnNaming": evaluate_column_naming,
    "NT3_BooleanNaming": evaluate_boolean_naming,
    "NT4_AuditColumns": evaluate_audit_columns,
    "NT5_DateTimeColumns": evaluate_datetime_columns,
    "NT6_SoftDelete": evaluate_soft_delete,
    "NT7_TableComment": evaluate_table_comment,
    "NT8_PrimaryKeyStandard": evaluate_primary_key_standard,
    "NT9_PrimaryKeyMissing": evaluate_primary_key_missing,
    "NT10_ColumnDescription": evaluate_column_description,
    "NT11_TableTooWide": evaluate_table_too_wide,
    "NT12_DomainOwner": evaluate_domain_owner,
    "NT13_NullableRate": evaluate_nullable_rate,
    "NT14_BusinessKey": evaluate_business_key,
    "NT16_DuplicateTable": evaluate_duplicate_table,
}


def evaluate_nt_rule(
    definition: NTTestDefinition,
    context: NTMetadataContext,
    config: Optional[Dict[str, Any]] = None,
    resolver: Optional[NTRuleConfigResolver] = None,
) -> NTRuleResult:
    evaluator = NT_RULE_REGISTRY.get(definition.name)
    if evaluator is None:
        raise KeyError(f"No NT evaluator registered for {definition.name}")
    effective_config = (
        config
        if config is not None
        else (resolver or NTRuleConfigResolver()).resolve(definition)
    )
    return evaluator(context, effective_config)
