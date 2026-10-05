import React, { useState } from 'react';

export default function SchemaView({ tableData }) {
  const [searchTerm, setSearchTerm] = useState('');

  if (!tableData || !tableData.columns) return null;

  const filteredColumns = tableData.columns.filter((c) =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.description && c.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="schema-view-container">
      {/* Header & Quick Stats */}
      <div className="schema-view-header">
        <div className="schema-view-title-group">
          <span className="schema-icon">📑</span>
          <div>
            <h3 className="schema-heading">Schema & Column Profiler Breakdown</h3>
            <p className="schema-subheading">
              Cấu trúc cột dữ liệu, kiểu dữ liệu, ràng buộc khóa chính và nhãn phân loại bảo mật (PII & Governance Tags)
            </p>
          </div>
        </div>

        <div className="schema-summary-chips">
          <span className="chip-stat"><strong>{filteredColumns.length}</strong> / {tableData.columns.length} Cột</span>
          <span className="chip-stat"><strong>{tableData.row_count.toLocaleString()}</strong> Dòng</span>
          <span className="chip-tier-pill">{tableData.tier || 'Tier: --'}</span>
        </div>
      </div>

      {/* Table Description Card in Schema Tab */}
      <div className="schema-description-card">
        <div className="schema-desc-header">
          <div className="schema-desc-title">
            <span className="desc-card-icon">📖</span>
            <strong>Mô tả bảng (Table Description):</strong>
          </div>
          <span className="schema-desc-badge">OpenMetadata Catalog</span>
        </div>
        <p className="schema-desc-body">
          {tableData.description || 'Chưa có mô tả trên OpenMetadata Catalog.'}
        </p>
      </div>

      {/* Dedicated Clean Search & Filter Toolbar */}
      <div className="schema-search-strip">
        <div className="schema-search-field">
          <svg className="search-field-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            placeholder="Tìm kiếm cột theo tên, kiểu dữ liệu hoặc mô tả..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="schema-search-input"
          />
          {searchTerm && (
            <button className="search-clear-btn" onClick={() => setSearchTerm('')} title="Xóa tìm kiếm">✕</button>
          )}
        </div>
        <div className="schema-filter-caption">
          {searchTerm ? `Tìm thấy ${filteredColumns.length} cột khớp` : `Hiển thị tất cả ${tableData.columns.length} cột`}
        </div>
      </div>

      <div className="schema-table-card">
        <div className="table-responsive">
          <table className="schema-detail-table">
            <thead>
              <tr>
                <th style={{ width: '22%' }}>Tên cột (Column)</th>
                <th style={{ width: '13%' }}>Kiểu dữ liệu</th>
                <th style={{ width: '20%' }}>Nhãn quản trị (PII & Tags)</th>
                <th style={{ width: '15%' }}>Tỷ lệ Null</th>
                <th style={{ width: '12%' }}>Distinct</th>
                <th style={{ width: '18%' }}>Chỉ số thống kê (Profiler)</th>
              </tr>
            </thead>
            <tbody>
              {filteredColumns.map((col) => (
                <tr key={col.name}>
                  <td>
                    <div className="col-cell-name">
                      <strong className="column-title">{col.name}</strong>
                      {col.is_pk && <span className="pk-badge" title="Primary Key">PK</span>}
                      {col.nullable === false && !col.is_pk && (
                        <span className="not-null-badge">NOT NULL</span>
                      )}
                    </div>
                    {col.description && (
                      <span className="col-desc-tooltip">{col.description}</span>
                    )}
                  </td>

                  <td>
                    <code className="data-type-code">{col.type}</code>
                  </td>

                  <td>
                    <div className="tags-flex-wrap">
                      {(col.tags && col.tags.length > 0) ? (
                        col.tags.map((tag, idx) => {
                          const tagName = typeof tag === 'object' ? (tag.name || tag.tagFQN) : String(tag);
                          const isSens = tagName.toLowerCase().includes('sensitive') || tagName.toLowerCase().includes('pii');
                          return (
                            <span
                              key={idx}
                              className={`tag-pill ${isSens ? 'pii-sensitive' : 'pii-safe'}`}
                            >
                              🏷️ {tagName}
                            </span>
                          );
                        })
                      ) : (
                        <span className="text-muted" style={{ fontStyle: 'italic', fontSize: '12px', color: 'var(--text-muted)' }}>—</span>
                      )}
                    </div>
                  </td>

                  <td>
                    <div className="null-metric-cell">
                      <div className="null-progress-bar">
                        <div
                          className="null-progress-fill"
                          style={{
                            width: `${Math.min(col.null_pct, 100)}%`,
                            backgroundColor: col.null_pct > 5 ? '#EF4444' : col.null_pct > 0 ? '#F59E0B' : '#10B981'
                          }}
                        ></div>
                      </div>
                      <span className="null-percent-label">{col.null_pct}%</span>
                    </div>
                  </td>

                  <td>
                    <span className="distinct-number">
                      {col.distinct.toLocaleString()}
                    </span>
                    <span className="distinct-ratio-sub">
                      ({col.distinct_pct}%)
                    </span>
                  </td>

                  <td>
                    <div className="profiler-stat-box">
                      {col.stats?.min && (
                        <span className="stat-line">
                          <strong>Min:</strong> {col.stats.min}
                        </span>
                      )}
                      {col.stats?.max && (
                        <span className="stat-line">
                          <strong>Max:</strong> {col.stats.max}
                        </span>
                      )}
                      {col.stats?.sample_values && (
                        <span className="stat-line sample-vals">
                          <strong>Values:</strong> {col.stats.sample_values.slice(0, 3).join(', ')}...
                        </span>
                      )}
                      {!col.stats?.min && !col.stats?.max && !col.stats?.sample_values && (
                        <span className="stat-line text-muted">Đã kiểm tra hợp lệ</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
