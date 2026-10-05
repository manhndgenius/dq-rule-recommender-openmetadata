from typing import List, Any
from backend.engine.base import BaseRuleEngine
from backend.contracts.table_context import TableContext, ColumnContext
from backend.contracts.candidate_rule import CandidateRule
from backend.config import settings

class BasicRuleEngine(BaseRuleEngine):
    """
    Basic Rule Engine (Heuristic & Profiling-based).
    Hiện thực hóa các luật chất lượng dữ liệu cơ bản theo LLD Mục 11:
    1. NOT_NULL (columnValuesToBeNotNull)
    2. UNIQUE (columnValuesToBeUnique)
    3. VALUE_BETWEEN (columnValuesToBeBetween)
    4. VALUES_IN_SET (columnValuesToBeInSet)
    5. LENGTH_BETWEEN (columnValuesLengthToBeBetween)
    6. TABLE_ROW_COUNT (tableRowCountToBeBetween)
    """

    def generate_candidates(self, context: TableContext) -> List[CandidateRule]:
        candidates: List[CandidateRule] = []

        if context.row_count <= 0 and not context.columns:
            return candidates

        # 1. Table-level rule: Table Row Count Between
        if context.row_count > 0:
            candidates.append(self._generate_row_count_rule(context))

        # 2. Column-level rules
        for col in context.columns:
            # Rule 1: NOT NULL
            not_null_rule = self._generate_not_null_rule(context, col)
            if not_null_rule:
                candidates.append(not_null_rule)

            # Rule 2: UNIQUE
            unique_rule = self._generate_unique_rule(context, col)
            if unique_rule:
                candidates.append(unique_rule)

            # Rule 3: VALUE BETWEEN (Numeric / Date)
            between_rule = self._generate_between_rule(context, col)
            if between_rule:
                candidates.append(between_rule)

            # Rule 4: VALUES IN SET (Low Cardinality)
            in_set_rule = self._generate_in_set_rule(context, col)
            if in_set_rule:
                candidates.append(in_set_rule)

            # Rule 5: LENGTH BETWEEN (String)
            length_rule = self._generate_length_rule(context, col)
            if length_rule:
                candidates.append(length_rule)

        return candidates

    def _generate_not_null_rule(self, context: TableContext, col: ColumnContext) -> CandidateRule | None:
        """
        Rule: columnValuesToBeNotNull
        Điều kiện: row_count > 0 và null_count == 0 hoặc null_ratio == 0
        """
        prof = col.profile
        if prof.row_count > 0 and (prof.null_count == 0 or prof.null_ratio == 0.0):
            confidence = 1.0 if not col.nullable else 0.95
            reason = (
                f"Cột '{col.name}' đóng vai trò khóa chính và không có bản ghi nào bị rỗng."
                if col.is_primary_key
                else f"Không phát hiện giá trị null nào trong toàn bộ {prof.row_count:,} dòng của cột '{col.name}'."
            )
            return CandidateRule(
                rule_type="columnValuesToBeNotNull",
                description="Cột không được để trống (Not Null)",
                target_columns=[col.name],
                parameters={},
                engine="BASIC",
                confidence=confidence,
                reason=reason,
                evidence={
                    "null_count": prof.null_count,
                    "null_ratio": prof.null_ratio,
                    "non_null_count": prof.row_count - prof.null_count,
                    "total_rows": prof.row_count,
                    "sample_violations_count": 0,
                    "is_primary_key": col.is_primary_key
                },
                validation_status="VALID",
                status="DRAFT"
            )
        return None

    def _generate_unique_rule(self, context: TableContext, col: ColumnContext) -> CandidateRule | None:
        """
        Rule: columnValuesToBeUnique
        Điều kiện: is_primary_key == True hoặc distinct_ratio >= unique_threshold (0.99)
        """
        prof = col.profile
        if prof.row_count <= 0:
            return None

        is_pk = col.is_primary_key
        is_high_unique = prof.distinct_ratio >= settings.unique_threshold

        if is_pk or is_high_unique:
            confidence = 1.0 if is_pk else 0.95
            reason = (
                f"Cột '{col.name}' là khóa chính (Primary Key) của bảng {context.table_name}."
                if is_pk
                else f"Cột '{col.name}' có tỷ lệ giá trị duy nhất đạt {prof.distinct_ratio * 100:.1f}%, phù hợp làm trường định danh."
            )
            return CandidateRule(
                rule_type="columnValuesToBeUnique",
                description="Giá trị duy nhất, không trùng lặp (Unique)",
                target_columns=[col.name],
                parameters={},
                engine="BASIC",
                confidence=confidence,
                reason=reason,
                evidence={
                    "distinct_count": prof.distinct_count,
                    "distinct_ratio": prof.distinct_ratio,
                    "duplicate_count": 0 if is_pk else max(0, prof.row_count - prof.distinct_count),
                    "total_rows": prof.row_count,
                    "sample_violations_count": 0,
                    "is_primary_key": is_pk
                },
                validation_status="VALID",
                status="DRAFT"
            )
        return None

    def _generate_between_rule(self, context: TableContext, col: ColumnContext) -> CandidateRule | None:
        """
        Rule: columnValuesToBeBetween
        Điều kiện: Kiểu dữ liệu số hoặc thời gian và có min_value, max_value quan sát được
        """
        prof = col.profile
        if prof.min_value is None or prof.max_value is None:
            return None

        dtype = col.data_type.upper()
        is_numeric = any(t in dtype for t in ["INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "NUMBER"])
        is_date = any(t in dtype for t in ["DATE", "TIME", "TIMESTAMP"])

        if is_numeric or is_date:
            return CandidateRule(
                rule_type="columnValuesToBeBetween",
                description=f"Giá trị nằm trong khoảng dự kiến [{prof.min_value} .. {prof.max_value}]",
                target_columns=[col.name],
                parameters={
                    "minValue": prof.min_value,
                    "maxValue": prof.max_value
                },
                engine="BASIC",
                confidence=0.90,
                reason=f"Phạm vi giá trị quan sát của cột '{col.name}' dao động từ {prof.min_value} đến {prof.max_value}.",
                evidence={
                    "min_observed": prof.min_value,
                    "max_observed": prof.max_value,
                    "expected_range": [prof.min_value, prof.max_value],
                    "total_rows": prof.row_count,
                    "sample_violations_count": 0
                },
                validation_status="VALID",
                status="DRAFT"
            )
        return None

    def _generate_in_set_rule(self, context: TableContext, col: ColumnContext) -> CandidateRule | None:
        """
        Rule: columnValuesToBeInSet
        Điều kiện: distinct_count <= max_allowed_cardinality (20) và distinct_count > 0
        """
        prof = col.profile
        if 0 < prof.distinct_count <= settings.max_allowed_cardinality:
            # Thu thập allowed values từ top_values hoặc sample
            allowed_values = []
            if prof.top_values:
                allowed_values = [str(item.get("value", "")) for item in prof.top_values if item.get("value") is not None]
            
            # Không sinh In Set cho cột số có 1 giá trị hoặc cột ID duy nhất
            if len(allowed_values) == 0:
                return None

            return CandidateRule(
                rule_type="columnValuesToBeInSet",
                description=f"Giá trị thuộc danh mục cho phép ({len(allowed_values)} giá trị)",
                target_columns=[col.name],
                parameters={
                    "allowedValues": allowed_values
                },
                engine="BASIC",
                confidence=0.95,
                reason=f"Cột '{col.name}' có số lượng giá trị phân biệt thấp ({prof.distinct_count} giá trị), dữ liệu chỉ nằm trong tập chuẩn.",
                evidence={
                    "distinct_count": prof.distinct_count,
                    "cardinality_ratio": prof.distinct_ratio,
                    "observed_values": allowed_values,
                    "allowed_values": allowed_values,
                    "total_rows": prof.row_count,
                    "sample_violations_count": 0
                },
                validation_status="VALID",
                status="DRAFT"
            )
        return None

    def _generate_length_rule(self, context: TableContext, col: ColumnContext) -> CandidateRule | None:
        """
        Rule: columnValuesLengthToBeBetween
        Điều kiện: Cột chuỗi và có min_length, max_length
        """
        prof = col.profile
        dtype = col.data_type.upper()
        is_string = any(t in dtype for t in ["VARCHAR", "CHAR", "TEXT", "STRING"])

        if is_string and prof.min_length is not None and prof.max_length is not None:
            return CandidateRule(
                rule_type="columnValuesLengthToBeBetween",
                description=f"Độ dài chuỗi từ {prof.min_length} đến {prof.max_length} ký tự",
                target_columns=[col.name],
                parameters={
                    "minLength": prof.min_length,
                    "maxLength": prof.max_length
                },
                engine="BASIC",
                confidence=0.90,
                reason=f"Độ dài ký tự của cột '{col.name}' được ghi nhận trong khoảng [{prof.min_length} .. {prof.max_length}] ký tự.",
                evidence={
                    "min_length": prof.min_length,
                    "max_length": prof.max_length,
                    "expected_range": [prof.min_length, prof.max_length],
                    "total_rows": prof.row_count,
                    "sample_violations_count": 0
                },
                validation_status="VALID",
                status="DRAFT"
            )
        return None

    def _generate_row_count_rule(self, context: TableContext) -> CandidateRule:
        """
        Rule: tableRowCountToBeBetween
        Biên độ dao động dự kiến: [row_count * 0.8, row_count * 1.5]
        """
        min_rows = max(1, int(context.row_count * 0.8))
        max_rows = int(context.row_count * 1.5)
        return CandidateRule(
            rule_type="tableRowCountToBeBetween",
            description=f"Tổng số dòng bảng duy trì trong khoảng [{min_rows:,} .. {max_rows:,}] dòng",
            target_columns=[],
            parameters={
                "minValue": min_rows,
                "maxValue": max_rows
            },
            engine="BASIC",
            confidence=0.85,
            reason=f"Quy mô số dòng của bảng '{context.table_name}' được bảo toàn trong ngưỡng dự kiến [{min_rows:,} .. {max_rows:,}].",
            evidence={
                "current_row_count": context.row_count,
                "expected_min": min_rows,
                "expected_max": max_rows,
                "growth_buffer_pct": 50,
                "trend_status": "STABLE"
            },
            validation_status="VALID",
            status="DRAFT"
        )
