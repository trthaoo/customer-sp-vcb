let currentTab = 'meta';
let currentMetaFilter = 'all';
let currentHandoverFilter = 'all';

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-view').forEach(view => view.style.display = 'none');

  document.getElementById(`tab-btn-${tab}`).classList.add('active');
  document.getElementById(`view-${tab}`).style.display = 'block';

  refreshCurrentTab();
}

function setMetaFilter(filter) {
  currentMetaFilter = filter;
  const container = document.querySelector('#view-meta .platform-filters');
  container.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  fetchMetaMetrics();
}

function setHandoverFilter(filter) {
  currentHandoverFilter = filter;
  const container = document.querySelector('#view-handover .platform-filters');
  container.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
  fetchHandoverQueue();
}

async function fetchMetaMetrics() {
  try {
    const res = await fetch(`/api/metrics?channel=meta&platform=${currentMetaFilter}`);
    const data = await res.json();
    document.getElementById('meta-inbound').innerText = data.inbound_count ?? 0;
    document.getElementById('meta-replied').innerText = data.auto_replied_count ?? 0;
    document.getElementById('meta-handover-open').innerText = data.handover_open_count ?? 0;
    document.getElementById('meta-resolved').innerText = data.resolved_count ?? 0;
    document.getElementById('meta-fallback').innerText = data.fallback_count ?? 0;
    document.getElementById('meta-last-event').innerText = data.last_event_at ? new Date(data.last_event_at).toLocaleTimeString() : 'chưa có data';

    const container = document.getElementById('meta-top-rules-container');
    if (data.top_matched_rules && data.top_matched_rules.length > 0) {
      let html = '<ul style="list-style: none; padding: 0;">';
      data.top_matched_rules.forEach(r => {
        html += `<li style="padding: 0.5rem 0; border-bottom: 1px solid var(--panel-border); display: flex; justify-content: space-between;">
          <span><code>${escapeHtml(r.rule)}</code></span>
          <strong>${r.count}</strong>
        </li>`;
      });
      html += '</ul>';
      container.innerHTML = html;
    } else {
      container.innerHTML = '<div class="empty-state">Chưa có event live. Case test và dry-run không hiện ở đây.</div>';
    }
  } catch (err) {
    console.error('Failed to fetch Meta metrics:', err);
  }
}

async function fetchTikTokMetrics() {
  try {
    const res = await fetch(`/api/metrics?channel=tiktok&platform=tiktok`);
    const data = await res.json();
    document.getElementById('tiktok-inbound').innerText = data.inbound_count ?? 0;
    document.getElementById('tiktok-replied').innerText = data.auto_replied_count ?? 0;
    document.getElementById('tiktok-handover-open').innerText = data.handover_open_count ?? 0;
    document.getElementById('tiktok-resolved').innerText = data.resolved_count ?? 0;
    document.getElementById('tiktok-fallback').innerText = data.fallback_count ?? 0;
    document.getElementById('tiktok-last-event').innerText = data.last_event_at ? new Date(data.last_event_at).toLocaleTimeString() : 'chưa có data';

    const container = document.getElementById('tiktok-top-rules-container');
    if (data.top_matched_rules && data.top_matched_rules.length > 0) {
      let html = '<ul style="list-style: none; padding: 0;">';
      data.top_matched_rules.forEach(r => {
        html += `<li style="padding: 0.5rem 0; border-bottom: 1px solid var(--panel-border); display: flex; justify-content: space-between;">
          <span><code>${escapeHtml(r.rule)}</code></span>
          <strong>${r.count}</strong>
        </li>`;
      });
      html += '</ul>';
      container.innerHTML = html;
    } else {
      container.innerHTML = '<div class="empty-state">Chưa có event live. Case test và dry-run không hiện ở đây.</div>';
    }
  } catch (err) {
    console.error('Failed to fetch TikTok metrics:', err);
  }
}

async function fetchHandoverBadge() {
  try {
    const res = await fetch('/api/handover/badge');
    const data = await res.json();
    const badge = document.getElementById('handover-badge');
    if (data.badge_count > 0) {
      badge.innerText = data.badge_count;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  } catch (err) {
    console.error('Failed to fetch handover badge:', err);
  }
}

async function fetchHandoverQueue() {
  try {
    const res = await fetch(`/api/handover?state=${currentHandoverFilter}`);
    const data = await res.json();
    const container = document.getElementById('handover-table-container');

    if (!data.queue || data.queue.length === 0) {
      container.innerHTML = '<div class="empty-state">Chưa có event live. Case test và dry-run không hiện ở đây.</div>';
      return;
    }

    let html = `
      <table class="handover-table">
        <thead>
          <tr>
            <th>Kênh</th>
            <th>Platform</th>
            <th>Surface</th>
            <th>Khách hàng</th>
            <th>Sản phẩm / Rule</th>
            <th>Lý do Escalated</th>
            <th>Draft Reply</th>
            <th>Trạng thái</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.queue.forEach(item => {
      const channelClass = item.channel === 'meta' ? 'tag-meta' : 'tag-tiktok';
      const stateClass = `tag-${item.handover_state}`;
      const filesStr = (item.knowledge_files || []).join(', ') || 'None';

      html += `
        <tr>
          <td><span class="tag ${channelClass}">${item.channel}</span></td>
          <td><strong>${item.platform.toUpperCase()}</strong></td>
          <td>${item.surface}</td>
          <td>
            <div style="font-weight: 600;">"${escapeHtml(item.user_message)}"</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">ID: ${item.id}</div>
          </td>
          <td>
            <div>SP: <strong>${escapeHtml(item.product_id || 'Chưa định danh')}</strong></div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Rule: ${escapeHtml(item.matched_rule || 'Fallback')}</div>
            <div style="font-size: 0.7rem; color: var(--accent-meta);">Files: ${escapeHtml(filesStr)}</div>
          </td>
          <td style="color: var(--accent-warning);">${escapeHtml(item.escalate_reason || 'Manual check')}</td>
          <td style="max-width: 250px;"><em>"${escapeHtml(item.reply_text || '')}"</em></td>
          <td><span class="tag ${stateClass}">${item.handover_state}</span></td>
          <td>
            <div style="display: flex; gap: 0.3rem; flex-wrap: wrap;">
              ${item.handover_state !== 'claimed' && item.handover_state !== 'resolved' ? 
                `<button class="action-btn" onclick="updateState('${item.id}', 'claimed')">Nhận xử lý</button>` : ''}
              ${item.handover_state !== 'waiting_on_us' && item.handover_state !== 'resolved' ? 
                `<button class="action-btn" onclick="updateState('${item.id}', 'waiting_on_us')">Chờ tin</button>` : ''}
              ${item.handover_state !== 'resolved' ? 
                `<button class="action-btn resolve-btn" onclick="resolveCase('${item.id}')">Hoàn tất</button>` : ''}
            </div>
          </td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
  } catch (err) {
    console.error('Failed to fetch handover queue:', err);
  }
}

async function updateState(eventId, state) {
  try {
    await fetch(`/api/handover/${eventId}/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: state, notes: '' })
    });
    fetchHandoverQueue();
    fetchHandoverBadge();
  } catch (err) {
    alert('Cập nhật trạng thái thất bại: ' + err.message);
  }
}

async function resolveCase(eventId) {
  const notes = prompt('Nhập ghi chú xử lý (tùy chọn):', 'Đã tư vấn chốt đơn cho khách qua Zernio');
  if (notes === null) return;
  try {
    await fetch(`/api/handover/${eventId}/state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: 'resolved', notes: notes })
    });
    fetchHandoverQueue();
    fetchHandoverBadge();
    if (currentTab === 'meta') fetchMetaMetrics();
    if (currentTab === 'tiktok') fetchTikTokMetrics();
  } catch (err) {
    alert('Lỗi hoàn tất ca: ' + err.message);
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function refreshCurrentTab() {
  fetchHandoverBadge();
  if (currentTab === 'meta') {
    fetchMetaMetrics();
  } else if (currentTab === 'tiktok') {
    fetchTikTokMetrics();
  } else if (currentTab === 'handover') {
    fetchHandoverQueue();
  } else if (currentTab === 'sessions') {
    loadChatSessions();
  }
}

let chatSessionsData = [];

async function loadChatSessions() {
  const container = document.getElementById('sessions-list-container');
  const chanFilter = document.getElementById('sessions-filter-chan') ? document.getElementById('sessions-filter-chan').value : 'all';
  try {
    const res = await fetch(`/api/chat-sessions?channel=${chanFilter}&limit=100`);
    const data = await res.json();
    chatSessionsData = data.sessions || [];
    renderSessionsList(chatSessionsData);
  } catch (err) {
    console.error('Failed to load chat sessions:', err);
    if (container) container.innerHTML = `<div class="empty-state">Lỗi tải dữ liệu sessions: ${escapeHtml(err.message)}</div>`;
  }
}

function filterSessionsList() {
  const query = (document.getElementById('sessions-search-input')?.value || '').toLowerCase().trim();
  if (!query) {
    renderSessionsList(chatSessionsData);
    return;
  }
  const filtered = chatSessionsData.filter(s => 
    (s.id && s.id.toLowerCase().includes(query)) ||
    (s.last_message && s.last_message.toLowerCase().includes(query)) ||
    (s.user_name && s.user_name.toLowerCase().includes(query)) ||
    (s.platform && s.platform.toLowerCase().includes(query))
  );
  renderSessionsList(filtered);
}

function renderSessionsList(sessions) {
  const container = document.getElementById('sessions-list-container');
  if (!container) return;

  if (!sessions || sessions.length === 0) {
    container.innerHTML = '<div class="empty-state">Chưa có session chat nào được lưu trong database. Hãy chat thử trên Playground hoặc gửi webhook để tạo phiên chat!</div>';
    return;
  }

  let html = `
    <table class="handover-table">
      <thead>
        <tr>
          <th>Session ID</th>
          <th>Funnel / Kênh</th>
          <th>Khách Hàng</th>
          <th>Lượt Chat</th>
          <th>Thời Điểm Cuối</th>
          <th>Tin Nhắn Khách Gần Nhất</th>
          <th>Phản Hồi Bot</th>
          <th>Trạng Thái</th>
          <th>Thao Tác</th>
        </tr>
      </thead>
      <tbody>
  `;

  sessions.forEach(s => {
    const badgeClass = s.status === 'handover' ? 'status-pill-fail' : 'status-pill-pass';
    const statusLabel = s.status === 'handover' ? 'Handover' : 'Active / Auto';
    const updatedTime = s.updated_at ? new Date(s.updated_at).toLocaleString() : '';

    html += `
      <tr>
        <td><code>${escapeHtml(s.id)}</code></td>
        <td>
          <span style="font-weight:600; text-transform:uppercase;">${escapeHtml(s.channel)}</span> · 
          <span style="color:var(--text-dim);">${escapeHtml(s.platform)} (${escapeHtml(s.surface)})</span>
        </td>
        <td><strong>${escapeHtml(s.user_name || 'Khách Hàng')}</strong></td>
        <td><span style="display:inline-block; padding:0.2rem 0.5rem; background:#334155; border-radius:12px; font-weight:700; font-size:0.8rem;">${s.turn_count || 1} turns</span></td>
        <td style="font-size:0.8rem; color:var(--text-dim);">${updatedTime}</td>
        <td style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(s.last_message || '')}">
          ${escapeHtml(s.last_message || '')}
        </td>
        <td style="max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--brand-gold);" title="${escapeHtml(s.last_reply || '')}">
          ${escapeHtml(s.last_reply || '')}
        </td>
        <td>
          <span class="status-pill ${badgeClass}">${statusLabel}</span>
        </td>
        <td>
          <div style="display:flex; gap:0.4rem;">
            <button class="action-btn" onclick="viewSessionDetails('${escapeHtml(s.id)}')" title="Xem toàn bộ transcript phiên chat" style="background:#2563eb; color:#fff;">
              👁 Transcript
            </button>
            <button class="action-btn" onclick="deleteSession('${escapeHtml(s.id)}')" title="Xóa session" style="background:#dc2626; color:#fff;">
              ✕
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;
}

async function viewSessionDetails(sessionId) {
  const modal = document.getElementById('session-transcript-modal');
  const titleEl = document.getElementById('modal-session-title');
  const subEl = document.getElementById('modal-session-subtitle');
  const bodyEl = document.getElementById('modal-session-body');
  const countEl = document.getElementById('modal-session-count');

  if (!modal) return;
  modal.style.display = 'flex';
  titleEl.textContent = `Session: ${sessionId}`;
  subEl.textContent = 'Đang tải toàn bộ hội thoại...';
  bodyEl.innerHTML = '<div style="text-align:center; padding:2rem; color:#94a3b8;">Đang tải...</div>';

  try {
    const res = await fetch(`/api/chat-sessions/${sessionId}`);
    if (!res.ok) throw new Error('Không tìm thấy session');
    const data = await res.json();

    subEl.textContent = `${data.channel.toUpperCase()} · ${data.platform.toUpperCase()} (${data.surface}) · Cập nhật: ${new Date(data.updated_at).toLocaleString()}`;
    countEl.textContent = `Tổng số: ${data.turns ? data.turns.length : 0} lượt trao đổi`;

    if (!data.turns || data.turns.length === 0) {
      bodyEl.innerHTML = '<div style="text-align:center; color:#94a3b8; padding:2rem;">Không có chi tiết turn nào trong session này.</div>';
      return;
    }

    let turnsHtml = '';
    data.turns.forEach((t, idx) => {
      turnsHtml += `
        <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:1rem; display:flex; flex-direction:column; gap:0.6rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:#94a3b8;">
            <span style="font-weight:700; color:#38bdf8;">Turn #${t.turn_index || (idx + 1)}</span>
            <span>${t.timestamp || ''}</span>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:flex-start;">
            <span style="background:#0284c7; color:#fff; font-size:0.7rem; font-weight:700; padding:0.15rem 0.4rem; border-radius:4px;">Khách</span>
            <div style="background:#0f172a; padding:0.6rem 0.8rem; border-radius:6px; color:#f8fafc; font-size:0.85rem; flex:1; white-space:pre-wrap;">
              ${escapeHtml(t.customer_message || t.user_message || '')}
            </div>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:flex-start;">
            <span style="background:#eab308; color:#0f172a; font-size:0.7rem; font-weight:700; padding:0.15rem 0.4rem; border-radius:4px;">Bot</span>
            <div style="background:#022c22; border:1px solid #065f46; padding:0.6rem 0.8rem; border-radius:6px; color:#ecfdf5; font-size:0.85rem; flex:1; white-space:pre-wrap;">
              ${escapeHtml(t.bot_reply || t.reply || '')}
            </div>
          </div>
          <div style="display:flex; flex-wrap:wrap; gap:0.4rem; font-size:0.7rem; margin-top:0.25rem;">
            ${t.intent ? `<span style="background:#334155; padding:0.1rem 0.4rem; border-radius:3px; color:#94a3b8;">Intent: <strong>${escapeHtml(t.intent)}</strong></span>` : ''}
            ${t.matched_product ? `<span style="background:#334155; padding:0.1rem 0.4rem; border-radius:3px; color:#38bdf8;">SP: <strong>${escapeHtml(t.matched_product)}</strong></span>` : ''}
            ${t.matched_rule ? `<span style="background:#334155; padding:0.1rem 0.4rem; border-radius:3px; color:#facc15;">Rule: <strong>${escapeHtml(t.matched_rule)}</strong></span>` : ''}
            ${t.decision ? `<span style="background:#334155; padding:0.1rem 0.4rem; border-radius:3px; color:#4ade80;">Decision: <strong>${escapeHtml(t.decision)}</strong></span>` : ''}
            ${t.attached_image_url ? `<span style="background:#065f46; padding:0.1rem 0.4rem; border-radius:3px; color:#a7f3d0;">📷 Có ảnh SP</span>` : ''}
          </div>
        </div>
      `;
    });
    bodyEl.innerHTML = turnsHtml;
  } catch (err) {
    bodyEl.innerHTML = `<div style="color:#ef4444; padding:1.5rem; text-align:center;">Lỗi: ${escapeHtml(err.message)}</div>`;
  }
}

function closeSessionModal() {
  const modal = document.getElementById('session-transcript-modal');
  if (modal) modal.style.display = 'none';
}

async function deleteSession(sessionId) {
  if (!confirm(`Bạn có chắc muốn xóa vĩnh viễn session ${sessionId}?`)) return;
  try {
    const res = await fetch(`/api/chat-sessions/${sessionId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Không thể xóa');
    loadChatSessions();
  } catch (err) {
    alert('Lỗi xóa session: ' + err.message);
  }
}

// Setup Server-Sent Events stream for live real-time update
function setupLiveStream() {
  if (window.EventSource) {
    const source = new EventSource('/api/events/stream');
    source.onmessage = function(event) {
      refreshCurrentTab();
    };
    source.onerror = function() {
      source.close();
      // Fallback to polling every 5 seconds
      setInterval(refreshCurrentTab, 5000);
    };
  } else {
    setInterval(refreshCurrentTab, 5000);
  }
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  refreshCurrentTab();
  setupLiveStream();
});
