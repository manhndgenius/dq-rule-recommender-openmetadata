"""
Update NT test definitions với sqlExpression templates.

Usage:
    python scripts/update_nt_sql_expressions.py [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / "backend" / ".env"

# SQL templates cần update
NT_SQL_EXPRESSIONS = {
    "NT1_TableNaming": """
SELECT '{{ table_name }}' AS table_name
WHERE '{{ table_name }}' !~ '^[a-z][a-z0-9_]*$'
   OR '{{ table_name }}' ~ '[A-Z]'
   OR '{{ table_name }}' ~ '\\s'
   OR '{{ table_name }}' ~ '[^a-z0-9_]'
LIMIT 1""",
    "NT2_ColumnNaming": """
SELECT column_name
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
  AND (
    column_name !~ '^[a-z][a-z0-9_]*$'
    OR column_name ~ '[A-Z]'
    OR column_name ~ '\\s'
    OR column_name ~ '[^a-z0-9_]'
  )""",
    "NT4_AuditColumns": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_name = '{{ table_name }}'
      AND c.column_name IN ('id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active')
    HAVING COUNT(DISTINCT c.column_name) >= 6
)
LIMIT 1""",
    "NT5_DateTimeColumns": """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
  AND (
    (column_name LIKE '%_at' AND data_type NOT IN ('timestamp', 'timestamptz', 'TIMESTAMP', 'TIMESTAMPTZ'))
    OR
    (column_name LIKE '%_date' AND data_type NOT IN ('date', 'DATE'))
  )""",
    "NT6_SoftDelete": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_name = '{{ table_name }}'
      AND (
        (c.column_name = 'is_active' AND c.data_type LIKE '%boolean%')
        OR
        (c.column_name = 'deleted_at' AND c.data_type IN ('timestamp', 'timestamptz'))
      )
)
LIMIT 1""",
    "NT7_TableComment": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_description d
    JOIN pg_catalog.pg_class c ON c.oid = d.objoid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = '{{ table_name }}'
      AND n.nspname = 'public'
      AND d.objsubid = 0
      AND d.description IS NOT NULL
      AND d.description != ''
)
LIMIT 1""",
    "NT10_ColumnDescription": """
SELECT c.column_name
FROM information_schema.columns c
LEFT JOIN pg_catalog.pg_description pd
    ON pd.objoid = (SELECT oid FROM pg_class WHERE relname = '{{ table_name }}')
    AND pd.objsubid = c.ordinal_position
WHERE c.table_name = '{{ table_name }}'
  AND c.column_name NOT IN ('id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active')
  AND pd.description IS NULL
  AND c.column_name !~ '^(id|_id|_at|_by|is_|is_active)$'""",
    "NT11_TableTooWide": """
SELECT '{{ table_name }}' AS table_name, COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
GROUP BY table_name
HAVING COUNT(*) > 50""",
    "NT12_DomainOwner": """
SELECT
    t.table_name,
    CASE
        WHEN o.owner IS NULL THEN 'Missing Owner'
        WHEN d.domain IS NULL THEN 'Missing Domain'
        ELSE 'OK'
    END AS issue
FROM information_schema.tables t
LEFT JOIN LATERAL (
    SELECT 1 AS owner
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_catalog.pg_description desc ON desc.objoid = c.oid AND desc.objsubid = 0
    WHERE c.relname = t.table_name
      AND n.nspname = 'public'
) o ON true
LEFT JOIN LATERAL (
    SELECT 1 AS domain
    FROM pg_catalog.pg_description desc
    JOIN pg_catalog.pg_class c ON c.oid = desc.objoid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = t.table_name
      AND n.nspname = 'public'
      AND desc.objsubid = 0
) d ON true
WHERE t.table_name = '{{ table_name }}'
  AND t.table_schema = 'public'
  AND (o.owner IS NULL OR d.domain IS NULL)""",
    "NT13_NullableRate": """
SELECT
    c.column_name,
    ROUND(
        COALESCE((SELECT COUNT(*) FROM "{{ table_name }}" WHERE {{ table_name }}.c.column_name IS NULL), 0)::numeric /
        NULLIF((SELECT COUNT(*) FROM "{{ table_name }}"), 0) * 100,
        2
    ) AS nullable_rate
FROM information_schema.columns c
WHERE c.table_name = '{{ table_name }}'
  AND c.is_nullable = 'YES'""",
    "NT14_BusinessKey": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_name = '{{ table_name }}'
      AND (
        c.column_name LIKE '%_code'
        OR c.column_name LIKE '%_no'
        OR c.column_name LIKE '%_number'
        OR c.column_name LIKE '%_ref'
      )
)
LIMIT 1""",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Update NT test definitions with sqlExpression")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads without sending HTTP requests")
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser.parse_args()


def main():
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

    # Step 1: Get existing definitions
    print("Fetching existing test definitions...")
    resp = session.get(f"{base_url}/api/v1/dataQuality/testDefinitions?limit=50", timeout=args.timeout)

    if not resp.ok:
        print(f"ERROR: Failed to fetch definitions: {resp.status_code}")
        return 1

    data = resp.json()
    definitions = {item["name"]: item for item in data.get("data", []) if item.get("name", "").startswith("NT")}
    print(f"Found {len(definitions)} NT definitions")

    # Step 2: Update each definition
    updated = []
    failed = []
    skipped = []

    for name, sql_template in NT_SQL_EXPRESSIONS.items():
        if name not in definitions:
            skipped.append(name)
            print(f"SKIP  {name} (not found)")
            continue

        defn = definitions[name]
        defn_id = defn.get("id")

        # Check if already has sqlExpression
        if defn.get("sqlExpression"):
            print(f"SKIP  {name} (already has sqlExpression)")
            skipped.append(name)
            continue

        # Build patch payload - update parameterDefinition to include sqlExpression
        param_def = defn.get("parameterDefinition", [])

        # Add sqlExpression param if not present
        param_names = [p.get("name") for p in param_def]
        if "sqlExpression" not in param_names:
            param_def.append({
                "name": "sqlExpression",
                "displayName": "sqlExpression",
                "description": "SQL query whose failing rows are reported by the test.",
                "dataType": "STRING",
                "required": True,
            })

        patch_payload = [
            {"op": "replace", "path": "/parameterDefinition", "value": param_def},
            {"op": "add", "path": "/sqlExpression", "value": sql_template.strip()},
        ]

        if args.dry_run:
            print(f"[DRY-RUN] would PATCH {name} (id={defn_id})")
            print(f"  sqlExpression: {sql_template.strip()[:100]}...")
            continue

        # Send PATCH request
        patch_url = f"{base_url}/api/v1/dataQuality/testDefinitions/{defn_id}"
        patch_headers = {**headers, "Content-Type": "application/json-patch+json"}

        try:
            resp = session.patch(
                patch_url,
                data=json.dumps(patch_payload),
                headers=patch_headers,
                timeout=args.timeout
            )

            if resp.ok:
                updated.append(name)
                print(f"UPDATE {name} (id={defn_id})")
            else:
                failed.append({"name": name, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
                print(f"FAIL  {name}: HTTP {resp.status_code}")
        except requests.RequestException as exc:
            failed.append({"name": name, "error": str(exc)})
            print(f"FAIL  {name}: {exc}")

    print("\n=== Summary ===")
    print(f"  Updated : {len(updated)}  -> {updated}")
    print(f"  Skipped : {len(skipped)}  -> {skipped}")
    print(f"  Failed  : {len(failed)}")
    if failed:
        for f in failed:
            print(f"    - {f['name']}: {f['error']}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
