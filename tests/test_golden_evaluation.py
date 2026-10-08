import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.evaluation.golden_evaluator import golden_dataset_evaluator

client = TestClient(app)

def test_ground_truth_specification_loaded():
    """Kiểm tra đặc tả Ground Truth Rules được tải đầy đủ cho 3 bảng cốt lõi"""
    spec = golden_dataset_evaluator.ground_truth_spec
    assert "tables" in spec
    tables = spec["tables"]
    assert "patients" in tables
    assert "medications" in tables
    assert "observations" in tables

    # Kiểm tra số lượng rule tối thiểu trong đặc tả
    assert len(tables["patients"]["expected_rules"]) >= 10
    assert len(tables["medications"]["expected_rules"]) >= 10
    assert len(tables["observations"]["expected_rules"]) >= 8

def test_golden_test_data_files():
    """Kiểm tra dữ liệu Golden Test Data có đầy đủ bản ghi sạch và bản ghi cấy lỗi"""
    for table_name in ["patients", "medications", "observations"]:
        records = golden_dataset_evaluator._load_golden_records(table_name)
        assert len(records) > 0, f"Bảng {table_name} không có dữ liệu test"
        
        clean = [r for r in records if r.get("_is_valid", True)]
        defects = [r for r in records if not r.get("_is_valid", True)]
        
        assert len(clean) >= 10, f"Bảng {table_name} cần ít nhất 10 bản ghi sạch"
        assert len(defects) >= 5, f"Bảng {table_name} cần ít nhất 5 bản ghi cấy lỗi"
        
        # Kiểm tra metadata bản ghi cấy lỗi
        for defect in defects:
            assert "_injected_fault" in defect, f"Thiếu mô tả lỗi cấy trong bản ghi bảng {table_name}"
            assert "_expected_violations" in defect, f"Thiếu expected_violations trong bảng {table_name}"

def test_evaluate_patients_table():
    """Đánh giá chi tiết bảng patients trên Golden Dataset"""
    res = golden_dataset_evaluator.evaluate_table("patients")
    assert res["table_name"] == "patients"
    assert res["metrics"]["recall"] >= 90.0
    assert res["defect_testing"]["defect_detection_rate"] == 100.0
    assert res["defect_testing"]["clean_pass_rate"] == 100.0
    assert res["defect_testing"]["caught_defects_count"] == 7

def test_evaluate_medications_table():
    """Đánh giá chi tiết bảng medications trên Golden Dataset"""
    res = golden_dataset_evaluator.evaluate_table("medications")
    assert res["table_name"] == "medications"
    assert res["metrics"]["recall"] >= 90.0
    assert res["defect_testing"]["defect_detection_rate"] == 100.0
    assert res["defect_testing"]["clean_pass_rate"] == 100.0
    assert res["defect_testing"]["caught_defects_count"] == 7

def test_evaluate_observations_table():
    """Đánh giá chi tiết bảng observations trên Golden Dataset"""
    res = golden_dataset_evaluator.evaluate_table("observations")
    assert res["table_name"] == "observations"
    assert res["metrics"]["recall"] >= 90.0
    assert res["defect_testing"]["defect_detection_rate"] == 100.0
    assert res["defect_testing"]["clean_pass_rate"] == 100.0
    assert res["defect_testing"]["caught_defects_count"] == 8

def test_run_benchmark_overall():
    """Kiểm tra báo cáo benchmark tổng thể 3 bảng"""
    benchmark = golden_dataset_evaluator.run_benchmark(force_refresh=True)
    summary = benchmark["overall_summary"]
    
    assert summary["overall_defect_detection_rate"] == 100.0
    assert summary["clean_data_pass_rate"] == 100.0
    assert summary["average_recall"] >= 90.0
    assert summary["average_f1_score"] >= 45.0
    assert len(benchmark["tables"]) == 3

def test_api_endpoint_golden_benchmark():
    """Kiểm tra Endpoint GET /api/v1/evaluation/golden-benchmark hoạt động chính xác"""
    response = client.get("/api/v1/evaluation/golden-benchmark")
    assert response.status_code == 200
    data = response.json()
    assert "overall_summary" in data
    assert "tables" in data
    assert data["overall_summary"]["overall_defect_detection_rate"] == 100.0
