import React, { useState, useEffect } from 'react';
import { openmetadataService } from '../../services/openmetadataService';

export default function GoldenBenchmarkModal({ isOpen, onClose }) {
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedTableTab, setSelectedTableTab] = useState('patients');

  useEffect(() => {
    if (isOpen) {
      loadBenchmark(false);
    }
  }, [isOpen]);

  const loadBenchmark = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const data = await openmetadataService.getGoldenEvaluationSummary(forceRefresh);
      if (data) {
        setBenchmarkData(data);
      }
    } catch (err) {
      console.error('Lỗi tải Golden Benchmark:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const overall = benchmarkData?.overall_summary;
  const tables = benchmarkData?.tables || [];
  const currentTableData = tables.find((t) => t.table_name === selectedTableTab) || tables[0];

  return (
    <div className="modal-backdrop" style={{ zIndex: 1100 }}>
      <div className="modal-dialog modal-large" style={{ maxWidth: 940, width: '92vw', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div className="modal-header" style={{ alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <h3 className="modal-title" style={{ margin: 0, fontSize: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🏆</span> Synthea Golden Dataset Benchmark & Quantitative Evaluation
              </h3>
              {overall && (
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 12,
                    fontSize: 11,
                    fontWeight: 700,
                    background: overall.status === 'EXCELLENT' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                    color: overall.status === 'EXCELLENT' ? '#10B981' : '#38BDF8',
                    border: `1px solid ${overall.status === 'EXCELLENT' ? '#10B981' : '#38BDF8'}`
                  }}
                >
                  {overall.status}
                </span>
              )}
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: 12, color: 'var(--text-muted, #94a3b8)' }}>
              Đối chiếu chuẩn Synthea Data Dictionary trên 3 bảng y tế cốt lõi (<code>patients</code>, <code>medications</code>, <code>observations</code>)
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              className="btn btn-secondary"
              onClick={() => loadBenchmark(true)}
              disabled={loading}
              style={{ fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 5 }}
              title="Chạy lại toàn bộ benchmark"
            >
              <span style={{ display: 'inline-block', transform: loading ? 'rotate(360deg)' : 'none', transition: 'transform 0.8s ease' }}>🔄</span>
              {loading ? 'Đang tính toán...' : 'Làm mới'}
            </button>
            <button className="btn-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body" style={{ overflowY: 'auto', padding: '16px 20px', flex: 1 }}>
          {loading && !benchmarkData ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
              <div style={{ fontSize: 24, marginBottom: 10 }}>⏳</div>
              <div>Đang chạy bộ kiểm thử định lượng Synthea Golden Benchmark...</div>
            </div>
          ) : !benchmarkData ? (
            <div style={{ textAlign: 'center', padding: '30px 0', color: '#ef4444' }}>
              Không thể tải dữ liệu benchmark. Vui lòng kiểm tra Backend API.
            </div>
          ) : (
            <>
              {/* Overall KPI Summary Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
                <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Bắt Lỗi (Bug Catch Rate)</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#10B981', marginTop: 4 }}>
                    {overall?.overall_defect_detection_rate}%
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Phát hiện toàn bộ lỗi cấy</div>
                </div>

                <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Độ Bao Phủ (Recall)</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#38BDF8', marginTop: 4 }}>
                    {overall?.average_recall}%
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Khớp chuẩn Ground Truth</div>
                </div>

                <div style={{ background: 'rgba(168, 85, 247, 0.08)', border: '1px solid rgba(168, 85, 247, 0.25)', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Dữ Liệu Sạch (Pass Rate)</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#A855F7', marginTop: 4 }}>
                    {overall?.clean_data_pass_rate}%
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>0 báo động giả (False Alarms)</div>
                </div>

                <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: 10, padding: '12px 14px' }}>
                  <div style={{ fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>Điểm F1-Score</div>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#F59E0B', marginTop: 4 }}>
                    {overall?.average_f1_score}%
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Cân bằng Precision / Recall</div>
                </div>
              </div>

              {/* Table Performance Matrix */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>📊</span> Bảng kết quả định lượng theo từng bảng y tế:
                </div>
                <div style={{ overflowX: 'auto', border: '1px solid var(--border-color, #334155)', borderRadius: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-secondary, rgba(255, 255, 255, 0.04))', borderBottom: '1px solid var(--border-color, #334155)' }}>
                        <th style={{ padding: '8px 12px' }}>Bảng Dữ Liệu</th>
                        <th style={{ padding: '8px 12px' }}>Số Cột</th>
                        <th style={{ padding: '8px 12px' }}>Rules Sinh Ra</th>
                        <th style={{ padding: '8px 12px' }}>Ground Truth</th>
                        <th style={{ padding: '8px 12px' }}>Precision</th>
                        <th style={{ padding: '8px 12px' }}>Recall</th>
                        <th style={{ padding: '8px 12px' }}>F1-Score</th>
                        <th style={{ padding: '8px 12px' }}>Bắt Lỗi (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tables.map((tbl) => (
                        <tr
                          key={tbl.table_name}
                          onClick={() => setSelectedTableTab(tbl.table_name)}
                          style={{
                            borderBottom: '1px solid var(--border-color, #1e293b)',
                            cursor: 'pointer',
                            background: selectedTableTab === tbl.table_name ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                            transition: 'background 0.2s ease'
                          }}
                        >
                          <td style={{ padding: '8px 12px', fontWeight: 600, color: '#38BDF8' }}>
                            <code>{tbl.table_name}</code>
                          </td>
                          <td style={{ padding: '8px 12px' }}>{tbl.total_columns}</td>
                          <td style={{ padding: '8px 12px' }}>{tbl.total_rules_generated}</td>
                          <td style={{ padding: '8px 12px' }}>{tbl.ground_truth_rules_count}</td>
                          <td style={{ padding: '8px 12px', color: '#94a3b8' }}>{tbl.metrics.precision}%</td>
                          <td style={{ padding: '8px 12px', fontWeight: 600, color: '#38BDF8' }}>{tbl.metrics.recall}%</td>
                          <td style={{ padding: '8px 12px', color: '#F59E0B' }}>{tbl.metrics.f1_score}%</td>
                          <td style={{ padding: '8px 12px', fontWeight: 700, color: '#10B981' }}>
                            {tbl.defect_testing.defect_detection_rate}% ({tbl.defect_testing.caught_defects_count}/{tbl.defect_testing.defect_records_count})
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Drill-down Injected Scenarios */}
              {currentTableData && (
                <div style={{ background: 'var(--bg-secondary, rgba(255, 255, 255, 0.02))', border: '1px solid var(--border-color, #334155)', borderRadius: 10, padding: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span>🧪</span> Kịch bản cấy lỗi thực nghiệm bảng <code>{currentTableData.table_name}</code>:
                    </div>
                    {/* Switcher pills */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      {tables.map((t) => (
                        <button
                          key={t.table_name}
                          onClick={() => setSelectedTableTab(t.table_name)}
                          style={{
                            padding: '3px 10px',
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            border: selectedTableTab === t.table_name ? '1px solid #38BDF8' : '1px solid transparent',
                            background: selectedTableTab === t.table_name ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                            color: selectedTableTab === t.table_name ? '#38BDF8' : '#94a3b8',
                            cursor: 'pointer'
                          }}
                        >
                          {t.table_name}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {currentTableData.defect_testing.scenarios.map((sc, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '8px 12px',
                          borderRadius: 6,
                          background: 'rgba(0, 0, 0, 0.15)',
                          border: '1px solid rgba(255, 255, 255, 0.06)'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ fontSize: 14 }}>{sc.is_detected ? '✅' : '❌'}</span>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary, #f1f5f9)' }}>
                              {sc.fault}
                            </div>
                            {sc.detected_by && sc.detected_by.length > 0 && (
                              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                                {sc.detected_by.map((r, rIdx) => (
                                  <span
                                    key={rIdx}
                                    style={{
                                      fontSize: 10,
                                      padding: '1px 6px',
                                      borderRadius: 4,
                                      background: 'rgba(16, 185, 129, 0.15)',
                                      color: '#10B981',
                                      border: '1px solid rgba(16, 185, 129, 0.3)'
                                    }}
                                  >
                                    Rule: {r}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>

                        <div>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: sc.is_detected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                              color: sc.is_detected ? '#10B981' : '#EF4444'
                            }}
                          >
                            {sc.is_detected ? 'ĐÃ BẮT LỖI' : 'BỎ SÓT'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer" style={{ borderTop: '1px solid var(--border-color, #334155)', padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: '#64748b' }}>
            <span>Nguồn tham chiếu: </span>
            <a
              href="https://github.com/synthetichealth/synthea/wiki/CSV-File-Data-Dictionary"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#38BDF8', textDecoration: 'none' }}
            >
              Synthea CSV Data Dictionary Wiki ↗
            </a>
          </div>
          <button className="btn btn-secondary" onClick={onClose} style={{ fontSize: 12, padding: '6px 16px' }}>
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
