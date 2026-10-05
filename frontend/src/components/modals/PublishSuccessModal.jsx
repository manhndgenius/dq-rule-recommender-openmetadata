import React from 'react';

export default function PublishSuccessModal({ isOpen, onClose, publishedRules, publishResult }) {
  if (!isOpen) return null;

  const publishedCount = publishResult?.published_count ?? publishedRules?.length ?? 0;
  const cases = publishResult?.published_test_cases || [];
  const omUrl = 'https://c3-app-009.duckdns.org';

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog modal-success">
        <div className="modal-header">
          <h3 className="modal-title">Xuất bản thành công lên OpenMetadata!</h3>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p>
            Hệ thống đã tự động chuyển đổi và đăng ký <strong>{publishedCount}</strong> Test Cases vào OpenMetadata Live Server:
          </p>
          
          {publishResult?.table_fqn && (
            <div style={{ marginBottom: 12, fontSize: 13 }}>
              <strong>Table FQN:</strong> <code style={{ color: '#38BDF8' }}>{publishResult.table_fqn}</code>
            </div>
          )}

          {publishResult?.tier_updated && (
            <div style={{ marginBottom: 12, padding: '8px 12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 8, fontSize: 13, color: '#10B981' }}>
              <strong>⭐ Phân tầng Tier:</strong> Đã đồng bộ phân tầng <code>{publishResult.tier || 'Chưa phân tầng'}</code> lên OpenMetadata Live!
            </div>
          )}

          <div className="publish-details">
            <pre>
              {cases.length > 0
                ? cases.map((tc, i) => `${i + 1}. [${tc.testDefinition}] ${tc.test_case_name}\n   -> ID: ${tc.test_case_id}`).join('\n\n')
                : publishedRules
                    .map(
                      (r, i) =>
                        `${i + 1}. [${r.engine}] ${r.description || r.rule_type} (${r.target_columns.join(', ') || 'Toàn bảng'})`
                    )
                    .join('\n')}
            </pre>
          </div>
          <div className="alert-box success">
            <strong>Trạng thái:</strong> Test Cases đã được đăng ký và liên kết trực tiếp vào Test Suite của bảng trên OpenMetadata Live Server.
          </div>
        </div>
        <div className="modal-footer">
          <button
            className="btn btn-primary"
            onClick={() => {
              onClose();
              window.open(omUrl, '_blank');
            }}
          >
            Mở OpenMetadata Server (duckdns) ↗
          </button>
        </div>
      </div>
    </div>
  );
}
