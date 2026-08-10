const state = {
  page: 1,
  pageSize: 50,
  total: 0,
  currentRecordId: null,
  scanPollTimer: null,
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `發生錯誤 (${res.status})`);
  }
  return res.json();
}

// ---------------- 連接狀態 ----------------

async function refreshAuthStatus() {
  const data = await api('/auth/status');
  $('connect-not-configured').classList.toggle('hidden', data.credentials_configured);
  $('connect-disconnected').classList.toggle('hidden', !data.credentials_configured || data.connected);
  $('connect-connected').classList.toggle('hidden', !data.connected);
  return data;
}

$('btn-connect').addEventListener('click', () => {
  window.location.href = '/auth/login';
});

$('btn-disconnect').addEventListener('click', async () => {
  await api('/auth/logout', { method: 'POST' });
  refreshAuthStatus();
});

// ---------------- 掃描 ----------------

$('btn-scan').addEventListener('click', async () => {
  const folder = $('folder-input').value.trim();
  if (!folder) {
    alert('請先輸入資料夾連結或 ID');
    return;
  }
  try {
    const { job_id } = await api('/api/scan', {
      method: 'POST',
      body: JSON.stringify({ folder }),
    });
    $('scan-progress').classList.remove('hidden');
    pollScanStatus(job_id);
  } catch (err) {
    alert(err.message);
  }
});

function pollScanStatus(jobId) {
  if (state.scanPollTimer) clearInterval(state.scanPollTimer);
  state.scanPollTimer = setInterval(async () => {
    try {
      const job = await api(`/api/scan/status?job_id=${jobId}`);
      const total = job.total_files || 0;
      const processed = job.processed_files || 0;
      const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
      $('progress-fill').style.width = `${pct}%`;
      $('progress-text').textContent = total
        ? `處理中… ${processed}/${total}（${job.current_file || ''}）`
        : '正在列出資料夾內的檔案…';

      if (job.status === 'done') {
        clearInterval(state.scanPollTimer);
        $('progress-text').textContent = `完成！共處理 ${total} 個檔案。`;
        loadRecords();
      } else if (job.status === 'error') {
        clearInterval(state.scanPollTimer);
        $('progress-text').textContent = `發生錯誤：${job.error}`;
      }
    } catch (err) {
      clearInterval(state.scanPollTimer);
      $('progress-text').textContent = `發生錯誤：${err.message}`;
    }
  }, 1500);
}

// ---------------- 搜尋 / 列表 ----------------

function confidenceBadge(level) {
  const label = { high: '高', medium: '中', low: '低' }[level] || level;
  return `<span class="badge badge-${level}">${label}</span>`;
}

async function loadRecords() {
  const q = $('search-input').value.trim();
  const needsReview = $('filter-needs-review').checked ? 'true' : '';
  const params = new URLSearchParams({ page: state.page, page_size: state.pageSize });
  if (q) params.set('q', q);
  if (needsReview) params.set('needs_review', needsReview);

  const data = await api(`/api/records?${params.toString()}`);
  state.total = data.total;
  renderRecords(data.records);
  renderPagination();
  $('stats-line').textContent =
    `共 ${data.stats.total} 筆資料，其中 ${data.stats.needs_review} 筆需複核`;
}

function renderRecords(records) {
  const tbody = $('records-tbody');
  tbody.innerHTML = '';
  if (records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#9ca3af">目前沒有符合條件的資料</td></tr>';
    return;
  }
  for (const rec of records) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(rec.name)}</td>
      <td>${escapeHtml(rec.phone)}</td>
      <td title="${escapeHtml(rec.address)}">${escapeHtml(rec.address)}</td>
      <td>${escapeHtml(rec.unit)}</td>
      <td>${confidenceBadge(rec.confidence)}</td>
      <td title="${escapeHtml(rec.source_folder_path)}">${escapeHtml(rec.source_file_name)}</td>
      <td>${escapeHtml(rec.file_type)}</td>
      <td><button class="btn btn-secondary btn-edit" data-id="${rec.id}">編輯</button></td>
    `;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll('.btn-edit').forEach((btn) => {
    btn.addEventListener('click', () => openModal(btn.dataset.id));
  });
}

function renderPagination() {
  const totalPages = Math.max(Math.ceil(state.total / state.pageSize), 1);
  $('page-label').textContent = `第 ${state.page} / ${totalPages} 頁`;
  $('btn-prev').disabled = state.page <= 1;
  $('btn-next').disabled = state.page >= totalPages;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

let searchDebounce = null;
$('search-input').addEventListener('input', () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => { state.page = 1; loadRecords(); }, 300);
});
$('filter-needs-review').addEventListener('change', () => { state.page = 1; loadRecords(); });
$('btn-prev').addEventListener('click', () => { if (state.page > 1) { state.page -= 1; loadRecords(); } });
$('btn-next').addEventListener('click', () => { state.page += 1; loadRecords(); });

$('btn-export').addEventListener('click', () => {
  const q = $('search-input').value.trim();
  const needsReview = $('filter-needs-review').checked ? 'true' : '';
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (needsReview) params.set('needs_review', needsReview);
  window.location.href = `/api/export?${params.toString()}`;
});

// ---------------- 編輯彈窗 ----------------

async function openModal(id) {
  const rec = await api(`/api/records/${id}`);
  state.currentRecordId = id;
  $('edit-name').value = rec.name || '';
  $('edit-phone').value = rec.phone || '';
  $('edit-address').value = rec.address || '';
  $('edit-unit').value = rec.unit || '';
  $('edit-raw').value = rec.raw_text || '';
  $('edit-mark-reviewed').checked = !rec.needs_review;

  const previewArea = $('preview-area');
  previewArea.innerHTML = '';
  if (rec.local_file_path && /\.(jpg|jpeg|png)$/i.test(rec.local_file_path)) {
    previewArea.innerHTML = `<img src="/api/records/${id}/file" alt="原始圖片預覽">`;
  } else if (rec.local_file_path) {
    previewArea.innerHTML = `<a href="/api/records/${id}/file" target="_blank">開啟原始檔案</a>`;
  }

  $('modal-backdrop').classList.remove('hidden');
}

$('btn-close-modal').addEventListener('click', () => {
  $('modal-backdrop').classList.add('hidden');
});

$('btn-save').addEventListener('click', async () => {
  const id = state.currentRecordId;
  if (!id) return;
  await api(`/api/records/${id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: $('edit-name').value.trim(),
      phone: $('edit-phone').value.trim(),
      address: $('edit-address').value.trim(),
      unit: $('edit-unit').value.trim(),
      mark_reviewed: $('edit-mark-reviewed').checked,
    }),
  });
  $('modal-backdrop').classList.add('hidden');
  loadRecords();
});

// ---------------- 初始化 ----------------

(async function init() {
  await refreshAuthStatus();
  await loadRecords();
})();
