import React, { useState } from 'react';

export default function ActivityFeedView({ tableData }) {
  const [feedItems, setFeedItems] = useState(tableData?.activity_feed || []);
  const [newComment, setNewComment] = useState('');
  const [activeFilter, setActiveFilter] = useState('ALL');

  const handlePostComment = (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    const newItem = {
      id: `act-${Date.now()}`,
      type: 'conversation',
      author: 'You (Data Engineer)',
      avatar: '👨‍🚀',
      time: 'Vừa xong',
      content: newComment
    };

    setFeedItems([newItem, ...feedItems]);
    setNewComment('');
  };

  const filteredItems = feedItems.filter((item) => {
    if (activeFilter === 'ALL') return true;
    if (activeFilter === 'TASK') return item.type === 'task';
    if (activeFilter === 'CONVERSATION') return item.type === 'conversation';
    if (activeFilter === 'ANNOUNCEMENT') return item.type === 'announcement';
    return true;
  });

  return (
    <div className="activity-feed-container">
      {/* Header */}
      <div className="feed-header">
        <div className="feed-title-group">
          <span className="feed-icon">💬</span>
          <div>
            <h3 className="feed-heading">Activity Feed & Tasks Collaboration</h3>
            <p className="feed-subheading">
              Kênh trao đổi, thảo luận, giao việc (Tasks) và thông báo thay đổi (Changelog) xoay quanh bảng <code>{tableData.table_name}</code>
            </p>
          </div>
        </div>

        <div className="feed-filter-chips">
          <button
            className={`f-chip ${activeFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ALL')}
          >
            Tất cả
          </button>
          <button
            className={`f-chip ${activeFilter === 'TASK' ? 'active' : ''}`}
            onClick={() => setActiveFilter('TASK')}
          >
            📋 Tasks ({feedItems.filter(f => f.type === 'task').length})
          </button>
          <button
            className={`f-chip ${activeFilter === 'CONVERSATION' ? 'active' : ''}`}
            onClick={() => setActiveFilter('CONVERSATION')}
          >
            💬 Thảo luận
          </button>
          <button
            className={`f-chip ${activeFilter === 'ANNOUNCEMENT' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ANNOUNCEMENT')}
          >
            📢 Thông báo
          </button>
        </div>
      </div>

      {/* Main Grid: Left Post & Stream, Right Tasks Quick Panel */}
      <div className="feed-grid-layout">
        <div className="feed-main-stream">
          {/* Post Box */}
          <form className="feed-post-card" onSubmit={handlePostComment}>
            <div className="post-input-wrap">
              <span className="post-avatar">👨‍🚀</span>
              <textarea
                className="post-textarea"
                rows="2"
                placeholder="Viết ghi chú, tag đồng nghiệp (@username) hoặc liên kết cột (#column)..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
              ></textarea>
            </div>
            <div className="post-actions-bar">
              <span className="post-hint">Hỗ trợ Markdown • Tự động gửi thông báo Slack</span>
              <button type="submit" className="btn btn-primary btn-sm" disabled={!newComment.trim()}>
                Gửi bình luận
              </button>
            </div>
          </form>

          {/* Feed List */}
          <div className="feed-items-list">
            {filteredItems.map((item) => (
              <div key={item.id} className={`feed-item-card ${item.type}`}>
                <div className="feed-item-avatar">{item.avatar}</div>
                <div className="feed-item-content">
                  <div className="feed-item-meta">
                    <strong className="item-author">{item.author}</strong>
                    <span className="item-time">{item.time}</span>
                    <span className={`item-type-badge ${item.type}`}>
                      {item.type.toUpperCase()}
                    </span>
                  </div>

                  {item.title && <h5 className="feed-item-title">{item.title}</h5>}
                  <p className="feed-item-body">{item.content}</p>

                  {item.type === 'task' && (
                    <div className="task-action-box">
                      <span>Phụ trách: <strong>{item.assignee}</strong></span>
                      <span className="task-status-open">🟢 Trạng thái: {item.status}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Sidebar: OpenMetadata Task Summary & Guidelines */}
        <div className="feed-sidebar">
          <div className="sidebar-card">
            <h4>📋 Nhiệm vụ quản trị mở (Open Tasks)</h4>
            <div className="task-quick-list">
              <div className="task-item">
                <span className="task-dot"></span>
                <div>
                  <strong>Bổ sung mô tả cột delivered_at</strong>
                  <span className="task-sub">Giao cho DataOps • Hạn: Ngày mai</span>
                </div>
              </div>
              <div className="task-item">
                <span className="task-dot"></span>
                <div>
                  <strong>Phê duyệt DQ Rule: total_amount</strong>
                  <span className="task-sub">Đã hoàn thành bởi Recommender</span>
                </div>
              </div>
            </div>
          </div>

          <div className="sidebar-card">
            <h4>📢 Chính sách thông báo (Announcements)</h4>
            <p className="ann-text">
              Bảng <code>orders</code> thuộc Tier 1. Mọi thay đổi schema hoặc sửa đổi rule chất lượng dữ liệu đều cần thông báo trước 24h trên kênh Slack <code>#data-alerts-ecommerce</code>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
