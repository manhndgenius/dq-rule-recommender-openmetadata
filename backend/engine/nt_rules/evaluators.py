"""The 15 metadata-only NT governance evaluators."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from backend.contracts.nt_execution import NTMetadataContext, NTOutcome, NTRuleResult
from backend.engine.nt_rules.base import (
    column_map,
    filtered_columns,
    make_result,
    normalize_data_type,
    primary_key_columns,
)


def _reference_name(reference: Dict[str, Any]) -> str:
    return str(
        reference.get("fullyQualifiedName")
        or reference.get("displayName")
        or reference.get("name")
        or ""
    )


def _metadata_field(context: NTMetadataContext, field: str) -> Any:
    aliases = {
        "domain": "domains",
        "owner": "owners",
        "tableConstraints": "table_constraints",
    }
    attribute = aliases.get(field, field)
    return getattr(context, attribute, None)


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def evaluate_table_naming(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT1_TableNaming: kiểm tra tên bảng khớp regex quy ước (snake_case)."""
    pattern = str(config.get("nameRegex") or r"^[a-z][a-z0-9_]*$")
    valid = re.fullmatch(pattern, context.table_name) is not None
    return make_result(
        "NT1_TableNaming",
        NTOutcome.PASS if valid else NTOutcome.FAIL,
        (
            f"Tên bảng '{context.table_name}' đúng chuẩn."
            if valid
            else f"Tên bảng '{context.table_name}' không khớp regex {pattern}."
        ),
        expected={"nameRegex": pattern},
        observed={"tableName": context.table_name},
    )


def evaluate_column_naming(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT2_ColumnNaming: kiểm tra tên các cột nghiệp vụ khớp regex quy ước."""
    pattern = str(config.get("nameRegex") or r"^[a-z][a-z0-9_]*$")
    columns = filtered_columns(
        context,
        config.get("excludedColumns") or [],
        config.get("excludedPatterns") or [],
    )
    invalid = [
        column.name
        for column in columns
        if re.fullmatch(pattern, column.name) is None
    ]
    return make_result(
        "NT2_ColumnNaming",
        NTOutcome.FAIL if invalid else NTOutcome.PASS,
        (
            f"Có {len(invalid)} cột không đúng chuẩn đặt tên."
            if invalid
            else "Tất cả cột đều đúng chuẩn đặt tên."
        ),
        expected={"nameRegex": pattern},
        observed={"invalidColumns": invalid, "checkedColumns": len(columns)},
        affected_columns=invalid,
    )


def evaluate_boolean_naming(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT3_BooleanNaming: cột BOOLEAN phải bắt đầu bằng prefix is_, has_ hoặc can_."""
    # BOOLEAN and BOOL are a fixed governance invariant, not user config.
    boolean_types = {
        normalize_data_type(value) for value in ("BOOLEAN", "BOOL")
    }
    prefixes = [
        str(prefix).lower()
        for prefix in config.get("allowedPrefixes") or ["is_", "has_", "can_"]
    ]
    excluded = {str(name).lower() for name in config.get("excludedColumns") or []}
    boolean_columns = [
        column
        for column in context.columns
        if normalize_data_type(column.data_type) in boolean_types
        and column.name.lower() not in excluded
    ]
    invalid = [
        column.name
        for column in boolean_columns
        if not any(column.name.lower().startswith(prefix) for prefix in prefixes)
    ]
    return make_result(
        "NT3_BooleanNaming",
        NTOutcome.FAIL if invalid else NTOutcome.PASS,
        (
            f"Có {len(invalid)} cột boolean không có prefix hợp lệ."
            if invalid
            else "Các cột boolean đều có prefix hợp lệ."
        ),
        expected={"allowedPrefixes": prefixes},
        observed={"booleanColumns": [c.name for c in boolean_columns]},
        affected_columns=invalid,
    )


def evaluate_audit_columns(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT4_AuditColumns: kiểm tra bảng có đủ danh sách cột audit được cấu hình."""
    required = [str(name) for name in config.get("requiredColumns") or []]
    # NT4 always compares audit-column names case-insensitively.
    case_sensitive = False
    available = {
        column.name if case_sensitive else column.name.lower()
        for column in context.columns
    }
    missing = [
        name
        for name in required
        if (name if case_sensitive else name.lower()) not in available
    ]
    require_all = bool(config.get("requireAll", True))
    passed = not missing if require_all else len(missing) < len(required)
    return make_result(
        "NT4_AuditColumns",
        NTOutcome.PASS if passed else NTOutcome.FAIL,
        (
            "Bảng có đủ các cột audit yêu cầu."
            if passed
            else f"Bảng thiếu các cột audit: {', '.join(missing)}."
        ),
        expected={"requiredColumns": required, "requireAll": require_all},
        observed={"missingColumns": missing},
        affected_columns=missing,
    )


def evaluate_datetime_columns(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT5_DateTimeColumns: đối chiếu suffix _at/_date với kiểu timestamp/date tương ứng."""
    excluded = {str(name).lower() for name in config.get("excludedColumns") or []}
    violations: List[Dict[str, Any]] = []
    mappings = config.get("suffixTypeMappings") or []
    for column in context.columns:
        if column.name.lower() in excluded:
            continue
        for mapping in mappings:
            suffix = str(mapping.get("suffix") or "")
            if not suffix or not column.name.lower().endswith(suffix.lower()):
                continue
            allowed = {
                normalize_data_type(value)
                for value in mapping.get("allowedTypes") or []
            }
            actual = normalize_data_type(column.data_type)
            if actual not in allowed:
                violations.append(
                    {
                        "column": column.name,
                        "actualType": actual,
                        "allowedTypes": sorted(allowed),
                        "suffix": suffix,
                    }
                )
            break
    affected = [item["column"] for item in violations]
    return make_result(
        "NT5_DateTimeColumns",
        NTOutcome.FAIL if violations else NTOutcome.PASS,
        (
            f"Có {len(violations)} cột ngày giờ sai kiểu dữ liệu."
            if violations
            else "Các cột ngày giờ đúng kiểu dữ liệu theo suffix."
        ),
        expected={"suffixTypeMappings": mappings},
        observed={"violations": violations},
        affected_columns=affected,
    )


def evaluate_soft_delete(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT6_SoftDelete: bảng phải có ít nhất một chiến lược soft delete hợp lệ."""
    columns = column_map(context)
    matched: List[str] = []
    strategies = config.get("acceptedStrategies") or []
    for strategy in strategies:
        name = str(strategy.get("column") or "")
        column = columns.get(name.lower())
        allowed = {
            normalize_data_type(value)
            for value in strategy.get("allowedTypes") or []
        }
        if column and normalize_data_type(column.data_type) in allowed:
            matched.append(name)
    return make_result(
        "NT6_SoftDelete",
        NTOutcome.PASS if matched else NTOutcome.FAIL,
        (
            f"Bảng hỗ trợ soft delete qua {', '.join(matched)}."
            if matched
            else "Bảng chưa có chiến lược soft delete hợp lệ."
        ),
        expected={"acceptedStrategies": strategies},
        observed={"matchedStrategies": matched},
    )


def evaluate_table_comment(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT7_TableComment: kiểm tra Description, Domain, Owner và độ dài mô tả bảng."""
    required = [str(field) for field in config.get("requiredFields") or []]
    minimum_length = int(config.get("minimumDescriptionLength", 1))
    missing = [
        field
        for field in required
        if not _is_present(_metadata_field(context, field))
    ]
    if "description" in required and context.description:
        if len(context.description.strip()) < minimum_length:
            missing.append("description")
    missing = list(dict.fromkeys(missing))
    return make_result(
        "NT7_TableComment",
        NTOutcome.FAIL if missing else NTOutcome.PASS,
        (
            f"Table thiếu metadata: {', '.join(missing)}."
            if missing
            else "Table có đầy đủ metadata bắt buộc."
        ),
        expected={
            "requiredFields": required,
            "minimumDescriptionLength": minimum_length,
        },
        observed={"missingFields": missing},
    )


def evaluate_primary_key_standard(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT8_PrimaryKeyStandard: PK phải đúng tên, kiểu, số cột và tên constraint cấu hình."""
    pk_columns = primary_key_columns(context)
    expected_column = str(config.get("expectedColumn") or "id")
    allow_composite = bool(config.get("allowComposite", False))
    expected_types = {
        normalize_data_type(value)
        for value in config.get("expectedTypes") or ["UUID"]
    }
    columns = column_map(context)
    reasons: List[str] = []
    if not pk_columns:
        reasons.append("missing_primary_key")
    if not allow_composite and len(pk_columns) > 1:
        reasons.append("composite_primary_key")
    if pk_columns and expected_column.lower() not in {
        name.lower() for name in pk_columns
    }:
        reasons.append("unexpected_primary_key_column")
    expected_pk = columns.get(expected_column.lower())
    actual_type = normalize_data_type(expected_pk.data_type) if expected_pk else None
    if expected_pk and actual_type not in expected_types:
        reasons.append("unexpected_primary_key_type")

    constraint_pattern = config.get("expectedConstraintNamePattern")
    if constraint_pattern:
        pk_constraints = [
            constraint
            for constraint in context.table_constraints
            if str(constraint.get("constraintType") or "").upper()
            == "PRIMARY_KEY"
        ]
        if not pk_constraints or not any(
            re.fullmatch(str(constraint_pattern), str(item.get("name") or ""))
            for item in pk_constraints
        ):
            reasons.append("unexpected_constraint_name")

    return make_result(
        "NT8_PrimaryKeyStandard",
        NTOutcome.FAIL if reasons else NTOutcome.PASS,
        (
            f"Primary Key không đạt chuẩn: {', '.join(reasons)}."
            if reasons
            else "Primary Key đạt chuẩn."
        ),
        expected={
            "column": expected_column,
            "types": sorted(expected_types),
            "allowComposite": allow_composite,
        },
        observed={
            "primaryKeyColumns": pk_columns,
            "primaryKeyType": actual_type,
            "violations": reasons,
        },
        affected_columns=pk_columns,
    )


def evaluate_primary_key_missing(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT9_PrimaryKeyMissing: kiểm tra bảng có khai báo ít nhất một Primary Key."""
    del config
    pk_columns = primary_key_columns(context)
    return make_result(
        "NT9_PrimaryKeyMissing",
        NTOutcome.PASS if pk_columns else NTOutcome.FAIL,
        (
            f"Bảng có Primary Key: {', '.join(pk_columns)}."
            if pk_columns
            else "Bảng chưa có Primary Key."
        ),
        expected={"primaryKeyRequired": True},
        observed={"primaryKeyColumns": pk_columns},
        affected_columns=pk_columns,
    )


def evaluate_column_description(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT10_ColumnDescription: cột nghiệp vụ phải có description đủ độ dài tối thiểu."""
    columns = filtered_columns(
        context,
        config.get("excludedColumns") or [],
        config.get("excludedPatterns") or [],
    )
    minimum_length = int(config.get("minimumDescriptionLength", 1))
    missing = [
        column.name
        for column in columns
        if not column.description
        or len(column.description.strip()) < minimum_length
    ]
    return make_result(
        "NT10_ColumnDescription",
        NTOutcome.FAIL if missing else NTOutcome.PASS,
        (
            f"Có {len(missing)} cột nghiệp vụ thiếu description."
            if missing
            else "Các cột nghiệp vụ có đầy đủ description."
        ),
        expected={"minimumDescriptionLength": minimum_length},
        observed={"missingDescriptionColumns": missing},
        affected_columns=missing,
    )


def evaluate_table_too_wide(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT11_TableTooWide: phân loại PASS/WARNING/FAIL theo tổng số cột của bảng."""
    excluded = {str(name).lower() for name in config.get("excludedColumns") or []}
    column_count = sum(
        1 for column in context.columns if column.name.lower() not in excluded
    )
    warning_threshold = int(config.get("warningThreshold", 50))
    failure_threshold = int(config.get("failureThreshold", 80))
    if warning_threshold > failure_threshold:
        return make_result(
            "NT11_TableTooWide",
            NTOutcome.ERROR,
            "Cấu hình threshold không hợp lệ.",
            error_code="INVALID_THRESHOLDS",
        )
    if column_count <= warning_threshold:
        outcome = NTOutcome.PASS
    elif column_count <= failure_threshold:
        outcome = NTOutcome.WARNING
    else:
        outcome = NTOutcome.FAIL
    return make_result(
        "NT11_TableTooWide",
        outcome,
        f"Bảng có {column_count} cột: {outcome.value}.",
        expected={
            "warningThreshold": warning_threshold,
            "failureThreshold": failure_threshold,
        },
        observed={"columnCount": column_count},
    )


def evaluate_domain_owner(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT12_DomainOwner: kiểm tra Domain/Owner bắt buộc và domain phải nằm trong whitelist."""
    required = [str(field) for field in config.get("requiredFields") or []]
    minimum_owner_count = int(config.get("minimumOwnerCount", 1))
    missing = [
        field
        for field in required
        if not _is_present(_metadata_field(context, field))
    ]
    if "owners" in required and len(context.owners) < minimum_owner_count:
        missing.append("owners")

    # Domain phải nằm trong whitelist (dùng regex match, không phân biệt hoa thường)
    allowed_domains = [str(value) for value in config.get("allowedDomains") or []]
    actual_domain_names = [_reference_name(item) for item in context.domains]
    invalid_domains: List[str] = []

    for domain_name in actual_domain_names:
        # Check xem domain có khớp với bất kỳ allowed domain nào không (regex, ignore case)
        matched = False
        domain_lower = domain_name.lower()
        for allowed in allowed_domains:
            # Tạo regex pattern từ allowed domain, escape special chars rồi thêm flexibility
            # VD: "Bệnh nhân & Định danh" sẽ khớp với "Bệnh nhân & Định danh", "bệnh nhân & định danh", etc.
            pattern = re.escape(allowed.lower())
            if re.search(pattern, domain_lower):
                matched = True
                break
        if not matched:
            invalid_domains.append(domain_name)

    violations = list(dict.fromkeys(missing))
    if invalid_domains:
        violations.append("domains_not_allowed")
    return make_result(
        "NT12_DomainOwner",
        NTOutcome.FAIL if violations else NTOutcome.PASS,
        (
            f"Domain/Owner không đạt chuẩn: {', '.join(violations)}."
            if violations
            else "Domain và Owner đạt chuẩn."
        ),
        expected={
            "requiredFields": required,
            "allowedDomains": allowed_domains,
            "minimumOwnerCount": minimum_owner_count,
        },
        observed={
            "domains": actual_domain_names,
            "ownerCount": len(context.owners),
            "invalidDomains": invalid_domains,
        },
    )


def evaluate_nullable_rate(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT13_NullableRate: phân loại PASS/WARNING/FAIL theo tỷ lệ cột cho phép null."""
    included = {str(name).lower() for name in config.get("includedColumns") or []}
    excluded = {str(name).lower() for name in config.get("excludedColumns") or []}
    columns = [
        column
        for column in context.columns
        if column.name.lower() not in excluded
        and (not included or column.name.lower() in included)
    ]
    if not columns:
        return make_result(
            "NT13_NullableRate",
            NTOutcome.ERROR,
            "Không có cột để tính tỷ lệ nullable.",
            error_code="NO_COLUMNS_TO_EVALUATE",
        )
    non_nullable_constraints = {"NOT_NULL", "PRIMARY_KEY"}
    nullable = [
        column.name
        for column in columns
        if str(column.constraint or "").upper() not in non_nullable_constraints
    ]
    rate = len(nullable) / len(columns) * 100.0
    warning_threshold = float(config.get("warningThreshold", 50.0))
    failure_threshold = float(config.get("failureThreshold", 80.0))
    if warning_threshold > failure_threshold:
        return make_result(
            "NT13_NullableRate",
            NTOutcome.ERROR,
            "Cấu hình threshold không hợp lệ.",
            error_code="INVALID_THRESHOLDS",
        )
    if rate <= warning_threshold:
        outcome = NTOutcome.PASS
    elif rate <= failure_threshold:
        outcome = NTOutcome.WARNING
    else:
        outcome = NTOutcome.FAIL
    return make_result(
        "NT13_NullableRate",
        outcome,
        f"Tỷ lệ cột nullable là {rate:.2f}%: {outcome.value}.",
        expected={
            "warningThreshold": warning_threshold,
            "failureThreshold": failure_threshold,
        },
        observed={
            "nullableRate": round(rate, 2),
            "nullableColumns": nullable,
            "checkedColumns": len(columns),
        },
        affected_columns=nullable,
    )


def evaluate_business_key(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT14_BusinessKey: tìm số lượng Business Key tối thiểu theo pattern tên cột."""
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in config.get("namePatterns") or []]
    excluded = {str(name).lower() for name in config.get("excludedColumns") or []}
    matches = [
        column.name
        for column in context.columns
        if column.name.lower() not in excluded
        and any(pattern.search(column.name) for pattern in patterns)
    ]
    minimum = int(config.get("minimumMatches", 1))
    outcome = NTOutcome.PASS if len(matches) >= minimum else NTOutcome.FAIL
    return make_result(
        "NT14_BusinessKey",
        outcome,
        (
            f"Tìm thấy Business Key: {', '.join(matches)}."
            if matches
            else "Không tìm thấy cột Business Key theo pattern cấu hình."
        ),
        expected={
            "namePatterns": [pattern.pattern for pattern in patterns],
            "minimumMatches": minimum,
        },
        observed={"matchedColumns": matches},
        affected_columns=matches,
    )


def evaluate_duplicate_table(
    context: NTMetadataContext,
    config: Dict[str, Any],
) -> NTRuleResult:
    """NT16_DuplicateTable: phát hiện bảng trùng tên ở các schema trong cùng database."""
    if not context.catalog_tables:
        return make_result(
            "NT16_DuplicateTable",
            NTOutcome.ERROR,
            "Chưa có catalog table trong phạm vi database để kiểm tra trùng tên.",
            error_code="CATALOG_SCOPE_NOT_LOADED",
        )
    case_sensitive = bool(config.get("caseSensitive", False))
    current_name = context.table_name if case_sensitive else context.table_name.lower()
    excluded_schemas = {
        str(value) if case_sensitive else str(value).lower()
        for value in config.get("excludedSchemas") or []
    }
    duplicates: List[str] = []
    for table in context.catalog_tables:
        fqn = str(table.get("fullyQualifiedName") or table.get("fqn") or "")
        name = str(table.get("name") or (fqn.split(".")[-1] if fqn else ""))
        schema_ref = table.get("databaseSchema") or {}
        schema = (
            _reference_name(schema_ref)
            if isinstance(schema_ref, dict)
            else str(schema_ref)
        )
        if not schema and fqn:
            schema = ".".join(fqn.split(".")[:-1])
        comparable_schema = schema if case_sensitive else schema.lower()
        comparable_name = name if case_sensitive else name.lower()
        if comparable_schema in excluded_schemas:
            continue
        if comparable_name == current_name and fqn != context.table_fqn:
            duplicates.append(fqn or name)
    return make_result(
        "NT16_DuplicateTable",
        NTOutcome.FAIL if duplicates else NTOutcome.PASS,
        (
            f"Tên bảng xuất hiện thêm ở {len(duplicates)} schema khác."
            if duplicates
            else "Không phát hiện table trùng tên trong database."
        ),
        expected={"uniqueWithin": config.get("comparisonScope", "DATABASE")},
        observed={"duplicateTables": duplicates},
    )
