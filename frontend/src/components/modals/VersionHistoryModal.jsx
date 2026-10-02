import React from 'react';

export default function VersionHistoryModal({ isOpen, onClose, tableData }) {
  if (!isOpen || !tableData) return null;

  const history = tableData.version_history || [];

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <h3 className="modal-title">📜 Lịch sử phiên bản (Version History) - {tableData.version || 'v1.2'}</h3>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <p className="modal-description">
            OpenMetadata tự động lưu vết mọi thay đổi về Schema, Metadata, Tags và Data Quality Rules theo thời gian:
          </p>

          <div className="version-timeline">
            {history.map((ver, idx) => (
              <div key={idx} className="version-item">
                <div className="version-badge-tag">{ver.version}</div>
                <div className="version-content">
                  <div className="version-meta">
                    <strong>{ver.author}</strong>
                    <span>• {ver.date}</span>
                  </div>
                  <ul className="version-changes-list">
                    {ver.changes.map((c, cIdx) => (
                      <li key={cIdx}>{c}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Đóng</button>
        </div>
      </div>
    </div>
  );
}
