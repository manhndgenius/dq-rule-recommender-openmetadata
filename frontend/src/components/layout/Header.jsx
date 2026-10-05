import React from 'react';

export default function Header({
  currentDatabase,
  onSelectDatabase,
  currentTable,
  onSelectTable,
  tableData,
  theme,
  onToggleTheme,
  availableTables = [],
  databasesList = [],
  isConnected = true
}) {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-logo-mark" title="Data Quality & Observability Platform">
          <svg width="34" height="34" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#38BDF8" />
                <stop offset="100%" stopColor="#7C3AED" />
              </linearGradient>
            </defs>
            <rect width="40" height="40" rx="10" fill="url(#logoGrad)" />
            {/* Hexagonal node grid / data pulse */}
            <path d="M20 9L29.5 14.5V25.5L20 31L10.5 25.5V14.5L20 9Z" stroke="#FFFFFF" strokeWidth="2" strokeLinejoin="round" fill="rgba(255, 255, 255, 0.12)" />
            <circle cx="20" cy="20" r="3.5" fill="#FFFFFF" />
            <line x1="20" y1="9" x2="20" y2="16.5" stroke="#FFFFFF" strokeWidth="1.5" strokeDasharray="1.5 1.5" />
            <line x1="29.5" y1="25.5" x2="23" y2="21.5" stroke="#FFFFFF" strokeWidth="1.5" strokeDasharray="1.5 1.5" />
            <line x1="10.5" y1="25.5" x2="17" y2="21.5" stroke="#FFFFFF" strokeWidth="1.5" strokeDasharray="1.5 1.5" />
          </svg>
        </div>
        <div className="brand-text">
          <div className="brand-title-wrap">
            <h1 className="brand-title">DQ Recommender</h1>
            <span className="brand-version-badge">v1.0</span>
          </div>
          <div className="brand-subtitle-line">
            <span className="brand-badge">Data Observability • OpenMetadata Live</span>
          </div>
        </div>
      </div>

      <div className="header-controls">
        <div className="selector-group">
          <label htmlFor="db-select">Database:</label>
          <select 
            id="db-select" 
            className="custom-select"
            value={currentDatabase}
            onChange={(e) => onSelectDatabase(e.target.value)}
          >
            {databasesList && databasesList.length > 0 ? (
              databasesList.map((db) => (
                <option key={db.name || db} value={db.name || db}>
                  {db.displayName || db.name || db}
                </option>
              ))
            ) : (
              <option value="HealthCare">HealthCare (healthcare_postgres)</option>
            )}
          </select>
        </div>

        <div className="selector-group">
          <label htmlFor="table-select">Table:</label>
          <select 
            id="table-select" 
            className="custom-select table-dropdown-select"
            value={currentTable}
            onChange={(e) => onSelectTable(e.target.value)}
          >
            {availableTables && availableTables.length > 0 ? (
              availableTables.map((t) => (
                <option key={t.name} value={t.name} title={t.description || `Bảng dữ liệu y tế ${t.name}`}>
                  {t.displayName || `public.${t.name}`}
                </option>
              ))
            ) : (
              <>
                <option value="patients" title="Bảng hồ sơ định danh và thông tin lâm sàng bệnh nhân">public.patients</option>
                <option value="encounters" title="Bảng lịch sử các đợt khám bệnh và điều trị">public.encounters</option>
                <option value="claims" title="Bảng hồ sơ yêu cầu chi trả bảo hiểm">public.claims</option>
              </>
            )}
          </select>
        </div>

        {/* Current Table Tier Pill */}
        {tableData?.tier ? (
          <div className="header-tier-pill" title={tableData.tier_label || tableData.tier}>
            <span className="tier-star">⭐</span>
            <span className="tier-text">{tableData.tier}</span>
          </div>
        ) : (
          <div className="header-tier-pill muted" style={{ opacity: 0.6 }} title="Chưa phân hạng trên OpenMetadata">
            <span className="tier-text">Tier: --</span>
          </div>
        )}

        {/* Link to OpenMetadata Live Server */}
        <a
          href="https://c3-app-009.duckdns.org"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-om-sandbox"
          title="Mở OpenMetadata Server thực tế (c3-app-009.duckdns.org)"
        >
          <span>🌐 OpenMetadata Live</span>
        </a>

        {/* Theme Toggle Button */}
        <button
          className="btn-theme-toggle"
          onClick={onToggleTheme}
          title="Chuyển đổi giao diện Sáng / Tối"
        >
          <span>{theme === 'light' ? '☀️ Sáng' : '🌙 Tối'}</span>
        </button>

        <div className="integration-status">
          <span className="status-indicator online" title="Database Connected">
            <span className="dot"></span> DB Online
          </span>
          <span className={`status-indicator ${isConnected ? 'online' : 'offline'}`} title={isConnected ? 'OpenMetadata Live Connected (duckdns)' : 'OpenMetadata Disconnected'}>
            <span className="dot"></span> {isConnected ? 'OM Live (HealthCare)' : 'OM Offline'}
          </span>
        </div>
      </div>
    </header>
  );
}
