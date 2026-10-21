import logging
import uuid
import re
import json
import hashlib
import urllib.parse
from typing import List, Dict, Any, Optional
import requests

from backend.config import settings
from backend.contracts.candidate_rule import CandidateRule
from backend.engine.sql_mapper.sql_renderer import render_sql_literal, SQLRenderError
from backend.engine.sql_mapper.sql_validator import validate_sql, SQLValidationError

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
    "tableCustomSQLQuery": "tableCustomSQLQuery",
    # Advanced rule types - all map to tableCustomSQLQuery
    "TEMPORAL": "tableCustomSQLQuery",
    "CROSS_COLUMN": "tableCustomSQLQuery",
    "CONDITIONAL_DEPENDENCY": "tableCustomSQLQuery",
}

# Default execution strategy for custom SQL
DEFAULT_STRATEGY = "ROWS"
DEFAULT_OPERATOR = "<="
DEFAULT_THRESHOLD = "0"


class OpenMetadataPublisher:
    """
    Module phụ trách chuyển đổi các Candidate Rules đã duyệt (ACCEPTED/EDITED)
    thành các Test Case chính thức và xuất bản (Publish) lên OpenMetadata Server.
    """

    def __init__(self, server_url: Optional[str] = None, token: Optional[str] = None):
        self.server_url = (server_url or settings.openmetadata_base_url).rstrip("/")
        self.token = token if token is not None else settings.openmetadata_jwt_token
        self.timeout = 15
        self._test_def_cache: Dict[str, Any] = {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _upsert_test_case(
        self,
        payload: Dict[str, Any],
        table_fqn: str,
    ):
        """Create a missing TestCase, otherwise update the existing one.

        OpenMetadata 1.12.13's PUT authorization path resolves the TestCase
        before create-or-update. With a bot identity this can return 404 when
        the TestCase does not exist, so creation must use POST explicitly.
        """
        test_case_fqn = f"{table_fqn}.{payload['name']}"
        encoded_fqn = urllib.parse.quote(test_case_fqn, safe="")
        lookup_url = (
            f"{self.server_url}/dataQuality/testCases/name/{encoded_fqn}"
        )
        collection_url = f"{self.server_url}/dataQuality/testCases"

        lookup = requests.get(
            lookup_url,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        if lookup.status_code == 404:
            return requests.post(
                collection_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
        if lookup.status_code == 200:
            return requests.put(
                collection_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )
        return lookup

    def _sanitize_name(self, name: str) -> str:
        """Chuẩn hóa name theo quy tắc ký tự của OpenMetadata"""
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        return clean.strip('_').lower()

    def _generate_stable_hash(self, table_fqn: str, rule_type: str, columns: List[str], conditions: List[Any]) -> str:
        """Generate stable hash for rule identification."""
        # Create canonical representation
        canonical = f"{table_fqn}|{rule_type}|{','.join(sorted(columns))}|{json.dumps(conditions, sort_keys=True)}"
        return hashlib.md5(canonical.encode()).hexdigest()[:8]

    def _get_sql_for_rule(self, rule: CandidateRule) -> Optional[str]:
        """
        Get SQL from rule, with fallback chain.
        Priority: sql -> expression -> parameters.sqlExpression
        """
        # For ADVANCED rules, use the sql field directly
        if rule.engine == "ADVANCED":
            if rule.sql:
                return rule.sql
            if rule.violation_predicate:
                return rule.violation_predicate
            return None

        # For BASIC rules, fallback to expression or parameters
        if rule.expression:
            return rule.expression
        params = rule.edited_parameters or rule.parameters or {}
        return params.get("sqlExpression")

    def _render_sql(self, rule: CandidateRule) -> tuple[Optional[str], Optional[str]]:
        """
        Render SQL with bind parameters.

        Returns:
            Tuple of (rendered_sql, error_message)
        """
        sql = self._get_sql_for_rule(rule)
        if not sql:
            return None, "No SQL found in rule"

        # For ADVANCED rules, we need to render bind parameters
        if rule.engine == "ADVANCED" and rule.params:
            try:
                return render_sql_literal(sql, rule.params), None
            except SQLRenderError as e:
                return None, f"SQL render error: {str(e)}"

        # For BASIC rules without params, just return as-is
        return sql, None

    def build_test_case_payload(self, rule: CandidateRule, table_fqn: str) -> tuple[Dict[str, Any], Optional[str]]:
        """
        Chuyển đổi CandidateRule sang payload CreateTestCase của OpenMetadata.

        Returns:
            Tuple of (payload, error_message)
        """
        om_test_def = TEST_DEFINITION_MAPPING.get(rule.rule_type, rule.rule_type)
        params = rule.edited_parameters or rule.parameters or {}

        # Build parameter values based on rule type
        parameter_values: List[Dict[str, Any]] = []

        if om_test_def == "tableCustomSQLQuery":
            # For ADVANCED rules, render SQL with bind parameters
            rendered_sql = None
            if rule.engine == "ADVANCED" and rule.sql:
                rendered_sql, _ = self._render_sql(rule)
            elif rule.expression:
                rendered_sql = rule.expression
            elif params.get("sqlExpression"):
                rendered_sql = params.get("sqlExpression")

            if rendered_sql:
                parameter_values.append({
                    "name": "sqlExpression",
                    "value": rendered_sql
                })
            parameter_values.extend([
                {"name": "strategy", "value": DEFAULT_STRATEGY},
                {"name": "operator", "value": DEFAULT_OPERATOR},
                {"name": "threshold", "value": DEFAULT_THRESHOLD},
            ])
        elif om_test_def in ["columnValuesToBeBetween", "tableRowCountToBeBetween"]:
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
            allowed = params.get("allowedValues")
            if not isinstance(allowed, list) or not allowed:
                return {}, "allowedValues must be configured before publishing"
            val_str = ",".join(str(v) for v in allowed)
            parameter_values.append({"name": "allowedValues", "value": val_str})

        # Entity Link - Advanced rules always use table-level
        if rule.engine == "ADVANCED":
            entity_link = f"<#E::table::{table_fqn}>"
        elif rule.target_columns and len(rule.target_columns) == 1:
            col_name = rule.target_columns[0]
            entity_link = f"<#E::table::{table_fqn}::columns::{col_name}>"
        else:
            entity_link = f"<#E::table::{table_fqn}>"

        # Generate stable name with hash
        columns = rule.target_columns or []
        conditions = rule.conditions or []
        hash_suffix = self._generate_stable_hash(table_fqn, rule.rule_type, columns, conditions)

        if rule.engine == "ADVANCED":
            # Advanced rules use format: dq_adv_<table>_<rule_type>_<hash>
            table_short = table_fqn.split('.')[-1]
            tc_name = f"dq_adv_{table_short}_{rule.rule_type}_{hash_suffix}"
        else:
            # Basic rules use existing format
            base_name = f"{table_fqn.split('.')[-1]}_{om_test_def}"
            if columns:
                base_name = f"{table_fqn.split('.')[-1]}_{columns[0]}_{om_test_def}"
            tc_name = self._sanitize_name(f"{base_name}_{rule.id[-6:]}")

        display_name = rule.description or f"{rule.rule_type} on {', '.join(columns) if columns else table_fqn.split('.')[-1]}"
        description = (
            f"**Data Quality Rule ({rule.engine})**\n\n"
            f"- **Mô tả**: {display_name}\n"
            f"- **Lý do**: {rule.reason}\n"
            f"- **Độ tin cậy**: {int(rule.confidence * 100)}%\n"
            f"- **Trạng thái duyệt**: {rule.status}"
        )

        payload = {
            "name": tc_name,
            "displayName": display_name,
            "description": description,
            "testDefinition": om_test_def,
            "entityLink": entity_link,
            "parameterValues": parameter_values
        }

        if om_test_def == "tableCustomSQLQuery":
            payload["computePassedFailedRowCount"] = False

        return payload, None

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

    def publish_rules(
        self,
        rules: List[CandidateRule],
        table_name: str,
        tier: Optional[str] = None,
        table_fqn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đẩy toàn bộ danh sách Rule đã chọn lên OpenMetadata.
        Đồng thời đồng bộ phân tầng Tier của bảng lên OpenMetadata nếu được chỉ định.
        Tự động bỏ qua các rule có trạng thái REJECTED hoặc DRAFT (chỉ nhận ACCEPTED, EDITED).
        """
        # Resolve table FQN
        if not table_fqn:
            table_fqn = f"healthcare_postgres.HealthCare.public.{table_name}"

        # Update tier if provided
        tier_updated = False
        if tier is not None:
            tier_updated = self.update_table_tier(table_name, tier)

        # Filter publishable rules
        publishable_rules = [r for r in rules if r.status in ["ACCEPTED", "EDITED"]]

        if not publishable_rules:
            return {
                "success": tier_updated,
                "message": f"Da cap nhat phan tang du lieu thanh {tier} tren OpenMetadata!" if tier_updated else "Khong co rule nao o trang thai ACCEPTED hoac EDITED de xuat ban.",
                "tier_updated": tier_updated,
                "tier": tier,
                "published_count": 0,
                "failed_count": 0,
                "published_test_cases": [],
                "failed_test_cases": []
            }

        published_cases = []
        failed_cases = []

        for r in publishable_rules:
            # Build payload first to validate
            payload, build_error = self.build_test_case_payload(r, table_fqn)
            if build_error:
                logger.error(f"Build payload failed for rule {r.id}: {build_error}")
                failed_cases.append({
                    "rule_id": r.id,
                    "rule_type": r.rule_type,
                    "stage": "PAYLOAD_BUILD",
                    "error": build_error,
                    "status": "FAILED"
                })
                continue

            # For ADVANCED rules with custom SQL, validate the SQL
            if r.engine == "ADVANCED" and r.sql:
                # Get the rendered SQL from payload
                sql_value = None
                for pv in payload.get("parameterValues", []):
                    if pv.get("name") == "sqlExpression":
                        sql_value = pv.get("value", "")
                        break
                if sql_value:
                    is_valid, sql_error = validate_sql(sql_value)
                    if not is_valid:
                        logger.error(f"SQL validation failed for rule {r.id}: {sql_error}")
                        failed_cases.append({
                            "rule_id": r.id,
                            "rule_type": r.rule_type,
                            "stage": "VALIDATION",
                            "error": sql_error,
                            "status": "FAILED"
                        })
                        continue

            # Publish to OpenMetadata
            try:
                resp = self._upsert_test_case(payload, table_fqn)
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    published_cases.append({
                        "rule_id": r.id,
                        "rule_type": r.rule_type,
                        "test_case_id": data.get("id"),
                        "test_case_name": data.get("name"),
                        "fullyQualifiedName": data.get("fullyQualifiedName"),
                        "testDefinition": data.get("testDefinition", {}).get("name") if isinstance(data.get("testDefinition"), dict) else data.get("testDefinition"),
                        "href": data.get("href"),
                        "status": "SUCCESS"
                    })
                else:
                    logger.error(f"Loi publish rule {r.id}: {resp.status_code} - {resp.text}")
                    failed_cases.append({
                        "rule_id": r.id,
                        "rule_type": r.rule_type,
                        "stage": "OPENMETADATA_PUBLISH",
                        "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                        "status": "FAILED"
                    })
            except Exception as e:
                logger.error(f"Ngoai le khi publish rule {r.id}: {e}")
                failed_cases.append({
                    "rule_id": r.id,
                    "rule_type": r.rule_type,
                    "stage": "OPENMETADATA_PUBLISH",
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
