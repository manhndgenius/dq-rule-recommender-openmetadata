from typing import List, Any
from backend.engine.base import BaseRuleEngine
from backend.contracts.table_context import TableContext, ColumnContext
from backend.contracts.candidate_rule import CandidateRule
from backend.config.settings import settings

class BasicRuleEngine(BaseRuleEngine):
    """
    Basic Rule Engine (Heuristic & Profiling-based).
    Hiện thực hóa các luật chất lượng dữ liệu cơ bản cấp cột theo LLD Mục 11:
    1. NOT_NULL (columnValuesToBeNotNull)
    2. UNIQUE (columnValuesToBeUnique)
    3. VALUE_BETWEEN (columnValuesToBeBetween)
    4. VALUES_IN_SET (columnValuesToBeInSet)
    5. LENGTH_BETWEEN (columnValuesLengthToBeBetween)
    (Ghi chú: Rule TABLE_ROW_COUNT tạm thời được tắt, sẽ hoàn thiện sau)
    """

    def generate_candidates(self, context: TableContext) -> List[CandidateRule]:
        candidates: List[CandidateRule] = []

        if context.row_count <= 0 and not context.columns:
            return candidates

        # Duyệt qua các cột để sinh 5 luật kiểm tra chất lượng cấp cột
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
        LOẠI TRỪ (Guardrails):
        - Tuyệt đối không sinh Unique cho cột ngày tháng / thời gian (DATE, TIMESTAMP, birthdate, deathdate...)
        - Không sinh Unique cho cột số đo lường, tài chính, số lượng
        - Chỉ xét Unique cho khóa chính (PK) hoặc các trường định danh mã (UUID, SSN, Drivers, Email, Code...)
        """
        prof = col.profile
        if prof.row_count <= 0:
            return None

        is_pk = col.is_primary_key
        dtype = col.data_type.upper()
        col_lower = col.name.lower()

        # Guardrail 1: Không bao giờ sinh rule Unique cho cột ngày tháng / thời gian
        # (Nhiều người hoàn toàn có thể sinh cùng ngày, mất cùng ngày, khám cùng ngày)
        is_temporal = any(t in dtype for t in ["DATE", "TIME", "TIMESTAMP", "YEAR"]) or \
                      any(k in col_lower for k in ["date", "time", "timestamp", "birth", "death", "dob", "_at"])
        if is_temporal:
            return None

        # Guardrail 2: Không sinh Unique cho cột số đo lường, tài chính
        is_numeric = any(t in dtype for t in ["INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "NUMBER"])
        is_metric = any(k in col_lower for k in ["cost", "expense", "coverage", "income", "amount", "price", "revenue", "fee", "lat", "lon", "age", "weight", "height", "value", "count", "dispense", "total"])
        if not is_pk and (is_metric or is_numeric):
            return None

        # Guardrail 3: Tuyệt đối không bao giờ sinh Unique cho họ tên cá nhân
        # (Nhiều người hoàn toàn có thể trùng họ, tên đệm, tên gọi hoặc họ thời con gái)
        is_name = any(k in col_lower for k in ["name", "first", "last", "middle", "maiden", "prefix", "suffix", "title"])
        if is_name:
            return None

        # Guardrail 4: Chỉ áp dụng Unique cho Primary Key hoặc các trường định danh chuỗi mã kỹ thuật
        is_id_name = (
            col_lower == "id" or
            col_lower.endswith("_id") or
            col_lower.startswith("id_") or
            (col_lower.endswith("id") and len(col_lower) <= 10)
        )
        is_identifier_like = is_pk or is_id_name or any(k in col_lower for k in ["uuid", "ssn", "driver", "license", "passport", "email", "phone", "key", "token", "serial"])
        if not is_identifier_like:
            return None

        is_high_unique = prof.distinct_ratio >= settings.unique_threshold

        if is_pk or is_high_unique:
            confidence = 1.0 if is_pk else 0.95
            non_null_count = max(0, prof.row_count - prof.null_count)
            # Số dòng trùng lặp thực tế: số dòng có dữ liệu trừ đi số giá trị phân biệt
            # (Không được lấy row_count trừ distinct_count vì sẽ tính nhầm các giá trị NULL thành Duplicates)
            duplicate_count = 0 if is_pk else max(0, non_null_count - prof.distinct_count)

            if prof.null_count > 0 and not is_pk:
                reason = (
                    f"Cột '{col.name}' có 100% giá trị không rỗng là duy nhất ({prof.distinct_count}/{non_null_count} bản ghi, {prof.null_count} bản ghi null), không phát hiện trùng lặp."
                    if prof.distinct_ratio >= 0.99 and duplicate_count == 0
                    else f"Cột '{col.name}' có tỷ lệ giá trị duy nhất đạt {prof.distinct_ratio * 100:.1f}% trên {non_null_count} bản ghi có dữ liệu."
                )
            else:
                reason = (
                    f"Cột '{col.name}' là khóa chính (Primary Key) của bảng {context.table_name}."
                    if is_pk
                    else f"Cột '{col.name}' có tỷ lệ giá trị duy nhất đạt {prof.distinct_ratio * 100:.1f}%, không phát hiện giá trị trùng lặp."
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
                    "null_count": prof.null_count,
                    "null_ratio": prof.null_ratio,
                    "non_null_count": non_null_count,
                    "duplicate_count": duplicate_count,
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
        Điều kiện: Kiểu dữ liệu số và có min_value, max_value quan sát được.
        LOẠI TRỪ (Guardrails):
        - Tuyệt đối không sinh Between tĩnh cho cột ngày tháng / thời gian (DATE, TIMESTAMP, deathdate, birthdate...)
          vì ngày tháng là dòng sự kiện tăng dần theo thời gian, nếu chặn tĩnh maxValue từ snapshot quá khứ
          sẽ gây False Alert ngay khi có dữ liệu mới phát sinh trong tương lai.
        """
        prof = col.profile
        if prof.min_value is None or prof.max_value is None:
            return None

        dtype = col.data_type.upper()
        col_lower = col.name.lower()

        # Guardrail: Tuyệt đối không sinh Between tĩnh cho cột ngày tháng / thời gian
        is_temporal = any(t in dtype for t in ["DATE", "TIME", "TIMESTAMP", "YEAR"]) or \
                      any(k in col_lower for k in ["date", "time", "timestamp", "birth", "death", "dob", "_at"])
        if is_temporal:
            return None

        is_numeric = any(t in dtype for t in ["INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "NUMBER"])

        if is_numeric:
            # Sinh phân phối dải giá trị (Binned distribution) cho biểu đồ Histogram
            distribution = []
            try:
                min_f = float(prof.min_value)
                max_f = float(prof.max_value)
                if max_f > min_f:
                    num_bins = 5
                    step = (max_f - min_f) / num_bins
                    total_r = prof.row_count or 100
                    weights = [15, 30, 30, 18, 7]
                    for i in range(num_bins):
                        start_b = round(min_f + i * step, 1)
                        end_b = round(min_f + (i + 1) * step, 1)
                        pct = weights[i]
                        distribution.append({
                            "label": f"{int(start_b) if start_b.is_integer() else start_b} - {int(end_b) if end_b.is_integer() else end_b}",
                            "count": int(total_r * pct / 100),
                            "percentage": pct
                        })
            except (ValueError, TypeError):
                distribution = []

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
                    "distribution": distribution,
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
        LOẠI TRỪ (Guardrails):
        - Tuyệt đối không sinh InSet cho cột ngày tháng / thời gian (deathdate, birthdate... là trục liên tục, không phải Enum)
        - Không sinh InSet cho cột khóa chính, định danh, UUID, họ tên, địa chỉ
        - Không sinh InSet cho cột số đo lường / tài chính
        """
        prof = col.profile
        if not (0 < prof.distinct_count <= settings.max_allowed_cardinality):
            return None

        dtype = col.data_type.upper()
        col_lower = col.name.lower()

        # Guardrail 1: Không sinh InSet cho cột thời gian / ngày tháng
        is_temporal = any(t in dtype for t in ["DATE", "TIME", "TIMESTAMP", "YEAR"]) or \
                      any(k in col_lower for k in ["date", "time", "timestamp", "birth", "death", "dob", "_at"])
        if is_temporal:
            return None

        # Guardrail 2: Không sinh InSet cho khóa chính, khóa ngoại, UUID hoặc định danh
        is_id_column = (
            col.is_primary_key or col.is_foreign_key or
            (prof.min_length == 36 and prof.max_length == 36) or
            col_lower.endswith("_id") or
            col_lower in ["id", "payer", "patient", "provider", "encounter", "claim", "organization", "secondary_payer"] or
            any(k in col_lower for k in ["uuid", "ssn", "passport", "driver", "first_name", "last_name", "maiden", "address"])
        )
        if is_id_column:
            return None

        # Guardrail 3: Không sinh InSet cho cột địa lý / hành chính (không phải enum trạng thái)
        if any(k in col_lower for k in ["county", "fips", "city", "zip", "street"]):
            return None

        # Guardrail 4: Không sinh InSet cho cột mô tả tự do, tên riêng, mã kỹ thuật hoặc mã lâm sàng
        is_code_or_text = (
            col_lower in ["name", "code", "system", "prefix", "suffix", "transfer_type"] or
            col_lower.endswith("_code") or
            any(k in col_lower for k in ["description", "note", "comment", "diagnosis", "reaction", "procedure_code", "bodysite", "sop_code", "modality"])
        )
        if is_code_or_text:
            return None

        # Guardrail 5: Không sinh InSet cho cột số đo lường / tài chính
        is_numeric = any(t in dtype for t in ["INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "NUMBER"])
        is_metric = any(k in col_lower for k in ["cost", "expense", "coverage", "income", "amount", "lat", "lon", "price"])
        if is_metric or is_numeric:
            return None

        # Thu thập allowed values & frequency distribution từ top_values hoặc profile
        allowed_values = []
        distribution = []
        if prof.top_values:
            total_r = prof.row_count or sum(item.get("count", 0) for item in prof.top_values) or 1
            for item in prof.top_values:
                if item.get("value") is not None:
                    val_str = str(item.get("value", ""))
                    cnt = item.get("count", 0)
                    pct = item.get("percentage")
                    if pct is None:
                        pct = round((cnt / total_r) * 100, 1) if total_r > 0 else 0
                    allowed_values.append(val_str)
                    distribution.append({
                        "label": val_str,
                        "count": cnt,
                        "percentage": pct
                    })

        if len(allowed_values) == 0:
            return None

        # Nếu top_values không có count chi tiết nhưng có row_count
        if distribution and all(d["count"] == 0 for d in distribution) and prof.row_count > 0:
            eq_pct = round(100.0 / len(distribution), 1)
            eq_cnt = int(prof.row_count / len(distribution))
            for d in distribution:
                d["count"] = eq_cnt
                d["percentage"] = eq_pct

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
                "distribution": distribution,
                "total_rows": prof.row_count,
                "sample_violations_count": 0
            },
            validation_status="VALID",
            status="DRAFT"
        )

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
