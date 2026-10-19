"""API routes cho Test Cases."""

import hashlib
import logging
from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.integrations.openmetadata.client import openmetadata_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.api_prefix}/tables", tags=["test-cases"])

def _generate_test_case_name(table_fqn: str, definition_name: str) -> str:
    """Tạo tên unique cho test case."""
    hash_suffix = hashlib.md5(f"{table_fqn}:{definition_name}".encode()).hexdigest()[:8]
    return f"dq_default_{definition_name}_{hash_suffix}"


@router.get("/test-definitions")
async def get_test_definitions():
    """
    Lấy NT Test Definitions trực tiếp từ OpenMetadata.

    OpenMetadata là source of truth cho danh tính và metadata của definitions.
    """
    definitions = openmetadata_client.get_test_definitions(prefix="NT")
    return {
        "total": len(definitions),
        "data": definitions
    }


@router.post("/{table_fqn}/test-cases/default")
async def create_default_test_cases(table_fqn: str):
    """
    Tạo native NT Test Cases từ tất cả enabled NT Test Definitions.

    Flow:
    1. Lấy tất cả NT definitions từ OpenMetadata.
    2. Liên kết mỗi Test Case trực tiếp với NT Test Definition tương ứng.
    3. DQ Backend đọc config riêng và thực thi handler của rule.
    """
    # Validate table_fqn
    if not table_fqn or "." not in table_fqn:
        raise HTTPException(status_code=400, detail="Invalid table_fqn format")

    # Extract table name from FQN
    table_name = table_fqn.split(".")[-1]

    # OpenMetadata is the source of truth for Test Definitions and Test Cases.
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

    invalid_definitions = []
    prepared_definitions = []
    for definition in definitions:
        definition_name = definition.get("name", "")
        reasons = []
        if definition.get("entityType") != "TABLE":
            reasons.append(
                f"entityType must be TABLE, got {definition.get('entityType')}"
            )
        if reasons:
            invalid_definitions.append({
                "definition": definition_name,
                "reasons": reasons,
            })
        else:
            prepared_definitions.append(definition)

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
    skipped_cases = []
    failed_cases = []

    for definition in prepared_definitions:
        definition_name = definition["name"]
        test_case_name = _generate_test_case_name(table_fqn, definition_name)
        existing_case = existing_by_name.get(test_case_name)
        if existing_case:
            skipped_cases.append(
                {
                    "name": test_case_name,
                    "sourceDefinition": definition_name,
                    "status": "EXISTS",
                    "id": existing_case.get("id"),
                    "fullyQualifiedName": existing_case.get("fullyQualifiedName"),
                }
            )
            continue

        test_case = {
            "name": test_case_name,
            "displayName": f"{definition.get('displayName', definition_name)} - {table_name}",
            "description": f"NT governance test generated from Test Definition {definition_name}.",
            "testDefinition": definition_name,
            "entityLink": f"<#E::table::{table_fqn}>",
            "parameterValues": [],
            "computePassedFailedRowCount": False,
        }

        # Existing identities were skipped above, so PUT only creates a missing case.
        result = openmetadata_client.upsert_test_case(test_case)

        if result.get("success"):
            data = result.get("data", {})
            created_cases.append({
                "name": test_case["name"],
                "sourceDefinition": definition_name,
                "testDefinition": definition_name,
                "status": "UPSERTED",
                "id": data.get("id"),
                "fullyQualifiedName": data.get("fullyQualifiedName")
            })
            logger.info(f"Upserted test case: {test_case['name']}")

        else:
            failed_cases.append({
                "sourceDefinition": definition_name,
                "testDefinition": definition_name,
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
        "skipped_count": len(skipped_cases),
        "failed_count": len(failed_cases),
        "test_cases": created_cases,
        "skipped": skipped_cases,
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
