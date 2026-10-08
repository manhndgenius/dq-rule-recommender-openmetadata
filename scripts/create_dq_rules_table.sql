-- Create Database (run as postgres superuser)
-- CREATE DATABASE dq_rules;

-- Connect to dq_rules database and run:

-- Drop existing table if exists (for clean start)
DROP TABLE IF EXISTS dq_rules CASCADE;
DROP TABLE IF EXISTS dq_rule_conditions CASCADE;

-- Main table for storing DQ rules
CREATE TABLE dq_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) NOT NULL UNIQUE,
    table_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(100) NOT NULL,
    description TEXT,
    target_columns TEXT[],  -- Array of column names
    parameters JSONB DEFAULT '{}',
    expression TEXT,
    engine VARCHAR(20) NOT NULL DEFAULT 'BASIC',  -- BASIC or ADVANCED
    confidence DECIMAL(3,2) DEFAULT 1.0,
    reason TEXT,
    evidence JSONB DEFAULT '{}',
    validation_status VARCHAR(20) DEFAULT 'VALID',
    validation_message TEXT,
    status VARCHAR(20) DEFAULT 'DRAFT',  -- DRAFT, ACCEPTED, EDITED, REJECTED
    -- Advanced rule specific fields
    sql TEXT,
    violation_predicate TEXT,
    params JSONB DEFAULT '{}',
    conditions JSONB DEFAULT '[]',
    edited_parameters JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for conditions (1:N relationship)
CREATE TABLE dq_rule_conditions (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(255) NOT NULL REFERENCES dq_rules(rule_id) ON DELETE CASCADE,
    condition_index INTEGER NOT NULL,
    condition_type VARCHAR(50),
    condition_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_dq_rules_table_name ON dq_rules(table_name);
CREATE INDEX idx_dq_rules_engine ON dq_rules(engine);
CREATE INDEX idx_dq_rules_rule_type ON dq_rules(rule_type);
CREATE INDEX idx_dq_rules_status ON dq_rules(status);
CREATE INDEX idx_dq_rule_conditions_rule_id ON dq_rule_conditions(rule_id);

-- Comments
COMMENT ON TABLE dq_rules IS 'Stores all DQ rule recommendations';
COMMENT ON TABLE dq_rule_conditions IS 'Stores conditions for advanced rules';
COMMENT ON COLUMN dq_rules.engine IS 'BASIC = heuristics, ADVANCED = LLM-generated';
COMMENT ON COLUMN dq_rules.sql IS 'SQL query for advanced rules';
COMMENT ON COLUMN dq_rules.violation_predicate IS 'SQL that returns violating rows';

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON TABLE dq_rules TO your_app_user;
-- GRANT ALL PRIVILEGES ON TABLE dq_rule_conditions TO your_app_user;
