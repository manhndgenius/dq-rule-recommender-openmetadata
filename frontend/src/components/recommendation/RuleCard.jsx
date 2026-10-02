import React from 'react';

export default function RuleCard({ rule, onReviewAction, onOpenEdit }) {
  const isBasic = rule.engine === 'BASIC';
  const isValid = rule.validation_status === 'VALID';
  const isAccepted = rule.status === 'ACCEPTED';
  const isEdited = rule.status === 'EDITED';
  const isRejected = rule.status === 'REJECTED';

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
          <span className="rule-type-name">{rule.rule_type}</span>
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
          {rule.target_columns && rule.target_columns.length > 0 ? (
            rule.target_columns.map((c) => (
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
              Null Count: <strong>{rule.evidence.null_count}</strong>
            </span>
          )}
          {rule.evidence?.distinct_count !== undefined && (
            <span className="evidence-tag">
              Distinct Count: <strong>{rule.evidence.distinct_count}</strong>
            </span>
          )}
          {rule.evidence?.min_observed !== undefined && rule.evidence?.max_observed !== undefined && (
            <span className="evidence-tag">
              Range: <strong>[{rule.evidence.min_observed} .. {rule.evidence.max_observed}]</strong>
            </span>
          )}
          {rule.evidence?.total_rows !== undefined && (
            <span className="evidence-tag">
              Sample: <strong>{rule.evidence.total_rows} rows</strong>
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
