import React, { useState } from 'react';

export default function ObservabilityView({ tableData }) {
  const [activeIncidentTab, setActiveIncidentTab] = useState('ALL');
  const [resolvedIncidents, setResolvedIncidents] = useState({});

  if (!tableData || !tableData.observability) {
    return (
      <div className="observability-empty">
        <p>Chưa có dữ liệu Data Observability cho bảng này.</p>
      </div>
    );
  }

  const {
    health_score = 95,
    health_status = 'HEALTHY',
    freshness = {},
    volume = {},
    test_suites = {},
    dimensions = [],
    recent_runs = [],
    incidents = []
  } = tableData.observability;

  const handleResolveIncident = (id) => {
    setResolvedIncidents((prev) => ({ ...prev, [id]: true }));
  };

  return (
    <div className="observability-container">
      {/* Top Banner: Overall Health & Critical SLA */}
      <div className="obs-hero-banner">
        <div className="obs-hero-left">
          <div className="health-score-dial">
            <svg viewBox="0 0 100 100" className="dial-svg">
              <circle cx="50" cy="50" r="42" className="dial-track" />
              <circle
                cx="50"
                cy="50"
                r="42"
                className="dial-fill"
                strokeDasharray="264"
                strokeDashoffset={264 - (264 * health_score) / 100}
              />
            </svg>
            <div className="dial-inner">
              <span className="dial-number">{health_score}%</span>
              <span className="dial-caption">Health Score</span>
            </div>
          </div>

          <div className="obs-hero-details">
            <div className="obs-title-wrap">
              <h3 className="obs-title">Data Observability & Quality Health</h3>
              <span className="badge-tier-lg">{tableData.tier || 'Tier.Tier1'}</span>
              <span className="badge-status-healthy">🟢 {health_status}</span>
            </div>
            <p className="obs-description">
              Theo dõi chất lượng, tính tươi mới (Freshness SLA), độ trễ dữ liệu và cảnh báo bất thường (Anomaly Detection) theo thời gian thực từ OpenMetadata.
            </p>
            <div className="obs-meta-pills">
              <span className="obs-pill">Domain: <strong>{tableData.domain || 'E-Commerce'}</strong></span>
              <span className="obs-pill">Owner: <strong>{tableData.owner?.name || 'Data Engineering'}</strong></span>
              <span className="obs-pill">FQN: <code>{tableData.fully_qualified_name || tableData.table_name}</code></span>
            </div>
          </div>
        </div>

        <div className="obs-hero-actions">
          <button
            className="btn btn-primary"
            onClick={() => window.open('https://sandbox.open-metadata.org/data-quality', '_blank')}
          >
            Mở OpenMetadata Profiler ↗
          </button>
        </div>
      </div>

      {/* 4 Pillars of Data Observability */}
      <div className="obs-pillars-grid">
        {/* Pillar 1: Freshness SLA */}
        <div className="pillar-card">
          <div className="pillar-header">
            <span className="pillar-icon">⏱️</span>
            <span className="pillar-title">Tính tươi mới (Freshness SLA)</span>
            <span className="badge-success-sm">Đạt SLA</span>
          </div>
          <div className="pillar-metric">
            <span className="metric-large">{freshness.actual_delay || '15 phút trước'}</span>
            <span className="metric-sub">Mục tiêu SLA: &lt; {freshness.sla_target || '30 phút'}</span>
          </div>
          <div className="pillar-footer">
            <span className="footer-label">Lần đồng bộ cuối:</span>
            <span className="footer-value">{freshness.last_sync || 'Vừa xong'}</span>
          </div>
        </div>

        {/* Pillar 2: Volume & Anomaly Tracking */}
        <div className="pillar-card">
          <div className="pillar-header">
            <span className="pillar-icon">📈</span>
            <span className="pillar-title">Dung lượng dòng & Anomaly</span>
            <span className="badge-info-sm">Bình thường</span>
          </div>
          <div className="pillar-metric">
            <span className="metric-large">{(volume.current_rows || tableData.row_count).toLocaleString()} dòng</span>
            <span className="metric-sub">Kỳ vọng: {volume.expected_range || '14.8k - 16k'} ({volume.daily_delta || '+3.4%'})</span>
          </div>
          <div className="pillar-footer">
            <span className="footer-label">Phát hiện bất thường:</span>
            <span className="footer-value text-success">Không có độ lệch bất thường</span>
          </div>
        </div>

        {/* Pillar 3: Test Suite Pass Rate */}
        <div className="pillar-card">
          <div className="pillar-header">
            <span className="pillar-icon">🧪</span>
            <span className="pillar-title">Test Suites Chất lượng</span>
            <span className="badge-warning-sm">{test_suites.warning || 1} Cảnh báo</span>
          </div>
          <div className="pillar-metric">
            <span className="metric-large">{test_suites.pass_rate || '92.8%'}</span>
            <span className="metric-sub">Đạt: {test_suites.passed} / {test_suites.total_tests} test cases</span>
          </div>
          <div className="pillar-footer">
            <span className="footer-label">Thất bại (Failed):</span>
            <span className="footer-value text-success">{test_suites.failed || 0} lỗi nghiêm trọng</span>
          </div>
        </div>

        {/* Pillar 4: Schema Stability */}
        <div className="pillar-card">
          <div className="pillar-header">
            <span className="pillar-icon">🛡️</span>
            <span className="pillar-title">Ổn định Schema (Drift)</span>
            <span className="badge-success-sm">Không thay đổi</span>
          </div>
          <div className="pillar-metric">
            <span className="metric-large">{tableData.column_count} Cột chuẩn</span>
            <span className="metric-sub">Đã gắn nhãn Governance & PII</span>
          </div>
          <div className="pillar-footer">
            <span className="footer-label">Lần thay đổi schema:</span>
            <span className="footer-value">0 lần trong 30 ngày qua</span>
          </div>
        </div>
      </div>

      {/* Row 2: Dimensions & 7-Day History Chart */}
      <div className="obs-two-column-grid">
        {/* Left: Data Quality 5 Dimensions */}
        <div className="obs-panel">
          <div className="obs-panel-header">
            <h4>📊 5 Chiều đo chất lượng dữ liệu (DQ Dimensions)</h4>
            <span className="caption-muted">Chuẩn DAMA & OpenMetadata</span>
          </div>
          <div className="dimensions-list">
            {dimensions.map((dim) => (
              <div key={dim.name} className="dimension-item">
                <div className="dim-info">
                  <span className="dim-name">{dim.name}</span>
                  <span className={`dim-score ${dim.score >= 95 ? 'excellent' : 'warning'}`}>
                    {dim.score}%
                  </span>
                </div>
                <div className="dim-progress-track">
                  <div
                    className={`dim-progress-fill ${dim.score >= 95 ? 'excellent' : 'warning'}`}
                    style={{ width: `${dim.score}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: 7-Day Test Execution History */}
        <div className="obs-panel">
          <div className="obs-panel-header">
            <h4>📅 Lịch sử thực thi Test Suite (7 ngày qua)</h4>
            <span className="caption-muted">Tự động chạy mỗi 2 giờ</span>
          </div>
          <div className="runs-history-timeline">
            {recent_runs.map((run, i) => (
              <div key={i} className="history-day-column">
                <div className="day-dots">
                  {run.failed > 0 && <span className="run-dot failed" title="Failed test"></span>}
                  {run.warning > 0 && <span className="run-dot warning" title="Warning test"></span>}
                  <span className="run-dot passed" title="Passed tests"></span>
                </div>
                <div className="day-bar">
                  <div
                    className="day-bar-fill"
                    style={{ height: `${(run.passed / 14) * 100}%` }}
                  ></div>
                </div>
                <span className="day-label">{run.date}</span>
                <span className="day-count">{run.passed}/{run.passed + run.warning}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Row 3: Incidents & Alerts Feed */}
      <div className="obs-panel full-width">
        <div className="obs-panel-header">
          <div className="header-with-badge">
            <h4>🚨 Cảnh báo & Sự cố dữ liệu (Active Incidents)</h4>
            <span className="incident-count-pill">{incidents.length} sự cố cần chú ý</span>
          </div>
          <div className="incident-tabs">
            <button
              className={`tab-btn-sm ${activeIncidentTab === 'ALL' ? 'active' : ''}`}
              onClick={() => setActiveIncidentTab('ALL')}
            >
              Tất cả
            </button>
            <button
              className={`tab-btn-sm ${activeIncidentTab === 'OPEN' ? 'active' : ''}`}
              onClick={() => setActiveIncidentTab('OPEN')}
            >
              Đang xử lý
            </button>
          </div>
        </div>

        <div className="incidents-list">
          {incidents.length === 0 ? (
            <div className="no-incident">
              <span className="icon-check">✅</span>
              <span>Không có sự cố dữ liệu nào được ghi nhận. Toàn bộ đường ống hoạt động tối ưu.</span>
            </div>
          ) : (
            incidents.map((inc) => (
              <div
                key={inc.id}
                className={`incident-card ${resolvedIncidents[inc.id] ? 'resolved' : ''}`}
              >
                <div className="inc-left">
                  <span className={`severity-tag ${inc.severity.toLowerCase()}`}>
                    {inc.severity}
                  </span>
                  <div>
                    <h5 className="inc-title">
                      {inc.title} {resolvedIncidents[inc.id] && <span className="resolved-tag">ĐÃ XỬ LÝ</span>}
                    </h5>
                    <div className="inc-meta">
                      <span>Mã: <code>{inc.id}</code></span>
                      <span>Phát hiện: {inc.detected_at}</span>
                      <span>Phụ trách: {inc.assigned_to}</span>
                    </div>
                  </div>
                </div>

                <div className="inc-right">
                  {!resolvedIncidents[inc.id] ? (
                    <button
                      className="btn btn-outline-success btn-sm"
                      onClick={() => handleResolveIncident(inc.id)}
                    >
                      ✓ Đánh dấu đã giải quyết
                    </button>
                  ) : (
                    <span className="text-success-done">✓ Đã đóng</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
