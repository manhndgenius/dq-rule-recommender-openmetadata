import React from 'react';

export default function PublishBar({ readyRulesCount, onPublish }) {
  if (readyRulesCount === 0) return null;

  return (
    <div className="publish-bar">
      <div className="publish-info">
        <span className="publish-badge">{readyRulesCount} Rules sẵn sàng</span>
        <span className="publish-text">
          Đã được Human Review chấp thuận để chuyển thành Test Suite trên OpenMetadata.
        </span>
      </div>
      <button className="btn btn-publish" onClick={onPublish}>
        <span className="btn-icon">🚀</span>
        <span>Publish to OpenMetadata</span>
      </button>
    </div>
  );
}
