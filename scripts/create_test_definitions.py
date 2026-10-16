"""Create the 16 governance test definitions on OpenMetadata.

All definitions share:
  - entityType = TABLE
  - supportedServices = ["Postgres"]

The script reads the JWT token + base URL from backend/.env, then POSTs each
definition to /api/v1/dataQuality/testDefinitions. Definitions that already
exist (matched by name) are skipped unless --force-update is passed.

Usage:
    python scripts/create_test_definitions.py
    python scripts/create_test_definitions.py --dry-run
    python scripts/create_test_definitions.py --force-update
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / "backend" / ".env"


# ---------------------------------------------------------------------------
# Test definition catalog
# ---------------------------------------------------------------------------
# Each entry follows OpenMetadata's TestDefinition payload contract:
#   name                 -> required, must be unique
#   displayName          -> human label
#   description          -> markdown body
#   entityType           -> TABLE | COLUMN
#   testPlatforms        -> list of supported platforms
#   supportedServices    -> list of service types this def supports
#   parameterDefinition  -> list of {name, displayName, description, dataType, required, optionValues?}
#   sqlExpression        -> optional default SQL fragment rendered in the UI
#   supportedDataTypes   -> list of column data types (only when entityType=COLUMN)
#
# We keep every definition at the TABLE level and rely on tableCustomSQLQuery
# semantics for the "how" – each rule's SQL/parameters live on the TestCase.
# ---------------------------------------------------------------------------

COMMON_FIELDS: Dict[str, Any] = {
    "entityType": "TABLE",
    "testPlatforms": ["OpenMetadata"],
    "supportedServices": ["Postgres"],
}


def _sql_param(name: str, description: str, required: bool = True) -> Dict[str, Any]:
    return {
        "name": name,
        "displayName": name,
        "description": description,
        "dataType": "STRING",
        "required": required,
    }


def _number_param(name: str, description: str, required: bool = True) -> Dict[str, Any]:
    return {
        "name": name,
        "displayName": name,
        "description": description,
        "dataType": "INT",
        "required": required,
    }


def _operator_param(
    name: str = "operator",
    description: str = "Comparison operator applied to the failing-row count.",
) -> Dict[str, Any]:
    return {
        "name": name,
        "displayName": name,
        "description": description,
        "dataType": "STRING",
        "required": True,
        "optionValues": ["<", "<=", ">", ">=", "==", "!="],
    }


def _threshold_param() -> Dict[str, Any]:
    return {
        "name": "threshold",
        "displayName": "threshold",
        "description": "Maximum allowed number of failing rows. Rows failing above the threshold mark the test as FAILED.",
        "dataType": "INT",
        "required": True,
    }


def _strategy_param() -> Dict[str, Any]:
    return {
        "name": "strategy",
        "displayName": "strategy",
        "description": "How the test executes the SQL – ROWS counts failing rows, COUNT returns a single scalar.",
        "dataType": "STRING",
        "required": True,
        "optionValues": ["ROWS", "COUNT"],
    }


def _base_sql_def(name: str, display: str, description: str) -> Dict[str, Any]:
    """Build a tableCustomSQLQuery-style definition body."""
    params = [_sql_param("sqlExpression", "SQL query whose failing rows are reported by the test."), _operator_param(), _threshold_param(), _strategy_param()]
    return {
        "name": name,
        "displayName": display,
        "description": description,
        "parameterDefinition": params,
        **COMMON_FIELDS,
    }


# 16 governance rules (NT1..NT16, skipping NT15 which is absent from the table)
RULES: List[Dict[str, Any]] = [
    _base_sql_def(
        "NT1_TableNaming",
        "Table Naming Convention",
        "Bảng phải đặt tên theo chuẩn snake_case, chỉ gồm chữ thường, số và dấu `_`.",
    ),
    _base_sql_def(
        "NT2_ColumnNaming",
        "Column Naming Convention",
        "Cột phải đặt tên theo chuẩn snake_case, chỉ gồm chữ thường, số và dấu `_`.",
    ),
    _base_sql_def(
        "NT3_BooleanNaming",
        "Boolean Naming",
        "Cột kiểu BOOLEAN phải bắt đầu bằng `is_`, `has_` hoặc `can_`.",
    ),
    _base_sql_def(
        "NT4_AuditColumns",
        "Audit Columns",
        "Bảng phải có đầy đủ các cột: `id`, `created_at`, `created_by`, `updated_at`, `updated_by`, `is_active`.",
    ),
    _base_sql_def(
        "NT5_DateTimeColumns",
        "Date Time Columns",
        "Cột kết thúc `_at` phải dùng TIMESTAMPTZ; cột kết thúc `_date` phải dùng DATE.",
    ),
    _base_sql_def(
        "NT6_SoftDelete",
        "Soft Delete",
        "Bảng phải hỗ trợ Soft Delete thông qua `is_active` hoặc `deleted_at` (TIMESTAMPTZ).",
    ),
    _base_sql_def(
        "NT7_TableComment",
        "Table Comment Standard",
        "Table Comment phải có đầy đủ Description, Domain, Owner.",
    ),
    _base_sql_def(
        "NT8_PrimaryKeyStandard",
        "Primary Key Standard",
        "PK phải là duy nhất, tên cột `id`, kiểu dữ liệu UUID. Không cho phép Composite PK.",
    ),
    _base_sql_def(
        "NT9_PrimaryKeyMissing",
        "Primary Key Missing",
        "Tất cả bảng phải có Primary Key.",
    ),
    _base_sql_def(
        "NT10_ColumnDescription",
        "Column Description",
        "Các cột nghiệp vụ phải có Description (bỏ qua các cột audit).",
    ),
    _base_sql_def(
        "NT11_TableTooWide",
        "Table Too Wide",
        "Đánh giá số lượng cột của bảng: PASS ≤ 50, WARNING 51–80, FAIL > 80.",
    ),
    _base_sql_def(
        "NT12_DomainOwner",
        "Domain Owner Validation",
        "Domain và Owner phải được khai báo; Domain phải thuộc danh mục chuẩn đã ban hành.",
    ),
    _base_sql_def(
        "NT13_NullableRate",
        "Nullable Rate",
        "Đánh giá tỷ lệ cột Nullable: PASS ≤ 50%, WARNING 50–80%, FAIL > 80%.",
    ),
    _base_sql_def(
        "NT14_BusinessKey",
        "Missing Business Key",
        "Bảng nên có ít nhất một Business Key theo pattern `_code`, `_no`, `_number`, `_ref`. Nếu không có → WARNING.",
    ),
    _base_sql_def(
        "NT16_DuplicateTable",
        "Duplicate Table Detection",
        "Phát hiện các bảng trùng tên trong cùng Service + Database nhưng xuất hiện ở nhiều Schema.",
    ),
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create governance test definitions on OpenMetadata")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without sending HTTP requests")
    parser.add_argument("--force-update", action="store_true", help="PATCH existing definitions instead of skipping them")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ENV_PATH)

    base_url = (os.getenv("OM_API") or "").rstrip("/")
    token = (os.getenv("OM_TOKEN") or "").strip()

    if not base_url or not token:
        print(f"ERROR: OM_API or OM_TOKEN missing in {ENV_PATH}", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    session = requests.Session()
    session.headers.update(headers)

    # Step 1 – fetch existing definitions so we can decide create vs skip
    existing: Dict[str, Dict[str, Any]] = {}
    list_url = f"{base_url}/api/v1/dataQuality/testDefinitions?limit=1000"
    try:
        resp = session.get(list_url, timeout=args.timeout)
        if resp.ok:
            data = resp.json()
            for item in data.get("data", []):
                existing[item.get("name")] = item
        else:
            print(f"WARN: GET testDefinitions returned {resp.status_code} – assuming empty", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"WARN: Cannot list existing definitions: {exc}", file=sys.stderr)

    print(f"Found {len(existing)} existing test definitions on the server.")
    print(f"Will process {len(RULES)} governance rules.\n")

    created: List[str] = []
    updated: List[str] = []
    skipped: List[str] = []
    failed: List[Dict[str, str]] = []

    for rule in RULES:
        name = rule["name"]
        body = {
            "name": name,
            "displayName": rule["displayName"],
            "description": rule["description"],
            "entityType": rule["entityType"],
            "testPlatforms": rule["testPlatforms"],
            "supportedServices": rule["supportedServices"],
            "parameterDefinition": rule["parameterDefinition"],
        }

        if args.dry_run:
            print(f"[DRY-RUN] would POST test definition {name}")
            print(json.dumps(body, indent=2, ensure_ascii=False))
            print("-" * 60)
            continue

        if name in existing and not args.force_update:
            skipped.append(name)
            print(f"SKIP   {name} (already exists, use --force-update to overwrite)")
            continue

        # Use PATCH (JSON-Patch) when updating, otherwise create via POST.
        if name in existing and args.force_update:
            defn_id = existing[name].get("id")
            patch_url = f"{base_url}/api/v1/dataQuality/testDefinitions/{defn_id}"
            patch_payload = [
                {"op": "replace", "path": "/displayName", "value": body["displayName"]},
                {"op": "replace", "path": "/description", "value": body["description"]},
                {"op": "replace", "path": "/parameterDefinition", "value": body["parameterDefinition"]},
                {"op": "replace", "path": "/supportedServices", "value": body["supportedServices"]},
            ]
            patch_headers = {**headers, "Content-Type": "application/json-patch+json"}
            try:
                resp = session.patch(patch_url, data=json.dumps(patch_payload), headers=patch_headers, timeout=args.timeout)
            except requests.RequestException as exc:
                failed.append({"name": name, "error": str(exc)})
                print(f"FAIL   {name}: {exc}")
                continue
            if resp.ok:
                updated.append(name)
                print(f"UPDATE {name} (id={defn_id})")
            else:
                failed.append({"name": name, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
                print(f"FAIL   {name}: HTTP {resp.status_code} {resp.text[:200]}")
        else:
            post_url = f"{base_url}/api/v1/dataQuality/testDefinitions"
            try:
                resp = session.post(post_url, json=body, timeout=args.timeout)
            except requests.RequestException as exc:
                failed.append({"name": name, "error": str(exc)})
                print(f"FAIL   {name}: {exc}")
                continue
            if resp.status_code in (200, 201):
                created.append(name)
                payload = resp.json()
                print(f"CREATE {name} (id={payload.get('id')})")
            else:
                failed.append({"name": name, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
                print(f"FAIL   {name}: HTTP {resp.status_code} {resp.text[:200]}")

    print("\n=== Summary ===")
    print(f"  Created : {len(created)}  -> {created}")
    print(f"  Updated : {len(updated)}  -> {updated}")
    print(f"  Skipped : {len(skipped)}  -> {skipped}")
    print(f"  Failed  : {len(failed)}")
    if failed:
        for f in failed:
            print(f"    - {f['name']}: {f['error']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
