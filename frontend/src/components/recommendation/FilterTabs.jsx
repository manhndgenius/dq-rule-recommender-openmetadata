import React from 'react';

export default function FilterTabs({
  activeFilter,
  setActiveFilter,
  stats,
  reviewedCount,
  totalCount
}) {
  const progressPct = totalCount > 0 ? Math.round((reviewedCount / totalCount) * 100) : 0;

  return (
    <div className="filter-bar">
      <div className="filter-tabs">
        <button
          className={`filter-tab ${activeFilter === 'ALL' ? 'active' : ''}`}
          onClick={() => setActiveFilter('ALL')}
        >
          Tất cả <span className="tab-count">{stats.all}</span>
        </button>
        <button
          className={`filter-tab ${activeFilter === 'BASIC' ? 'active' : ''}`}
          onClick={() => setActiveFilter('BASIC')}
          title="Rule DQ theo Heuristics cơ bản"
        >
          Basic <span className="tab-count">{stats.basic}</span>
        </button>
        <button
          className={`filter-tab ${activeFilter === 'ADVANCED' ? 'active' : ''}`}
          onClick={() => setActiveFilter('ADVANCED')}
          title="Rule DQ nâng cao theo Domain & LLM"
        >
          Advanced <span className="tab-count">{stats.advanced}</span>
        </button>
        <button
          className={`filter-tab ${activeFilter === 'WARNING' ? 'active' : ''}`}
          onClick={() => setActiveFilter('WARNING')}
          title="Rule có cảnh báo từ Validator"
        >
          Cảnh báo <span className="tab-count">{stats.warning}</span>
        </button>
        <button
          className={`filter-tab ${activeFilter === 'ACCEPTED' ? 'active' : ''}`}
          onClick={() => setActiveFilter('ACCEPTED')}
          title="Rule đã được duyệt chấp thuận"
        >
          Đã duyệt <span className="tab-count">{stats.accepted}</span>
        </button>
      </div>

      <div className="review-progress" title={`Tiến độ duyệt: ${reviewedCount}/${totalCount} (${progressPct}%)`}>
        <div className="review-progress-head">
          <span className="progress-label">Tiến độ Review:</span>
          <span className="progress-fraction">
            <strong>{reviewedCount}</strong>/{totalCount}
          </span>
          <span className="progress-pct-badge">{progressPct}%</span>
        </div>
        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${Math.max(progressPct, reviewedCount > 0 ? 5 : 0)}%` }}
          ></div>
        </div>
      </div>
    </div>
  );
}
