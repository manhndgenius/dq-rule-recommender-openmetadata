import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.integrations.openmetadata_client import openmetadata_client
from backend.engine.basic_engine import BasicRuleEngine
from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile

logger = logging.getLogger("golden_evaluator")

GOLDEN_DIR = Path(__file__).resolve().parent / "golden_dataset"
GROUND_TRUTH_FILE = GOLDEN_DIR / "ground_truth_rules.json"
TEST_DATA_DIR = GOLDEN_DIR / "test_data"

class GoldenDatasetEvaluator:
    """
    Bộ thẩm định và chấm điểm định lượng (Benchmark Evaluator)
    đối chiếu trực tiếp với Synthea Ground Truth Specification & Golden Test Data.
    Áp dụng cho 3 bảng cốt lõi: patients, medications, observations.
    """

    def __init__(self):
        self.basic_engine = BasicRuleEngine()
        self.ground_truth_spec = self._load_ground_truth()
        self._cached_benchmark: Optional[Dict[str, Any]] = None

    def _load_ground_truth(self) -> Dict[str, Any]:
        """Tải đặc tả Ground Truth Rules từ JSON"""
        if not GROUND_TRUTH_FILE.exists():
            logger.error(f"Không tìm thấy file Ground Truth: {GROUND_TRUTH_FILE}")
            return {"tables": {}}
        try:
            with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc file ground_truth_rules.json: {e}")
            return {"tables": {}}

    def _load_golden_records(self, table_name: str) -> List[Dict[str, Any]]:
        """Tải các bản ghi test data (Clean + Labeled Faults) của bảng"""
        file_path = TEST_DATA_DIR / f"{table_name}_golden.json"
        if not file_path.exists():
            logger.warning(f"Không tìm thấy file test data: {file_path}")
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("records", [])
        except Exception as e:
            logger.error(f"Lỗi đọc test data {table_name}: {e}")
            return []

    def _match_rule(self, candidate: CandidateRule, expected: Dict[str, Any]) -> bool:
        """
        Kiểm tra mức độ tương đồng giữa một Candidate Rule do Engine sinh ra
        và một Expected Rule trong Synthea Ground Truth.
        """
        if candidate.rule_type != expected["rule_type"]:
            return False

        # So sánh danh sách cột mục tiêu
        cand_cols = sorted([c.lower() for c in candidate.target_columns])
        exp_cols = sorted([c.lower() for c in expected["target_columns"]])
        if cand_cols != exp_cols:
            return False

        # So sánh tham số cụ thể theo loại rule
        if candidate.rule_type == "columnValuesToBeInSet":
            cand_allowed = set(str(v).lower() for v in candidate.parameters.get("allowedValues", []))
            exp_allowed = set(str(v).lower() for v in expected.get("parameters", {}).get("allowedValues", []))
            # Nếu tập sinh ra chứa tập chuẩn hoặc trùng khớp hoàn toàn
            if not cand_allowed or not exp_allowed:
                return False
            intersection = cand_allowed.intersection(exp_allowed)
            return len(intersection) >= min(len(cand_allowed), len(exp_allowed)) * 0.7

        if candidate.rule_type == "columnValuesLengthToBeBetween":
            c_min = candidate.parameters.get("minLength")
            c_max = candidate.parameters.get("maxLength")
            e_min = expected.get("parameters", {}).get("minLength")
            e_max = expected.get("parameters", {}).get("maxLength")
            if e_min is not None and c_min != e_min:
                return False
            if e_max is not None and c_max != e_max:
                return False

        return True

    def _validate_record_against_rule(self, record: Dict[str, Any], rule: CandidateRule) -> bool:
        """
        Thực thi kiểm tra 1 dòng dữ liệu xem có vi phạm Rule hay không.
        Trả về True nếu HỢP LỆ (Pass), False nếu VI PHẠM (Violated).
        """
        rtype = rule.rule_type
        cols = rule.target_columns
        params = rule.parameters or {}

        for col in cols:
            val = record.get(col)

            if rtype == "columnValuesToBeNotNull":
                if val is None or val == "" or str(val).strip() == "":
                    return False

            elif rtype == "columnValuesLengthToBeBetween":
                if val is not None:
                    s_len = len(str(val))
                    min_len = params.get("minLength")
                    max_len = params.get("maxLength")
                    if min_len is not None and s_len < min_len:
                        return False
                    if max_len is not None and s_len > max_len:
                        return False

            elif rtype == "columnValuesToBeInSet":
                if val is not None:
                    allowed = [str(x).lower() for x in params.get("allowedValues", [])]
                    if str(val).lower() not in allowed:
                        return False

            elif rtype == "columnValuesToBeBetween":
                if val is not None:
                    try:
                        num_val = float(val)
                        min_v = params.get("minValue")
                        max_v = params.get("maxValue")
                        if min_v is not None and num_val < float(min_v):
                            return False
                        if max_v is not None and num_val > float(max_v):
                            return False
                    except (ValueError, TypeError):
                        pass

        return True

    def _build_context_from_golden_records(self, table_name: str, clean_records: List[Dict[str, Any]]) -> TableContext:
        """
        Xây dựng TableContext và ColumnProfile trực tiếp từ tập dữ liệu sạch của Golden Dataset.
        Đảm bảo tính xác thực, độc lập và tốc độ thực thi miligiây (không phụ thuộc timeout mạng).
        """
        row_count = len(clean_records)
        if row_count == 0:
            return TableContext(
                datasource_id="golden-dataset",
                database_name="synthea_standard",
                schema_name="public",
                table_name=table_name,
                row_count=0,
                columns=[]
            )

        # Trích xuất tất cả các tên cột (loại trừ metadata cấy lỗi _is_valid, _injected_fault)
        all_keys = [k for k in clean_records[0].keys() if not k.startswith("_")]
        columns: List[ColumnContext] = []

        for col_name in all_keys:
            vals = [r.get(col_name) for r in clean_records]
            non_null_vals = [v for v in vals if v is not None and v != ""]
            null_count = row_count - len(non_null_vals)
            null_ratio = round(null_count / row_count, 4) if row_count > 0 else 0.0

            distinct_set = set(non_null_vals)
            distinct_count = len(distinct_set)
            distinct_ratio = round(distinct_count / row_count, 4) if row_count > 0 else 0.0

            sample_val = non_null_vals[0] if non_null_vals else None
            is_pk = (col_name == "id")
            min_val = None
            max_val = None
            min_len = None
            max_len = None
            top_vals = []

            # Phân loại kiểu dữ liệu
            if isinstance(sample_val, (int, float)) and not isinstance(sample_val, bool):
                data_type = "NUMERIC(14,2)" if isinstance(sample_val, float) else "INTEGER"
                if non_null_vals:
                    min_val = min(non_null_vals)
                    max_val = max(non_null_vals)
            elif any(k in col_name.lower() for k in ["cost", "expenses", "coverage", "income", "lat", "lon"]):
                data_type = "NUMERIC(14,2)"
                nums = [float(v) for v in non_null_vals if v is not None]
                if nums:
                    min_val = min(nums)
                    max_val = max(nums)
            elif col_name.lower() == "dispenses":
                data_type = "INTEGER"
                nums = [int(v) for v in non_null_vals if v is not None]
                if nums:
                    min_val = min(nums)
                    max_val = max(nums)
            elif any(k in col_name.lower() for k in ["date", "time", "start_at", "stop_at"]):
                data_type = "TIMESTAMP"
            else:
                data_type = "VARCHAR(255)"
                lengths = [len(str(v)) for v in non_null_vals]
                if lengths:
                    min_len = min(lengths)
                    max_len = max(lengths)

                # Danh mục categorical enum low cardinality (loại trừ UUID / FK / PK)
                skip_enum = is_pk or any(k in col_name.lower() for k in ["patient", "encounter", "payer", "ssn", "drivers", "passport", "first_name", "last_name", "address", "city"])
                if 0 < distinct_count <= 20 and not skip_enum:
                    top_vals = [{"value": str(v), "count": vals.count(v)} for v in distinct_set]

            prof = ColumnProfile(
                row_count=row_count,
                null_count=null_count,
                null_ratio=null_ratio,
                distinct_count=distinct_count,
                distinct_ratio=distinct_ratio,
                min_value=min_val,
                max_value=max_val,
                min_length=min_len,
                max_length=max_len,
                top_values=top_vals
            )

            columns.append(ColumnContext(
                name=col_name,
                data_type=data_type,
                nullable=null_count > 0 or not is_pk,
                is_primary_key=is_pk,
                profile=prof
            ))

        return TableContext(
            datasource_id="golden-dataset",
            database_name="synthea_standard",
            schema_name="public",
            table_name=table_name,
            table_description=f"Synthea Golden Standard Healthcare Table: {table_name}",
            row_count=row_count,
            columns=columns
        )

    def evaluate_table(self, table_name: str) -> Dict[str, Any]:
        """
        Đánh giá chuyên sâu 1 bảng đối chiếu với Ground Truth và Test Data:
        1. Tính Precision, Recall, F1 trên tập luật
        2. Tính Defect Detection Rate trên tập dữ liệu cấy lỗi
        """
        expected_rules = self.ground_truth_spec.get("tables", {}).get(table_name, {}).get("expected_rules", [])
        records = self._load_golden_records(table_name)

        # Tách biệt Clean Data và Injected Defect Data
        clean_records = [r for r in records if r.get("_is_valid", True)]
        defect_records = [r for r in records if not r.get("_is_valid", True)]

        # 1. Xây dựng TableContext từ clean baseline và sinh candidate rules
        context = self._build_context_from_golden_records(table_name, clean_records)
        candidates = self.basic_engine.generate_candidates(context)

        # 2. Tính toán Precision, Recall, F1
        matched_candidates = set()
        matched_expected = set()

        for c_idx, cand in enumerate(candidates):
            for e_idx, exp in enumerate(expected_rules):
                if self._match_rule(cand, exp):
                    matched_candidates.add(c_idx)
                    matched_expected.add(e_idx)
                    break

        true_positives = len(matched_candidates)
        total_generated = len(candidates)
        total_expected = len(expected_rules)

        precision = round(true_positives / total_generated * 100, 2) if total_generated > 0 else 0.0
        recall = round(len(matched_expected) / total_expected * 100, 2) if total_expected > 0 else 0.0
        f1_score = round(2 * (precision * recall) / (precision + recall), 2) if (precision + recall) > 0 else 0.0

        # Danh sách các luật chuẩn chưa tìm thấy (Missing Ground Truth Rules)
        missing_rules = [
            {
                "rule_type": exp["rule_type"],
                "target_columns": exp["target_columns"],
                "category": exp.get("category", "GENERAL"),
                "reason": exp.get("reason", "")
            }
            for e_idx, exp in enumerate(expected_rules)
            if e_idx not in matched_expected
        ]

        # 3. Kiểm thử trên tập dữ liệu Golden Data (Clean & Injected Defects)
        clean_records = [r for r in records if r.get("_is_valid", True)]
        defect_records = [r for r in records if not r.get("_is_valid", True)]

        # a. Đo False Alarm Rate trên dữ liệu sạch
        false_alarms_count = 0
        for rec in clean_records:
            for rule in candidates:
                if not self._validate_record_against_rule(rec, rule):
                    false_alarms_count += 1
                    break

        clean_pass_rate = round((len(clean_records) - false_alarms_count) / len(clean_records) * 100, 2) if clean_records else 100.0

        # b. Đo Defect Detection Rate trên dữ liệu cấy lỗi
        caught_defects = 0
        defect_scenarios = []

        # Kiểm tra Unique ID riêng biệt trên toàn bộ bảng test
        seen_ids = set()
        duplicate_id_detected = False
        for rec in records:
            rid = rec.get("id")
            if rid:
                if rid in seen_ids:
                    duplicate_id_detected = True
                    break
                seen_ids.add(rid)

        for rec in defect_records:
            fault_desc = rec.get("_injected_fault", "Unknown defect")
            is_caught = False
            caught_by_rules = []

            # Nếu là lỗi duplicate ID và có rule Unique
            if "DUPLICATE_PRIMARY_KEY" in fault_desc and any(r.rule_type == "columnValuesToBeUnique" for r in candidates):
                if duplicate_id_detected:
                    is_caught = True
                    caught_by_rules.append("columnValuesToBeUnique:id")

            # Kiểm tra theo từng rule
            for rule in candidates:
                if not self._validate_record_against_rule(rec, rule):
                    is_caught = True
                    caught_by_rules.append(f"{rule.rule_type}:{','.join(rule.target_columns)}")

            if is_caught:
                caught_defects += 1

            defect_scenarios.append({
                "fault": fault_desc,
                "is_detected": is_caught,
                "detected_by": caught_by_rules[:2]
            })

        defect_detection_rate = round(caught_defects / len(defect_records) * 100, 2) if defect_records else 100.0

        return {
            "table_name": table_name,
            "total_columns": len(context.columns),
            "total_rules_generated": total_generated,
            "ground_truth_rules_count": total_expected,
            "metrics": {
                "true_positives": true_positives,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score
            },
            "missing_golden_rules": missing_rules,
            "defect_testing": {
                "total_test_records": len(records),
                "clean_records_count": len(clean_records),
                "clean_pass_rate": clean_pass_rate,
                "defect_records_count": len(defect_records),
                "caught_defects_count": caught_defects,
                "defect_detection_rate": defect_detection_rate,
                "scenarios": defect_scenarios
            }
        }

    def run_benchmark(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Chạy toàn diện Golden Benchmark trên cả 3 bảng cốt lõi
        (patients, medications, observations) và tính điểm tổng hợp.
        """
        if self._cached_benchmark and not force_refresh:
            return self._cached_benchmark

        target_tables = ["patients", "medications", "observations"]
        results = []

        total_gen = 0
        total_gt = 0
        total_tp = 0
        total_defects = 0
        total_caught = 0

        for tname in target_tables:
            res = self.evaluate_table(tname)
            results.append(res)
            total_gen += res["total_rules_generated"]
            total_gt += res["ground_truth_rules_count"]
            total_tp += res["metrics"]["true_positives"]
            total_defects += res["defect_testing"]["defect_records_count"]
            total_caught += res["defect_testing"]["caught_defects_count"]

        avg_precision = round(sum(r["metrics"]["precision"] for r in results) / len(results), 2)
        avg_recall = round(sum(r["metrics"]["recall"] for r in results) / len(results), 2)
        avg_f1 = round(sum(r["metrics"]["f1_score"] for r in results) / len(results), 2)
        overall_detection_rate = round(total_caught / total_defects * 100, 2) if total_defects > 0 else 100.0
        avg_clean_pass = round(sum(r["defect_testing"]["clean_pass_rate"] for r in results) / len(results), 2)

        summary = {
            "benchmark_name": "Synthea Healthcare Golden Dataset Evaluation",
            "evaluated_tables": target_tables,
            "overall_summary": {
                "total_rules_generated": total_gen,
                "total_ground_truth_rules": total_gt,
                "average_precision": avg_precision,
                "average_recall": avg_recall,
                "average_f1_score": avg_f1,
                "overall_defect_detection_rate": overall_detection_rate,
                "clean_data_pass_rate": avg_clean_pass,
                "status": "EXCELLENT" if overall_detection_rate >= 90.0 and avg_f1 >= 80.0 else "GOOD"
            },
            "tables": results
        }

        self._cached_benchmark = summary
        return summary

golden_dataset_evaluator = GoldenDatasetEvaluator()
