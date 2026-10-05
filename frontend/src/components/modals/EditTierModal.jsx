import React, { useState, useEffect } from 'react';

export default function EditTierModal({ isOpen, onClose, currentTier, onSaveTier }) {
  const [selectedTier, setSelectedTier] = useState(currentTier || null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSelectedTier(currentTier || null);
      setIsSaving(false);
    }
  }, [isOpen, currentTier]);

  if (!isOpen) return null;

  const tiers = [
    { id: 'Tier.Tier1', label: 'Tier 1 - Mission Critical', desc: 'Dữ liệu trọng yếu tài chính, thanh toán, doanh thu toàn công ty', color: '#8B5CF6' },
    { id: 'Tier.Tier2', label: 'Tier 2 - High Importance', desc: 'Dữ liệu phân tích khách hàng, báo cáo hoạt động tuần', color: '#3B82F6' },
    { id: 'Tier.Tier3', label: 'Tier 3 - Medium Importance', desc: 'Dữ liệu nội bộ bộ phận, bảng phân loại chuẩn hóa', color: '#10B981' },
    { id: 'Tier.Tier4', label: 'Tier 4 - Low Importance', desc: 'Dữ liệu phụ, phân tích ad-hoc thử nghiệm', color: '#F59E0B' },
    { id: 'Tier.Tier5', label: 'Tier 5 - Non-Critical / Scratch', desc: 'Dữ liệu tạm, staging hoặc thử nghiệm ngắn hạn', color: '#6B7280' },
    { id: null, label: 'Chưa phân tầng (Unassigned / None)', desc: 'Xóa nhãn phân tầng Tier khỏi bảng trên OpenMetadata', color: '#9CA3AF' }
  ];

  const handleSave = async () => {
    setIsSaving(true);
    await onSaveTier(selectedTier);
    setIsSaving(false);
    onClose();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-dialog">
        <div className="modal-header">
          <h3 className="modal-title">⭐ Quản trị Phân tầng dữ liệu (Edit Data Tier)</h3>
          <button className="btn-close" onClick={onClose} disabled={isSaving}>✕</button>
        </div>
        <div className="modal-body">
          <p className="modal-description">
            Chọn cấp độ Tier cho bảng để đồng bộ trực tiếp lên <strong>OpenMetadata Live</strong>:
          </p>

          <div className="tier-options-list">
            {tiers.map((t) => (
              <label
                key={t.id ?? 'unassigned'}
                className={`tier-option-card ${selectedTier === t.id ? 'selected' : ''}`}
                onClick={() => setSelectedTier(t.id)}
              >
                <input
                  type="radio"
                  name="tier-select"
                  checked={selectedTier === t.id}
                  onChange={() => setSelectedTier(t.id)}
                  style={{ display: 'none' }}
                />
                <div className="tier-opt-top">
                  <span className="tier-pill-badge" style={{ borderColor: t.color, color: t.color }}>
                    {t.id ? `⭐ ${t.id}` : '⚪ Tier: --'}
                  </span>
                  <span className="tier-opt-title">{t.label}</span>
                </div>
                <p className="tier-opt-desc">{t.desc}</p>
              </label>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isSaving}>Hủy</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Đang lưu lên OpenMetadata...' : 'Lưu & Đẩy sang OpenMetadata'}
          </button>
        </div>
      </div>
    </div>
  );
}
