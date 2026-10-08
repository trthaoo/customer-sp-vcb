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
