import React from 'react';

export default function PublishSuccessModal({ isOpen, onClose, publishedRules }) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog modal-success">
        <div className="modal-header">
          <h3 className="modal-title">✅ Xuất bản thành công lên OpenMetadata!</h3>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p>
            Hệ thống đã tự động chuyển đổi và đăng ký {publishedRules.length} Test Cases vào OpenMetadata Test Suite:
          </p>
          <div className="publish-details">
            <pre>
              {publishedRules
                .map(
                  (r, i) =>
                    `${i + 1}. [${r.engine}] ${r.rule_type} (${r.target_columns.join(', ')}) -> Status: ${r.status}`
                )
                .join('\n')}
            </pre>
          </div>
          <div className="alert-box success">
            <strong>Trạng thái:</strong> Test Suite đã hoạt động ở chế độ Executable Test trên OpenMetadata.
          </div>
        </div>
        <div className="modal-footer">
          <button
            className="btn btn-primary"
            onClick={() => {
              onClose();
              window.open('https://openmetadata.org', '_blank');
            }}
          >
            Xem trực tiếp trên OpenMetadata UI ↗
          </button>
        </div>
      </div>
    </div>
  );
}
