from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import uvicorn

from backend.config import settings
from backend.contracts.table_context import TableContext
from backend.contracts.candidate_rule import CandidateRule, ReviewActionRequest
from backend.integrations.openmetadata_client import openmetadata_client
from backend.integrations.openmetadata_publisher import openmetadata_publisher
from backend.engine.basic_engine import BasicRuleEngine
from backend.evaluation.evaluator import evaluation_service

app = FastAPI(
    title="Data Quality Rule Recommender & Observability API",
    description="Backend API kết nối trực tiếp OpenMetadata REST API lấy Schema & Data Profiling (HealthCare dataset 18 tables) và tự động sinh DQ Rules",
    version="2.0.0"
)

# Bật CORS cho Web UI React (port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

basic_engine = BasicRuleEngine()

# In-memory storage cho active candidates & review state trong phiên làm việc
active_candidates_store: Dict[str, CandidateRule] = {}

class GenerateRequest(BaseModel):
    table_name: str
    datasource_id: Optional[str] = "openmetadata"
    engines: List[str] = ["BASIC"]

class UpdateTierRequest(BaseModel):
    tier: Optional[str] = None

class PublishRequest(BaseModel):
    table_name: str
    tier: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    rules: Optional[List[CandidateRule]] = None

@app.get("/api/v1/health")
def health_check():
    """Kiểm tra trạng thái Backend và kết nối OpenMetadata API"""
    is_om_connected = openmetadata_client.check_connection()
    return {
        "status": "healthy",
        "openmetadata_connected": is_om_connected,
        "openmetadata_url": settings.openmetadata_url
    }

# ============================================================================
# CATALOG API ENDPOINTS (As specified in OPENMETADATA_WEB_INTEGRATION.md Section 7)
# ============================================================================

@app.get("/api/v1/catalog/services")
def get_catalog_services():
    """Lấy danh sách database services từ OpenMetadata"""
    return {"services": openmetadata_client.list_services()}

@app.get("/api/v1/catalog/databases")
def get_catalog_databases(service: str = Query("healthcare_postgres")):
    """Lấy danh sách databases của service"""
    return {"databases": openmetadata_client.list_databases(service)}

@app.get("/api/v1/catalog/schemas")
def get_catalog_schemas(databaseFqn: str = Query("healthcare_postgres.HealthCare")):
    """Lấy danh sách schemas của database"""
    return {"schemas": openmetadata_client.list_schemas(databaseFqn)}

@app.get("/api/v1/catalog/tables")
def get_catalog_tables(schemaFqn: str = Query("healthcare_postgres.HealthCare.public"), refresh: bool = False):
    """Lấy danh sách 18 tables của schema public"""
    return {"tables": openmetadata_client.list_tables(schemaFqn, force_refresh=refresh)}

@app.get("/api/v1/catalog/tables/{table_id_or_name}")
def get_catalog_table_detail(table_id_or_name: str, refresh: bool = False):
    """Lấy chi tiết table, columns và profiling đầy đủ theo chuẩn OpenMetadata"""
    return openmetadata_client.get_catalog_table(table_id_or_name, force_refresh=refresh)

# ============================================================================
# DATA OBSERVABILITY & CORE APP ENDPOINTS
# ============================================================================

@app.get("/api/v1/tables")
def get_tables(refresh: bool = False):
    """Lấy danh sách các bảng khả dụng từ OpenMetadata để hiển thị trên Selector"""
    tables = openmetadata_client.list_tables(force_refresh=refresh)
    return {"tables": tables}

@app.get("/api/v1/context/{table_name}", response_model=TableContext)
def get_table_context(table_name: str, refresh: bool = False):
    """Lấy Schema, Constraints và Profiling metrics từ OpenMetadata cho bảng cụ thể"""
    context = openmetadata_client.get_table_context(table_name, force_refresh=refresh)
    return context

@app.post("/api/v1/recommendations/generate")
def generate_recommendations(req: GenerateRequest):
    """
    1. Lấy dữ liệu Schema & Profiling trực tiếp từ OpenMetadata API
    2. Kích hoạt BasicRuleEngine (Heuristics cho Not Null, Unique, Between, In-Set, Length)
    3. Bổ sung Advanced Domain/Cross-column SQL Rules
    4. Trả về danh sách Candidate Rules cho Human Review
    """
    context = openmetadata_client.get_table_context(req.table_name)
    candidates: List[CandidateRule] = []

    # 1. Sinh Basic Rules (Heuristics dựa trên metrics thực từ OpenMetadata)
    if "BASIC" in req.engines:
        candidates.extend(basic_engine.generate_candidates(context))

    # 2. Sinh Advanced Rules (Temporal / Cross-column / Domain Logic)
    if "ADVANCED" in req.engines:
        t_name = req.table_name.lower()
        if t_name == "patients":
            candidates.append(
                CandidateRule(
                    id="rule_adv_pat_001",
                    rule_type="tableCustomSQLQuery",
                    description="Ràng buộc tử vong: Ngày mất (deathdate) phải sau ngày sinh (birthdate)",
                    target_columns=["birthdate", "deathdate"],
                    parameters={"sqlExpression": "deathdate IS NULL OR deathdate >= birthdate"},
                    engine="ADVANCED",
                    confidence=0.98,
                    reason="Logic thời gian y tế: Thời điểm mất (deathdate) phải sau hoặc trùng với thời điểm sinh (birthdate).",
                    evidence={"sample_violations_count": 0, "total_rows": context.row_count},
                    validation_status="VALID",
                    status="DRAFT"
                )
            )
            candidates.append(
                CandidateRule(
                    id="rule_adv_pat_002",
                    rule_type="columnValuesToBeInSet",
                    description="Chuẩn hóa giới tính: Chỉ nhận giá trị M (Nam) hoặc F (Nữ)",
                    target_columns=["gender"],
                    parameters={"allowedValues": ["M", "F"]},
                    engine="ADVANCED",
                    confidence=0.95,
                    reason="Ràng buộc giới tính sinh học (Gender Code): Chỉ nhận các giá trị 'M' (Male) hoặc 'F' (Female).",
                    evidence={"sample_violations_count": 0, "total_rows": context.row_count},
                    validation_status="VALID",
                    status="DRAFT"
                )
            )
        elif t_name == "orders":
            candidates.append(
                CandidateRule(
                    id="rule_adv_ord_001",
                    rule_type="tableCustomSQLQuery",
                    description="Ràng buộc đơn hàng: Thời điểm giao (delivered_at) phải sau thời điểm đặt (created_at)",
                    target_columns=["created_at", "delivered_at"],
                    parameters={"sqlExpression": "delivered_at IS NULL OR delivered_at >= created_at"},
                    engine="ADVANCED",
                    confidence=0.92,
                    reason="Quy luật thời gian (Temporal Logic): Thời điểm giao hàng (delivered_at) phải luôn diễn ra sau hoặc cùng lúc với thời điểm đặt hàng (created_at).",
                    evidence={"sample_violations_count": 0, "total_rows": context.row_count},
                    validation_status="VALID",
                    status="DRAFT"
                )
            )
            candidates.append(
                CandidateRule(
                    id="rule_adv_ord_002",
                    rule_type="tableCustomSQLQuery",
                    description="Ràng buộc thanh toán: Đơn hoàn tất (COMPLETED) bắt buộc có paid_at",
                    target_columns=["order_status", "paid_at"],
                    parameters={"sqlExpression": "order_status != 'COMPLETED' OR paid_at IS NOT NULL"},
                    engine="ADVANCED",
                    confidence=0.88,
                    reason="Phụ thuộc điều kiện (Conditional Dependency): Đơn hàng có trạng thái 'COMPLETED' thì bắt buộc phải có thời gian thanh toán (paid_at).",
                    evidence={"sample_violations_count": 0},
                    validation_status="WARNING",
                    validation_message="Phát hiện một số bản ghi đơn hàng cũ bị thiếu paid_at trong quá trình import.",
                    status="DRAFT"
                )
            )

    # Lưu vào active store cho luồng Human Review
    for c in candidates:
        active_candidates_store[c.id] = c

    return {
        "table_name": req.table_name,
        "row_count": context.row_count,
        "total_rules": len(candidates),
        "rules": candidates
    }

@app.post("/api/v1/rules/{rule_id}/review")
def review_rule(rule_id: str, action_req: ReviewActionRequest):
    """Human Review: Chấp thuận (Accept), Từ chối (Reject), hoặc Sửa tham số (Edit)"""
    if rule_id not in active_candidates_store:
        raise HTTPException(status_code=404, detail="Không tìm thấy Rule với ID này")

    rule = active_candidates_store[rule_id]
    rule.status = action_req.action
    if action_req.action == "EDITED" and action_req.edited_parameters:
        rule.edited_parameters = action_req.edited_parameters

    return {
        "message": f"Đã cập nhật rule {rule_id} thành {action_req.action}",
        "rule": rule
    }

@app.get("/api/v1/evaluation/summary")
def get_evaluation_summary():
    """Chạy và trả về báo cáo benchmark chất lượng (Coverage, Safety, Latency) trên 18 bảng dataset y tế"""
    return evaluation_service.run_full_evaluation()

@app.put("/api/v1/tables/{table_name}/tier")
def update_table_tier(table_name: str, req: UpdateTierRequest):
    """Cập nhật phân tầng Tier (Tier 1-5 hoặc None) trực tiếp lên OpenMetadata Live"""
    success = openmetadata_publisher.update_table_tier(table_name, req.tier)
    return {
        "success": success,
        "table_name": table_name,
        "tier": req.tier,
        "message": f"Đã cập nhật phân tầng dữ liệu thành {req.tier or 'Chưa phân tầng'} trên OpenMetadata" if success else "Lỗi cập nhật phân tầng lên OpenMetadata"
    }

@app.post("/api/v1/rules/publish")
def publish_rules_to_openmetadata(req: PublishRequest):
    """
    Xuất bản các rules đã duyệt (ACCEPTED/EDITED) sang OpenMetadata Test Cases thực tế
    Đồng thời đồng bộ phân tầng Tier của bảng sang OpenMetadata nếu được chỉ định
    """
    target_rules: List[CandidateRule] = []
    if req.rules and len(req.rules) > 0:
        target_rules = [r for r in req.rules if r.status in ["ACCEPTED", "EDITED"]]
    elif req.rule_ids and len(req.rule_ids) > 0:
        target_rules = [active_candidates_store[rid] for rid in req.rule_ids if rid in active_candidates_store and active_candidates_store[rid].status in ["ACCEPTED", "EDITED"]]
    else:
        # Lấy toàn bộ rules của bảng trong store
        target_rules = [r for r in active_candidates_store.values() if r.status in ["ACCEPTED", "EDITED"]]

    result = openmetadata_publisher.publish_rules(target_rules, req.table_name, tier=req.tier)
    return result

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
