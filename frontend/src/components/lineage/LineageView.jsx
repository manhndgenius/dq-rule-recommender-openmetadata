import React, { useState, useRef, useEffect } from 'react';

export default function LineageView({ tableData }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const [filterType, setFilterType] = useState('ALL');
  const [zoomLevel, setZoomLevel] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [showColumnLineage, setShowColumnLineage] = useState(false);
  const [showImpactAnalysis, setShowImpactAnalysis] = useState(false);

  const containerRef = useRef(null);
  const dragStartRef = useRef({ startX: 0, startY: 0, initialPanX: 0, initialPanY: 0 });
  const dragDistanceRef = useRef(0);

  if (!tableData || !tableData.lineage) {
    return (
      <div className="lineage-empty">
        <p>Không có dữ liệu Lineage cho bảng này.</p>
      </div>
    );
  }

  const { upstream = [], pipelines = [], current, downstream = [] } = tableData.lineage;

  const handleZoom = (delta) => {
    setZoomLevel((prev) => {
      const next = Math.min(Math.max(prev + delta, 0.4), 2.5);
      return Math.round(next * 100) / 100;
    });
  };

  const handleResetView = () => {
    setZoomLevel(1);
    setPan({ x: 0, y: 0 });
  };

  // 1. Phóng to / Thu nhỏ bằng cách lăn chuột (Mouse Wheel Zoom)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      setZoomLevel((prev) => {
        const next = Math.min(Math.max(prev * zoomFactor, 0.4), 2.5);
        return Math.round(next * 100) / 100;
      });
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheel);
    };
  }, []);

  // 2. Giữ chuột để kéo biểu đồ (Mouse Drag / Pan)
  const handleMouseDown = (e) => {
    if (e.button !== 0) return; // Chỉ nhận chuột trái
    setIsDragging(true);
    dragDistanceRef.current = 0;
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialPanX: pan.x,
      initialPanY: pan.y
    };
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleWindowMouseMove = (e) => {
      const dx = e.clientX - dragStartRef.current.startX;
      const dy = e.clientY - dragStartRef.current.startY;
      dragDistanceRef.current += Math.abs(dx) + Math.abs(dy);
      setPan({
        x: dragStartRef.current.initialPanX + dx,
        y: dragStartRef.current.initialPanY + dy
      });
    };

    const handleWindowMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handleWindowMouseMove);
    window.addEventListener('mouseup', handleWindowMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleWindowMouseMove);
      window.removeEventListener('mouseup', handleWindowMouseUp);
    };
  }, [isDragging]);

  const handleNodeClick = (node) => {
    // Nếu người dùng vừa giữ chuột kéo biểu đồ (drag > 6px) thì không mở drawer chi tiết
    if (dragDistanceRef.current > 6) return;
    setSelectedNode(node);
  };

  const isVisible = (type) => {
    if (filterType === 'ALL') return true;
    if (filterType === 'TABLE' && (type === 'table' || type === 'topic')) return true;
    if (filterType === 'PIPELINE' && type === 'pipeline') return true;
    if (filterType === 'DASHBOARD' && type === 'dashboard') return true;
    return false;
  };

  return (
    <div className="lineage-container">
      {/* Top Controls Toolbar */}
      <div className="lineage-toolbar">
        <div className="lineage-toolbar-left">
          <div className="lineage-title-group">
            <div>
              <h3 className="lineage-heading">End-to-End Data Lineage Graph</h3>
              <p className="lineage-subheading">
                Luồng phả hệ dữ liệu tự động đồng bộ từ OpenMetadata Metadata Graph
              </p>
            </div>
          </div>
        </div>

        <div className="lineage-toolbar-right">
          {/* Filter by Entity */}
          <div className="lineage-filter-group">
            <span className="filter-label">Bộ lọc:</span>
            <button
              className={`btn-chip ${filterType === 'ALL' ? 'active' : ''}`}
              onClick={() => setFilterType('ALL')}
            >
              Tất cả
            </button>
            <button
              className={`btn-chip ${filterType === 'TABLE' ? 'active' : ''}`}
              onClick={() => setFilterType('TABLE')}
            >
              Tables
            </button>
            <button
              className={`btn-chip ${filterType === 'PIPELINE' ? 'active' : ''}`}
              onClick={() => setFilterType('PIPELINE')}
            >
              Pipelines
            </button>
            <button
              className={`btn-chip ${filterType === 'DASHBOARD' ? 'active' : ''}`}
              onClick={() => setFilterType('DASHBOARD')}
            >
              Dashboards
            </button>
          </div>

          {/* Column Lineage Toggle */}
          <button
            className={`btn-toggle-col ${showColumnLineage ? 'active' : ''}`}
            onClick={() => setShowColumnLineage(!showColumnLineage)}
          >
            {showColumnLineage ? 'Ẩn Column Lineage' : 'Bật Column Lineage'}
          </button>

          {/* Impact Analysis Toggle */}
          <button
            className={`btn-toggle-impact ${showImpactAnalysis ? 'active' : ''}`}
            onClick={() => setShowImpactAnalysis(!showImpactAnalysis)}
          >
            {showImpactAnalysis ? 'Ẩn Impact Analysis' : 'Bật Impact Analysis'}
          </button>

          {/* Zoom Controls */}
          <div className="zoom-controls">
            <button className="btn-zoom" onClick={() => handleZoom(-0.1)} title="Thu nhỏ (hoặc lăn chuột xuống)">－</button>
            <span className="zoom-value" title="Tỷ lệ thu phóng hiện tại">{Math.round(zoomLevel * 100)}%</span>
            <button className="btn-zoom" onClick={() => handleZoom(0.1)} title="Phóng to (hoặc lăn chuột lên)">＋</button>
            <button className="btn-zoom" onClick={handleResetView} title="Khôi phục mặc định (Reset zoom & vị trí)">↺</button>
          </div>
        </div>
      </div>

      {/* Impact Analysis Warning Banner if enabled */}
      {showImpactAnalysis && (
        <div className="impact-analysis-banner">
          <div className="impact-banner-left">
            <div>
              <strong>Báo cáo phân tích tác động hạ nguồn (Downstream Impact Analysis):</strong>
              <p>Nếu bảng <code>{tableData.table_name}</code> gặp sự cố chất lượng dữ liệu, sẽ có <strong>{downstream.length} tài sản hạ nguồn</strong> bị gián đoạn hoạt động.</p>
            </div>
          </div>
          <div className="impact-summary-pills">
            <span className="impact-pill-crit">2 Bảng DW quan trọng</span>
            <span className="impact-pill-bi">2 Báo cáo BI Dashboard (Tableau, Looker)</span>
          </div>
        </div>
      )}

      {/* Main Graph Canvas */}
      <div
        ref={containerRef}
        className={`lineage-canvas-wrapper ${isDragging ? 'is-dragging' : ''}`}
        onMouseDown={handleMouseDown}
      >
        <div
          className="lineage-canvas"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoomLevel})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.15s ease-out'
          }}
        >
          {/* Column 1: Upstream Ingestion Sources */}
          <div className="lineage-column">
            <div className="column-header">
              <span className="col-badge">NGUỒN DỮ LIỆU (UPSTREAM)</span>
            </div>
            <div className="nodes-stack">
              {upstream.map((node) =>
                isVisible(node.type) && (
                  <div
                    key={node.id}
                    className={`lineage-node node-source ${selectedNode?.id === node.id ? 'selected' : ''}`}
                    onClick={() => handleNodeClick(node)}
                  >
                    <div className="node-info">
                      <span className="node-type-label">{node.service}</span>
                      <strong className="node-name">{node.name}</strong>
                      <span className="node-fqn">{node.fqn}</span>
                    </div>
                    <span className="node-status-dot online" title="Healthy"></span>
                  </div>
                )
              )}
            </div>
          </div>

          {/* Connection Arrows 1 */}
          <div className="lineage-connector-col">
            <div className="connector-flow">
              <div className="flow-line"></div>
              <span className="flow-arrow">➔</span>
            </div>
          </div>

          {/* Column 2: Transformation & Pipelines */}
          <div className="lineage-column">
            <div className="column-header">
              <span className="col-badge">BIẾN ĐỔI (ETL / DBT PIPELINES)</span>
            </div>
            <div className="nodes-stack">
              {pipelines.map((pipe) =>
                isVisible(pipe.type) && (
                  <div
                    key={pipe.id}
                    className={`lineage-node node-pipeline ${selectedNode?.id === pipe.id ? 'selected' : ''}`}
                    onClick={() => handleNodeClick(pipe)}
                  >
                    <div className="node-info">
                      <span className="node-type-label">{pipe.engine}</span>
                      <strong className="node-name">{pipe.name}</strong>
                      <span className="node-runtime">Chạy: {pipe.last_run}</span>
                    </div>
                    <span className="node-badge-success">{pipe.status}</span>
                  </div>
                )
              )}
            </div>
          </div>

          {/* Connection Arrows 2 */}
          <div className="lineage-connector-col">
            <div className="connector-flow">
              <div className="flow-line"></div>
              <span className="flow-arrow">➔</span>
            </div>
          </div>

          {/* Column 3: Current Selected Table */}
          <div className="lineage-column">
            <div className="column-header">
              <span className="col-badge active-highlight">BẢNG HIỆN TẠI (FOCUSED)</span>
            </div>
            <div className="nodes-stack">
              <div
                className={`lineage-node node-current ${selectedNode?.id === current.id ? 'selected' : ''}`}
                onClick={() => handleNodeClick(current)}
              >
                <div className="node-header-current">
                  <span className="current-tier-pill">{current.tier || 'Tier: --'}</span>
                </div>
                <div className="node-info">
                  <span className="node-type-label">PostgreSQL Catalog</span>
                  <strong className="node-name highlight-name">{current.name}</strong>
                  <span className="node-fqn">{current.fqn}</span>
                </div>
                {showColumnLineage && (
                  <div className="column-lineage-preview">
                    <span className="col-flow-item">order_id ➔ PK</span>
                    <span className="col-flow-item">total_amount ➔ Revenue Metric</span>
                    <span className="col-flow-item">order_status ➔ Dimension</span>
                  </div>
                )}
                <div className="node-footer-current">
                  <span className="rule-badge-applied">Đã áp dụng Data Quality Rules</span>
                </div>
              </div>
            </div>
          </div>

          {/* Connection Arrows 3 */}
          <div className="lineage-connector-col">
            <div className="connector-flow">
              <div className="flow-line"></div>
              <span className="flow-arrow">➔</span>
            </div>
          </div>

          {/* Column 4: Downstream Analytics & BI Dashboards */}
          <div className="lineage-column">
            <div className="column-header">
              <span className="col-badge">HẠ NGUỒN (DOWNSTREAM CONSUMERS)</span>
            </div>
            <div className="nodes-stack">
              {downstream.map((down) =>
                isVisible(down.type) && (
                  <div
                    key={down.id}
                    className={`lineage-node node-downstream ${selectedNode?.id === down.id ? 'selected' : ''} ${down.type === 'dashboard' ? 'node-bi' : ''} ${showImpactAnalysis ? 'impact-highlighted' : ''}`}
                    onClick={() => handleNodeClick(down)}
                  >
                    <div className="node-info">
                      <span className="node-type-label">{down.service}</span>
                      <strong className="node-name">{down.name}</strong>
                      <span className="node-fqn">{down.fqn}</span>
                      {showImpactAnalysis && (
                        <span className="impact-badge-tag">Bị tác động nếu {tableData?.table_name || 'orders'} lỗi</span>
                      )}
                    </div>
                    <span className="node-status-dot online"></span>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div className="node-detail-drawer">
          <div className="drawer-header">
            <h4>Chi tiết thực thể: {selectedNode.name}</h4>
            <button className="btn-close-drawer" onClick={() => setSelectedNode(null)}>✕</button>
          </div>
          <div className="drawer-body">
            <div className="drawer-prop">
              <span className="prop-name">Fully Qualified Name:</span>
              <code className="prop-val">{selectedNode.fqn || selectedNode.name}</code>
            </div>
            <div className="drawer-prop">
              <span className="prop-name">Loại thực thể (Type):</span>
              <span className="prop-val-badge">{selectedNode.type?.toUpperCase()}</span>
            </div>
            <div className="drawer-prop">
              <span className="prop-name">Dịch vụ (Service):</span>
              <span className="prop-val">{selectedNode.service || selectedNode.engine || 'OpenMetadata Catalog'}</span>
            </div>
            <div className="drawer-prop">
              <span className="prop-name">Trạng thái sức khỏe:</span>
              <span className="health-badge healthy">Hoạt động bình thường (Healthy)</span>
            </div>
            <div className="drawer-actions">
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => window.open('https://sandbox.open-metadata.org/explore', '_blank')}
              >
                Mở trong OpenMetadata Sandbox
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
