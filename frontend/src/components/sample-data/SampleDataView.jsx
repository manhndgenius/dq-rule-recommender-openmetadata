import React, { useState } from 'react';

export default function SampleDataView({ tableData }) {
  const [isMasked, setIsMasked] = useState(true);

  if (!tableData || !tableData.sample_data || tableData.sample_data.length === 0) {
    return (
      <div className="sample-data-empty">
        <p>Chưa có dữ liệu mẫu được nạp cho bảng này.</p>
      </div>
    );
  }

  const sampleRows = tableData.sample_data;
  const headers = Object.keys(sampleRows[0]);

  // Mask sensitive values
  const formatCellValue = (header, value) => {
    if (value === null || value === undefined) {
      return <span className="null-literal">NULL</span>;
    }
    const strVal = String(value);

    if (isMasked) {
      if (header.includes('email')) {
        const parts = strVal.split('@');
        return <span className="cell-val masked">{parts[0].slice(0, 2)}*****@{parts[1] || '***.com'}</span>;
      }
      if (header.includes('customer_id')) {
        return <span className="cell-val masked">{strVal.slice(0, 5)}***{strVal.slice(-1)}</span>;
      }
    }

    return <span className="cell-val">{strVal}</span>;
  };

  return (
    <div className="sample-data-container">
      <div className="sample-data-header">
        <div className="sample-data-title-group">
          <span className="sample-icon">👁️</span>
          <div>
            <h3 className="sample-heading">Dữ liệu mẫu thực tế (Sample Data Preview)</h3>
            <p className="sample-subheading">
              Hiển thị {sampleRows.length} bản ghi mẫu thực tế từ bảng <code>{tableData.table_name}</code> để đối chiếu với các luật DQ
            </p>
          </div>
        </div>

        <div className="sample-actions">
          {/* PII Masking Toggle */}
          <button
            className={`btn-mask-toggle ${isMasked ? 'masked-active' : ''}`}
            onClick={() => setIsMasked(!isMasked)}
            title="Bật/Tắt che giấu dữ liệu PII nhạy cảm"
          >
            {isMasked ? '🔒 Đang che dữ liệu PII' : '🔓 Đang hiện dữ liệu thô'}
          </button>

          <span className="sample-badge-count">{sampleRows.length} records</span>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => alert('Dữ liệu đã được nạp sẵn để đối chiếu với các luật Data Quality trên Web!')}
          >
            📋 Xuất file CSV
          </button>
        </div>
      </div>

      <div className="sample-table-card">
        <div className="table-responsive">
          <table className="sample-preview-table">
            <thead>
              <tr>
                <th style={{ width: '50px' }}>#</th>
                {headers.map((h) => (
                  <th key={h}>
                    {h}
                    {(h.includes('email') || h.includes('customer_id')) && (
                      <span className="pii-indicator-tag" title="Cột nhạy cảm PII">PII</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sampleRows.map((row, idx) => (
                <tr key={idx}>
                  <td className="row-num">{idx + 1}</td>
                  {headers.map((h) => (
                    <td key={h}>{formatCellValue(h, row[h])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
