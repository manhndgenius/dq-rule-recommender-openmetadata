import React, { useState } from 'react';
import { renderSQLWithParams } from '../../utils/sql';

export default function EditRuleModal({ rule, isOpen, onClose, onSave }) {
  const initialParams = rule?.edited_parameters || rule?.parameters || {};
  const [minValue, setMinValue] = useState(initialParams.minValue ?? 0);
  const [maxValue, setMaxValue] = useState(initialParams.maxValue ?? 100);
  const [minLength, setMinLength] = useState(initialParams.minLength ?? 1);
  const [maxLength, setMaxLength] = useState(initialParams.maxLength ?? 255);
  const [allowedValues, setAllowedValues] = useState((initialParams.allowedValues || []).join(', '));
  const [sqlExpression, setSqlExpression] = useState(
    renderSQLWithParams(rule?.sql || rule?.violation_predicate || initialParams.sqlExpression, rule?.params)
  );

  if (!isOpen || !rule) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const updatedParams = {};
    if (rule.rule_type === 'columnValuesToBeBetween' || rule.rule_type === 'tableRowCountToBeBetween') {
      updatedParams.minValue = parseFloat(minValue);
      updatedParams.maxValue = parseFloat(maxValue);
    } else if (rule.rule_type === 'columnValuesLengthToBeBetween') {
      updatedParams.minLength = parseInt(minLength, 10);
      updatedParams.maxLength = parseInt(maxLength, 10);
    } else if (rule.rule_type === 'columnValuesToBeInSet') {
      updatedParams.allowedValues = allowedValues.split(',').map((s) => s.trim()).filter(Boolean);
    } else if (rule.rule_type === 'tableCustomSQLQuery') {
      updatedParams.sqlExpression = sqlExpression.trim();
    }
    if (rule.engine === 'ADVANCED') {
      updatedParams.sqlExpression = sqlExpression.trim();
    }
    const updatedSql = rule.engine === 'ADVANCED' ? sqlExpression.trim() : null;
    onSave(rule.id, updatedParams, updatedSql);
  };

  const isBetweenRule = rule.rule_type === 'columnValuesToBeBetween' || rule.rule_type === 'tableRowCountToBeBetween';
  const isLengthRule = rule.rule_type === 'columnValuesLengthToBeBetween';
  const isInSetRule = rule.rule_type === 'columnValuesToBeInSet';
  const isCustomSqlRule = rule.rule_type === 'tableCustomSQLQuery';
  const isAdvancedSqlRule = rule.engine === 'ADVANCED' && Boolean(rule.sql || rule.violation_predicate);
  const hasNoParams = !isBetweenRule && !isLengthRule && !isInSetRule && !isCustomSqlRule && !isAdvancedSqlRule;
  const displayColumns = rule.target_columns || rule.columns || [];

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <div className="modal-title-group">
            <h3 className="modal-title">Chỉnh sửa tham số Rule</h3>
            <span className="modal-subtitle">{rule.rule_type}</span>
          </div>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Mục tiêu áp dụng:{' '}
              <strong style={{ color: 'var(--text-light)' }}>
                {displayColumns.length > 0
                  ? displayColumns.join(', ')
                  : '📊 Toàn bảng (Table-level)'}
              </strong>
            </p>

            {/* Min-Max Between Rules (Table Row Count OR Column Values) */}
            {isBetweenRule && (
              <>
                <div className="form-group">
                  <label className="form-label">
                    {rule.rule_type === 'tableRowCountToBeBetween' 
                      ? 'Min Rows (Số dòng tối thiểu kỳ vọng):' 
                      : 'Min Value (Ngưỡng giá trị tối thiểu):'}
                  </label>
                  <input
                    type="number"
                    step="any"
                    className="form-input"
                    value={minValue}
                    onChange={(e) => setMinValue(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">
                    {rule.rule_type === 'tableRowCountToBeBetween' 
                      ? 'Max Rows (Số dòng tối đa kỳ vọng):' 
                      : 'Max Value (Ngưỡng giá trị tối đa):'}
                  </label>
                  <input
                    type="number"
                    step="any"
                    className="form-input"
                    value={maxValue}
                    onChange={(e) => setMaxValue(e.target.value)}
                    required
                  />
                </div>
              </>
            )}

            {/* String Length Between Rule */}
            {isLengthRule && (
              <>
                <div className="form-group">
                  <label className="form-label">Min Length (Độ dài chuỗi tối thiểu):</label>
                  <input
                    type="number"
                    step="1"
                    className="form-input"
                    value={minLength}
                    onChange={(e) => setMinLength(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Max Length (Độ dài chuỗi tối đa):</label>
                  <input
                    type="number"
                    step="1"
                    className="form-input"
                    value={maxLength}
                    onChange={(e) => setMaxLength(e.target.value)}
                    required
                  />
                </div>
              </>
            )}

            {/* In-Set Categorical Rule */}
            {isInSetRule && (
              <div className="form-group">
                <label className="form-label">Tập giá trị hợp lệ (ngăn cách bằng dấu phẩy):</label>
                <input
                  type="text"
                  className="form-input"
                  value={allowedValues}
                  onChange={(e) => setAllowedValues(e.target.value)}
                  required
                />
              </div>
            )}

            {/* Custom SQL Query Rule */}
            {isCustomSqlRule && (
              <div className="form-group">
                <label className="form-label">Biểu thức SQL điều kiện:</label>
                <textarea
                  className="form-input"
                  rows={4}
                  value={sqlExpression}
                  onChange={(e) => setSqlExpression(e.target.value)}
                  required
                />
              </div>
            )}

            {/* Advanced Rule SQL */}
            {isAdvancedSqlRule && (
              <div className="form-group">
                <label className="form-label">Câu SQL tìm các dòng vi phạm:</label>
                <textarea
                  className="form-input sql-edit-textarea"
                  rows={7}
                  value={sqlExpression}
                  onChange={(e) => setSqlExpression(e.target.value)}
                  spellCheck={false}
                  required
                />
                <span className="form-help-text">
                  Query phải trả về các dòng vi phạm quy tắc dữ liệu.
                </span>
              </div>
            )}

            {/* Rules without parameters like Not Null, Unique */}
            {hasNoParams && (
              <div className="alert-box success">
                Rule này không có tham số số học cần tinh chỉnh (Ví dụ: Not Null, Unique). Bấm "Lưu" để xác nhận duyệt nhanh.
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Hủy bỏ
            </button>
            <button type="submit" className="btn btn-primary">
              Lưu & Đổi trạng thái Duyệt
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
