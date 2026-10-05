import logging
import uuid
import re
import json
from typing import List, Dict, Any, Optional
import requests

from backend.config import settings
from backend.contracts.candidate_rule import CandidateRule

logger = logging.getLogger("openmetadata_publisher")

# Mapping nội bộ sang tên TestDefinition chính xác của OpenMetadata
TEST_DEFINITION_MAPPING = {
    "columnValuesToBeNotNull": "columnValuesToBeNotNull",
    "columnValuesToBeUnique": "columnValuesToBeUnique",
    "columnValuesToBeBetween": "columnValuesToBeBetween",
    "columnValuesToBeInSet": "columnValuesToBeInSet",
    "columnValuesLengthToBeBetween": "columnValueLengthsToBeBetween",
    "columnValueLengthsToBeBetween": "columnValueLengthsToBeBetween",
    "tableRowCountToBeBetween": "tableRowCountToBeBetween",
    "tableCustomSQLQuery": "tableCustomSQLQuery"
}

class OpenMetadataPublisher:
    """
    Module phụ trách chuyển đổi các Candidate Rules đã duyệt (ACCEPTED/EDITED)
    thành các Test Case chính thức và xuất bản (Publish) lên OpenMetadata Server.
    """

    def __init__(self, server_url: Optional[str] = None, token: Optional[str] = None):
        self.server_url = (server_url or settings.openmetadata_base_url).rstrip("/")
        self.token = token if token is not None else settings.openmetadata_jwt_token
        self.timeout = 15

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _sanitize_name(self, name: str) -> str:
        """Chuẩn hóa name theo quy tắc ký tự của OpenMetadata"""
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return clean.strip('_').lower()

    def build_test_case_payload(self, rule: CandidateRule, table_fqn: str) -> Dict[str, Any]:
        """Chuyển đổi CandidateRule sang payload CreateTestCase của OpenMetadata"""
        om_test_def = TEST_DEFINITION_MAPPING.get(rule.rule_type, rule.rule_type)
        params = rule.edited_parameters or rule.parameters or {}

        # 1. Entity Link
        if rule.target_columns and len(rule.target_columns) == 1:
            col_name = rule.target_columns[0]
            entity_link = f"<#E::table::{table_fqn}::columns::{col_name}>"
            base_name = f"{table_fqn.split('.')[-1]}_{col_name}_{om_test_def}"
        else:
            entity_link = f"<#E::table::{table_fqn}>"
            base_name = f"{table_fqn.split('.')[-1]}_{om_test_def}"

        tc_name = self._sanitize_name(f"{base_name}_{rule.id[-6:]}")

        # 2. Parameter values
        parameter_values: List[Dict[str, Any]] = []
        if om_test_def in ["columnValuesToBeBetween", "tableRowCountToBeBetween"]:
            if "minValue" in params and params["minValue"] is not None:
                parameter_values.append({"name": "minValue", "value": str(params["minValue"])})
            if "maxValue" in params and params["maxValue"] is not None:
                parameter_values.append({"name": "maxValue", "value": str(params["maxValue"])})
        elif om_test_def == "columnValueLengthsToBeBetween":
            if "minLength" in params and params["minLength"] is not None:
                parameter_values.append({"name": "minLength", "value": str(params["minLength"])})
            if "maxLength" in params and params["maxLength"] is not None:
                parameter_values.append({"name": "maxLength", "value": str(params["maxLength"])})
        elif om_test_def == "columnValuesToBeInSet":
            allowed = params.get("allowedValues", [])
            if isinstance(allowed, list):
                val_str = ",".join(str(v) for v in allowed)
            else:
                val_str = str(allowed)
            parameter_values.append({"name": "allowedValues", "value": val_str})
        elif om_test_def == "tableCustomSQLQuery":
            sql_expr = params.get("sqlExpression", rule.expression or "")
            parameter_values.append({"name": "sqlExpression", "value": sql_expr})

        display_name = rule.description or f"{rule.rule_type} on {', '.join(rule.target_columns) if rule.target_columns else table_fqn.split('.')[-1]}"
        description = (
            f"**Data Quality Rule ({rule.engine})**\n\n"
            f"- **Mô tả**: {display_name}\n"
            f"- **Lý do**: {rule.reason}\n"
            f"- **Độ tin cậy**: {int(rule.confidence * 100)}%\n"
            f"- **Trạng thái duyệt**: {rule.status}"
        )

        return {
            "name": tc_name,
            "displayName": display_name,
            "description": description,
            "testDefinition": om_test_def,
            "entityLink": entity_link,
            "parameterValues": parameter_values
        }

    def update_table_tier(self, table_name: str, tier: Optional[str]) -> bool:
        """
        Cập nhật phân tầng Tier (Tier.Tier1 - Tier.Tier5 hoặc None) cho Table trên OpenMetadata.
        Sử dụng JSON Patch RFC 6902 trên endpoint PATCH /api/v1/tables/{table_id}.
        """
        try:
            from backend.integrations.openmetadata_client import openmetadata_client
            # 1. Tìm table ID
            tables = openmetadata_client.list_tables()
            matched = next((t for t in tables if t.get("name") == table_name), None)
            table_id = matched.get("id") if matched else None
            
            if not table_id:
                table_fqn = f"healthcare_postgres.HealthCare.public.{table_name}"
                res = requests.get(f"{self.server_url}/tables/name/{table_fqn}?fields=tags", headers=self._get_headers(), timeout=self.timeout)
                if res.status_code == 200:
                    detail = res.json()
                    table_id = detail.get("id")
                    current_tags = detail.get("tags", [])
                else:
                    logger.error(f"Không tìm thấy bảng {table_name} trên OpenMetadata")
                    return False
            else:
                res = requests.get(f"{self.server_url}/tables/{table_id}?fields=tags", headers=self._get_headers(), timeout=self.timeout)
                current_tags = res.json().get("tags", []) if res.status_code == 200 else []

            # 2. Lọc bỏ các tag Tier cũ
            filtered_tags = [
                t for t in current_tags
                if not (t.get("tagFQN", "").lower().startswith("tier.") or t.get("name", "").lower().startswith("tier"))
            ]

            # 3. Thêm tag Tier mới nếu có giá trị
            clean_tier = None
            if tier and str(tier).strip() and str(tier).strip().lower() not in ["none", "null", "undefined", "tier: --", "--"]:
                clean_tier = str(tier).strip()
                if not clean_tier.startswith("Tier."):
                    clean_tier = f"Tier.{clean_tier}"
                filtered_tags.append({
                    "tagFQN": clean_tier,
                    "source": "Classification",
                    "labelType": "Manual",
                    "state": "Confirmed"
                })

            # 4. Gửi PATCH request
            patch_headers = {
                "Content-Type": "application/json-patch+json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}" if self.token else ""
            }
            patch_data = [
                {
                    "op": "add",
                    "path": "/tags",
                    "value": filtered_tags
                }
            ]

            patch_url = f"{self.server_url}/tables/{table_id}"
            resp = requests.patch(patch_url, headers=patch_headers, data=json.dumps(patch_data), timeout=self.timeout)
            if resp.status_code == 200:
                logger.info(f"Cập nhật thành công Tier={clean_tier} cho bảng {table_name}")
                # Invalidate backend cache
                openmetadata_client._cache.pop(f"catalog_table_{table_name}", None)
                openmetadata_client._cache.pop(f"catalog_table_{table_id}", None)
                return True
            else:
                logger.error(f"Lỗi PATCH tier {table_name}: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Ngoại lệ khi update tier cho bảng {table_name}: {e}")
            return False

    def publish_rules(self, rules: List[CandidateRule], table_name: str, tier: Optional[str] = None) -> Dict[str, Any]:
        """
        Đẩy toàn bộ danh sách Rule đã chọn lên OpenMetadata.
        Đồng thời đồng bộ phân tầng Tier của bảng lên OpenMetadata nếu được chỉ định.
        Tự động bỏ qua các rule có trạng thái REJECTED hoặc DRAFT (chỉ nhận ACCEPTED, EDITED).
        """
        table_fqn = f"healthcare_postgres.HealthCare.public.{table_name}"
        tier_updated = False
        if tier is not None:
            tier_updated = self.update_table_tier(table_name, tier)

        publishable_rules = [r for r in rules if r.status in ["ACCEPTED", "EDITED"]]

        if not publishable_rules:
            return {
                "success": tier_updated,
                "message": f"Đã cập nhật phân tầng dữ liệu thành {tier} trên OpenMetadata!" if tier_updated else "Không có rule nào ở trạng thái ACCEPTED hoặc EDITED để xuất bản.",
                "tier_updated": tier_updated,
                "tier": tier,
                "published_count": 0,
                "failed_count": 0,
                "published_test_cases": []
            }

        published_cases = []
        failed_cases = []

        url = f"{self.server_url}/dataQuality/testCases"

        for r in publishable_rules:
            payload = self.build_test_case_payload(r, table_fqn)
            try:
                resp = requests.put(url, headers=self._get_headers(), json=payload, timeout=self.timeout)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    published_cases.append({
                        "rule_id": r.id,
                        "test_case_id": data.get("id"),
                        "test_case_name": data.get("name"),
                        "fullyQualifiedName": data.get("fullyQualifiedName"),
                        "testDefinition": data.get("testDefinition", {}).get("name"),
                        "href": data.get("href"),
                        "status": "SUCCESS"
                    })
                else:
                    logger.error(f"Lỗi publish rule {r.id}: {resp.status_code} - {resp.text}")
                    failed_cases.append({
                        "rule_id": r.id,
                        "error": resp.text,
                        "status": "FAILED"
                    })
            except Exception as e:
                logger.error(f"Ngoại lệ khi publish rule {r.id}: {e}")
                failed_cases.append({
                    "rule_id": r.id,
                    "error": str(e),
                    "status": "FAILED"
                })

        return {
            "success": len(published_cases) > 0 or tier_updated,
            "table_name": table_name,
            "table_fqn": table_fqn,
            "tier_updated": tier_updated,
            "tier": tier,
            "published_count": len(published_cases),
            "failed_count": len(failed_cases),
            "published_test_cases": published_cases,
            "failed_test_cases": failed_cases,
            "openmetadata_url": self.server_url
        }

openmetadata_publisher = OpenMetadataPublisher()
