import React from 'react';

export default function ActionToolbar({
  onGenerate,
  useBasic,
  setUseBasic,
  useAdvanced,
  setUseAdvanced,
  searchQuery,
  setSearchQuery,
  isGenerating
}) {
  return (
    <div className="action-bar">
      <div className="trigger-group">
        <button
          className="btn btn-primary btn-glow"
          onClick={onGenerate}
          disabled={isGenerating}
        >
          <span className="btn-icon">⚡</span>
          <span className="btn-text">
            {isGenerating ? 'Đang phân tích...' : 'Generate Quality Rules'}
          </span>
        </button>

        <div className="engine-toggles">
          <label className="toggle-checkbox" title="Tự động sinh từ profiling và heuristic toán học">
            <input
              type="checkbox"
              checked={useBasic}
              onChange={(e) => setUseBasic(e.target.checked)}
            />
            <span className="chk-box"></span>
            <span className="label-text">Basic (Heuristics)</span>
          </label>

          <label className="toggle-checkbox" title="Sử dụng LLM phân tích ngữ nghĩa, temporal và cross-column">
            <input
              type="checkbox"
              checked={useAdvanced}
              onChange={(e) => setUseAdvanced(e.target.checked)}
            />
            <span className="chk-box"></span>
            <span className="label-text">Advanced (LLM)</span>
          </label>
        </div>
      </div>

      <div className="filter-controls">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Tìm theo tên rule, cột..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
