import React, { useState, useMemo } from 'react';
import RuleCard from './RuleCard';

export default function ColumnRuleBrowser({
  rules,
  tableData,
  onReviewAction,
  onOpenEdit,
  searchQuery,
  activeFilter,
  selectedColumn,
  setSelectedColumn
}) {
  const [colFilter, setColFilter] = useState('ALL'); // 'ALL' | 'WITH_RULES' | 'PENDING' | 'COMPLETED'
  const [colSearch, setColSearch] = useState('');

  // 1. Group rules by column
  const { tableLevelGroup, columnGroups, allColumnsList } = useMemo(() => {
    const tableRules = rules.filter(
      (r) => !r.target_columns || r.target_columns.length === 0
    );

    const tableGroup = {
      name: '__TABLE_LEVEL__',
      displayName: 'Toàn bảng (Table-level)',
      isTableLevel: true,
      dataType: 'TABLE',
      isPrimaryKey: false,
      rules: tableRules,
      totalRules: tableRules.length,
      reviewedCount: tableRules.filter((r) => r.status !== 'DRAFT').length,
      acceptedCount: tableRules.filter((r) => r.status === 'ACCEPTED' || r.status === 'EDITED').length,
      rejectedCount: tableRules.filter((r) => r.status === 'REJECTED').length,
      hasWarning: tableRules.some((r) => r.validation_status === 'WARNING'),
      hasAdvanced: tableRules.some((r) => r.engine === 'ADVANCED'),
      ruleTypes: [...new Set(tableRules.map((r) => r.rule_type))]
    };

    // Columns from tableData or derived from rules
    const knownColsMap = new Map();
    if (tableData && tableData.columns && Array.isArray(tableData.columns)) {
      tableData.columns.forEach((c) => {
        knownColsMap.set(c.name, {
          name: c.name,
          displayName: c.name,
          dataType: c.data_type || 'VARCHAR',
          isPrimaryKey: Boolean(c.is_primary_key),
          description: c.description || ''
        });
      });
    }

    // Ensure all target_columns mentioned in rules exist in map
    rules.forEach((r) => {
      if (r.target_columns && Array.isArray(r.target_columns)) {
        r.target_columns.forEach((colName) => {
          if (!knownColsMap.has(colName)) {
            knownColsMap.set(colName, {
              name: colName,
              displayName: colName,
              dataType: 'VARCHAR',
              isPrimaryKey: false,
              description: ''
            });
          }
        });
      }
    });

    const colGroups = Array.from(knownColsMap.values()).map((c) => {
      const colRules = rules.filter(
        (r) => r.target_columns && r.target_columns.includes(c.name)
      );

      return {
        ...c,
        isTableLevel: false,
        rules: colRules,
        totalRules: colRules.length,
        reviewedCount: colRules.filter((r) => r.status !== 'DRAFT').length,
        acceptedCount: colRules.filter((r) => r.status === 'ACCEPTED' || r.status === 'EDITED').length,
        rejectedCount: colRules.filter((r) => r.status === 'REJECTED').length,
        hasWarning: colRules.some((r) => r.validation_status === 'WARNING'),
        hasAdvanced: colRules.some((r) => r.engine === 'ADVANCED'),
        ruleTypes: [...new Set(colRules.map((r) => r.rule_type))]
      };
    });

    // Sort: PKs first, then columns with rules, then alphabetical
    colGroups.sort((a, b) => {
      if (a.isPrimaryKey && !b.isPrimaryKey) return -1;
      if (!a.isPrimaryKey && b.isPrimaryKey) return 1;
      if (a.totalRules > 0 && b.totalRules === 0) return -1;
      if (a.totalRules === 0 && b.totalRules > 0) return 1;
      return a.name.localeCompare(b.name);
    });

    // Chỉ hiển thị nhóm Toàn bảng (Table-level) nếu có rule cấp bảng thực tế
    const allList = tableGroup.totalRules > 0 ? [tableGroup, ...colGroups] : colGroups;

    return {
      tableLevelGroup: tableGroup,
      columnGroups: colGroups,
      allColumnsList: allList
    };
  }, [rules, tableData]);

  // Columns with rules only (for the quick carousel and switcher)
  const columnsWithRules = useMemo(() => {
    return allColumnsList.filter((col) => col.totalRules > 0);
  }, [allColumnsList]);

  // Filter columns in the Column List Overview
  const filteredColumns = useMemo(() => {
    return allColumnsList.filter((col) => {
      // Filter by colFilter tab
      if (colFilter === 'WITH_RULES' && col.totalRules === 0) return false;
      if (colFilter === 'PENDING' && (col.totalRules === 0 || col.reviewedCount === col.totalRules)) return false;
      if (colFilter === 'COMPLETED' && (col.totalRules === 0 || col.reviewedCount < col.totalRules)) return false;

      // Filter by global activeFilter (BASIC, ADVANCED, WARNING, ACCEPTED)
      if (activeFilter === 'BASIC' && !col.rules.some((r) => r.engine === 'BASIC')) return false;
      if (activeFilter === 'ADVANCED' && !col.rules.some((r) => r.engine === 'ADVANCED')) return false;
      if (activeFilter === 'WARNING' && !col.hasWarning) return false;
      if (activeFilter === 'ACCEPTED' && col.acceptedCount === 0) return false;

      // Filter by search query (combines toolbar search & local column search)
      const query = (colSearch || searchQuery || '').trim().toLowerCase();
      if (query) {
        const matchName = col.displayName.toLowerCase().includes(query);
        const matchType = col.dataType.toLowerCase().includes(query);
        const matchRuleType = col.ruleTypes.some((t) => t.toLowerCase().includes(query));
        const matchDesc = col.description ? col.description.toLowerCase().includes(query) : false;
        if (!matchName && !matchType && !matchRuleType && !matchDesc) return false;
      }

      return true;
    });
  }, [allColumnsList, colFilter, colSearch, searchQuery, activeFilter]);

  // Format short readable label for rule type badge
  const getRuleTypeBadge = (type) => {
    switch (type) {
      case 'columnValuesToBeNotNull':
        return { label: 'NOT NULL', color: 'badge-null' };
      case 'columnValuesToBeUnique':
        return { label: 'UNIQUE', color: 'badge-unique' };
      case 'columnValuesToBeBetween':
        return { label: 'RANGE / BETWEEN', color: 'badge-between' };
      case 'columnValuesToBeInSet':
        return { label: 'IN-SET (ENUM)', color: 'badge-set' };
      case 'columnValuesLengthToBeBetween':
        return { label: 'LENGTH', color: 'badge-length' };
      case 'tableRowCountToBeBetween':
        return { label: 'ROW COUNT', color: 'badge-rowcount' };
      case 'tableCustomSQLQuery':
        return { label: 'CUSTOM SQL', color: 'badge-sql' };
      default:
        return { label: type.replace('columnValues', '').replace('ToBe', ' '), color: 'badge-default' };
    }
  };

  // Find active column details
  const activeColObj = useMemo(() => {
    if (!selectedColumn) return null;
    return allColumnsList.find((c) => c.name === selectedColumn) || null;
  }, [selectedColumn, allColumnsList]);

  // Get index of active column in columnsWithRules for Prev / Next navigation
  const activeColIndex = useMemo(() => {
    if (!activeColObj) return -1;
    return columnsWithRules.findIndex((c) => c.name === activeColObj.name);
  }, [activeColObj, columnsWithRules]);

  // Batch accept all rules of the current column
  const handleBatchAcceptColumn = () => {
    if (!activeColObj) return;
    activeColObj.rules.forEach((r) => {
      if (r.status !== 'ACCEPTED') {
        onReviewAction(r.id, 'ACCEPTED');
      }
    });
  };

  // -------------------------------------------------------------
  // VIEW A: COLUMN LIST (Khi chưa chọn cột nào)
  // -------------------------------------------------------------
  if (!selectedColumn) {
    const totalCols = allColumnsList.length;
    const withRulesCols = columnsWithRules.length;
    const pendingCols = allColumnsList.filter(
      (c) => c.totalRules > 0 && c.reviewedCount < c.totalRules
    ).length;
    const doneCols = allColumnsList.filter(
      (c) => c.totalRules > 0 && c.reviewedCount === c.totalRules
    ).length;

    return (
      <div className="column-browser-container">
        {/* Banner Overview */}
        <div className="column-browser-hero">
          <div className="cb-hero-left">
            <div>
              <h3 className="cb-hero-title">Danh sách các Cột & Đề xuất Rule DQ</h3>
              <p className="cb-hero-sub">
                Chọn một cột bất kỳ bên dưới để kiểm tra và duyệt các rule Data Quality tương ứng. 
                Đã phân tích <strong>{rules.length}</strong> rule trên <strong>{withRulesCols}</strong> cột.
              </p>
            </div>
          </div>
          <div className="cb-hero-stats">
            <div className="cb-stat-pill">
              <span className="lbl">Tổng cột:</span>
              <strong>{totalCols}</strong>
            </div>
            <div className="cb-stat-pill highlight">
              <span className="lbl">Cột có rule:</span>
              <strong>{withRulesCols}</strong>
            </div>
            <div className="cb-stat-pill">
              <span className="lbl">Tổng rule DQ:</span>
              <strong>{rules.length}</strong>
            </div>
          </div>
        </div>

        {/* Filter & Search Bar */}
        <div className="cb-filter-bar">
          <div className="cb-filter-tabs">
            <button
              className={`cb-tab ${colFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setColFilter('ALL')}
            >
              Tất cả cột <span className="cb-count">{totalCols}</span>
            </button>
            <button
              className={`cb-tab ${colFilter === 'WITH_RULES' ? 'active' : ''}`}
              onClick={() => setColFilter('WITH_RULES')}
            >
              Có rule DQ <span className="cb-count">{withRulesCols}</span>
            </button>
            <button
              className={`cb-tab ${colFilter === 'PENDING' ? 'active' : ''}`}
              onClick={() => setColFilter('PENDING')}
            >
              Cần duyệt <span className="cb-count">{pendingCols}</span>
            </button>
            <button
              className={`cb-tab ${colFilter === 'COMPLETED' ? 'active' : ''}`}
              onClick={() => setColFilter('COMPLETED')}
            >
              Đã duyệt xong <span className="cb-count">{doneCols}</span>
            </button>
          </div>

          <div className="cb-search-input-wrap">
            <span className="cb-search-icon">🔍</span>
            <input
              type="text"
              className="cb-search-input"
              placeholder="Tìm theo tên cột, kiểu dữ liệu, loại rule..."
              value={colSearch}
              onChange={(e) => setColSearch(e.target.value)}
            />
            {colSearch && (
              <button
                className="cb-search-clear"
                onClick={() => setColSearch('')}
                title="Xóa tìm kiếm"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Empty Search Result */}
        {filteredColumns.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <h3>Không tìm thấy cột nào khớp bộ lọc</h3>
            <p>Vui lòng thử từ khóa khác hoặc chuyển bộ lọc sang "Tất cả cột".</p>
          </div>
        )}

        {/* Columns Grid */}
        <div className="cb-columns-grid">
          {filteredColumns.map((col) => {
            const isDone = col.totalRules > 0 && col.reviewedCount === col.totalRules;
            const isPending = col.totalRules > 0 && col.reviewedCount < col.totalRules;
            const progress = col.totalRules > 0 ? Math.round((col.reviewedCount / col.totalRules) * 100) : 0;

            return (
              <div
                key={col.name}
                className={`cb-column-card ${col.isTableLevel ? 'table-level' : ''} ${isDone ? 'done' : ''}`}
                onClick={() => setSelectedColumn(col.name)}
                title={`Bấm để xem và duyệt ${col.totalRules} rule của ${col.displayName}`}
              >
                {/* Card Header */}
                <div className="cbc-head">
                  <div className="cbc-head-left">
                    <strong className="cbc-name">{col.displayName}</strong>
                    {col.isPrimaryKey && (
                      <span className="cbc-pk-badge" title="Primary Key">PK</span>
                    )}
                  </div>
                  <div className="cbc-head-right">
                    <span className="cbc-type-badge">{col.dataType}</span>
                  </div>
                </div>

                {/* Column Description / Notes if available */}
                {col.description && (
                  <p className="cbc-desc" title={col.description}>
                    {col.description}
                  </p>
                )}

                {/* Candidate Rule Type Tags */}
                <div className="cbc-rules-preview">
                  {col.totalRules > 0 ? (
                    col.ruleTypes.map((rt) => {
                      const badge = getRuleTypeBadge(rt);
                      return (
                        <span key={rt} className={`cbc-rule-tag ${badge.color}`}>
                          {badge.label}
                        </span>
                      );
                    })
                  ) : (
                    <span className="cbc-no-rules">Chưa có rule DQ đề xuất</span>
                  )}
                </div>

                {/* Card Footer & Progress */}
                <div className="cbc-footer">
                  <div className="cbc-status-info">
                    {col.totalRules === 0 ? (
                      <span className="cbc-status-text muted">0 rules</span>
                    ) : isDone ? (
                      <span className="cbc-status-text success">
                        Đã duyệt ({col.acceptedCount}/{col.totalRules})
                      </span>
                    ) : (
                      <span className="cbc-status-text pending">
                        Cần duyệt ({col.reviewedCount}/{col.totalRules})
                      </span>
                    )}

                    {col.totalRules > 0 && (
                      <div className="cbc-mini-bar">
                        <div
                          className={`cbc-mini-fill ${isDone ? 'done' : ''}`}
                          style={{ width: `${progress}%` }}
                        ></div>
                      </div>
                    )}
                  </div>

                  <button
                    className="cbc-btn-view"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedColumn(col.name);
                    }}
                  >
                    <span>Xem {col.totalRules} rule</span>
                    <span className="arrow">➔</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------
  // VIEW B: COLUMN DETAIL & RULES REVIEW (Khi đã bấm vào 1 cột)
  // -------------------------------------------------------------
  const colRules = activeColObj ? activeColObj.rules : [];
  const colProgress = activeColObj && activeColObj.totalRules > 0
    ? Math.round((activeColObj.reviewedCount / activeColObj.totalRules) * 100)
    : 0;

  const prevCol = activeColIndex > 0 ? columnsWithRules[activeColIndex - 1] : null;
  const nextCol = activeColIndex >= 0 && activeColIndex < columnsWithRules.length - 1
    ? columnsWithRules[activeColIndex + 1]
    : null;

  return (
    <div className="column-detail-review-view">
      {/* Top Navigation & Breadcrumb Banner */}
      <div className="cd-nav-banner">
        <div className="cd-nav-left">
          <button
            className="cd-btn-back"
            onClick={() => setSelectedColumn(null)}
            title="Quay lại danh sách toàn bộ các cột"
          >
            <span className="back-arrow">◀</span>
            <strong>Danh sách cột</strong>
            <span className="cd-col-count-badge">({allColumnsList.length} cột)</span>
          </button>

          <div className="cd-col-identity">
            <div className="cd-col-texts">
              <div className="cd-col-headline">
                {activeColObj?.isTableLevel ? (
                  <div className="cd-col-name-wrap">
                    <h3 className="cd-col-name">Toàn bảng</h3>
                    <span className="cd-col-level-tag">(Table-level)</span>
                    <span className="cd-col-type">{activeColObj?.dataType}</span>
                  </div>
                ) : (
                  <>
                    <h3 className="cd-col-name">{activeColObj?.displayName}</h3>
                    <span className="cd-col-type">{activeColObj?.dataType}</span>
                    {activeColObj?.isPrimaryKey && (
                      <span className="cbc-pk-badge">Primary Key</span>
                    )}
                    {activeColObj?.hasAdvanced && (
                      <span className="cd-badge-adv">Advanced Domain</span>
                    )}
                  </>
                )}
              </div>
              {activeColObj?.description && (
                <p className="cd-col-subdesc">{activeColObj.description}</p>
              )}
            </div>
          </div>
        </div>

        <div className="cd-nav-right">
          {/* Progress Card */}
          <div className="cd-progress-card">
            <div className="cd-pcard-header">
              <span className="pcard-label">Tiến độ cột:</span>
              <span className="pcard-fraction">
                <strong>{activeColObj?.reviewedCount}</strong>/{activeColObj?.totalRules}
              </span>
              <span className="pcard-pct">{colProgress}%</span>
            </div>
            <div className="cd-pbar-wrap">
              <div className="cd-pbar-fill" style={{ width: `${colProgress}%` }}></div>
            </div>
          </div>

          {/* Batch Accept Button for this column */}
          {activeColObj && activeColObj.totalRules > 0 && activeColObj.acceptedCount < activeColObj.totalRules && (
            <button
              className="btn-batch-accept"
              onClick={handleBatchAcceptColumn}
              title="Duyệt chấp thuận tất cả các rule của cột này trong 1 cú nhấp"
            >
              <span>✔</span> Duyệt tất cả rule cột này
            </button>
          )}
        </div>
      </div>

      {/* Quick Column Switcher (Pill carousel) */}
      <div className="cd-column-pills-bar">
        <span className="cd-pills-label">Cột khác:</span>
        <div className="cd-pills-scroll">
          {columnsWithRules.map((c) => {
            const isActive = c.name === selectedColumn;
            const isColDone = c.totalRules > 0 && c.reviewedCount === c.totalRules;
            return (
              <button
                key={c.name}
                className={`cd-pill-item ${isActive ? 'active' : ''} ${isColDone ? 'done' : ''}`}
                onClick={() => setSelectedColumn(c.name)}
                title={`Chuyển sang cột ${c.displayName} (${c.totalRules} rule)`}
              >
                <span>{c.displayName}</span>
                <span className="pill-count">{c.totalRules}</span>
                {isColDone && <span className="pill-check">✓</span>}
              </button>
            );
          })}
        </div>

        <div className="cd-pills-nav-btns">
          <button
            className="cd-btn-prev"
            disabled={!prevCol}
            onClick={() => prevCol && setSelectedColumn(prevCol.name)}
            title={prevCol ? `Cột trước: ${prevCol.displayName}` : 'Đã là cột đầu tiên'}
          >
            ◀ Cột trước
          </button>
          <button
            className="cd-btn-next"
            disabled={!nextCol}
            onClick={() => nextCol && setSelectedColumn(nextCol.name)}
            title={nextCol ? `Cột tiếp theo: ${nextCol.displayName}` : 'Đã là cột cuối cùng'}
          >
            Cột tiếp ▶
          </button>
        </div>
      </div>

      {/* Empty State for Column with no rules */}
      {colRules.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>Cột '{activeColObj?.displayName}' chưa có rule DQ nào được sinh</h3>
          <p>Bấm nút <strong>Generate Quality Rules</strong> ở trên để tạo thêm rule.</p>
        </div>
      )}

      {/* Rules Stream for this Column */}
      {colRules.length > 0 && (
        <div className="rules-container">
          {colRules.map((rule) => {
            const isCrossColumn = rule.target_columns && rule.target_columns.length > 1;
            const otherCols = isCrossColumn
              ? rule.target_columns.filter((c) => c !== activeColObj?.name)
              : [];

            return (
              <div key={rule.id} className="rule-card-wrapper">
                {isCrossColumn && (
                  <div className="cross-col-indicator">
                    <span className="cc-icon">🔗</span>
                    <span>
                      Rule liên cột (Cross-column) cùng với:{' '}
                      {otherCols.map((c) => (
                        <button
                          key={c}
                          className="cc-link-btn"
                          onClick={() => setSelectedColumn(c)}
                          title={`Xem chi tiết cột ${c}`}
                        >
                          {c} ↗
                        </button>
                      ))}
                    </span>
                  </div>
                )}
                <RuleCard
                  rule={rule}
                  onReviewAction={onReviewAction}
                  onOpenEdit={onOpenEdit}
                />
              </div>
            );
          })}
        </div>
      )}

      {/* Bottom Footer Navigation */}
      <div className="cd-bottom-nav">
        <button
          className="btn-bottom-back"
          onClick={() => setSelectedColumn(null)}
        >
          <span>◀</span> Quay lại danh sách cột
        </button>

        {nextCol ? (
          <button
            className="btn-bottom-next"
            onClick={() => setSelectedColumn(nextCol.name)}
          >
            <span>Sang cột tiếp theo: <strong>{nextCol.displayName}</strong> ({nextCol.totalRules} rule)</span>
            <span>➔</span>
          </button>
        ) : (
          <div className="cd-all-reviewed-hint">
            <span>🎉 Bạn đã duyệt đến cột cuối cùng trong bảng!</span>
          </div>
        )}
      </div>
    </div>
  );
}
