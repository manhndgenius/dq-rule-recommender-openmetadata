import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.contracts.candidate_rule import CandidateRule

client = TestClient(app)

def test_01_health_and_openmetadata_connection():
    """Yêu cầu 5: Xác nhận Backend kết nối thành công tới OpenMetadata Live server"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["openmetadata_connected"] is True
    assert "duckdns.org" in data["openmetadata_url"]

def test_02_catalog_tables_contains_18_healthcare_tables():
    """Yêu cầu 5: Xác nhận danh sách bảng là 18 bảng dataset y tế HealthCare từ OpenMetadata"""
    response = client.get("/api/v1/catalog/tables")
    assert response.status_code == 200
    tables = response.json().get("tables", [])
    assert len(tables) >= 18
    table_names = [t["name"] for t in tables]
    expected_healthcare = [
        "patients", "encounters", "claims", "medications", "conditions",
        "allergies", "careplans", "procedures", "observations", "immunizations"
    ]
    for exp in expected_healthcare:
        assert exp in table_names

def test_03_table_context_patients_real_metadata_no_mock():
    """Yêu cầu 5: Bảng patients trích xuất đúng 108 dòng, 28 cột, owner=None, tags=[], domain=None"""
    response = client.get("/api/v1/context/patients")
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "patients"
    assert data["row_count"] == 108
    assert len(data["columns"]) == 28
    assert data["owner"] is None
    assert data["domain"] is None
    assert data["tags"] == []

    # Kiểm tra cột khóa chính id và birthdate
    col_dict = {c["name"]: c for c in data["columns"]}
    assert "id" in col_dict
    assert col_dict["id"]["is_primary_key"] is True
    assert "birthdate" in col_dict
    assert col_dict["birthdate"]["profile"]["null_count"] == 0

def test_04_rule_recommendations_with_vietnamese_descriptions_and_evidence():
    """Yêu cầu 1 & 2: Sinh rules có description tiếng Việt và evidence định lượng đầy đủ"""
    req_body = {
        "table_name": "patients",
        "engines": ["BASIC", "ADVANCED"]
    }
    response = client.post("/api/v1/recommendations/generate", json=req_body)
    assert response.status_code == 200
    data = response.json()
    assert data["table_name"] == "patients"
    rules = data["rules"]
    assert len(rules) > 0

    # Kiểm tra ít nhất 1 rule Not Null có description tiếng Việt và evidence
    not_null_rule = next((r for r in rules if r["rule_type"] == "columnValuesToBeNotNull"), None)
    assert not_null_rule is not None
    assert "không được để trống" in not_null_rule["description"] or "Not Null" in not_null_rule["description"]
    assert "null_count" in not_null_rule["evidence"]
    assert "total_rows" in not_null_rule["evidence"]
    assert not_null_rule["evidence"]["total_rows"] == 108

    # Kiểm tra ít nhất 1 rule Row Count có description tiếng Việt
    row_count_rule = next((r for r in rules if r["rule_type"] == "tableRowCountToBeBetween"), None)
    assert row_count_rule is not None
    assert "dòng" in row_count_rule["description"]
    assert "current_row_count" in row_count_rule["evidence"]
    assert row_count_rule["evidence"]["current_row_count"] == 108

def test_05_human_review_actions_accept_and_edit():
    """Yêu cầu 1: Luồng Human Review hỗ trợ Accept và Edit tham số"""
    # Sinh rule trước
    gen_res = client.post("/api/v1/recommendations/generate", json={"table_name": "patients", "engines": ["BASIC"]})
    rules = gen_res.json()["rules"]
    assert len(rules) > 0
    test_rule_1 = rules[0]
    test_rule_2 = rules[1]

    # 1. Chấp thuận Rule 1 (ACCEPTED)
    rev_res1 = client.post(f"/api/v1/rules/{test_rule_1['id']}/review", json={"action": "ACCEPTED"})
    assert rev_res1.status_code == 200
    assert rev_res1.json()["rule"]["status"] == "ACCEPTED"

    # 2. Điều chỉnh tham số Rule 2 (EDITED)
    rev_res2 = client.post(f"/api/v1/rules/{test_rule_2['id']}/review", json={
        "action": "EDITED",
        "edited_parameters": {"minValue": 50, "maxValue": 200}
    })
    assert rev_res2.status_code == 200
    assert rev_res2.json()["rule"]["status"] == "EDITED"
    assert rev_res2.json()["rule"]["edited_parameters"] == {"minValue": 50, "maxValue": 200}

def test_06_publish_rules_to_live_openmetadata_server():
    """Yêu cầu 4: Đẩy Rule đã duyệt sang OpenMetadata Live server tạo TestCase thật"""
    # Tạo một rule mẫu đã được ACCEPTED
    test_rule = CandidateRule(
        id="test_publish_e2e_01",
        rule_type="columnValuesToBeNotNull",
        description="Kiểm thử E2E: Cột ngày sinh không được null",
        target_columns=["birthdate"],
        engine="BASIC",
        confidence=1.0,
        reason="Kiểm thử tích hợp xuất bản tự động lên OpenMetadata Live",
        evidence={"null_count": 0, "total_rows": 108},
        status="ACCEPTED"
    )

    pub_res = client.post("/api/v1/rules/publish", json={
        "table_name": "patients",
        "rules": [test_rule.model_dump()]
    })
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["success"] is True
    assert data["published_count"] >= 1
    cases = data["published_test_cases"]
    assert len(cases) >= 1
    assert cases[0]["status"] == "SUCCESS"
    assert cases[0]["test_case_id"] is not None
    assert "healthcare_postgres.HealthCare.public.patients" in cases[0]["fullyQualifiedName"]

def test_07_evaluation_benchmark_safety_and_coverage():
    """Yêu cầu 3: Chạy bộ Evaluation Benchmark đo lường Safety & Coverage theo LLD Mục 27"""
    eval_res = client.get("/api/v1/evaluation/summary")
    assert eval_res.status_code == 200
    report = eval_res.json()
    assert report["evaluated_tables_count"] == 18
    assert report["total_columns_evaluated"] == 258
    assert report["total_rules_generated"] > 500
    assert report["overall_column_coverage_pct"] >= 90.0

    # Kiểm tra các chỉ số an toàn (Safety Metrics)
    safety = report["safety_metrics"]
    assert safety["invalid_column_rate"] == 0.0
    assert safety["duplicate_candidate_rate"] == 0.0
    assert safety["type_validation_failure_rate"] == 0.0
    assert safety["all_safety_passed"] is True
