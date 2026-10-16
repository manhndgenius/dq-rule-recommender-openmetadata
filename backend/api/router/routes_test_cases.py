"""API routes cho Test Cases."""

import hashlib
import logging
import re
from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.integrations.openmetadata.client import openmetadata_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.api_prefix}/tables", tags=["test-cases"])

CUSTOM_SQL_TEST_DEFINITION = "tableCustomSQLQuery"
DEFAULT_CUSTOM_SQL_PARAMETERS = [
    {"name": "strategy", "value": "ROWS"},
    {"name": "operator", "value": "<="},
    {"name": "threshold", "value": "0"},
]

def _generate_test_case_name(table_fqn: str, definition_name: str) -> str:
    """Tạo tên unique cho test case."""
    hash_suffix = hashlib.md5(f"{table_fqn}:{definition_name}".encode()).hexdigest()[:8]
    return f"dq_default_{definition_name}_{hash_suffix}"


@router.get("/test-definitions")
async def get_test_definitions():
    """
    Lấy NT Test Definitions trực tiếp từ OpenMetadata.

    OpenMetadata là source of truth cho sqlExpression và parameterDefinition.
    """
    definitions = openmetadata_client.get_test_definitions(prefix="NT")
    return {
        "total": len(definitions),
        "data": definitions
    }


@router.post("/{table_fqn}/test-cases/default")
async def create_default_test_cases(table_fqn: str):
    """
    Tạo custom SQL Test Cases từ tất cả enabled NT Test Definitions.

    Flow:
    1. Lấy tất cả NT definitions từ OpenMetadata.
    2. Lấy SQL từ TestDefinition.sqlExpression và render table_name.
    3. Tạo Test Case bằng definition chung tableCustomSQLQuery.
    4. Map SQL đã render vào parameterValues.sqlExpression.
    """
    # Validate table_fqn
    if not table_fqn or "." not in table_fqn:
        raise HTTPException(status_code=400, detail="Invalid table_fqn format")

    # Extract table name from FQN
    table_name = table_fqn.split(".")[-1]

    # OpenMetadata is the source of truth for definitions and SQL expressions.
    definitions = openmetadata_client.get_test_definitions(prefix="NT")
    definitions = [d for d in definitions if d.get("enabled", True)]

    if not definitions:
        return {
            "success": False,
            "table_fqn": table_fqn,
            "table_name": table_name,
            "definition_count": 0,
            "definitions_found": [],
            "created_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "test_cases": [],
            "skipped": [],
            "failed": [],
            "error": "No enabled NT Test Definitions found on OpenMetadata.",
        }

    invalid_definitions = []
    prepared_definitions = []
    for definition in definitions:
        definition_name = definition.get("name", "")
        sql_expression = definition.get("sqlExpression")
        reasons = []
        if definition.get("entityType") != "TABLE":
            reasons.append(
                f"entityType must be TABLE, got {definition.get('entityType')}"
            )
        if not sql_expression:
            reasons.append("Missing sqlExpression on Test Definition")

        rendered_sql = None
        if sql_expression:
            rendered_sql = re.sub(
                r"\{\{\s*table_name\s*\}\}",
                table_name,
                sql_expression,
            )
            if re.search(r"\{\{.*?\}\}", rendered_sql, flags=re.DOTALL):
                reasons.append("SQL contains unsupported unresolved template variables")

        if reasons:
            invalid_definitions.append({
                "definition": definition_name,
                "reasons": reasons,
            })
        else:
            prepared_definitions.append((definition, rendered_sql))

    if invalid_definitions:
        return {
            "success": False,
            "table_fqn": table_fqn,
            "table_name": table_name,
            "definition_count": len(definitions),
            "created_count": 0,
            "skipped_count": 0,
            "failed_count": len(invalid_definitions),
            "test_cases": [],
            "skipped": [],
            "failed": invalid_definitions,
            "error": "NT Test Definition catalog is not ready for default Test Cases.",
        }

    created_cases = []
    failed_cases = []

    for definition, rendered_sql in prepared_definitions:
        definition_name = definition["name"]

        test_case = {
            "name": _generate_test_case_name(table_fqn, definition_name),
            "displayName": f"{definition.get('displayName', definition_name)} - {table_name}",
            "description": f"Custom SQL test generated from Test Definition {definition_name}.",
            "testDefinition": CUSTOM_SQL_TEST_DEFINITION,
            "entityLink": f"<#E::table::{table_fqn}>",
            "parameterValues": [
                {"name": "sqlExpression", "value": rendered_sql},
                *DEFAULT_CUSTOM_SQL_PARAMETERS,
            ],
            "computePassedFailedRowCount": False,
        }

        # PUT creates a missing case and updates an existing case with the same identity.
        result = openmetadata_client.upsert_test_case(test_case)

        if result.get("success"):
            data = result.get("data", {})
            created_cases.append({
                "name": test_case["name"],
                "sourceDefinition": definition_name,
                "testDefinition": CUSTOM_SQL_TEST_DEFINITION,
                "status": "UPSERTED",
                "id": data.get("id"),
                "fullyQualifiedName": data.get("fullyQualifiedName")
            })
            logger.info(f"Upserted test case: {test_case['name']}")

        else:
            failed_cases.append({
                "sourceDefinition": definition_name,
                "testDefinition": CUSTOM_SQL_TEST_DEFINITION,
                "name": test_case["name"],
                "error": result.get("error", "Unknown error")
            })
            logger.error(f"Failed to create test case {definition_name}: {result.get('error')}")

    return {
        "success": len(failed_cases) == 0,
        "table_fqn": table_fqn,
        "table_name": table_name,
        "definition_count": len(definitions),
        "created_count": len(created_cases),
        "skipped_count": 0,
        "failed_count": len(failed_cases),
        "test_cases": created_cases,
        "skipped": [],
        "failed": failed_cases
    }


@router.get("/{table_fqn}/test-cases/default/status")
async def get_default_test_case_status(table_fqn: str):
    """Return every NT governance definition and its application status."""
    if not table_fqn or "." not in table_fqn:
        raise HTTPException(status_code=400, detail="Invalid table_fqn format")

    definitions = openmetadata_client.get_test_definitions(prefix="NT")
    definitions = [definition for definition in definitions if definition.get("enabled", True)]
    existing_result = openmetadata_client.get_table_test_cases(table_fqn)

    if not existing_result.get("success"):
        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to read existing Test Cases from OpenMetadata: "
                f"{existing_result.get('error', 'Unknown error')}"
            ),
        )

    existing_by_name = {
        test_case.get("name"): test_case
        for test_case in existing_result.get("data", [])
        if test_case.get("name")
    }
    statuses = []

    for definition in definitions:
        definition_name = definition.get("name", "")
        test_case_name = _generate_test_case_name(table_fqn, definition_name)
        existing_case = existing_by_name.get(test_case_name)
        statuses.append({
            **definition,
            "status": "APPLIED" if existing_case else "NOT_APPLIED",
            "applied": existing_case is not None,
            "testCaseName": test_case_name,
            "testCaseId": existing_case.get("id") if existing_case else None,
            "testCaseFqn": (
                existing_case.get("fullyQualifiedName") if existing_case else None
            ),
        })

    applied_count = sum(1 for item in statuses if item["applied"])
    return {
        "table_fqn": table_fqn,
        "total": len(statuses),
        "applied_count": applied_count,
        "not_applied_count": len(statuses) - applied_count,
        "data": statuses,
    }


@router.get("/{table_fqn}/test-cases")
async def get_table_test_cases(table_fqn: str):
    """
    Lấy danh sách test cases của một table từ OpenMetadata.
    """
    result = openmetadata_client.get_table_test_cases(table_fqn)
    return {
        "data": result.get("data", []),
        "total": result.get("total", 0),
        **({"error": result.get("error")} if not result.get("success") else {}),
    }
