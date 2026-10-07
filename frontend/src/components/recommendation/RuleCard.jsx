import React from 'react';

// Mapping cho rule type labels
const RULE_TYPE_LABELS = {
  // Basic rule types
  'columnValuesToBeNotNull': 'Not Null',
  'columnValuesToBeUnique': 'Unique',
  'columnValuesToBeBetween': 'Range',
  'columnValuesToBeInSet': 'In Set',
  'columnValueLengthsToBeBetween': 'Length',
  'tableRowCountToBeBetween': 'Row Count',
  'tableCustomSQLQuery': 'Custom SQL',
  // Advanced rule types
  'TEMPORAL': 'Temporal Logic',
  'CROSS_COLUMN': 'Cross-Column',
  'CONDITIONAL_DEPENDENCY': 'Conditional',
};

// Mapping cho rule type badges màu
const RULE_TYPE_COLORS = {
  // Basic
  'columnValuesToBeNotNull': '#10B981',
  'columnValuesToBeUnique': '#3B82F6',
  'columnValuesToBeBetween': '#8B5CF6',
  'columnValuesToBeInSet': '#F59E0B',
  'columnValueLengthsToBeBetween': '#EC4899',
  'tableRowCountToBeBetween': '#6366F1',
  'tableCustomSQLQuery': '#EF4444',
  // Advanced
  'TEMPORAL': '#06B6D4',
  'CROSS_COLUMN': '#8B5CF6',
  'CONDITIONAL_DEPENDENCY': '#F97316',
};

export default function RuleCard({ rule, onReviewAction, onOpenEdit }) {
  const isBasic = rule.engine === 'BASIC';
  const isAdvanced = rule.engine === 'ADVANCED';
  const isValid = rule.validation_status === 'VALID';
  const isAccepted = rule.status === 'ACCEPTED';
  const isEdited = rule.status === 'EDITED';
  const isRejected = rule.status === 'REJECTED';

  // Get display label cho rule type
  const ruleTypeLabel = RULE_TYPE_LABELS[rule.rule_type] || rule.rule_type;
  const ruleTypeColor = RULE_TYPE_COLORS[rule.rule_type] || '#6B7280';

  // Columns: ADVANCED rules dùng 'columns', BASIC dùng 'target_columns'
  const displayColumns = isAdvanced ? (rule.columns || []) : (rule.target_columns || []);

  // Format parameters
  const currentParams = isEdited && rule.edited_parameters ? rule.edited_parameters : rule.parameters;
  let paramsDisplay;
  if (currentParams.sqlExpression) {
    paramsDisplay = (
      <div className="params-box sql-code">
        <strong>SQL Condition:</strong> {currentParams.sqlExpression}
      </div>
    );
  } else if (Object.keys(currentParams).length > 0) {
    const paramStrings = Object.entries(currentParams).map(([k, v]) =>
      `${k}: ${Array.isArray(v) ? `[${v.join(', ')}]` : v}`
    );
    paramsDisplay = <div className="params-box">{paramStrings.join('  •  ')}</div>;
  } else {
    paramsDisplay = (
      <div className="params-box" style={{ color: 'var(--text-subtle)' }}>
        No parameters required (Standard integrity check)
      </div>
    );
  }

  // Status Badge Label
  let statusBadgeLabel = rule.status;
  if (isAccepted) statusBadgeLabel = 'ACCEPTED ✔';
  if (isEdited) statusBadgeLabel = 'EDITED ✏';
  if (isRejected) statusBadgeLabel = 'REJECTED ✖';

  return (
    <div className={`rule-card status-${rule.status.toLowerCase()}`}>
      {/* Header */}
      <div className="card-header">
        <div className="card-header-left">
          <span className={`badge-engine ${isBasic ? 'basic' : 'advanced'}`}>
            {rule.engine}
          </span>
          {/* Rule Type Badge cho ADVANCED rules */}
          {isAdvanced && (
            <span
              className="badge-rule-type"
              style={{
                backgroundColor: `${ruleTypeColor}20`,
                color: ruleTypeColor,
                borderColor: `${ruleTypeColor}40`
              }}
            >
              {ruleTypeLabel}
            </span>
          )}
          <div className="rule-title-group">
            <span className="rule-type-name">{rule.rule_type}</span>
            {rule.description && (
              <span className="rule-desc-text">{rule.description}</span>
            )}
          </div>
        </div>
        <div className="card-header-right">
          <span className={`badge-validation ${isValid ? 'valid' : 'warning'}`}>
            {isValid ? '✅ Validated' : '⚠️ Conflict/Warning'}
          </span>
          <span className="confidence-tag">
            Confidence: {(rule.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Target Columns & Parameters */}
      <div className="card-target-params">
        <div className="target-columns">
          <span className="target-label">Target:</span>
          {displayColumns && displayColumns.length > 0 ? (
            displayColumns.map((c) => (
              <span key={c} className="column-pill">{c}</span>
            ))
          ) : (
            <span className="column-pill" style={{ fontStyle: 'italic', opacity: 0.9 }}>
              📊 Toàn bảng (Table-level)
            </span>
          )}
        </div>
        {paramsDisplay}
      </div>

      {/* SQL Violation Query cho ADVANCED rules */}
      {isAdvanced && rule.sql && (
        <div className="sql-violation-box">
          <div className="sql-violation-header">
            <span>🔍 Violation Query</span>
            <span className="sql-tag">SQL</span>
          </div>
          <code className="sql-violation-code">
            {rule.violation_predicate || rule.sql}
          </code>
          {rule.params && Object.keys(rule.params).length > 0 && (
            <div className="sql-params">
              <span className="params-label">Params:</span>
              {Object.entries(rule.params).map(([k, v]) => (
                <span key={k} className="param-item">{k}: {JSON.stringify(v)}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Explanation & Evidence */}
      <div className="card-explanation">
        <div className="reason-text">
          <span>💡</span>
          <span>{rule.reason}</span>
        </div>

        {rule.validation_message && (
          <div className="warning-callout">
            <span>⚠️</span>
            <span><strong>Validator Notice:</strong> {rule.validation_message}</span>
          </div>
        )}

        <div className="evidence-tags">
          {rule.evidence?.null_count !== undefined && (
            <span className="evidence-tag">
              Null: <strong>{rule.evidence.null_count}</strong> {rule.evidence.null_ratio !== undefined ? `(${Math.round(rule.evidence.null_ratio * 100)}%)` : ''}
            </span>
          )}
          {rule.evidence?.distinct_count !== undefined && (
            <span className="evidence-tag">
              Distinct: <strong>{rule.evidence.distinct_count}</strong> {rule.evidence.distinct_ratio !== undefined ? `(${Math.round(rule.evidence.distinct_ratio * 100)}%)` : ''}
            </span>
          )}
          {rule.evidence?.duplicate_count !== undefined && (
            <span className="evidence-tag">
              Duplicates: <strong>{rule.evidence.duplicate_count}</strong>
            </span>
          )}
          {rule.evidence?.min_observed !== undefined && rule.evidence?.max_observed !== undefined && (
            <span className="evidence-tag">
              Range: <strong>[{rule.evidence.min_observed} .. {rule.evidence.max_observed}]</strong>
            </span>
          )}
          {rule.evidence?.min_length !== undefined && rule.evidence?.max_length !== undefined && (
            <span className="evidence-tag">
              Length: <strong>[{rule.evidence.min_length} .. {rule.evidence.max_length}] chars</strong>
            </span>
          )}
          {rule.evidence?.expected_min !== undefined && rule.evidence?.expected_max !== undefined && (
            <span className="evidence-tag">
              Expected Rows: <strong>[{rule.evidence.expected_min.toLocaleString()} .. {rule.evidence.expected_max.toLocaleString()}]</strong>
            </span>
          )}
          {(rule.evidence?.total_rows !== undefined || rule.evidence?.current_row_count !== undefined) && (
            <span className="evidence-tag">
              Dataset Rows: <strong>{(rule.evidence.total_rows ?? rule.evidence.current_row_count).toLocaleString()}</strong>
            </span>
          )}
          {rule.evidence?.sample_violations_count !== undefined && (
            <span className="evidence-tag">
              Violations: <strong>{rule.evidence.sample_violations_count}</strong>
            </span>
          )}
          {rule.evidence?.is_primary_key && (
            <span className="evidence-tag" style={{ color: '#10B981', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
              Primary Key 🔑
            </span>
          )}
        </div>
      </div>

      {/* Footer & Actions */}
      <div className="card-footer">
        <span className={`review-status-badge ${rule.status.toLowerCase()}`}>
          {statusBadgeLabel}
        </span>

        <div className="action-buttons">
          <button
            className="btn-action btn-reject"
            onClick={() => onReviewAction(rule.id, 'REJECTED')}
          >
            <span>✖</span> Reject
          </button>
          <button
            className="btn-action btn-edit"
            onClick={() => onOpenEdit(rule)}
          >
            <span>✏️</span> Edit
          </button>
          <button
            className="btn-action btn-accept"
            onClick={() => onReviewAction(rule.id, 'ACCEPTED')}
          >
            <span>✔</span> {isAccepted ? 'Accepted' : 'Accept Rule'}
          </button>
        </div>
      </div>
    </div>
  );
}
