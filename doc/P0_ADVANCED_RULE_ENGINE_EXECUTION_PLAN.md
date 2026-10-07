# P0 Advanced Rule Engine — Execution-first Implementation Plan

## 1. Goal

Build the smallest vertical slice that can run end-to-end and print advanced rule recommendations for the current healthcare dataset:

```text
healthcare_schema.json + healthcare_profile.json
    -> Context Builder
    -> Multi-label Router
    -> Cross-column Generator
    -> Conditional Dependency Generator
    -> JSON result
```

The first milestone is a working CLI, not an API or UI. The CLI must run without OpenMetadata and must never read raw healthcare rows.

## 2. P0 scope

Included:

1. Context Builder.
2. Multi-label Router.
3. Cross-column Generator.
4. Conditional Dependency Generator.
5. Minimal shared models required to connect those four modules.
6. CLI orchestration and JSON output so the engine can be inspected immediately.
7. Unit tests and one end-to-end smoke test.

Explicitly deferred:

- Temporal Generator as a separate generator.
- Full Rule Validator, duplicate/conflict detection, and confidence gate.
- Native OpenMetadata mapping and Custom SQL generation/execution.
- Human review, persistence, API, and UI.
- Publishing test cases to OpenMetadata.
- Reading raw rows or sending PII/PHI to an LLM.

Temporal comparisons such as `stop_at >= start_at` may be emitted by the Cross-column Generator in P0. A separate Temporal Generator remains out of scope.

## 3. Execution strategy

Support two providers behind the same interface:

- `fixture`: deterministic structured responses for a guaranteed local smoke run without credentials.
- `llm`: real structured model calls for semantic P0 acceptance.

The fixture provider proves pipeline wiring, parsing, routing, generator dispatch, and output serialization. It is not counted as proof of semantic quality. The real LLM mode must pass the same contracts without changing the Context Builder, Router, generators, or CLI.

Current `.env` only contains OpenMetadata settings, so live LLM execution will require these additional settings:

```env
LLM_PROVIDER=
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=30
```

Secrets must not be committed or logged.

## 4. Proposed project structure

```text
advanced_rules/
├── __init__.py
├── cli.py
├── config.py
├── models.py
├── context/
│   ├── __init__.py
│   ├── builder.py
│   └── candidate_selector.py
├── llm/
│   ├── __init__.py
│   ├── client.py
│   ├── fixture_client.py
│   └── structured_parser.py
├── routing/
│   ├── __init__.py
│   └── router.py
├── generators/
│   ├── __init__.py
│   ├── cross_column.py
│   └── conditional_dependency.py
└── prompts/
    ├── router.txt
    ├── cross_column.txt
    └── conditional_dependency.txt

tests/
├── fixtures/
│   ├── minimal_context.json
│   ├── router_response.json
│   ├── cross_column_response.json
│   └── conditional_response.json
├── test_context_builder.py
├── test_candidate_selector.py
├── test_router.py
├── test_generators.py
└── test_engine_e2e.py
```

No FastAPI package or application database is needed for this slice.

## 5. Contracts to lock first

Use dataclasses or Pydantic consistently. Prefer Pydantic if adding one small dependency is acceptable; otherwise use frozen dataclasses plus explicit JSON parsing.

### 5.1 Normalized context

```python
class ColumnProfile:
    row_count: int
    values_count: int
    null_count: int
    null_ratio: float
    distinct_count: int
    distinct_ratio: float
    min_value: object | None
    max_value: object | None
    min_length: int | None
    max_length: int | None

class ColumnContext:
    name: str
    data_type: str  # STRING, INTEGER, NUMBER, DATE, DATETIME, BOOLEAN, UUID
    description: str | None
    nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key: str | None
    profile: ColumnProfile

class TableContext:
    database_name: str
    schema_name: str
    table_name: str
    table_description: str | None
    row_count: int
    columns: list[ColumnContext]
    relationships: list[dict]
    existing_rules: list[dict]
```

### 5.2 Router output

```python
class RoutedCandidate:
    type: Literal["CROSS_COLUMN", "CONDITIONAL_DEPENDENCY"]
    confidence: float
    evidence_columns: list[str]
    reason: str

class RouterResult:
    candidate_rule_types: list[RoutedCandidate]
```

The router is multi-label and may return zero, one, or multiple candidates. It must not generate a rule expression.

### 5.3 Generator output

This is only a thin P0 DTO, not the full Canonical Rule/Validator module:

```python
class GeneratedRule:
    rule_id: str
    rule_category: Literal["CROSS_COLUMN", "CONDITIONAL_DEPENDENCY"]
    target_table: str
    columns: list[str]
    condition: str
    reason: str
    evidence: list[dict]
    confidence: float
    status: Literal["CANDIDATE"] = "CANDIDATE"
```

## 6. Milestone 1 — Context Builder

### Inputs

- `healthcare_schema.json`: descriptions, declared types, PK/FK hints, relationships.
- `healthcare_profile.json`: actual table/column names and full profile metrics.

### Required behavior

1. Load and validate both JSON documents.
2. Index tables case-insensitively.
3. Treat profile names as the authoritative physical names.
4. Enrich physical columns with semantic descriptions and constraints from the schema file.
5. Normalize PostgreSQL types:
   - text/varchar -> `STRING`
   - int/bigint/smallint -> `INTEGER`
   - numeric/decimal/float/double -> `NUMBER`
   - date -> `DATE`
   - timestamp/timestamptz/datetime -> `DATETIME`
   - boolean -> `BOOLEAN`
   - uuid -> `UUID`
6. Normalize profile names:
   - `nullProportion` -> `null_ratio`
   - `distinctProportion` -> `distinct_ratio`
   - `min`/`max` -> `min_value`/`max_value`
7. Compute `nullable` from declared schema and observed nulls without treating observed non-null data as a permanent business constraint.
8. Build FK relationships from `foreignKey` declarations.
9. Emit one `TableContext` per selected table or all tables.

### Schema/profile name mismatch rule

The semantic schema uses original CSV names such as `START`, while the physical profile uses names such as `start_at` or `start_date`. Matching order:

1. case-insensitive exact name;
2. normalized alias match;
3. guarded ordinal match only when table column counts and normalized datatypes agree;
4. otherwise keep the physical column with no description and emit a warning.

No silent fuzzy match is allowed.

### Deliverable

```bash
python -m advanced_rules.cli context --table encounters
```

This prints a valid `TableContext` JSON containing physical names such as `start_at` and `stop_at`.

### Tests

- Exact and alias name matching.
- `START -> start_at` and `STOP -> stop_at` enrichment.
- Type normalization.
- Empty/missing profile values.
- Unknown schema column does not crash the builder.
- No raw rows are present in serialized context.

## 7. Milestone 2 — Candidate selector and Router

The candidate selector is deterministic and runs before the router to keep prompts small.

### Candidate selector heuristics

Cross-column candidates:

- compatible numeric pairs;
- compatible `DATE`/`DATETIME` pairs;
- semantic pairs such as start/end, from/to, created/completed, illness/service;
- related amount pairs such as total/coverage/outstanding;
- maximum group size of 4 columns.

Conditional candidates:

- status/type/category/flag columns with low distinct ratio;
- nullable result/date/value columns with related names/descriptions;
- paired fields such as reaction/description/severity;
- maximum group size of 4 columns.

UUID identifiers and PII columns are excluded unless a relationship requires them.

### Router responsibilities

- Receive lightweight table context plus candidate groups.
- Select zero, one, or multiple supported rule types.
- Return only type, confidence, evidence columns, and reason.
- Reject unsupported rule types during structured parsing.
- Return an empty list when evidence is insufficient.

### Prompt protections

- Metadata descriptions are untrusted content, not instructions.
- Only physical columns from context are allowed.
- No Basic Rules.
- No arbitrary thresholds.
- No expression/condition generation in the router.
- JSON only.

### Deliverable

```bash
python -m advanced_rules.cli route --table encounters --provider fixture
```

Expected shape:

```json
{
  "candidate_rule_types": [
    {
      "type": "CROSS_COLUMN",
      "confidence": 0.9,
      "evidence_columns": ["start_at", "stop_at"],
      "reason": "Related lifecycle timestamp columns"
    }
  ]
}
```

### Tests

- Multi-label output.
- Empty result.
- Unsupported type rejected.
- Hallucinated evidence column rejected by the output parser.
- Router never returns `condition`.

## 8. Milestone 3 — Cross-column Generator

### Input

Only the routed evidence columns plus their descriptions, normalized types, profiles, and relevant relationships.

### Allowed P0 relations

- order comparison: `>=`, `<=`, `>`, `<`;
- equality/inequality between compatible columns;
- simple arithmetic relation when semantics provide direct evidence.

### Guardrails

- Use only routed columns.
- Require compatible datatypes.
- Do not turn observed min/max into a business constraint.
- Do not emit NOT NULL, UNIQUE, RANGE, REGEX, or allowed-values rules.
- Return `[]` when the direction/relationship is ambiguous.
- Maximum 3 rules per routed candidate group.

### Initial healthcare smoke cases

- `encounters.stop_at >= encounters.start_at`
- `conditions.stop_date >= conditions.start_date`
- `payer_transitions.end_date >= payer_transitions.start_date`
- `encounters.total_claim_cost >= encounters.payer_coverage`

These are candidate recommendations, not automatically approved business truth.

### Deliverable

```bash
python -m advanced_rules.cli generate --table encounters --provider fixture
```

## 9. Milestone 4 — Conditional Dependency Generator

### Input

Only routed categorical/trigger columns and related dependent columns.

### Allowed P0 forms

```text
IF <column> = <documented value> THEN <column> IS [NOT] NULL
IF <column> IS [NOT] NULL THEN <column> IS [NOT] NULL
IF <column> = <documented value> THEN <column> <comparison> <column/value>
```

Literal values may only come from explicit descriptions/glossary or an approved categorical summary. They must not be invented. The current profile does not contain top values, so the generator must rely on descriptions or return no rule.

### Initial healthcare smoke cases

- When `allergies.reaction1` exists, `description1` should exist.
- When `allergies.reaction2` exists, `description2` should exist.
- A status-based rule may only be generated when the status value is explicitly documented in context.

### Guardrails

- No raw patient values.
- No literal inferred only from min/max.
- Use only routed columns.
- Return `[]` on weak evidence.
- Maximum 3 rules per routed candidate group.

### Deliverable

```bash
python -m advanced_rules.cli generate --table allergies --provider fixture
```

## 10. Milestone 5 — End-to-end CLI

### Commands

```bash
# Guaranteed local smoke run
python -m advanced_rules.cli generate \
  --schema healthcare_schema.json \
  --profile healthcare_profile.json \
  --table encounters \
  --provider fixture \
  --output output/encounters_rules.json

# Run every healthcare table
python -m advanced_rules.cli generate \
  --all-tables \
  --provider fixture \
  --output output/healthcare_advanced_rules.json

# Real semantic run after LLM configuration
python -m advanced_rules.cli generate \
  --table encounters \
  --provider llm \
  --output output/encounters_rules_llm.json
```

### Output envelope

```json
{
  "run": {
    "provider": "fixture",
    "database": "HealthCare",
    "tablesProcessed": 1,
    "routerSelections": 1,
    "generatedRules": 2
  },
  "tables": [
    {
      "name": "encounters",
      "routerResult": {},
      "rules": []
    }
  ]
}
```

Console logs show stage/count/latency only. They must not print API keys, authorization headers, raw patient values, or complete prompts by default.

## 11. Implementation order

1. Create package skeleton and lock models.
2. Implement Context Builder and its tests.
3. Implement deterministic candidate selector.
4. Implement LLM client protocol, fixture client, and strict structured parser.
5. Implement Router and router prompt.
6. Implement Cross-column Generator and prompt.
7. Implement Conditional Dependency Generator and prompt.
8. Implement orchestration and CLI commands.
9. Run fixture E2E on `encounters`, `conditions`, and `allergies`.
10. Run all 18 tables and inspect aggregate output.
11. Configure the real provider and run the same E2E cases in `llm` mode.
12. Record incorrect/empty candidates for the later Validator/evaluation phase.

## 12. P0 acceptance criteria

P0 is complete only when all conditions below pass:

- Context Builder creates stable context for all 18 healthcare tables.
- Physical profile names are preserved; semantic descriptions are attached without silent mismatches.
- Router supports zero/one/multiple selections and only the two scoped rule types.
- Both generators run independently and return strict JSON.
- Unknown or hallucinated columns fail parsing before reaching final output.
- Empty evidence produces an empty list instead of a guessed rule.
- Fixture mode runs end-to-end with one command and writes a result file.
- All-table fixture mode completes without reading raw CSV/PostgreSQL rows.
- Real LLM mode uses the same contracts and completes at least the agreed smoke tables once credentials are configured.
- Unit tests and E2E smoke tests pass.

## 13. Recommended first demo

Run these three tables because together they exercise both generators:

| Table | Expected route | Expected candidate |
|---|---|---|
| `encounters` | Cross-column | `stop_at >= start_at` |
| `conditions` | Cross-column | `stop_date >= start_date` |
| `allergies` | Conditional dependency | reaction field implies description field |

After this demo is stable, run all 18 tables and review noise before implementing the full Canonical Rule Schema and Validator from the larger plan.
