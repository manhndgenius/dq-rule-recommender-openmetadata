/**
 * OpenMetadata Integration Service (Frontend)
 * Tuân thủ tài liệu D:\VSF\OPENMETADATA_WEB_INTEGRATION.md
 * Kết nối qua Backend API trung gian (không lộ token trên client)
 */

const API_BASE = 'http://localhost:8000/api/v1';

export const openmetadataService = {
  /**
   * Kiểm tra trạng thái Backend và OpenMetadata API
   */
  async checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) return await res.json();
    } catch (err) {
      console.warn('Lỗi kết nối Backend Health:', err);
    }
    return { status: 'offline', openmetadata_connected: false };
  },

  /**
   * Lấy danh sách Services
   */
  async getServices() {
    try {
      const res = await fetch(`${API_BASE}/catalog/services`);
      if (res.ok) {
        const data = await res.json();
        return data.services || [];
      }
    } catch (err) {
      console.warn('Lỗi lấy Services:', err);
    }
    return [{ name: 'healthcare_postgres', fullyQualifiedName: 'healthcare_postgres', serviceType: 'Postgres' }];
  },

  /**
   * Lấy danh sách Databases
   */
  async getDatabases(service = 'healthcare_postgres') {
    try {
      const res = await fetch(`${API_BASE}/catalog/databases?service=${encodeURIComponent(service)}`);
      if (res.ok) {
        const data = await res.json();
        return data.databases || [];
      }
    } catch (err) {
      console.warn('Lỗi lấy Databases:', err);
    }
    return [{ name: 'HealthCare', fullyQualifiedName: 'healthcare_postgres.HealthCare' }];
  },

  /**
   * Lấy danh sách Schemas
   */
  async getSchemas(databaseFqn = 'healthcare_postgres.HealthCare') {
    try {
      const res = await fetch(`${API_BASE}/catalog/schemas?databaseFqn=${encodeURIComponent(databaseFqn)}`);
      if (res.ok) {
        const data = await res.json();
        return data.schemas || [];
      }
    } catch (err) {
      console.warn('Lỗi lấy Schemas:', err);
    }
    return [{ name: 'public', fullyQualifiedName: 'healthcare_postgres.HealthCare.public' }];
  },

  /**
   * Lấy danh sách 18 Tables từ OpenMetadata
   */
  async getTables(schemaFqn = 'healthcare_postgres.HealthCare.public', refresh = false) {
    try {
      const res = await fetch(`${API_BASE}/catalog/tables?schemaFqn=${encodeURIComponent(schemaFqn)}${refresh ? '&refresh=true' : ''}`);
      if (res.ok) {
        const data = await res.json();
        return data.tables || [];
      }
    } catch (err) {
      console.warn('Lỗi lấy danh sách Tables từ OpenMetadata:', err);
    }
    return [];
  },

  /**
   * Lấy chi tiết Table, Columns và Profiling đầy đủ
   */
  async getTableDetail(tableIdOrName, refresh = false) {
    try {
      const res = await fetch(`${API_BASE}/catalog/tables/${encodeURIComponent(tableIdOrName)}${refresh ? '?refresh=true' : ''}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi lấy chi tiết bảng ${tableIdOrName}:`, err);
    }
    return null;
  },

  /**
   * Lấy TableContext chuẩn hóa cho Rule Recommender & UI Tabs
   */
  async getTableContext(tableName, refresh = false) {
    try {
      const res = await fetch(`${API_BASE}/context/${encodeURIComponent(tableName)}${refresh ? '?refresh=true' : ''}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi lấy TableContext cho bảng ${tableName}:`, err);
    }
    return null;
  },

  /**
   * Sinh candidate rules bằng BasicRuleEngine & Advanced Rules
   */
  async generateRules(tableName, engines = ['BASIC', 'ADVANCED']) {
    try {
      const res = await fetch(`${API_BASE}/recommendations/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          table_name: tableName,
          engines: engines
        })
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi sinh candidate rules cho bảng ${tableName}:`, err);
    }
    return null;
  },

  /**
   * Sinh Advanced Rules (LLM) với SQL violation queries
   * Pipeline: Router → Generator (LLM) → SQL Mapper → SQL
   * Trả về rules kèm sql, violation_predicate
   *
   * @param {string} tableName - Tên bảng cần sinh rules
   * @param {Array} columns - Danh sách columns với metadata (name, data_type, nullable, description, profiling)
   * @param {number} minConfidence - Ngưỡng confidence tối thiểu (default: 0.6)
   * @returns {Object} { table_name, candidates, rules, total_rules_generated, total_sql_mapped, total_sql_failed }
   */
  async generateAdvancedRules(tableName, columns, minConfidence = 0.6) {
    try {
      const res = await fetch(`${API_BASE}/advanced-rules/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          table_name: tableName,
          columns: columns,
          min_confidence: minConfidence
        })
      });
      if (res.ok) {
        return await res.json();
      }
      // Log error response
      const errorText = await res.text();
      console.warn(`Lỗi sinh Advanced Rules (${res.status}):`, errorText);
    } catch (err) {
      console.warn(`Lỗi kết nối sinh Advanced Rules cho bảng ${tableName}:`, err);
    }
    return null;
  },

  /**
   * Review hành động (Accept, Reject, Edit)
   */
  async reviewRule(ruleId, action, editedParameters = null) {
    try {
      const res = await fetch(`${API_BASE}/rules/${ruleId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          edited_parameters: editedParameters
        })
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi gửi review cho rule ${ruleId}:`, err);
    }
    return null;
  },

  /**
   * Cập nhật phân tầng Tier (Tier 1-5 hoặc null) của bảng lên OpenMetadata
   */
  async updateTableTier(tableName, tier) {
    try {
      const res = await fetch(`${API_BASE}/tables/${encodeURIComponent(tableName)}/tier`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: tier })
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi cập nhật tier cho bảng ${tableName}:`, err);
    }
    return { success: false, message: 'Lỗi kết nối khi cập nhật Tier' };
  },

  /**
   * Xuất bản (Publish) các Rule đã duyệt lên OpenMetadata Test Cases thực tế
   * Đồng thời đồng bộ Tier của bảng lên OpenMetadata
   */
  async publishRules(tableName, rulesOrIds = null, tier = null) {
    try {
      const payload = { table_name: tableName };
      if (tier) {
        payload.tier = tier;
      }
      if (Array.isArray(rulesOrIds)) {
        if (rulesOrIds.length > 0 && typeof rulesOrIds[0] === 'object') {
          payload.rules = rulesOrIds;
        } else {
          payload.rule_ids = rulesOrIds;
        }
      }
      const res = await fetch(`${API_BASE}/rules/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn(`Lỗi xuất bản rules lên OpenMetadata cho bảng ${tableName}:`, err);
    }
    return { success: false, message: 'Lỗi kết nối tới máy chủ OpenMetadata' };
  },

  /**
   * Lấy báo cáo Benchmark Evaluation định lượng
   */
  async getEvaluationSummary() {
    try {
      const res = await fetch(`${API_BASE}/evaluation/summary`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('Lỗi lấy báo cáo Evaluation:', err);
    }
    return null;
  }
};
