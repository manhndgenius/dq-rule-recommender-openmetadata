# Implementation Plan: PostgreSQL persistence for DQ rules and NT configs

## 1. Objective

Run and verify persistence locally before any shared-environment rollout, using
one PostgreSQL database named `dq_rules` and exactly two application tables:

1. `dq_rules`: generated/recommended BASIC, ADVANCED, and STATISTICAL rules.
2. `nt_rule_configs`: effective user configuration for the 15 NT governance
   rules.

OpenMetadata remains the source of truth for NT Test Definitions, Test Cases,
table metadata, and published Test Case results. The DQ recommender database
must not duplicate those entities.

Run history remains in the current in-memory `NTRunStore` during this phase.
Persisting run history is explicitly out of scope.

## 2. Current-state findings

- PostgreSQL connectivity and a `dq_rules` schema already exist in
  `backend/storage/db_service.py`.
- `RuleRepository` already supports non-destructive upserts keyed by table,
  engine, and rule fingerprint.
- Recommendation persistence is not active in the main API path:
  `routes_recommendation.py` declares `DB_AVAILABLE = False`, calls generation
  with `persist=False`, and reads previous values from an in-memory cache.
- Review updates also target the in-memory generation cache.
- NT defaults and form schema are code-owned. NT Test Definitions are loaded
  from OpenMetadata.
- NT user configuration is currently stored in browser `localStorage` and sent
  back in every `/nt-runs` request.
- `dq_rule_conditions` is not needed: `dq_rules.conditions` already stores the
  same structure as JSONB and no runtime code reads the separate table.

## 3. Architecture decisions

### 3.1 Ownership

| Data | Source of truth |
| --- | --- |
| Generated/recommended rules | PostgreSQL `dq_rules` |
| User overrides for the 15 NT rules | PostgreSQL `nt_rule_configs` |
| NT evaluator implementation/defaults/form schema | DQ recommender code |
| NT Test Definitions and Test Cases | OpenMetadata |
| Final Test Case results | OpenMetadata |
| Current run progress and retry snapshot | In-memory `NTRunStore` |

### 3.2 NT config scope

Phase 1 preserves current behavior: configuration is global per NT rule, not
per table or per user. `rule_name` is therefore unique.

If database/schema/table overrides are requested later, add `scope_type` and
`scope_fqn` in a separate migration. Do not add unused scope semantics now.

### 3.3 Merge order for effective NT config

```text
code defaults -> persisted nt_rule_configs.config
```

The backend performs this merge. The browser is not a source of truth and the
run endpoint does not trust configuration supplied by the client.

## 4. Target database schema

Use SQL migrations committed to the repository. Migrations must be
transactional and idempotent for local reruns.

### 4.1 `dq_rules`

Retain the columns used by `RuleRepository`, including:

- stable `rule_id`;
- `table_fqn`, `engine`, and `rule_fingerprint` identity;
- rule definition fields and JSONB parameters/evidence/conditions;
- review status and edited parameters;
- generated/rendered SQL;
- creation/update timestamps.

Required constraints/indexes:

```sql
UNIQUE (rule_id)
UNIQUE (table_fqn, engine, rule_fingerprint)
INDEX (table_fqn)
INDEX (table_fqn, engine)
INDEX (status)
```

The fingerprint unique index remains the protection against duplicate
recommendations across repeated generations.

### 4.2 `nt_rule_configs`

```sql
CREATE TABLE IF NOT EXISTS nt_rule_configs (
    rule_name VARCHAR(100) PRIMARY KEY,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (jsonb_typeof(config) = 'object')
);
```

Do not seed all 15 rows merely to duplicate code defaults. Insert a row only
when a user saves an override. Missing rows resolve to code defaults.

### 4.3 Legacy `dq_rule_conditions`

- Stop creating or writing this table in a clean local database.
- Do not drop it automatically in an additive migration.
- Before a later production cleanup, verify it contains no unique data; only
  then remove it with a separately approved destructive migration.

## 5. Backend implementation

### Phase A - migration and local connectivity

1. Add versioned SQL migrations, with an initial migration that creates or
   reconciles `dq_rules` and creates `nt_rule_configs`.
2. Add a small migration runner invoked explicitly from CLI; do not mutate
   schema implicitly on every request.
3. Keep all credentials in `backend/.env`; never commit the local password.
4. Add a database readiness check that runs `SELECT 1` and reports a concise
   startup/health error.
5. Make connection timeout configurable and short enough to fail visibly in
   local development.

### Phase B - persist generated rules

1. Use `RuleRepository` from the recommendation and generation-job paths.
2. Change generation to persist successful normalized candidates through the
   existing fingerprint upsert; do not delete accepted/edited/rejected/applied
   rows on regeneration.
3. When the request asks for existing rules, read PostgreSQL instead of
   `generation_cache`.
4. Change review actions to update `dq_rules` transactionally. The in-memory
   review/cache objects may remain request-local optimizations but must not be
   authoritative.
5. Return a clear `503` if PostgreSQL is unavailable rather than silently
   returning an empty rule list.

### Phase C - persist NT configs

1. Add `NTRuleConfigRepository` with:
   - `get(rule_name)`;
   - `list_all()`;
   - `upsert(rule_name, config, updated_by, expected_version)`;
   - optional `delete_override(rule_name)` to restore code defaults.
2. Validate `rule_name` against `DEFAULT_RULE_CONFIG` and validate the merged
   config with `validate_nt_rule_config` before commit.
3. Use optimistic concurrency: update only when `version` matches the version
   read by the UI; return `409` for stale edits.
4. Extend `/api/v1/nt-rules`:

```text
GET    /config-schema                 form metadata and code defaults
GET    /configs                       all persisted overrides/effective configs
GET    /{rule_name}/config            one effective config plus version
PUT    /{rule_name}/config            validate and upsert override
DELETE /{rule_name}/config            remove override; fall back to defaults
```

5. In `NTRunService.prepare`, load all persisted overrides, merge them with
   defaults, and copy the effective map into the existing in-memory run
   snapshot. This preserves consistent retry behavior during a backend
   process lifetime.
6. Stop using request-provided `rule_configs` as execution input. Keep the
   field temporarily optional only if backward compatibility is needed, then
   remove it after the UI migration.

## 6. OpenMetadata UI changes

1. Add typed API methods for reading, saving, and deleting NT config overrides.
2. Change `useNtRuleConfigModal` to load the selected rule's effective config
   from the backend and save with `PUT`.
3. Remove `localStorage` reads/writes from the production path.
4. Stop attaching `getAllNTRuleConfigs()` to `startNtRun`; send only
   `table_fqn` and `pipeline_id`.
5. Show separate loading, save-success, validation, conflict (`409`), and
   backend-unavailable states.
6. One-time localStorage migration is unnecessary unless existing browser
   values must be preserved. If required, expose an explicit import action;
   never silently overwrite database config from an arbitrary browser.

## 7. Local PostgreSQL setup

Add a local-only Compose file containing PostgreSQL only:

```text
container: dq-rule-postgres-local
host port: 5433
database: dq_rules
named volume: dq-rule-postgres-data
healthcheck: pg_isready
```

Port `5433` avoids colliding with a PostgreSQL instance used by a local
OpenMetadata stack. Configure the backend's untracked `.env` accordingly.

Local execution sequence:

1. Start the PostgreSQL container.
2. Wait for its healthcheck.
3. Run migrations explicitly.
4. Run repository/integration tests against the local database.
5. Start the DQ backend and, only when end-to-end verification requires it,
   the local OpenMetadata/UI services.
6. Exercise generate -> reload -> review and NT config -> reload -> NT run.
7. Stop every backend/OpenMetadata/UI service started during the session.
8. Stop the PostgreSQL container while preserving its named volume, then
   verify no session-started process/container remains running.

## 8. Test plan

### Repository tests

- migration from an empty database creates exactly the two application tables;
- applying migrations twice is safe;
- generated rule upsert is idempotent;
- accepted/edited/rejected/applied status survives regeneration;
- two distinct table FQNs cannot collide;
- valid NT config upserts and increments version;
- invalid rule names and invalid config are rejected without a write;
- stale version update returns a conflict;
- deleting an override restores defaults.

### Service/API tests

- recommendation reload reads persisted rules after clearing process memory;
- review status survives backend restart;
- effective NT config is defaults plus persisted override;
- `/nt-runs` snapshots database config at creation time;
- a later config edit does not alter an already-created run;
- database outage returns an explicit service error;
- Test Case results are still published only to OpenMetadata.

### UI tests

- modal loads backend config;
- save calls `PUT` and no longer writes localStorage;
- reset calls `DELETE` and displays defaults;
- `409` keeps the modal open and asks the user to reload;
- Run no longer sends browser-owned config.

### Local end-to-end acceptance

1. Generate rules for a table and verify rows in `dq_rules`.
2. Restart the DQ backend and verify the same rules are returned.
3. Accept/edit a rule, regenerate, and verify its reviewed state is preserved.
4. Edit one NT rule config, refresh or use another browser, and verify the same
   persisted value is loaded.
5. Run the 15 NT checks and verify the backend used the persisted config.
6. Verify results appear once in OpenMetadata and are not executed by a second
   executor.
7. Confirm no application server started for the test is left running.

## 9. Delivery order

1. Migration + local PostgreSQL Compose + database health check.
2. `dq_rules` persistence activation and tests.
3. `nt_rule_configs` repository/API and tests.
4. OpenMetadata UI migration away from localStorage.
5. Backend/UI regression tests.
6. Local end-to-end test, process/container shutdown, and evidence report.

## 10. Definition of done

- A clean local PostgreSQL instance contains `dq_rules` and
  `nt_rule_configs`; no new dependency on `dq_rule_conditions` exists.
- Generated rules and review state survive backend restart.
- NT config is shared across browsers and survives restart.
- NT runs use a server-side config snapshot, not browser localStorage.
- OpenMetadata remains authoritative for definitions, Test Cases, and results.
- Unit, integration, UI, and local end-to-end tests pass.
- All services started during verification are stopped before handoff.
