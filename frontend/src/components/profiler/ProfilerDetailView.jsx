import React, { useState } from 'react';

export default function ProfilerDetailView({ tableData }) {
  const [selectedCol, setSelectedCol] = useState(
    tableData?.columns?.find((c) => c.histogram)?.name || tableData?.columns?.[0]?.name || ''
  );

  if (!tableData) return null;

  const activeColumn = tableData.columns.find((c) => c.name === selectedCol) || tableData.columns[0];

  return (
    <div className="profiler-detail-container">
      {/* Profiler Header & KPIs */}
      <div className="profiler-hero-banner">
        <div className="profiler-title-group">
          <span className="profiler-icon">📊</span>
          <div>
            <h3 className="profiler-heading">Data Profiler & Distribution Metrics</h3>
            <p className="profiler-subheading">
              Thống kê hình thái dữ liệu (Shape of Data), phân phối histogram, độ phân tán và tỷ lệ giá trị bất thường
            </p>
          </div>
        </div>

        <div className="profiler-hero-kpis">
          <div className="p-kpi">
            <span className="p-kpi-lbl">Tổng số dòng</span>
            <span className="p-kpi-val">{tableData.row_count.toLocaleString()}</span>
          </div>
          <div className="p-kpi">
            <span className="p-kpi-lbl">Dung lượng</span>
            <span className="p-kpi-val">{tableData.size_mb || '4.8 MB'}</span>
          </div>
          <div className="p-kpi">
            <span className="p-kpi-lbl">Số cột đã đo</span>
            <span className="p-kpi-val">{tableData.columns.length}</span>
          </div>
          <div className="p-kpi">
            <span className="p-kpi-lbl">Thời điểm quét</span>
            <span className="p-kpi-val highlight">{tableData.freshness}</span>
          </div>
        </div>
      </div>

      {/* Main Profiler Layout: Left Column Selector, Right Detailed Stats */}
      <div className="profiler-split-layout">
        {/* Left: Column List with Quick Profiling Stats */}
        <div className="profiler-cols-list">
          <div className="cols-list-header">
            <h4>Danh sách cột ({tableData.columns.length})</h4>
          </div>
          <div className="cols-list-scroll">
            {tableData.columns.map((c) => (
              <div
                key={c.name}
                className={`col-item-card ${selectedCol === c.name ? 'active' : ''}`}
                onClick={() => setSelectedCol(c.name)}
              >
                <div className="col-item-top">
                  <strong className="col-item-name">{c.name}</strong>
                  <span className="col-item-type">{c.type}</span>
                </div>
                <div className="col-item-metrics">
                  <span>Null: <strong>{c.null_pct}%</strong></span>
                  <span>Distinct: <strong>{c.distinct.toLocaleString()}</strong></span>
                </div>
                {c.histogram && <span className="badge-has-histogram">📊 Phân phối Histogram</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Deep Profiling & Histogram Chart */}
        <div className="profiler-col-details">
          {activeColumn && (
            <>
              <div className="col-details-header">
                <div>
                  <div className="col-name-row">
                    <h3 className="active-col-title">{activeColumn.name}</h3>
                    <code className="active-col-type">{activeColumn.type}</code>
                    {activeColumn.is_pk && <span className="pk-badge">Primary Key</span>}
                  </div>
                  <p className="col-desc-text">{activeColumn.description || 'Chưa có mô tả'}</p>
                </div>
                <span className="col-profiler-badge">OpenMetadata Native Profiler</span>
              </div>

              {/* 4 Cards: Nulls, Uniqueness, Quantiles, Mean */}
              <div className="profiler-stats-grid">
                <div className="p-stat-card">
                  <span className="stat-label">Tỷ lệ Null (Missing)</span>
                  <div className="stat-num-row">
                    <span className="stat-num">{activeColumn.null_pct}%</span>
                    <span className="stat-count-sub">({activeColumn.null_pct === 0 ? '0 dòng' : 'Có missing'})</span>
                  </div>
                  <div className="p-progress">
                    <div
                      className="p-progress-fill"
                      style={{
                        width: `${Math.min(activeColumn.null_pct, 100)}%`,
                        backgroundColor: activeColumn.null_pct > 5 ? '#EF4444' : activeColumn.null_pct > 0 ? '#F59E0B' : '#10B981'
                      }}
                    ></div>
                  </div>
                </div>

                <div className="p-stat-card">
                  <span className="stat-label">Số giá trị duy nhất (Distinct)</span>
                  <div className="stat-num-row">
                    <span className="stat-num">{activeColumn.distinct.toLocaleString()}</span>
                    <span className="stat-count-sub">({activeColumn.distinct_pct}%)</span>
                  </div>
                  <div className="p-progress">
                    <div
                      className="p-progress-fill distinct"
                      style={{ width: `${Math.min(activeColumn.distinct_pct, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="p-stat-card">
                  <span className="stat-label">Giá trị nhỏ nhất (Min)</span>
                  <span className="stat-num stat-text-truncate">{activeColumn.stats?.min || 'N/A'}</span>
                  <span className="stat-count-sub">Cận dưới quan sát</span>
                </div>

                <div className="p-stat-card">
                  <span className="stat-label">Giá trị lớn nhất (Max)</span>
                  <span className="stat-num stat-text-truncate">{activeColumn.stats?.max || 'N/A'}</span>
                  <span className="stat-count-sub">Cận trên quan sát</span>
                </div>
              </div>

              {/* Histogram Visualization (If Column Has Numeric/Categorical Buckets) */}
              <div className="histogram-panel">
                <div className="hist-header">
                  <h4>Biểu đồ phân phối tần suất (Frequency Distribution)</h4>
                  <span className="hist-caption">Chuẩn OpenMetadata Column Histogram</span>
                </div>

                {activeColumn.histogram ? (
                  <div className="histogram-bars">
                    {activeColumn.histogram.map((b, idx) => (
                      <div key={idx} className="hist-bar-item">
                        <div className="hist-bar-track">
                          <div
                            className="hist-bar-fill"
                            style={{ height: `${b.pct}%` }}
                          >
                            <span className="hist-pct-tip">{b.pct}%</span>
                          </div>
                        </div>
                        <span className="hist-label">{b.bucket}</span>
                        <span className="hist-count">({b.count.toLocaleString()})</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="hist-empty">
                    <span className="hist-empty-icon">📈</span>
                    <p>
                      Cột dạng chuỗi định danh hoặc thời gian liên tục. Mẫu giá trị quan sát:
                      <code> {activeColumn.stats?.sample_values?.join(', ') || 'Đang cập nhật'}</code>
                    </p>
                  </div>
                )}
              </div>

              {/* Frequently Joined Tables */}
              {activeColumn.frequently_joined && (
                <div className="joined-tables-box">
                  <span className="joined-lbl">🔗 Các bảng thường xuyên JOIN với cột này:</span>
                  <div className="joined-pills">
                    {activeColumn.frequently_joined.map((j) => (
                      <code key={j} className="joined-pill">{j}</code>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
