"""Tests for persisted NT governance application status."""

import asyncio

import pytest
from fastapi import HTTPException

from backend.api.router import routes_test_cases


TABLE_FQN = "service.database.schema.orders"


def test_default_status_matches_existing_test_cases(monkeypatch):
    definitions = [
        {"name": "NT_RULE_A", "displayName": "Rule A", "enabled": True},
        {"name": "NT_RULE_B", "displayName": "Rule B", "enabled": True},
        {"name": "NT_DISABLED", "displayName": "Disabled", "enabled": False},
    ]
    applied_name = routes_test_cases._generate_test_case_name(TABLE_FQN, "NT_RULE_A")

    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_test_definitions",
        lambda prefix: definitions,
    )
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_table_test_cases",
        lambda table_fqn: {
            "success": True,
            "total": 1,
            "data": [
                {
                    "id": "case-id",
                    "name": applied_name,
                    "fullyQualifiedName": f"{table_fqn}.{applied_name}",
                }
            ],
        },
    )

    result = asyncio.run(
        routes_test_cases.get_default_test_case_status(TABLE_FQN)
    )

    assert result["total"] == 2
    assert result["applied_count"] == 1
    assert result["not_applied_count"] == 1
    assert result["data"][0]["status"] == "APPLIED"
    assert result["data"][0]["testCaseId"] == "case-id"
    assert result["data"][1]["status"] == "NOT_APPLIED"
    assert result["data"][1]["testCaseId"] is None


def test_default_status_reports_openmetadata_failure(monkeypatch):
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_test_definitions",
        lambda prefix: [{"name": "NT_RULE_A", "enabled": True}],
    )
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_table_test_cases",
        lambda table_fqn: {
            "success": False,
            "data": [],
            "error": "connection refused",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes_test_cases.get_default_test_case_status(TABLE_FQN))

    assert exc_info.value.status_code == 502
    assert "connection refused" in exc_info.value.detail


def test_default_status_rejects_invalid_table_fqn():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(routes_test_cases.get_default_test_case_status("orders"))

    assert exc_info.value.status_code == 400
