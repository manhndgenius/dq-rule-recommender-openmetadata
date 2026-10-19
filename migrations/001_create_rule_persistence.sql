CREATE TABLE IF NOT EXISTS dq_rules (
    id BIGSERIAL PRIMARY KEY,
    rule_id VARCHAR(255) NOT NULL UNIQUE,
    table_name VARCHAR(255) NOT NULL,
    table_fqn TEXT,
    rule_type VARCHAR(100) NOT NULL,
    subtype VARCHAR(100),
    description TEXT,
    target_columns TEXT[] NOT NULL DEFAULT '{}',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression TEXT,
    engine VARCHAR(20) NOT NULL DEFAULT 'BASIC',
    confidence DECIMAL(5,4) NOT NULL DEFAULT 1.0,
    reason TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_status VARCHAR(20) NOT NULL DEFAULT 'VALID',
    validation_message TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    edited_parameters JSONB,
    profile_metric VARCHAR(100),
    profile_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    threshold_status VARCHAR(50),
    sql TEXT,
    rendered_sql TEXT,
    violation_predicate TEXT,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    rule_fingerprint VARCHAR(64),
    generation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Additive compatibility for databases created by the legacy runtime DDL.
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS table_fqn TEXT;
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS subtype VARCHAR(100);
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS rendered_sql TEXT;
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS rule_fingerprint VARCHAR(64);
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS generation_metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS profile_metric VARCHAR(100);
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS profile_history JSONB DEFAULT '[]'::jsonb;
ALTER TABLE dq_rules ADD COLUMN IF NOT EXISTS threshold_status VARCHAR(50);
ALTER TABLE dq_rules ALTER COLUMN confidence TYPE DECIMAL(5,4);

CREATE INDEX IF NOT EXISTS idx_dq_rules_table_fqn
    ON dq_rules(table_fqn);
CREATE INDEX IF NOT EXISTS idx_dq_rules_table_engine
    ON dq_rules(table_fqn, engine);
CREATE INDEX IF NOT EXISTS idx_dq_rules_status
    ON dq_rules(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dq_rules_fingerprint
    ON dq_rules(table_fqn, engine, rule_fingerprint)
    WHERE table_fqn IS NOT NULL AND rule_fingerprint IS NOT NULL;

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

