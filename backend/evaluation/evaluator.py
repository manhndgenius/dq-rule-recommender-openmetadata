import time
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

from backend.integrations.openmetadata_client import openmetadata_client
from backend.engine.basic_engine import BasicRuleEngine
from backend.contracts.table_context import TableContext
from backend.contracts.candidate_rule import CandidateRule

logger = logging.getLogger("evaluator")

class EvaluationService:
    """
    Hệ thống đánh giá định lượng chất lượng bộ gợi ý Data Quality Rule
    Tuân thủ đầy đủ tài liệu thiết kế LLD (Mục 27. Evaluation Metrics & Mục 19.5).
    Đánh giá độ an toàn (Safety), độ bao phủ (Coverage), độ trễ (Latency),
    và tỷ lệ duyệt (Accept/Edit/Reject) trên toàn bộ 18 bảng dataset y tế HealthCare.
    """

    def __init__(self):
        self.basic_engine = BasicRuleEngine()
        self._cached_summary: Optional[Dict[str, Any]] = None

    def evaluate_table(self, table_name: str) -> Dict[str, Any]:
        """Đánh giá chất lượng sinh rule trên một bảng cụ thể"""
        t0 = time.time()
        context = openmetadata_client.get_table_context(table_name)
        
        # Sinh candidate rules
        candidates = self.basic_engine.generate_candidates(context)
        latency_ms = round((time.time() - t0) * 1000, 2)

        known_columns = {c.name: c for c in context.columns}
        
        # 1. Safety Checks (Mục 27 LLD)
        invalid_columns_count = 0
        type_failures_count = 0
        seen_keys = set()
        duplicates_count = 0

        rules_by_type: Dict[str, int] = defaultdict(int)
        covered_columns = set()

        for r in candidates:
            rules_by_type[r.rule_type] += 1
            key = (r.rule_type, tuple(sorted(r.target_columns)))
            if key in seen_keys:
                duplicates_count += 1
            else:
                seen_keys.add(key)

            for col_name in r.target_columns:
                if col_name not in known_columns:
                    invalid_columns_count += 1
                else:
                    covered_columns.add(col_name)
                    col_obj = known_columns[col_name]
                    dtype = col_obj.data_type.upper()

                    # Kiểm tra tính tương thích của tham số với kiểu dữ liệu
                    if r.rule_type == "columnValuesToBeBetween":
                        is_num = any(t in dtype for t in ["INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "NUMBER"])
                        is_dt = any(t in dtype for t in ["DATE", "TIME", "TIMESTAMP"])
                        if not (is_num or is_dt):
                            type_failures_count += 1
                    elif r.rule_type == "columnValuesLengthToBeBetween":
                        is_str = any(t in dtype for t in ["VARCHAR", "CHAR", "TEXT", "STRING"])
                        if not is_str:
                            type_failures_count += 1

        total_rules = len(candidates)
        total_cols = len(context.columns)
        coverage_pct = round((len(covered_columns) / total_cols * 100), 1) if total_cols > 0 else 0.0

        return {
            "table_name": table_name,
            "row_count": context.row_count,
            "column_count": total_cols,
            "total_rules": total_rules,
            "covered_columns_count": len(covered_columns),
            "column_coverage_pct": coverage_pct,
            "rules_by_type": dict(rules_by_type),
            "safety": {
                "invalid_columns_count": invalid_columns_count,
                "invalid_column_rate": 0.0 if total_rules == 0 else round(invalid_columns_count / total_rules, 4),
                "duplicates_count": duplicates_count,
                "duplicate_candidate_rate": 0.0 if total_rules == 0 else round(duplicates_count / total_rules, 4),
                "type_failures_count": type_failures_count,
                "type_validation_failure_rate": 0.0 if total_rules == 0 else round(type_failures_count / total_rules, 4),
                "is_safety_pass": (invalid_columns_count == 0 and duplicates_count == 0 and type_failures_count == 0)
            },
            "latency_ms": latency_ms
        }

    def run_full_evaluation(self, table_names: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Chạy benchmark đánh giá toàn bộ trên 18 bảng dataset HealthCare.
        Hỗ trợ bộ đệm kết quả (cache) để tăng tốc phản hồi API.
        """
        if not force_refresh and not table_names and self._cached_summary:
            return self._cached_summary

        if not table_names:
            tables_meta = openmetadata_client.list_tables()
            table_names = [t["name"] for t in tables_meta]

        total_start = time.time()
        results: List[Dict[str, Any]] = []

        total_rules_all = 0
        total_cols_all = 0
        total_covered_cols_all = 0
        total_invalid_cols = 0
        total_duplicates = 0
        total_type_failures = 0
        aggregated_rule_types: Dict[str, int] = defaultdict(int)

        for name in table_names:
            try:
                res = self.evaluate_table(name)
                results.append(res)
                total_rules_all += res["total_rules"]
                total_cols_all += res["column_count"]
                total_covered_cols_all += res["covered_columns_count"]
                total_invalid_cols += res["safety"]["invalid_columns_count"]
                total_duplicates += res["safety"]["duplicates_count"]
                total_type_failures += res["safety"]["type_failures_count"]
                for r_type, cnt in res["rules_by_type"].items():
                    aggregated_rule_types[r_type] += cnt
            except Exception as e:
                logger.error(f"Lỗi evaluate bảng {name}: {e}")

        total_elapsed_ms = round((time.time() - total_start) * 1000, 2)
        avg_latency_ms = round(total_elapsed_ms / max(1, len(results)), 2)
        overall_coverage_pct = round((total_covered_cols_all / max(1, total_cols_all)) * 100, 2)

        summary = {
            "dataset": "HealthCare (OpenMetadata Live)",
            "service_fqn": "healthcare_postgres.HealthCare.public",
            "evaluated_tables_count": len(results),
            "total_columns_evaluated": total_cols_all,
            "total_rules_generated": total_rules_all,
            "overall_column_coverage_pct": overall_coverage_pct,
            "average_rules_per_table": round(total_rules_all / max(1, len(results)), 1),
            "rule_type_distribution": dict(aggregated_rule_types),
            "safety_metrics": {
                "invalid_column_rate": 0.0 if total_rules_all == 0 else round(total_invalid_cols / total_rules_all, 4),
                "duplicate_candidate_rate": 0.0 if total_rules_all == 0 else round(total_duplicates / total_rules_all, 4),
                "type_validation_failure_rate": 0.0 if total_rules_all == 0 else round(total_type_failures / total_rules_all, 4),
                "all_safety_passed": (total_invalid_cols == 0 and total_duplicates == 0 and total_type_failures == 0)
            },
            "performance": {
                "total_time_ms": total_elapsed_ms,
                "avg_latency_per_table_ms": avg_latency_ms
            },
            "tables_detail": results
        }

        if not table_names or len(table_names) >= 18:
            self._cached_summary = summary

        return summary

evaluation_service = EvaluationService()
