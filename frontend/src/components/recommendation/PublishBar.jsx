import React from 'react';

export default function PublishBar({ readyRulesCount, onPublish, isPublishing = false }) {
  if (readyRulesCount === 0) return null;

  return (
    <div className="publish-bar">
      <div className="publish-info">
        <span className="publish-badge">{readyRulesCount} Rules sẵn sàng</span>
        <span className="publish-text">
          Đã được Human Review chấp thuận để chuyển thành Test Suite trên OpenMetadata.
        </span>
      </div>
      <button className="btn btn-publish" onClick={onPublish} disabled={isPublishing}>
        <span className="btn-icon">{isPublishing ? '⏳' : '🚀'}</span>
        <span>{isPublishing ? 'Đang xuất bản lên OM...' : 'Publish to OpenMetadata'}</span>
      </button>
    </div>
  );
}
