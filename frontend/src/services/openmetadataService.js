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
  async getTables(schemaFqn = 'healthcare_postgres.HealthCare.public') {
    try {
      const res = await fetch(`${API_BASE}/catalog/tables?schemaFqn=${encodeURIComponent(schemaFqn)}`);
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
  async getTableDetail(tableIdOrName) {
    try {
      const res = await fetch(`${API_BASE}/catalog/tables/${encodeURIComponent(tableIdOrName)}`);
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
  async getTableContext(tableName) {
    try {
      const res = await fetch(`${API_BASE}/context/${encodeURIComponent(tableName)}`);
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
  }
};
