"""API routes cho datasource/catalog."""

from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from backend.config.settings import settings
from backend.contracts.candidate_rule import CandidateRule
from backend.integrations.openmetadata.client import openmetadata_client
from backend.integrations.openmetadata_publisher import openmetadata_publisher


router = APIRouter(prefix=settings.api_prefix, tags=["datasource"])


class UpdateTierRequest(BaseModel):
    """Request model cho việc cập nhật tier."""
    tier: Optional[str] = None


class PublishRequest(BaseModel):
    """Request model cho việc publish rules."""
    table_name: str
    tier: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    rules: Optional[List[CandidateRule]] = None


@router.get("/health")
def health_check():
    """Kiểm tra trạng thái Backend và kết nối OpenMetadata API."""
    is_om_connected = openmetadata_client.check_connection()
    return {
        "status": "healthy",
        "openmetadata_connected": is_om_connected,
        "openmetadata_url": settings.openmetadata_url,
    }


@router.get("/catalog/services")
def get_catalog_services():
    """Lấy danh sách database services từ OpenMetadata."""
    return {"services": openmetadata_client.list_services()}


@router.get("/catalog/databases")
def get_catalog_databases(service: str = Query("healthcare_postgres")):
    """Lấy danh sách databases của service."""
    return {"databases": openmetadata_client.list_databases(service)}


@router.get("/catalog/schemas")
def get_catalog_schemas(databaseFqn: str = Query("healthcare_postgres.HealthCare")):
    """Lấy danh sách schemas của database."""
    return {"schemas": openmetadata_client.list_schemas(databaseFqn)}


@router.get("/catalog/tables")
def get_catalog_tables(schemaFqn: str = Query("healthcare_postgres.HealthCare.public")):
    """Lấy danh sách tables của schema."""
    return {"tables": openmetadata_client.list_tables(schemaFqn)}


@router.get("/catalog/tables/{table_id_or_name}")
def get_catalog_table_detail(table_id_or_name: str):
    """Lấy chi tiết table, columns và profiling đầy đủ."""
    return openmetadata_client.get_catalog_table(table_id_or_name)


@router.get("/tables")
def get_tables():
    """Lấy danh sách các bảng khả dụng từ OpenMetadata."""
    return {"tables": openmetadata_client.list_tables()}


@router.put("/tables/{table_name}/tier")
def update_table_tier(table_name: str, req: UpdateTierRequest):
    """Cập nhật phân tầng Tier của bảng lên OpenMetadata."""
    success = openmetadata_publisher.update_table_tier(table_name, req.tier)
    return {
        "success": success,
        "table_name": table_name,
        "tier": req.tier,
        "message": f"Đã cập nhật tier thành {req.tier or 'Chưa phân tầng'}" if success else "Lỗi cập nhật tier"
    }


@router.post("/rules/publish")
def publish_rules(req: PublishRequest):
    """Xuất bản các rules đã duyệt lên OpenMetadata Test Cases."""
    target_rules: List[CandidateRule] = []
    from backend.review.review_service import review_service
    if req.rules and len(req.rules) > 0:
        target_rules = [r for r in req.rules if r.status in ["ACCEPTED", "EDITED"]]
    elif req.rule_ids and len(req.rule_ids) > 0:
        for rid in req.rule_ids:
            rule = review_service._candidates.get(rid)
            if rule and rule.status in ["ACCEPTED", "EDITED"]:
                target_rules.append(rule)
    else:
        target_rules = [r for r in review_service.list_candidates() if r.status in ["ACCEPTED", "EDITED"]]

    result = openmetadata_publisher.publish_rules(target_rules, req.table_name, tier=req.tier)
    return result
