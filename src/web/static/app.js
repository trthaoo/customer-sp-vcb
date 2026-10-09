let currentTab = 'meta';
let currentMetaFilter = 'all';
let currentHandoverFilter = 'all';

function switchTab(tab) {
  currentTab = tab;
  if (window.posthog && typeof window.posthog.capture === "function") {
    try { window.posthog.capture('dashboard_tab_switched', { tab: tab }); } catch (e) {}
  }
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
    if (activeModalSessionId) {
      viewSessionDetails(activeModalSessionId, true);
    }
  }
}

let chatSessionsData = [];

async function loadChatSessions() {
  const container = document.getElementById('sessions-list-container');
  const chanFilter = document.getElementById('sessions-filter-chan') ? document.getElementById('sessions-filter-chan').value : 'all';
  const ratingFilter = document.getElementById('sessions-filter-rating') ? document.getElementById('sessions-filter-rating').value : 'all';

  try {
    const res = await fetch(`/api/chat-sessions?channel=${chanFilter}&rating=${ratingFilter}&limit=100`);
    const data = await res.json();
    chatSessionsData = data.sessions || [];

    // Update Overview Stats Bar
    updateSessionsOverviewStats(chatSessionsData);

    // Render list preserving current search filter
    filterSessionsList();
  } catch (err) {
    console.error('Failed to load chat sessions:', err);
    if (container) container.innerHTML = `<div class="empty-state">Lỗi tải dữ liệu sessions: ${escapeHtml(err.message)}</div>`;
  }
}

async function updateSessionsOverviewStats(sessions) {
  const totalEl = document.getElementById('stat-sessions-total');
  const goldEl = document.getElementById('stat-golden-count');
  const openFailEl = document.getElementById('stat-open-fail-count');
  const fixedFailEl = document.getElementById('stat-fixed-fail-count');
  const backupFilesEl = document.getElementById('stat-backup-files');

  if (totalEl) totalEl.textContent = sessions.length;

  let goldenCount = 0;
  let openFailCount = 0;
  let fixedFailCount = 0;

  sessions.forEach(s => {
    if (s.rating === 'pass') {
      goldenCount++;
    } else if (s.rating === 'fail') {
      const status = s.rating_data?.status || 'open';
      if (status === 'fixed') {
        fixedFailCount++;
      } else {
        openFailCount++;
      }
    }
  });

  if (goldEl) goldEl.textContent = goldenCount;
  if (openFailEl) openFailEl.textContent = openFailCount;
  if (fixedFailEl) fixedFailEl.textContent = fixedFailCount;

  // Fetch disk backup folder stats
  try {
    const bRes = await fetch('/api/chat-backups/stats');
    if (bRes.ok) {
      const bData = await bRes.json();
      if (backupFilesEl) {
        backupFilesEl.textContent = `${bData.session_count || 0} JSON & ${bData.md_count || 0} MD files`;
        backupFilesEl.title = `Thư mục sao lưu: ${bData.folder_path}\nTổng số turns đã lưu: ${bData.total_turns}`;
      }
    }
  } catch (e) {
    // Non-fatal
  }
}

function filterSessionsList() {
  const query = (document.getElementById('sessions-search-input')?.value || '').toLowerCase().trim();
  if (!query) {
    renderSessionsList(chatSessionsData);
    return;
  }
  const filtered = chatSessionsData.filter(s => {
    const rd = s.rating_data || {};
    return (
      (s.id && s.id.toLowerCase().includes(query)) ||
      (s.last_message && s.last_message.toLowerCase().includes(query)) ||
      (s.last_reply && s.last_reply.toLowerCase().includes(query)) ||
      (s.user_name && s.user_name.toLowerCase().includes(query)) ||
      (s.platform && s.platform.toLowerCase().includes(query)) ||
      (s.rating && s.rating.toLowerCase().includes(query)) ||
      (rd.title && rd.title.toLowerCase().includes(query)) ||
      (rd.notes && rd.notes.toLowerCase().includes(query)) ||
      (rd.error_category && rd.error_category.toLowerCase().includes(query)) ||
      (rd.error_category_label && rd.error_category_label.toLowerCase().includes(query)) ||
      (rd.root_cause && rd.root_cause.toLowerCase().includes(query)) ||
      (rd.suggested_fix && rd.suggested_fix.toLowerCase().includes(query)) ||
      (rd.target_file_to_fix && rd.target_file_to_fix.toLowerCase().includes(query))
    );
  });
  renderSessionsList(filtered);
}

function renderSessionsList(sessions) {
  const container = document.getElementById('sessions-list-container');
  if (!container) return;

  if (!sessions || sessions.length === 0) {
    container.innerHTML = '<div class="empty-state">Không có phiên chat nào khớp với bộ lọc hiện tại. Hãy chat trên Brand Playground để tạo phiên chat & đánh giá case!</div>';
    return;
  }

  let html = `
    <table class="handover-table">
      <thead>
        <tr>
          <th>Session ID</th>
          <th>Funnel / Kênh</th>
          <th>Khách Hàng</th>
          <th>Lượt</th>
          <th>Thời Điểm</th>
          <th style="min-width:210px;">Đánh Giá &amp; Feedback</th>
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
    const updatedTime = s.updated_at ? new Date(s.updated_at).toLocaleTimeString() : '';
    const rd = s.rating_data || {};

    // Rating feedback column
    let ratingHtml = '';
    if (s.rating === 'pass') {
      const title = rd.title || 'Mẫu chuẩn đạt';
      ratingHtml = `
        <div>
          <span style="display:inline-block; padding:0.2rem 0.55rem; background:#065f46; color:#a7f3d0; border:1px solid #059669; border-radius:12px; font-weight:700; font-size:0.75rem;">
            🌟 ĐẠT - GOLDEN
          </span>
          <div style="font-size:0.75rem; color:#fde047; margin-top:3px; max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(title)}">
            "${escapeHtml(title)}"
          </div>
        </div>
      `;
    } else if (s.rating === 'fail') {
      const isFixed = rd.status === 'fixed';
      const catLabel = rd.error_category_label || rd.error_category || 'Lỗi';
      const rootCause = rd.root_cause || '';
      const targetFile = rd.target_file_to_fix || '';

      ratingHtml = `
        <div>
          <span style="display:inline-block; padding:0.2rem 0.55rem; background:${isFixed ? '#14532d' : '#881337'}; color:${isFixed ? '#86efac' : '#fecdd3'}; border:1px solid ${isFixed ? '#16a34a' : '#e11d48'}; border-radius:12px; font-weight:700; font-size:0.75rem;">
            ${isFixed ? '🟢 FAIL (ĐÃ FIX)' : '🔴 FAIL (CHỜ FIX)'}
          </span>
          <div style="font-size:0.74rem; color:#fb7185; font-weight:600; margin-top:2px; max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(catLabel)}">
            ${escapeHtml(catLabel)}
          </div>
          ${rootCause ? `<div style="font-size:0.72rem; color:#cbd5e1; max-width:200px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(rootCause)}">🔍 ${escapeHtml(rootCause)}</div>` : ''}
          ${targetFile ? `<div style="font-size:0.7rem; color:#38bdf8; margin-top:2px;">📄 <code>${escapeHtml(targetFile)}</code></div>` : ''}
        </div>
      `;
    } else {
      ratingHtml = `
        <div>
          <span style="display:inline-block; padding:0.18rem 0.5rem; background:#334155; color:#94a3b8; border:1px solid #475569; border-radius:12px; font-size:0.74rem;">
            ⚪ Chưa đánh giá
          </span>
        </div>
      `;
    }

    html += `
      <tr id="session-row-${escapeHtml(s.id)}">
        <td><code>${escapeHtml(s.id)}</code></td>
        <td>
          <span style="font-weight:600; text-transform:uppercase;">${escapeHtml(s.channel)}</span> · 
          <span style="color:var(--text-dim);">${escapeHtml(s.platform)} (${escapeHtml(s.surface)})</span>
        </td>
        <td><strong>${escapeHtml(s.user_name || 'Khách Hàng')}</strong></td>
        <td><span style="display:inline-block; padding:0.2rem 0.5rem; background:#334155; border-radius:12px; font-weight:700; font-size:0.8rem;">${s.turn_count || 1} turns</span></td>
        <td style="font-size:0.8rem; color:var(--text-dim);">${updatedTime}</td>
        <td>${ratingHtml}</td>
        <td style="max-width:180px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(s.last_message || '')}">
          ${escapeHtml(s.last_message || '')}
        </td>
        <td style="max-width:180px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--brand-gold);" title="${escapeHtml(s.last_reply || '')}">
          ${escapeHtml(s.last_reply || '')}
        </td>
        <td>
          <span class="status-pill ${badgeClass}">${statusLabel}</span>
        </td>
        <td>
          <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
            <button class="action-btn" onclick="viewSessionDetails('${escapeHtml(s.id)}')" title="Xem toàn bộ transcript & feedback phiên chat" style="background:#2563eb; color:#fff;">
              👁 Transcript
            </button>
            <button class="action-btn" onclick="quickDownloadBackup('${escapeHtml(s.id)}', 'json')" title="Tải file backup JSON từ data/chat_logs/" style="background:#0284c7; color:#fff;">
              💾 JSON
            </button>
            <button class="action-btn" onclick="downloadSessionCsv('${escapeHtml(s.id)}')" title="Tải xuống CSV transcript" style="background:#d97706; color:#fff;">
              📥 CSV
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

let activeModalSessionId = null;

async function viewSessionDetails(sessionId, silent = false) {
  activeModalSessionId = sessionId;
  const modal = document.getElementById('session-transcript-modal');
  const titleEl = document.getElementById('modal-session-title');
  const subEl = document.getElementById('modal-session-subtitle');
  const bodyEl = document.getElementById('modal-session-body');
  const countEl = document.getElementById('modal-session-count');
  const feedbackBannerEl = document.getElementById('modal-feedback-banner');

  if (!modal) return;
  modal.style.display = 'flex';
  titleEl.textContent = `Session: ${sessionId}`;
  if (!silent) {
    subEl.textContent = 'Đang tải toàn bộ hội thoại...';
    bodyEl.innerHTML = '<div style="text-align:center; padding:2rem; color:#94a3b8;">Đang tải...</div>';
    if (feedbackBannerEl) feedbackBannerEl.style.display = 'none';
  }

  try {
    const res = await fetch(`/api/chat-sessions/${sessionId}`);
    if (!res.ok) throw new Error('Không tìm thấy session');
    const data = await res.json();

    subEl.textContent = `${data.channel.toUpperCase()} · ${data.platform.toUpperCase()} (${data.surface}) · Cập nhật: ${new Date(data.updated_at).toLocaleString()}`;
    countEl.textContent = `Tổng số: ${data.turns ? data.turns.length : 0} lượt trao đổi &bull; Sao lưu tại: data/chat_logs/${sessionId}.json`;

    // Render Rich Feedback Banner
    if (feedbackBannerEl) {
      const rd = data.rating_data || {};
      if (data.rating === 'pass') {
        feedbackBannerEl.style.display = 'block';
        feedbackBannerEl.innerHTML = `
          <div style="background:#022c22; border:1px solid #059669; border-radius:8px; padding:0.85rem 1rem; color:#ecfdf5;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <strong style="color:#34d399; font-size:0.9rem;">🌟 BENCHMARK GOLDEN EXAMPLE (Mẫu Chuẩn Đạt)</strong>
              <span style="font-size:0.75rem; color:#6ee7b7;">ID: ${escapeHtml(rd.case_id || '')}</span>
            </div>
            <div style="font-size:0.85rem; font-weight:600; margin-top:4px; color:#fde047;">${escapeHtml(rd.title || 'Mẫu chuẩn')}</div>
            ${rd.notes ? `<div style="font-size:0.8rem; margin-top:4px; color:#a7f3d0;">${escapeHtml(rd.notes)}</div>` : ''}
            ${rd.tags && rd.tags.length ? `<div style="margin-top:6px; display:flex; gap:4px; flex-wrap:wrap;">${rd.tags.map(t => `<span style="background:#065f46; color:#d1fae5; font-size:0.7rem; padding:0.1rem 0.4rem; border-radius:3px;">#${escapeHtml(t)}</span>`).join('')}</div>` : ''}
          </div>
        `;
      } else if (data.rating === 'fail') {
        const isFixed = rd.status === 'fixed';
        feedbackBannerEl.style.display = 'block';
        feedbackBannerEl.innerHTML = `
          <div style="background:#1e1b24; border:1px solid ${isFixed ? '#16a34a' : '#e11d48'}; border-radius:8px; padding:0.85rem 1rem; color:#f8fafc;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
              <div style="display:flex; align-items:center; gap:0.5rem;">
                <strong style="color:${isFixed ? '#4ade80' : '#fb7185'}; font-size:0.9rem;">⚠️ AUDIT CASE LỖI &amp; KHẮC PHỤC</strong>
                <span style="background:${isFixed ? '#14532d' : '#881337'}; color:${isFixed ? '#86efac' : '#fecdd3'}; border:1px solid ${isFixed ? '#16a34a' : '#e11d48'}; font-size:0.72rem; font-weight:700; padding:0.15rem 0.5rem; border-radius:10px;">
                  ${isFixed ? '🟢 ĐÃ FIX' : '🔴 CHỜ FIX (OPEN)'}
                </span>
              </div>
              <div style="display:flex; gap:0.4rem; align-items:center;">
                ${rd.case_id ? `
                  <button onclick="toggleCaseFixStatus('${escapeHtml(rd.case_id)}', '${isFixed ? 'fixed' : 'open'}')" class="action-btn" style="background:${isFixed ? '#d97706' : '#16a34a'}; color:#fff; font-size:0.75rem; padding:0.25rem 0.6rem;">
                    ${isFixed ? '🔄 Mở lại case' : '✓ Đánh dấu ĐÃ FIX'}
                  </button>
                ` : ''}
              </div>
            </div>

            <div style="font-size:0.8rem; color:#fb7185; font-weight:600; margin-top:6px;">
              Phân loại: ${escapeHtml(rd.error_category_label || rd.error_category || 'Lỗi')} ${rd.failed_turn_index ? `(Turn #${rd.failed_turn_index})` : ''}
            </div>

            <div style="margin-top:6px; background:#2a1720; border-left:3px solid #e11d48; padding:0.5rem 0.75rem; border-radius:4px; font-size:0.82rem;">
              <strong style="color:#f43f5e;">🚨 Nguyên nhân bot sai:</strong> ${escapeHtml(rd.root_cause || 'Chưa ghi chú')}
            </div>

            <div style="margin-top:6px; background:#0c2838; border-left:3px solid #0284c7; padding:0.5rem 0.75rem; border-radius:4px; font-size:0.82rem;">
              <strong style="color:#38bdf8;">🛠️ Giải pháp / Rule cần sửa:</strong> ${escapeHtml(rd.suggested_fix || 'Chưa ghi chú')}
              ${rd.target_file_to_fix ? `<div style="margin-top:4px; font-size:0.75rem; color:#fde047;">📄 File cần sửa: <code>${escapeHtml(rd.target_file_to_fix)}</code></div>` : ''}
            </div>
          </div>
        `;
      } else {
        feedbackBannerEl.style.display = 'block';
        feedbackBannerEl.innerHTML = `
          <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:0.6rem 0.9rem; color:#94a3b8; font-size:0.8rem; display:flex; justify-content:space-between; align-items:center;">
            <span>⚪ Phiên chat này chưa có đánh giá. Bạn có thể mở <a href="/playground" style="color:#38bdf8; text-decoration:underline;">Brand Playground</a> để đánh giá Đạt / Báo lỗi.</span>
          </div>
        `;
      }
    }

    if (!data.turns || data.turns.length === 0) {
      bodyEl.innerHTML = '<div style="text-align:center; color:#94a3b8; padding:2rem;">Không có chi tiết turn nào trong session này.</div>';
      return;
    }

    const rd = data.rating_data || {};
    let turnsHtml = '';
    data.turns.forEach((t, idx) => {
      const turnNo = t.turn_index || (idx + 1);
      const isFailedTurn = rd.failed_turn_index && rd.failed_turn_index === turnNo;

      turnsHtml += `
        <div style="background:${isFailedTurn ? '#2a1720' : '#1e293b'}; border:1px solid ${isFailedTurn ? '#e11d48' : '#334155'}; border-radius:8px; padding:1rem; display:flex; flex-direction:column; gap:0.6rem;">
          <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:#94a3b8;">
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <span style="font-weight:700; color:#38bdf8;">Turn #${turnNo}</span>
              ${isFailedTurn ? '<span style="background:#e11d48; color:#fff; font-size:0.7rem; font-weight:700; padding:0.1rem 0.4rem; border-radius:3px;">🚨 LƯỢT PHÁT HIỆN LỖI</span>' : ''}
            </div>
            <span>${t.timestamp || ''}</span>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:flex-start;">
            <span style="background:#0284c7; color:#fff; font-size:0.7rem; font-weight:700; padding:0.15rem 0.4rem; border-radius:4px;">Khách</span>
            <div style="background:#0f172a; padding:0.6rem 0.8rem; border-radius:6px; color:#f8fafc; font-size:0.85rem; flex:1; white-space:pre-wrap;">
              ${escapeHtml(t.customer_message || t.user_message || '')}
              ${t.attachment_name ? `<div style="font-size:0.75rem; color:#38bdf8; margin-top:4px;">📎 Đính kèm: ${escapeHtml(t.attachment_name)}</div>` : ''}
            </div>
          </div>
          <div style="display:flex; gap:0.5rem; align-items:flex-start;">
            <span style="background:#eab308; color:#0f172a; font-size:0.7rem; font-weight:700; padding:0.15rem 0.4rem; border-radius:4px;">Bot</span>
            <div style="background:#022c22; border:1px solid #065f46; padding:0.6rem 0.8rem; border-radius:6px; color:#ecfdf5; font-size:0.85rem; flex:1; white-space:pre-wrap;">
              ${escapeHtml(t.bot_reply || t.reply || '')}
            </div>
          </div>
          <div style="display:flex; flex-wrap:wrap; gap:0.4rem; font-size:0.7rem; margin-top:0.25rem;">
            ${t.status_badge ? `<span style="background:#334155; padding:0.1rem 0.4rem; border-radius:3px; color:#4ade80;">Badge: <strong>${escapeHtml(t.status_badge)}</strong></span>` : ''}
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

async function toggleCaseFixStatus(caseId, currentStatus) {
  const newStatus = currentStatus === 'fixed' ? 'open' : 'fixed';
  try {
    const res = await fetch(`/api/playground/session/cases/${caseId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, fixed_notes: newStatus === 'fixed' ? 'Đã khắc phục qua Dashboard Logs' : '' })
    });
    if (!res.ok) throw new Error('Không thể cập nhật trạng thái');
    await loadChatSessions();
    if (activeModalSessionId) {
      viewSessionDetails(activeModalSessionId, true);
    }
  } catch (err) {
    alert('Lỗi cập nhật trạng thái: ' + err.message);
  }
}

function closeSessionModal() {
  const modal = document.getElementById('session-transcript-modal');
  if (modal) modal.style.display = 'none';
  activeModalSessionId = null;
}

function downloadActiveSessionBackup(format) {
  if (!activeModalSessionId) return;
  quickDownloadBackup(activeModalSessionId, format);
}

function quickDownloadBackup(sessionId, format = 'json') {
  window.open(`/api/chat-backups/${sessionId}?format=${format}`, '_blank');
}

async function downloadSessionCsv(sessionId) {
  if (!sessionId) return;
  try {
    const res = await fetch(`/api/chat-sessions/${sessionId}`);
    if (!res.ok) throw new Error('Không tìm thấy session');
    const data = await res.json();
    const turns = data.turns || [];
    if (turns.length === 0) {
      alert('Session này chưa có turns nào để xuất CSV.');
      return;
    }

    let csv = '\uFEFFTurn,Timestamp,KhachHang,BotReply,Intent,SanPham,Rule,Decision\n';
    turns.forEach((t, i) => {
      csv += [
        t.turn_index || (i + 1),
        `"${(t.timestamp || '').replace(/"/g, '""')}"`,
        `"${(t.customer_message || t.user_message || '').replace(/"/g, '""')}"`,
        `"${(t.bot_reply || t.reply || '').replace(/"/g, '""')}"`,
        `"${(t.intent || '').replace(/"/g, '""')}"`,
        `"${(t.matched_product || '').replace(/"/g, '""')}"`,
        `"${(t.matched_rule || '').replace(/"/g, '""')}"`,
        `"${(t.decision || '').replace(/"/g, '""')}"`
      ].join(',') + '\n';
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session_${sessionId}.csv`;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    a.remove();
  } catch (err) {
    alert('Lỗi xuất CSV: ' + err.message);
  }
}

function exportCurrentModalSessionCsv() {
  if (activeModalSessionId) {
    downloadSessionCsv(activeModalSessionId);
  }
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
      if (!event.data) return;
      try {
        const msg = JSON.parse(event.data);
        // Visual indicator ping
        const ind = document.getElementById('sessions-live-indicator');
        if (ind) {
          ind.style.borderColor = '#22c55e';
          ind.style.background = 'rgba(34, 197, 94, 0.3)';
          setTimeout(() => {
            ind.style.borderColor = 'rgba(34, 197, 94, 0.4)';
            ind.style.background = 'rgba(34, 197, 94, 0.15)';
          }, 800);
        }

        // Live update sessions
        if (msg.type === 'chat_session_updated' || msg.type === 'case_rated' || msg.type === 'case_updated' || msg.type === 'chat_session_deleted') {
          if (currentTab === 'sessions') {
            loadChatSessions();
            if (activeModalSessionId && (activeModalSessionId === msg.session_id || msg.type === 'case_updated')) {
              viewSessionDetails(activeModalSessionId, true);
            }
          }
        }
      } catch (e) {
        // Ping comment or plain text
      }
      refreshCurrentTab();
    };
    source.onerror = function() {
      // Reconnection handled automatically by browser EventSource
    };
  }

  // Active polling sync every 3.5 seconds to guarantee 100% real-time reliability
  setInterval(() => {
    refreshCurrentTab();
  }, 3500);
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname.toLowerCase();
  const hash = window.location.hash.toLowerCase();
  if (path.includes('/logs') || path.includes('/sessions') || path.includes('/dashboard') || hash === '#sessions' || hash === '#logs') {
    switchTab('sessions');
  } else {
    refreshCurrentTab();
  }
  setupLiveStream();
});
