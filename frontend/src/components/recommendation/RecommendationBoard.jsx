import React, { useState } from 'react';
import ActionToolbar from './ActionToolbar';
import FilterTabs from './FilterTabs';
import RuleCard from './RuleCard';
import PublishBar from './PublishBar';
import ColumnRuleBrowser from './ColumnRuleBrowser';

export default function RecommendationBoard({
  rules,
  tableData,
  activeFilter,
  setActiveFilter,
  searchQuery,
  setSearchQuery,
  useBasic,
  setUseBasic,
  useAdvanced,
  setUseAdvanced,
  isGenerating,
  generationStep,
  onGenerate,
  onReviewAction,
  onOpenEdit,
  onPublish
}) {
  // Default to 'COLUMNS' view as requested by user
  const [viewMode, setViewMode] = useState('COLUMNS'); // 'COLUMNS' | 'FLAT'
  const [selectedColumn, setSelectedColumn] = useState(null);

  // Compute Stats
  const stats = {
    all: rules.length,
    basic: rules.filter((r) => r.engine === 'BASIC').length,
    advanced: rules.filter((r) => r.engine === 'ADVANCED').length,
    warning: rules.filter((r) => r.validation_status === 'WARNING').length,
    accepted: rules.filter((r) => r.status === 'ACCEPTED' || r.status === 'EDITED').length
  };

  const reviewedCount = rules.filter((r) => r.status !== 'DRAFT').length;

  // Filter Rules (for flat view)
  const filteredRules = rules.filter((rule) => {
    if (activeFilter === 'BASIC' && rule.engine !== 'BASIC') return false;
    if (activeFilter === 'ADVANCED' && rule.engine !== 'ADVANCED') return false;
    if (activeFilter === 'WARNING' && rule.validation_status !== 'WARNING') return false;
    if (activeFilter === 'ACCEPTED' && rule.status !== 'ACCEPTED' && rule.status !== 'EDITED') return false;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchType = rule.rule_type.toLowerCase().includes(q);
      const matchCol = rule.target_columns.some((c) => c.toLowerCase().includes(q));
      const matchReason = rule.reason.toLowerCase().includes(q);
      if (!matchType && !matchCol && !matchReason) return false;
    }

    return true;
  });

  return (
    <section className="recommendation-panel" id="recommendation-panel">
      {/* Top Toolbar */}
      <ActionToolbar
        onGenerate={onGenerate}
        useBasic={useBasic}
        setUseBasic={setUseBasic}
        useAdvanced={useAdvanced}
        setUseAdvanced={setUseAdvanced}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        isGenerating={isGenerating}
      />

      {/* Mode Switcher Bar */}
      <div className="view-mode-bar">
        <div className="view-mode-toggles">
          <button
            className={`btn-mode-toggle ${viewMode === 'COLUMNS' ? 'active' : ''}`}
            onClick={() => setViewMode('COLUMNS')}
            title="Hiển thị danh sách các cột trước, bấm vào cột để duyệt luật"
          >
            <span className="mode-icon">🗂️</span>
            <span>Xem theo Cột {selectedColumn ? `(${selectedColumn})` : ''}</span>
          </button>

          <button
            className={`btn-mode-toggle ${viewMode === 'FLAT' ? 'active' : ''}`}
            onClick={() => setViewMode('FLAT')}
            title="Hiển thị danh sách phẳng tất cả các rule"
          >
            <span className="mode-icon">📑</span>
            <span>Tất cả Rule ({rules.length})</span>
          </button>
        </div>

        {/* Filter Tabs & Review Progress */}
        <FilterTabs
          activeFilter={activeFilter}
          setActiveFilter={setActiveFilter}
          stats={stats}
          reviewedCount={reviewedCount}
          totalCount={rules.length}
        />
      </div>

      {/* Loading State Overlay */}
      {isGenerating && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <h3>{generationStep.title}</h3>
          <p>{generationStep.subtitle}</p>
        </div>
      )}

      {/* Main Content: Column View (Default) */}
      {!isGenerating && viewMode === 'COLUMNS' && (
        <ColumnRuleBrowser
          rules={rules}
          tableData={tableData}
          onReviewAction={onReviewAction}
          onOpenEdit={onOpenEdit}
          searchQuery={searchQuery}
          activeFilter={activeFilter}
          selectedColumn={selectedColumn}
          setSelectedColumn={setSelectedColumn}
        />
      )}

      {/* Main Content: Flat Rules View */}
      {!isGenerating && viewMode === 'FLAT' && (
        <>
          {filteredRules.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📋</div>
              <h3>Không tìm thấy Rule nào phù hợp</h3>
              <p>Hãy thử đổi bộ lọc hoặc bấm nút <strong>Generate Quality Rules</strong> ở trên.</p>
            </div>
          ) : (
            <div className="rules-container">
              {filteredRules.map((rule) => (
                <RuleCard
                  key={rule.id}
                  rule={rule}
                  onReviewAction={onReviewAction}
                  onOpenEdit={onOpenEdit}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Sticky Publish Bar */}
      <PublishBar readyRulesCount={stats.accepted} onPublish={onPublish} />
    </section>
  );
}
