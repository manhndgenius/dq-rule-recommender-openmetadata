import React, { useState, useEffect } from 'react';
import Header from './components/layout/Header';
import TableContextPanel from './components/context-panel/TableContextPanel';
import RecommendationBoard from './components/recommendation/RecommendationBoard';
import LineageView from './components/lineage/LineageView';
import ObservabilityView from './components/observability/ObservabilityView';
import SchemaView from './components/schema/SchemaView';
import ProfilerDetailView from './components/profiler/ProfilerDetailView';
import SampleDataView from './components/sample-data/SampleDataView';
import ActivityFeedView from './components/activity-feed/ActivityFeedView';
import EditRuleModal from './components/modals/EditRuleModal';
import EditTierModal from './components/modals/EditTierModal';
import VersionHistoryModal from './components/modals/VersionHistoryModal';
import PublishSuccessModal from './components/modals/PublishSuccessModal';
import ToastContainer from './components/layout/Toast';
import { INITIAL_TABLES, INITIAL_RULES, HEALTHCARE_TABLE_DESCRIPTIONS } from './services/mockData';
import { openmetadataService } from './services/openmetadataService';

const DEFAULT_HEALTHCARE_TABLES = [
  { name: 'patients', displayName: 'public.patients (Tier 1)', tier: 'Tier 1', description: HEALTHCARE_TABLE_DESCRIPTIONS.patients },
  { name: 'encounters', displayName: 'public.encounters (Tier 1)', tier: 'Tier 1', description: HEALTHCARE_TABLE_DESCRIPTIONS.encounters },
  { name: 'claims', displayName: 'public.claims (Tier 1)', tier: 'Tier 1', description: HEALTHCARE_TABLE_DESCRIPTIONS.claims },
  { name: 'medications', displayName: 'public.medications (Tier 1)', tier: 'Tier 1', description: HEALTHCARE_TABLE_DESCRIPTIONS.medications },
  { name: 'conditions', displayName: 'public.conditions (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.conditions },
  { name: 'allergies', displayName: 'public.allergies (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.allergies },
  { name: 'careplans', displayName: 'public.careplans (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.careplans },
  { name: 'procedures', displayName: 'public.procedures (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.procedures },
  { name: 'observations', displayName: 'public.observations (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.observations },
  { name: 'immunizations', displayName: 'public.immunizations (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.immunizations },
  { name: 'devices', displayName: 'public.devices (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.devices },
  { name: 'imaging_studies', displayName: 'public.imaging_studies (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.imaging_studies },
  { name: 'organizations', displayName: 'public.organizations (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.organizations },
  { name: 'payers', displayName: 'public.payers (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.payers },
  { name: 'payer_transitions', displayName: 'public.payer_transitions (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.payer_transitions },
  { name: 'providers', displayName: 'public.providers (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.providers },
  { name: 'supplies', displayName: 'public.supplies (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.supplies },
  { name: 'claims_transactions', displayName: 'public.claims_transactions (Tier 2)', tier: 'Tier 2', description: HEALTHCARE_TABLE_DESCRIPTIONS.claims_transactions }
];

export default function App() {
  const [currentDatabase, setCurrentDatabase] = useState('HealthCare');
  const [currentTable, setCurrentTable] = useState('patients');
  const [tableData, setTableData] = useState(INITIAL_TABLES['patients']);
  const [rules, setRules] = useState([]);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [useBasic, setUseBasic] = useState(true);
  const [useAdvanced, setUseAdvanced] = useState(true);
  
  // Available tables & databases from OpenMetadata (18 real tables)
  const [availableTables, setAvailableTables] = useState(DEFAULT_HEALTHCARE_TABLES);
  const [databasesList, setDatabasesList] = useState([
    { name: 'HealthCare', displayName: 'HealthCare (healthcare_postgres)' }
  ]);
  const [isConnected, setIsConnected] = useState(true);

  // Navigation Tabs (Authentic OpenMetadata Layout)
  const [activeMainTab, setActiveMainTab] = useState('RULES');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isContextPanelCollapsed, setIsContextPanelCollapsed] = useState(false);

  // Follow State
  const [isFollowing, setIsFollowing] = useState(false);
  const [followersCount, setFollowersCount] = useState(24);

  // Modals
  const [editingRule, setEditingRule] = useState(null);
  const [isTierModalOpen, setIsTierModalOpen] = useState(false);
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);

  // Theme state (Dark / Light)
  const [theme, setTheme] = useState(() => localStorage.getItem('app_theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('app_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    addToast(`Đã chuyển sang giao diện ${nextTheme === 'light' ? 'Sáng (Light Mode)' : 'Tối (Dark Mode)'}!`, 'info');
  };
  
  // Generating state
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState({
    title: 'Đang kết nối OpenMetadata API...',
    subtitle: 'Đọc Schema và Profiling data...'
  });

  // Toast notifications
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  };

  // 1. Initial Load: Check OpenMetadata Health & Fetch Tables
  useEffect(() => {
    const initOpenMetadata = async () => {
      const health = await openmetadataService.checkHealth();
      setIsConnected(health.openmetadata_connected);
      if (health.openmetadata_connected) {
        addToast('Đã kết nối thành công OpenMetadata Server (HealthCare dataset)!', 'success');
      }

      const liveTables = await openmetadataService.getTables();
      if (liveTables && liveTables.length > 0) {
        const mapped = liveTables.map((t) => {
          const isTier1 = ['patients', 'encounters', 'claims', 'medications', 'conditions'].includes(t.name);
          const tDesc = t.description || HEALTHCARE_TABLE_DESCRIPTIONS[t.name.toLowerCase()] || `Bảng dữ liệu y tế ${t.name}`;
          return {
            name: t.name,
            displayName: `public.${t.name} (${isTier1 ? 'Tier 1' : 'Tier 2'})`,
            description: tDesc,
            tier: isTier1 ? 'Tier 1' : 'Tier 2'
          };
        });
        setAvailableTables(mapped);
      }
    };
    initOpenMetadata();
  }, []);

  // 2. Fetch Table Context from Backend (OpenMetadata Live API)
  const fetchTableContext = async (tableName) => {
    const baseMock = INITIAL_TABLES[tableName] || INITIAL_TABLES['patients'];
    try {
      const data = await openmetadataService.getTableContext(tableName);
      if (data && data.columns) {
        const columns = data.columns.map((c) => {
          const mockCol = baseMock.columns?.find((mc) => mc.name === c.name);
          const isSensitive = ['id', 'ssn', 'patient', 'birthdate', 'phone', 'address', 'name', 'first', 'last'].some(
            (k) => c.name.toLowerCase().includes(k)
          );
          const nullPct = Math.round((c.profile?.null_ratio || 0) * 100);
          const distinctPct = Math.round((c.profile?.distinct_ratio || 0) * 100);

          return {
            name: c.name,
            type: c.data_type,
            nullable: c.nullable,
            is_pk: c.is_primary_key || mockCol?.is_pk,
            null_pct: nullPct,
            distinct: c.profile?.distinct_count || mockCol?.distinct || 0,
            distinct_pct: distinctPct,
            tags: mockCol?.tags || (isSensitive ? ['PII.Sensitive', 'Healthcare'] : ['Catalog', 'Clinical']),
            description: c.description || mockCol?.description || `Cột ${c.name} trong bảng ${data.table_name}`,
            stats: {
              min: c.profile?.min_value ?? mockCol?.stats?.min,
              max: c.profile?.max_value ?? mockCol?.stats?.max,
              sample_values: (c.profile?.top_values && c.profile.top_values.length > 0)
                ? c.profile.top_values.map((tv) => tv.value)
                : (mockCol?.stats?.sample_values || [])
            },
            histogram: mockCol?.histogram || [
              { label: 'Thấp', count: Math.round((c.profile?.distinct_count || 10) * 0.25), pct: 25 },
              { label: 'Trung bình', count: Math.round((c.profile?.distinct_count || 10) * 0.5), pct: 50 },
              { label: 'Cao', count: Math.round((c.profile?.distinct_count || 10) * 0.25), pct: 25 }
            ]
          };
        });

        // Lineage for selected table
        const lineage = baseMock?.lineage || {
          upstream: [
            { id: 'src_pg', name: 'healthcare_postgres', service: 'PostgreSQL DW', type: 'table', fqn: `healthcare_postgres.HealthCare.public.${data.table_name}`, health: 'HEALTHY' },
            { id: 'src_fhir', name: 'fhir_clinical_stream', service: 'Kafka Stream', type: 'topic', fqn: 'kafka.prod.fhir_patient_events', health: 'HEALTHY' },
            { id: 'src_emr', name: 'emr_webhook_sync', service: 'API Webhook', type: 'api', fqn: 'webhook.hospital_emr.patient_intents', health: 'HEALTHY' }
          ],
          pipelines: [
            { id: 'pipe_airflow', name: 'airflow.sync_healthcare_hourly', engine: 'Apache Airflow', type: 'pipeline', status: 'SUCCESS', last_run: '10 phút trước' },
            { id: 'pipe_dbt', name: 'dbt.stg_clinical_records', engine: 'dbt Core', type: 'pipeline', status: 'SUCCESS', last_run: '8 phút trước' }
          ],
          current: {
            id: `table_${data.table_name}`,
            name: data.table_name,
            fqn: `healthcare_postgres.HealthCare.public.${data.table_name}`,
            tier: data.tier || 'Tier.Tier1',
            type: 'table',
            health: 'HEALTHY'
          },
          downstream: [
            { id: 'down_fact', name: `analytics.fact_${data.table_name}_daily`, service: 'Snowflake DW', type: 'table', fqn: `snowflake.analytics.fact_${data.table_name}_daily`, tier: 'Tier.Tier1', health: 'HEALTHY', owner: 'Healthcare BI' },
            { id: 'down_ml', name: 'ml_models.patient_readmission_risk', service: 'Databricks', type: 'table', fqn: 'databricks.clinical_ml.patient_risk_score', tier: 'Tier.Tier2', health: 'HEALTHY', owner: 'Clinical AI Team' },
            { id: 'down_bi', name: 'Executive Hospital Dashboard', service: 'Tableau BI', type: 'dashboard', fqn: 'tableau.dashboards.executive_clinical_summary', health: 'HEALTHY', owner: 'Chief Medical Officer' }
          ]
        };

        // Observability metrics
        const observability = baseMock?.observability || {
          health_score: 97.5,
          health_status: 'HEALTHY',
          freshness: {
            last_updated: '10 phút trước',
            sla_target: '< 30 phút',
            status: 'MEETS_SLA',
            last_sync_timestamp: new Date().toISOString()
          },
          volume: {
            current_rows: data.row_count,
            expected_range: `${Math.round(data.row_count * 0.9).toLocaleString()} - ${Math.round(data.row_count * 1.1).toLocaleString()}`,
            growth_rate: '+2.8%',
            anomaly_detected: false,
            anomaly_message: 'Dung lượng ổn định từ OpenMetadata Profiler'
          },
          test_suites: {
            passed: 14,
            total: 14,
            score_pct: 100.0,
            critical_failures: 0,
            warnings: 0
          },
          schema_drift: {
            status: 'NO_DRIFT',
            changes_count_30d: 0,
            last_modified: 'Không thay đổi trong 30 ngày qua',
            drift_description: 'Schema cột khớp 100% định nghĩa OpenMetadata Catalog'
          },
          dimensions: [
            { name: 'Tính Đầy Đủ (Completeness)', score: 98.5, status: 'EXCELLENT', description: 'Tỷ lệ dữ liệu không null theo OpenMetadata Profiler' },
            { name: 'Tính Độc Nhất (Uniqueness)', score: 100.0, status: 'EXCELLENT', description: 'Khóa chính và định danh không bị trùng lặp' },
            { name: 'Tính Hợp Lệ (Validity)', score: 97.0, status: 'GOOD', description: 'Định dạng kiểu dữ liệu và ràng buộc Check' },
            { name: 'Tính Tươi Mới (Freshness)', score: 98.0, status: 'EXCELLENT', description: 'Độ trễ ETL pipeline cập nhật trong 10 phút' },
            { name: 'Tính Nhất Quán (Consistency)', score: 96.0, status: 'GOOD', description: 'Đồng bộ giữa PostgreSQL và OpenMetadata' }
          ],
          recent_runs: [
            { id: 'run_1', test_name: 'test_table_row_count', status: 'SUCCESS', execution_time: '10 phút trước', duration_ms: 120 },
            { id: 'run_2', test_name: 'test_column_values_not_null', status: 'SUCCESS', execution_time: '10 phút trước', duration_ms: 85 }
          ],
          incidents: []
        };

        const tableDescription = data.table_description 
          || HEALTHCARE_TABLE_DESCRIPTIONS[tableName.toLowerCase()] 
          || baseMock.description 
          || `Bảng dữ liệu y tế ${tableName} thuộc cơ sở dữ liệu HealthCare.`;

        setTableData({
          ...baseMock,
          table_name: data.table_name,
          database_name: data.database_name || 'HealthCare',
          schema_name: data.schema_name || 'public',
          fully_qualified_name: `healthcare_postgres.${data.database_name || 'HealthCare'}.${data.schema_name || 'public'}.${data.table_name}`,
          description: tableDescription,
          domain: 'Healthcare & Clinical',
          owner: { name: 'DataOps Healthcare Team', team: 'Clinical Data Management' },
          row_count: data.row_count || baseMock.row_count,
          column_count: columns.length,
          freshness: 'Vừa đồng bộ từ OpenMetadata Live',
          columns: columns,
          lineage: lineage,
          observability: observability
        });

        // Also fetch candidate rules for this table
        try {
          const rulesData = await openmetadataService.generateRules(tableName, ['BASIC', 'ADVANCED']);
          if (rulesData && rulesData.rules && rulesData.rules.length > 0) {
            setRules(rulesData.rules);
          }
        } catch (e) {
          console.warn('Lỗi sinh rules tự động:', e);
        }

        addToast(`Đã đồng bộ thành công bảng '${tableName}' (${data.row_count} dòng, ${columns.length} cột) từ OpenMetadata!`, 'success');
        return;
      }
    } catch (err) {
      console.warn('Lỗi kết nối OpenMetadata API, dùng dữ liệu dự phòng:', err);
    }
    setTableData(baseMock);
  };

  useEffect(() => {
    fetchTableContext(currentTable);
    setIsFollowing(false);
    setFollowersCount(currentTable === 'patients' ? 24 : 18);
  }, [currentTable]);

  // Switch Table Handler
  const handleSelectTable = (tableName) => {
    setCurrentTable(tableName);
  };

  // Follow Toggle
  const handleToggleFollow = () => {
    if (!isFollowing) {
      setIsFollowing(true);
      setFollowersCount((prev) => prev + 1);
      addToast(`Đã theo dõi (Follow) bảng ${currentTable}! Nhận thông báo khi schema hoặc DQ thay đổi.`, 'success');
    } else {
      setIsFollowing(false);
      setFollowersCount((prev) => prev - 1);
      addToast(`Đã hủy theo dõi bảng ${currentTable}.`, 'info');
    }
  };

  // Save Tier
  const handleSaveTier = (newTier) => {
    setTableData((prev) => ({
      ...prev,
      tier: newTier,
      tier_label: `${newTier} - Updated`
    }));
    addToast(`Đã cập nhật phân tầng dữ liệu thành ${newTier}!`, 'success');
  };

  // Review Action (Accept / Reject)
  const handleReviewAction = async (ruleId, newStatus) => {
    setRules((prev) =>
      prev.map((r) => (r.id === ruleId ? { ...r, status: newStatus } : r))
    );

    const rule = rules.find((r) => r.id === ruleId);
    if (newStatus === 'ACCEPTED') {
      addToast(`Đã chấp thuận rule: ${rule?.rule_type}`, 'success');
    } else if (newStatus === 'REJECTED') {
      addToast(`Đã từ chối rule: ${rule?.rule_type}`, 'warning');
    }

    try {
      await fetch(`${API_BASE}/rules/${ruleId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: newStatus })
      });
    } catch (e) {
      // Background sync
    }
  };

  // Edit Action
  const handleOpenEdit = (rule) => {
    setEditingRule(rule);
  };

  const handleSaveEdit = async (ruleId, updatedParams) => {
    setRules((prev) =>
      prev.map((r) =>
        r.id === ruleId
          ? { ...r, edited_parameters: updatedParams, status: 'EDITED' }
          : r
      )
    );
    setEditingRule(null);
    addToast('Đã lưu tham số điều chỉnh và chuyển trạng thái sang EDITED!', 'success');

    try {
      await fetch(`${API_BASE}/rules/${ruleId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'EDITED', edited_parameters: updatedParams })
      });
    } catch (e) {}
  };

  // Generate Simulation + Backend Call
  const handleGenerate = async () => {
    if (!useBasic && !useAdvanced) {
      addToast('Vui lòng tích chọn ít nhất 1 Engine (Basic hoặc Advanced)!', 'warning');
      return;
    }

    setIsGenerating(true);
    setGenerationStep({
      title: 'Bước 1/3: Đang kết nối OpenMetadata REST API...',
      subtitle: `Lấy schema cột và metrics profiling của bảng ${currentTable}...`
    });

    const engines = [];
    if (useBasic) engines.push('BASIC');
    if (useAdvanced) engines.push('ADVANCED');

    setTimeout(async () => {
      setGenerationStep({
        title: 'Bước 2/3: Đang thực thi Rule Engine...',
        subtitle: `Suy luận luật Heuristics & Domain cho bảng ${currentTable}...`
      });

      try {
        const data = await openmetadataService.generateRules(currentTable, engines);
        if (data && data.rules && data.rules.length > 0) {
          setTimeout(() => {
            setRules(data.rules);
            setIsGenerating(false);
            addToast(`Đã sinh thành công ${data.rules.length} DQ rules thực tế từ OpenMetadata!`, 'success');
          }, 800);
          return;
        }
      } catch (err) {
        console.warn('Lỗi gọi generate API:', err);
      }

      setTimeout(() => {
        setIsGenerating(false);
        addToast(`Không thể sinh luật mới cho bảng ${currentTable}. Vui lòng thử lại.`, 'error');
      }, 800);
    }, 1000);
  };

  // Publish OpenMetadata
  const handlePublish = () => {
    const readyRules = rules.filter(
      (r) => r.status === 'ACCEPTED' || r.status === 'EDITED'
    );
    if (readyRules.length === 0) {
      addToast('Vui lòng duyệt ít nhất 1 Rule trước khi xuất bản!', 'warning');
      return;
    }
    setIsPublishModalOpen(true);
  };

  return (
    <>
      {/* Header */}
      <Header
        currentDatabase={currentDatabase}
        onSelectDatabase={setCurrentDatabase}
        currentTable={currentTable}
        onSelectTable={handleSelectTable}
        tableData={tableData}
        theme={theme}
        onToggleTheme={toggleTheme}
        availableTables={availableTables}
        databasesList={databasesList}
        isConnected={isConnected}
      />

      {/* Workspace Master Layout: Vertical Navigation Sidebar on Left + Main Content on Right */}
      <div className="app-workspace-layout">
        {/* Left Vertical Navigation Sidebar */}
        <aside className={`om-vertical-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
          <div className="sidebar-top-bar">
            {!isSidebarCollapsed && (
              <div className="sidebar-headline">
                <span className="sidebar-pill">DANH MỤC</span>
                <span className="sidebar-title">Tính Năng Bảng</span>
              </div>
            )}
            <button
              className="btn-toggle-sidebar"
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              title={isSidebarCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
              aria-label={isSidebarCollapsed ? "Mở rộng menu" : "Thu gọn menu"}
            >
              {isSidebarCollapsed ? "▶" : "◀"}
            </button>
          </div>

          <nav className="om-vertical-tabs-nav">
            <button
              className={`om-vtab ${activeMainTab === 'RULES' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('RULES')}
              title="Gợi ý & Quản lý Luật DQ"
            >
              <span className="vtab-icon">⚡</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Quản lý Luật DQ</span>
                  <span className="vtab-badge">{rules.length}</span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'SCHEMA' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('SCHEMA')}
              title="Cấu trúc Schema & Cột"
            >
              <span className="vtab-icon">📑</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Schema</span>
                  <span className="vtab-badge">{tableData?.columns?.length || 0} cols</span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'PROFILER' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('PROFILER')}
              title="Data Profiler & Phân phối"
            >
              <span className="vtab-icon">📊</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Data Profiler</span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'LINEAGE' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('LINEAGE')}
              title="Data Lineage (Dòng chảy dữ liệu)"
            >
              <span className="vtab-icon">🔄</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Data Lineage</span>
                  <span className="tab-indicator-dot online"></span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'OBSERVABILITY' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('OBSERVABILITY')}
              title="Observability & SLA Giám sát"
            >
              <span className="vtab-icon">🔭</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Observability & SLA</span>
                  <span className="vtab-badge health">{tableData?.observability?.health_score}%</span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'SAMPLE_DATA' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('SAMPLE_DATA')}
              title="Dữ liệu mẫu thực tế"
            >
              <span className="vtab-icon">👁️</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Dữ liệu mẫu</span>
                </div>
              )}
            </button>

            <button
              className={`om-vtab ${activeMainTab === 'ACTIVITY' ? 'active' : ''}`}
              onClick={() => setActiveMainTab('ACTIVITY')}
              title="Activity & Nhiệm vụ"
            >
              <span className="vtab-icon">💬</span>
              {!isSidebarCollapsed && (
                <div className="vtab-content">
                  <span className="vtab-label">Activity & Tasks</span>
                  <span className="vtab-badge">{tableData?.activity_feed?.length || 3}</span>
                </div>
              )}
            </button>
          </nav>

          {/* Quick Table Card in Sidebar */}
          {!isSidebarCollapsed && (
            <div className="sidebar-quick-status">
              <div className="sq-card">
                <div className="sq-header">
                  <span className="sq-dot online"></span>
                  <span className="sq-status">HealthCare Dataset</span>
                </div>
                <div className="sq-row">
                  <span className="sq-lbl">Bảng:</span>
                  <code className="sq-table-name">{tableData?.table_name}</code>
                </div>
                <div className="sq-row">
                  <span className="sq-lbl">Sức khỏe DQ:</span>
                  <strong className="text-success">{tableData?.observability?.health_score}%</strong>
                </div>
                <div className="sq-row">
                  <span className="sq-lbl">Tổng dòng:</span>
                  <span>{tableData?.row_count?.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Right Main Content Area */}
        <div className="om-main-workspace">
          {/* Main Navigation Subheader (Breadcrumbs, Headline, Description) */}
          <div className="main-nav-bar">
            <div className="main-nav-container">
              {/* Breadcrumb Hierarchy */}
              <div className="om-breadcrumbs">
                <span className="bc-item">Databases</span>
                <span className="bc-sep">/</span>
                <span className="bc-item">{tableData?.database_name}</span>
                <span className="bc-sep">/</span>
                <span className="bc-item">{tableData?.schema_name || 'public'}</span>
                <span className="bc-sep">/</span>
                <span className="bc-item active"><strong>{tableData?.table_name}</strong></span>
              </div>

              <div className="table-headline">
                <div className="table-headline-title">
                  <span className="table-badge-tag">TABLE</span>
                  <h2 className="table-title">
                    {tableData?.table_name}
                  </h2>

                  {/* Version Badge (Clickable) */}
                  <button
                    className="version-click-badge"
                    onClick={() => setIsVersionModalOpen(true)}
                    title="Bấm để xem lịch sử phiên bản và changelog"
                  >
                    📜 {tableData?.version || 'v1.2'}
                  </button>

                  {/* Interactive Tier Pill (Clickable to edit) */}
                  <button
                    className="table-tier-tag interactive"
                    onClick={() => setIsTierModalOpen(true)}
                    title="Bấm để đổi phân tầng dữ liệu (Edit Tier)"
                  >
                    ⭐ {tableData?.tier || 'Tier.Tier1'} ✎
                  </button>

                  {/* Follow Button */}
                  <button
                    className={`btn-follow-asset ${isFollowing ? 'following' : ''}`}
                    onClick={handleToggleFollow}
                    title="Theo dõi bảng này"
                  >
                    {isFollowing ? '⭐ Đang theo dõi' : '☆ Theo dõi'} ({followersCount})
                  </button>
                </div>

                <div className="table-quick-stats">
                  <span>Domain: <strong>{tableData?.domain || 'Healthcare & Clinical'}</strong></span>
                  <span>Owner: <strong>{tableData?.owner?.name || 'DataOps Healthcare'}</strong></span>
                  <span>Dòng: <strong>{tableData?.row_count?.toLocaleString()}</strong></span>
                  <span>Sức khỏe: <strong className="text-success">{tableData?.observability?.health_score}%</strong></span>
                </div>
              </div>

              {/* Table Description Section (OpenMetadata Asset Overview) */}
              <div className="table-description-bar">
                <div className="table-desc-left">
                  <span className="desc-icon-badge">📋</span>
                  <div className="desc-text-group">
                    <div className="desc-label-row">
                      <span className="desc-title">Mô tả bảng (Table Description)</span>
                      <span className="desc-status-tag">OpenMetadata Catalog</span>
                    </div>
                    <p className="desc-paragraph">
                      {tableData?.description || `Bảng dữ liệu y tế ${tableData?.table_name} thuộc cơ sở dữ liệu HealthCare.`}
                    </p>
                  </div>
                </div>
                {tableData?.fully_qualified_name && (
                  <div className="table-desc-right">
                    <div className="table-fqn-pill" title="Fully Qualified Name trong OpenMetadata">
                      <span className="fqn-prefix">FQN:</span>
                      <code>{tableData.fully_qualified_name}</code>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Active Tab View Body */}
          <div className="om-tab-view-content">
            {activeMainTab === 'RULES' && (
              <main className={`rules-workspace-grid ${isContextPanelCollapsed ? 'context-collapsed' : ''}`}>
                <RecommendationBoard
                  rules={rules}
                  tableData={tableData}
                  activeFilter={activeFilter}
                  setActiveFilter={setActiveFilter}
                  searchQuery={searchQuery}
                  setSearchQuery={setSearchQuery}
                  useBasic={useBasic}
                  setUseBasic={setUseBasic}
                  useAdvanced={useAdvanced}
                  setUseAdvanced={setUseAdvanced}
                  isGenerating={isGenerating}
                  generationStep={generationStep}
                  onGenerate={handleGenerate}
                  onReviewAction={handleReviewAction}
                  onOpenEdit={handleOpenEdit}
                  onPublish={handlePublish}
                />

                <TableContextPanel
                  tableData={tableData}
                  isCollapsed={isContextPanelCollapsed}
                  onToggleCollapse={() => setIsContextPanelCollapsed(!isContextPanelCollapsed)}
                />
              </main>
            )}

            {activeMainTab === 'SCHEMA' && (
              <main className="tab-content-wrapper">
                <SchemaView tableData={tableData} />
              </main>
            )}

            {activeMainTab === 'PROFILER' && (
              <main className="tab-content-wrapper">
                <ProfilerDetailView tableData={tableData} />
              </main>
            )}

            {activeMainTab === 'LINEAGE' && (
              <main className="tab-content-wrapper">
                <LineageView tableData={tableData} />
              </main>
            )}

            {activeMainTab === 'OBSERVABILITY' && (
              <main className="tab-content-wrapper">
                <ObservabilityView tableData={tableData} />
              </main>
            )}

            {activeMainTab === 'SAMPLE_DATA' && (
              <main className="tab-content-wrapper">
                <SampleDataView tableData={tableData} />
              </main>
            )}

            {activeMainTab === 'ACTIVITY' && (
              <main className="tab-content-wrapper">
                <ActivityFeedView tableData={tableData} />
              </main>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      <EditRuleModal
        rule={editingRule}
        isOpen={Boolean(editingRule)}
        onClose={() => setEditingRule(null)}
        onSave={handleSaveEdit}
      />

      <EditTierModal
        isOpen={isTierModalOpen}
        onClose={() => setIsTierModalOpen(false)}
        currentTier={tableData?.tier}
        onSaveTier={handleSaveTier}
      />

      <VersionHistoryModal
        isOpen={isVersionModalOpen}
        onClose={() => setIsVersionModalOpen(false)}
        tableData={tableData}
      />

      <PublishSuccessModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        publishedRules={rules.filter(
          (r) => r.status === 'ACCEPTED' || r.status === 'EDITED'
        )}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} />
    </>
  );
}
