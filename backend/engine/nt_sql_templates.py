"""SQL templates cho NT governance rules.

SQL trả về các dòng VI PHẠM rule.
{{ table_name }} sẽ được replace bằng tên table thực.
"""

NT_SQL_TEMPLATES = {
    "NT1_TableNaming": """
SELECT '{{ table_name }}' AS table_name
WHERE '{{ table_name }}' !~ '^[a-z][a-z0-9_]*$'
   OR '{{ table_name }}' ~ '[A-Z]'
   OR '{{ table_name }}' ~ '\s'
   OR '{{ table_name }}' ~ '[^a-z0-9_]'
LIMIT 1
""",
    "NT2_ColumnNaming": """
SELECT column_name
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
  AND (
    column_name !~ '^[a-z][a-z0-9_]*$'
    OR column_name ~ '[A-Z]'
    OR column_name ~ '\s'
    OR column_name ~ '[^a-z0-9_]'
  )
""",
    "NT3_BooleanNaming": """
SELECT attname AS invalid_column
FROM pg_catalog.pg_attribute a
WHERE a.attrelid = '{{ table_name }}'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND a.atttypid = 'boolean'::regtype
  AND a.attname !~ '^(is_|has_|can_)[a-z0-9_]+$'
""",
    "NT4_AuditColumns": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.columns c
    WHERE c.table_name = '{{ table_name }}'
    GROUP BY c.table_name
    HAVING COUNT(DISTINCT c.column_name) >= ARRAY_LENGTH(
        ARRAY['id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active']::text[], 1
    )
    AND bool_and(
        c.column_name IN ('id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active')
    )
)
LIMIT 1
""",
    "NT5_DateTimeColumns": """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
  AND (
    (column_name LIKE '%_at' AND data_type NOT IN ('timestamp', 'timestamptz', 'TIMESTAMP', 'TIMESTAMPTZ'))
    OR
    (column_name LIKE '%_date' AND data_type NOT IN ('date', 'DATE'))
  )
""",
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
LIMIT 1
""",
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
LIMIT 1
""",
    "NT8_PrimaryKeyStandard": """
SELECT
    tc.table_name,
    kcu.column_name,
    'Non-standard PK' AS issue
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = '{{ table_name }}'
  AND tc.constraint_type = 'PRIMARY KEY'
  AND (
    kcu.column_name != 'id'
    OR tc.constraint_name != 'pk_{{ table_name }}'
  )
""",
    "NT9_PrimaryKeyMissing": """
SELECT '{{ table_name }}' AS table_name
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints tc
    WHERE tc.table_name = '{{ table_name }}'
      AND tc.constraint_type = 'PRIMARY KEY'
)
LIMIT 1
""",
    "NT10_ColumnDescription": """
SELECT c.column_name
FROM information_schema.columns c
LEFT JOIN pg_catalog.pg_description pd
    ON pd.objoid = (SELECT oid FROM pg_class WHERE relname = '{{ table_name }}')
    AND pd.objsubid = c.ordinal_position
WHERE c.table_name = '{{ table_name }}'
  AND c.column_name NOT IN ('id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active')
  AND pd.description IS NULL
  AND c.column_name !~ '^(id|_id|_at|_by|is_|is_active)$'
""",
    "NT11_TableTooWide": """
SELECT '{{ table_name }}' AS table_name, COUNT(*) AS column_count
FROM information_schema.columns
WHERE table_name = '{{ table_name }}'
GROUP BY table_name
HAVING COUNT(*) > 50
""",
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
) o ON true
LEFT JOIN LATERAL (
    SELECT 1 AS domain
) d ON true
WHERE t.table_name = '{{ table_name }}'
  AND t.table_schema = 'public'
  AND (o.owner IS NULL OR d.domain IS NULL)
""",
    "NT13_NullableRate": """
SELECT
    c.column_name,
    ROUND(
        (SELECT COUNT(*) FROM "{{ table_name }}" WHERE c.column_name IS NULL)::numeric /
        NULLIF((SELECT COUNT(*) FROM "{{ table_name }}"), 0) * 100,
        2
    ) AS nullable_rate
FROM information_schema.columns c
WHERE c.table_name = '{{ table_name }}'
  AND c.is_nullable = 'YES'
HAVING ROUND(
    (SELECT COUNT(*) FROM "{{ table_name }}" WHERE c.column_name IS NULL)::numeric /
    NULLIF((SELECT COUNT(*) FROM "{{ table_name }}"), 0) * 100,
    2
) > 50
""",
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
LIMIT 1
""",
    "NT16_DuplicateTable": """
SELECT
    t.relname AS duplicate_table,
    COUNT(DISTINCT n.nspname) AS schema_count
FROM pg_catalog.pg_class t
JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace
WHERE t.relkind IN ('r', 'p')
  AND t.relname = (
      SELECT c.relname
      FROM pg_catalog.pg_class c
      WHERE c.oid = '{{ table_name }}'::regclass
  )
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND n.nspname NOT LIKE 'pg_temp_%'
GROUP BY t.relname
HAVING COUNT(DISTINCT n.nspname) > 1
""",
}


def get_sql_for_definition(definition_name: str, table_name: str) -> str:
    """
    Lấy SQL cho một definition và replace {{ table_name }}.

    Args:
        definition_name: Tên definition (e.g., 'NT1_TableNaming')
        table_name: Tên table thực

    Returns:
        SQL đã replace hoặc empty string nếu không có
    """
    template = NT_SQL_TEMPLATES.get(definition_name)
    if not template:
        return ""
    return template.replace("{{ table_name }}", table_name)


def get_all_definitions_with_sql() -> list:
    """Trả về danh sách tất cả definitions có SQL."""
    return [
        {"name": name, "sql": template.strip()}
        for name, template in NT_SQL_TEMPLATES.items()
    ]
