import React from 'react';

export default function TableContextPanel({ tableData, isCollapsed = false, onToggleCollapse }) {
  if (!tableData) return null;

  if (isCollapsed) {
    return (
      <aside className="context-panel collapsed" id="context-panel">
        <button
          className="btn-expand-context"
          onClick={onToggleCollapse}
          title="Mở rộng thông tin bảng (Expand Table Context)"
          aria-label="Mở rộng thông tin bảng"
        >
          <span className="expand-context-icon">◀</span>
          <span className="expand-context-text">📊 Thông tin bảng</span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="context-panel" id="context-panel">
      {/* Panel Top: Table Name, Tier Badge & Collapse Button */}
      <div className="panel-header">
        <div className="panel-header-left">
          <div className="panel-header-title">
            <h2>📊 Table Context</h2>
            <span className="badge-source">{tableData.table_name}</span>
          </div>
          {tableData.tier ? (
            <span className={`badge-tier ${tableData.tier.toLowerCase().replace('.', '-')}`}>
              ⭐ {tableData.tier}
            </span>
          ) : (
            <span className="badge-tier" style={{ opacity: 0.6, borderStyle: 'dashed' }}>
              Tier: --
            </span>
          )}
        </div>
        {onToggleCollapse && (
          <button
            className="btn-collapse-context"
            onClick={onToggleCollapse}
            title="Thu gọn Table Context (Collapse)"
            aria-label="Thu gọn thông tin bảng"
          >
            ▶
          </button>
        )}
      </div>

      {/* Governance & Metadata Badges */}
      <div className="governance-meta-box">
        <div className="gov-meta-row">
          <span className="gov-label">Domain:</span>
          <span className="gov-value">
            {tableData.domain ? (tableData.domain.displayName || tableData.domain.name || tableData.domain) : '--'}
          </span>
        </div>
        <div className="gov-meta-row">
          <span className="gov-label">Owner:</span>
          <span className="gov-value">
            {tableData.owner?.displayName || tableData.owner?.name ? (tableData.owner.displayName || tableData.owner.name) : '--'}
          </span>
        </div>
        <div className="gov-meta-row">
          <span className="gov-label">Thẻ (Tags):</span>
          {tableData.tags && tableData.tags.length > 0 ? (
            <div className="gov-tags-wrap">
              {tableData.tags.map((t, idx) => (
                <span key={idx} className="gov-tag-pill" style={{ borderColor: t.color }}>
                  {t.name || t.tagFQN}
                </span>
              ))}
            </div>
          ) : (
            <span className="gov-value text-muted" style={{ fontStyle: 'italic', fontSize: '12px', color: 'var(--text-muted)' }}>
              Chưa gắn thẻ trên OpenMetadata
            </span>
          )}
        </div>
      </div>

      {/* Observability Quick Health Status */}
      {tableData.observability && (
        <div className="quick-health-box">
          <div className="health-score-mini">
            <span className="health-score-val">{tableData.observability.health_score}%</span>
            <div className="health-score-info">
              <strong>Data Health Score</strong>
              <span className="health-sub">Freshness: {tableData.observability.freshness?.actual_delay}</span>
            </div>
          </div>
          <span className="badge-live-pulse">🟢 Active SLA</span>
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Tổng số dòng</span>
          <span className="kpi-value">{tableData.row_count.toLocaleString()}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Số lượng cột</span>
          <span className="kpi-value">{tableData.column_count}</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Lần quét</span>
          <span className="kpi-value highlight">{tableData.freshness}</span>
        </div>
      </div>

      {/* Columns Schema & Profiling Table */}
      <div className="schema-section">
        <div className="section-title-wrap">
          <h3 className="section-title">Cấu trúc cột & Chỉ số phân phối</h3>
          <span className="column-count-tag">{tableData.columns.length} columns</span>
        </div>

        <div className="table-responsive">
          <table className="schema-table">
            <thead>
              <tr>
                <th>Tên cột</th>
                <th>Kiểu dữ liệu</th>
                <th>Tỷ lệ Null</th>
                <th style={{ textAlign: 'right' }}>Distinct</th>
              </tr>
            </thead>
            <tbody>
              {tableData.columns.map((col) => (
                <tr key={col.name}>
                  <td>
                    <span className="col-name">{col.name}</span>
                    {col.is_pk && <span className="pk-sub-badge">PK</span>}
                  </td>
                  <td>
                    <span className="type-tag">{col.type}</span>
                  </td>
                  <td>
                    <div className="null-bar-wrapper">
                      <div className="null-bar">
                        <div
                          className="null-bar-fill"
                          style={{
                            width: `${Math.min(col.null_pct, 100)}%`,
                            backgroundColor: col.null_pct > 5 ? '#EF4444' : col.null_pct > 0 ? '#F59E0B' : '#10B981'
                          }}
                        ></div>
                      </div>
                      <span className="null-text">{col.null_pct}%</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <span className="distinct-tag">{col.distinct.toLocaleString()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </aside>
  );
}
