/* StarWaves 前端逻辑：管理页与分享页共用一套渲染。 */

const KEY_NAME = 'starwaves_api_key';
let apiKey = localStorage.getItem(KEY_NAME) || '';

const params = new URLSearchParams(location.search);
const shareId = params.get('share');
const isShare = Boolean(shareId);

const $ = (sel) => document.querySelector(sel);

const GAME_THEME = {
  hsr: {
    label: '星穹铁道', emoji: '🚂', ring: 'border-amber-300/25', glow: 'shadow-amber-500/10',
    bar: 'from-amber-300 to-violet-500',
    chip: 'border-amber-300/25 bg-amber-400/10 text-amber-200',
    c1: '#fcd34d', c2: '#8b5cf6',
  },
  wuwa: {
    label: '鸣潮', emoji: '🌊', ring: 'border-cyan-300/25', glow: 'shadow-cyan-500/10',
    bar: 'from-cyan-300 to-blue-500',
    chip: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-200',
    c1: '#67e8f9', c2: '#3b82f6',
  },
};

const ELEMENT_COLORS = {
  物理: '#e5e7eb', 风: '#4ade80', 雷: '#a78bfa', 冰: '#7dd3fc', 火: '#f87171',
  量子: '#c084fc', 虚数: '#fde047',
  冷凝: '#7dd3fc', 热熔: '#f87171', 导电: '#a78bfa', 衍射: '#fde047', 气动: '#4ade80', 湮灭: '#94a3b8',
};

const RESOURCE_LABELS = {
  jades: '星琼', credits: '信用点', starlight: '星芒', embers: '余烬',
  special_pass: '星轨专票', star_pass: '星轨通票',
  astrites: '星声', shell_credits: '贝币', waveplates: '结晶波片',
};

/* ---------- 基础工具 ---------- */
async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (apiKey) headers['X-API-Key'] = apiKey;
  const resp = await fetch(path, Object.assign({}, options, { headers }));
  if (resp.status === 401 && !options.retried) {
    const key = prompt('该服务开启了 API Key 保护，请输入 API Key：');
    if (key) {
      apiKey = key.trim();
      localStorage.setItem(KEY_NAME, apiKey);
      return api(path, Object.assign({}, options, { retried: true }));
    }
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try { detail = (await resp.json()).detail || detail; } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json();
}

function toast(message, ok = true) {
  const el = $('#toast');
  el.textContent = message;
  el.className = `fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] rounded-xl border px-5 py-2.5 text-sm shadow-2xl ${
    ok ? 'border-emerald-400/30 bg-[#0d1a14] text-emerald-200'
      : 'border-red-400/30 bg-[#1a0d10] text-red-200'
  }`;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 2600);
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', { hour12: false });
}

function fmtDuration(ms) {
  const totalMin = Math.floor(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return h > 0 ? `${h} 小时 ${m} 分` : `${m} 分钟`;
}

/* ---------- 渲染 ---------- */
let timers = [];

function render(data) {
  $('#player-name').textContent = data.player.nickname;
  if (isShare) {
    $('#share-banner').classList.remove('hidden');
    $('#share-owner').textContent = data.player.nickname;
  } else {
    $('#admin-actions').classList.remove('hidden');
    $('#admin-actions').classList.add('flex');
    $('#share-hint').classList.remove('hidden');
    $('#share-hint').textContent = `分享链接：${location.origin}${location.pathname}?share=${data.player.share_id}`;
  }
  $('#updated-at').textContent = data.updated_at ? `最后更新：${fmtTime(data.updated_at)}` : '';
  renderGame('hsr', data.games.hsr);
  renderGame('wuwa', data.games.wuwa);
  startTimers(data);
}

function statBox(label, value) {
  return `<div class="rounded-lg border border-white/10 bg-white/[0.03] py-2">
    <div class="text-lg font-bold">${Number(value || 0).toLocaleString()}</div>
    <div class="text-[11px] text-slate-500">${label}</div></div>`;
}

function elementBadge(name) {
  const color = ELEMENT_COLORS[name] || '#94a3b8';
  return `<span class="text-[11px] px-1.5 py-0.5 rounded border" style="color:${color};border-color:${color}55;background:${color}15">${esc(name)}</span>`;
}

function renderChart(key, history, theme) {
  if (!history || history.length < 2) return '';
  const W = 300;
  const H = 60;
  const P = 4;
  const maxV = Math.max(...history.map((h) => h.max), 1);
  const pts = history.map((h, i) => {
    const x = P + (i / (history.length - 1)) * (W - 2 * P);
    const y = H - P - (h.current / maxV) * (H - 2 * P);
    return [x, y];
  });
  const line = pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const area = `${P},${H - P} ${line} ${W - P},${H - P}`;
  const last = history[history.length - 1];
  return `
    <div class="mt-3">
      <div class="flex items-center justify-between mb-1">
        <p class="text-xs text-slate-500">体力历史 <span class="text-slate-600">(最近 ${history.length} 条)</span></p>
        <p class="text-[11px] text-slate-600">${fmtTime(last.at)}</p>
      </div>
      <svg viewBox="0 0 ${W} ${H}" class="w-full h-16" preserveAspectRatio="none">
        <defs>
          <linearGradient id="grad-${key}" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="${theme.c1}"></stop>
            <stop offset="1" stop-color="${theme.c2}"></stop>
          </linearGradient>
        </defs>
        <polygon points="${area}" fill="url(#grad-${key})" opacity="0.14"></polygon>
        <polyline points="${line}" fill="none" stroke="url(#grad-${key})" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></polyline>
      </svg>
    </div>`;
}

function renderGame(key, game) {
  const root = $(`#game-${key}`);
  const theme = GAME_THEME[key];
  if (!game) {
    const syncButton = key === 'hsr' && !isShare
      ? `<button class="sync-btn mt-2 rounded-lg border border-amber-300/30 bg-amber-400/10 px-4 py-1.5 text-sm text-amber-200 hover:bg-amber-400/20 transition" data-game="${key}">🔄 米游社一键同步</button>`
      : '';
    root.innerHTML = `
      <div class="rounded-2xl border ${theme.ring} bg-white/[0.04] backdrop-blur p-6 shadow-xl ${theme.glow} flex flex-col items-center justify-center text-center min-h-[280px]">
        <p class="text-3xl">${theme.emoji}</p>
        <p class="mt-3 font-bold">${theme.label}</p>
        <p class="text-xs text-slate-500 mt-1">还没有数据</p>
        ${isShare ? '' : `<button class="update-btn mt-4 rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">⬆ 更新数据</button>${syncButton}`}
      </div>`;
    return;
  }
  const p = game.profile;
  const st = game.stamina;
  const pct = st.max > 0 ? Math.min(100, Math.round((st.current / st.max) * 100)) : 0;
  const sourceLabel = { manual: '手动录入', ocr: '截图 OCR', sync: '自动同步' }[game.last_update?.source] || '历史数据';
  const chars = (game.characters || []).slice(0, 12);
  const charHtml = chars.length
    ? chars.map((c) => `
        <div class="shrink-0 w-24 rounded-xl border border-white/10 bg-white/[0.04] p-2 text-center">
          <div class="text-amber-300 text-sm">${'★'.repeat(Math.max(1, Math.min(5, c.rarity)))}</div>
          <div class="text-sm font-semibold truncate mt-1">${esc(c.name)}</div>
          <div class="text-[11px] text-slate-500">Lv.${c.level}</div>
          ${c.element ? `<div class="mt-1">${elementBadge(c.element)}</div>` : ''}
        </div>`).join('')
    : '<p class="text-xs text-slate-500 py-4">暂无角色数据</p>';
  const resources = Object.entries(game.resources || {});
  const resourceHtml = resources.length
    ? resources.map(([k, v]) => `<span class="rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs">${esc(RESOURCE_LABELS[k] || k)} <b class="text-slate-100">${Number(v).toLocaleString()}</b></span>`).join('')
    : '<span class="text-xs text-slate-500">暂无资源数据</span>';
  const syncButton = key === 'hsr' && !isShare
    ? `<button class="sync-btn rounded-lg border border-amber-300/30 bg-amber-400/10 px-2.5 py-1 text-[11px] text-amber-200 hover:bg-amber-400/20 transition" data-game="${key}">🔄 米游社同步</button>`
    : '';
  const chartHtml = renderChart(key, game.history, theme);

  root.innerHTML = `
    <div class="rounded-2xl border ${theme.ring} bg-white/[0.04] backdrop-blur p-5 shadow-xl ${theme.glow}">
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="text-xl">${theme.emoji}</span>
          <div>
            <h3 class="font-bold">${theme.label}${p.nickname ? ` · ${esc(p.nickname)}` : ''}</h3>
            <p class="text-xs text-slate-500">UID ${esc(p.uid) || '未绑定'}</p>
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          ${syncButton}
          ${game.last_update ? `<span class="rounded-full border ${theme.chip} px-2 py-0.5 text-[11px]">${sourceLabel}</span>` : ''}
        </div>
      </div>

      <div class="mt-4 rounded-xl border border-white/10 bg-black/25 p-4">
        <div class="flex items-end justify-between">
          <div>
            <p class="text-xs text-slate-500">${esc(st.name)}</p>
            <p class="text-2xl font-black mt-0.5">${st.current}<span class="text-sm font-medium text-slate-500"> / ${st.max}</span></p>
          </div>
          <p id="cd-${key}" class="text-xs text-slate-400">${st.full ? '已回满 ✓' : '计算中…'}</p>
        </div>
        <div class="mt-2 h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r ${theme.bar} transition-all duration-700" style="width:${pct}%"></div>
        </div>
      </div>

      <div class="mt-3 grid grid-cols-3 gap-2 text-center">
        ${statBox('等级', p.level)}${statBox('活跃天数', p.active_days)}${statBox('成就', p.achievements)}
      </div>

      <div class="mt-3 flex flex-wrap gap-1.5">${resourceHtml}</div>

      <div class="mt-4">
        <p class="text-xs text-slate-500 mb-2">角色图鉴 <span class="text-slate-600">(${(game.characters || []).length} 名)</span></p>
        <div class="flex gap-2 overflow-x-auto pb-1">${charHtml}</div>
      </div>

      ${chartHtml}

      ${game.last_update ? `<p class="mt-3 text-[11px] text-slate-600">最近更新：${fmtTime(game.last_update.at)} · 共 ${game.snapshot_count} 条记录</p>` : ''}
    </div>`;
}

function startTimers(data) {
  timers.forEach(clearInterval);
  timers = [];
  for (const key of ['hsr', 'wuwa']) {
    const game = data.games[key];
    if (!game || game.stamina.full || !game.stamina.full_at) continue;
    const fullAt = new Date(game.stamina.full_at);
    const el = $(`#cd-${key}`);
    if (!el) continue;
    const tick = () => {
      const ms = fullAt.getTime() - Date.now();
      el.textContent = ms <= 0 ? '已回满 ✓' : `约 ${fmtDuration(ms)} 后回满`;
    };
    tick();
    timers.push(setInterval(tick, 30000));
  }
}

/* ---------- 更新弹窗 ---------- */
let editorGame = 'hsr';
let ocrUsed = false;

function openModal(game) {
  editorGame = game || editorGame;
  ocrUsed = false;
  setGameTab(editorGame);
  clearForm();
  $('#modal').classList.remove('hidden');
}

function closeModal() {
  $('#modal').classList.add('hidden');
}

function setGameTab(game) {
  editorGame = game;
  document.querySelectorAll('.game-tab').forEach((btn) => {
    const active = btn.dataset.game === game;
    btn.className = `game-tab rounded-xl border py-2.5 text-sm font-semibold transition ${
      active ? 'border-violet-400/60 bg-gradient-to-r from-violet-500/30 to-cyan-500/30'
             : 'border-white/10 bg-white/5'
    }`;
  });
}

function clearForm() {
  for (const id of ['f-uid', 'f-nickname', 'f-level', 'f-days', 'f-ach', 'f-stamina', 'f-resources']) {
    $(`#${id}`).value = '';
  }
  $('#f-stamina-max').value = '240';
  $('#char-list').innerHTML = '';
  $('#ocr-status').classList.add('hidden');
  $('#ocr-raw').classList.add('hidden');
  $('#ocr-raw-text').textContent = '';
}

function fillForm(parsed) {
  $('#f-uid').value = parsed.uid || '';
  $('#f-level').value = parsed.level ?? '';
  $('#f-days').value = parsed.active_days ?? '';
  $('#f-ach').value = parsed.achievements ?? '';
  $('#f-stamina').value = parsed.stamina_current ?? '';
  $('#f-stamina-max').value = parsed.stamina_max ?? 240;
}

const FIELD_LABELS = {
  uid: 'UID', level: '等级', active_days: '活跃天数', achievements: '成就数',
  stamina_current: '体力', stamina_max: '体力上限', characters: '角色数量',
};

function setOcrStatus(message, ok = null) {
  const el = $('#ocr-status');
  el.textContent = message;
  el.className = `mt-3 rounded-xl border px-4 py-3 text-sm ${
    ok === false ? 'border-red-400/30 bg-red-400/10 text-red-200'
    : ok === true ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
    : 'border-white/10 bg-white/5 text-slate-300'
  }`;
  el.classList.remove('hidden');
}

async function handleFile(file) {
  if (!file) return;
  setOcrStatus('⏳ 正在识别，请稍候（首次使用需下载模型，可能较慢）…');
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await api(`/api/upload/${editorGame}`, { method: 'POST', body: fd });
    if (res.saved) {
      closeModal();
      toast('已保存（OCR 自动入库，建议稍后人工核对）');
      await load();
      return;
    }
    ocrUsed = true;
    fillForm(res.parsed);
    $('#ocr-raw').classList.remove('hidden');
    $('#ocr-raw-text').textContent = res.ocr_text;
    const missing = res.parsed.missing_fields || [];
    setOcrStatus(
      missing.length
        ? `⚠ 识别完成，但未识别出：${missing.map((k) => FIELD_LABELS[k] || k).join('、')}，请手动补齐`
        : '✓ 识别完成，请核对数字后保存',
      missing.length === 0,
    );
  } catch (err) {
    setOcrStatus(`❌ ${err.message}`, false);
  }
}

function addCharRow(ch = {}) {
  const row = document.createElement('div');
  row.className = 'grid grid-cols-12 gap-2 items-center';
  row.innerHTML = `
    <input class="field col-span-4 char-name" placeholder="角色名" value="${esc(ch.name || '')}" />
    <input class="field col-span-2 char-rarity" type="number" min="1" max="6" placeholder="稀有度" value="${ch.rarity || 4}" />
    <input class="field col-span-2 char-level" type="number" min="1" max="120" placeholder="等级" value="${ch.level || 1}" />
    <input class="field col-span-3 char-element" placeholder="属性（冰/风…）" value="${esc(ch.element || '')}" />
    <button type="button" class="col-span-1 h-9 rounded-lg border border-white/10 text-slate-400 hover:text-red-300 hover:border-red-400/40 transition char-del">✕</button>`;
  row.querySelector('.char-del').addEventListener('click', () => row.remove());
  $('#char-list').appendChild(row);
}

function collectForm() {
  const chars = [...document.querySelectorAll('#char-list > div')]
    .map((row) => ({
      name: row.querySelector('.char-name').value.trim(),
      rarity: Number(row.querySelector('.char-rarity').value) || 4,
      level: Number(row.querySelector('.char-level').value) || 1,
      element: row.querySelector('.char-element').value.trim(),
    }))
    .filter((c) => c.name);
  let resources = {};
  const raw = $('#f-resources').value.trim();
  if (raw) {
    try {
      resources = JSON.parse(raw);
    } catch (e) {
      throw new Error('资源 JSON 格式错误，请检查后重试');
    }
  }
  return {
    uid: $('#f-uid').value.trim(),
    nickname: $('#f-nickname').value.trim(),
    level: Number($('#f-level').value) || 0,
    active_days: Number($('#f-days').value) || 0,
    achievements: Number($('#f-ach').value) || 0,
    stamina_current: Number($('#f-stamina').value) || 0,
    stamina_max: Number($('#f-stamina-max').value) || 240,
    resources,
    characters: chars,
    source: ocrUsed ? 'ocr' : 'manual',
  };
}

/* ---------- 事件绑定 ---------- */
$('#btn-update')?.addEventListener('click', () => openModal('hsr'));
$('#btn-share')?.addEventListener('click', async () => {
  try {
    const data = await api('/api/me');
    const url = `${location.origin}${location.pathname}?share=${data.player.share_id}`;
    await navigator.clipboard.writeText(url);
    toast('分享链接已复制到剪贴板');
  } catch (err) {
    toast(`复制失败：${err.message}`, false);
  }
});

document.querySelectorAll('.game-tab').forEach((btn) =>
  btn.addEventListener('click', () => setGameTab(btn.dataset.game))
);
document.querySelectorAll('[data-close]').forEach((el) =>
  el.addEventListener('click', closeModal)
);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});

const dz = $('#dropzone');
const fileInput = $('#file-input');
dz.addEventListener('click', () => fileInput.click());
dz.addEventListener('dragover', (e) => {
  e.preventDefault();
  dz.classList.add('border-violet-400/70');
});
dz.addEventListener('dragleave', () => dz.classList.remove('border-violet-400/70'));
dz.addEventListener('drop', (e) => {
  e.preventDefault();
  dz.classList.remove('border-violet-400/70');
  handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
  handleFile(fileInput.files[0]);
  fileInput.value = '';
});

$('#btn-add-char').addEventListener('click', () => addCharRow());
$('#editor').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const payload = collectForm();
    await api(`/api/profiles/${editorGame}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    closeModal();
    toast('数据已保存');
    await load();
  } catch (err) {
    toast(err.message, false);
  }
});

document.body.addEventListener('click', (e) => {
  const btn = e.target.closest('.update-btn');
  if (btn) openModal(btn.dataset.game);
  const syncBtn = e.target.closest('.sync-btn');
  if (syncBtn) syncHsr(syncBtn);
});

async function syncHsr(btn) {
  btn.disabled = true;
  btn.textContent = '同步中…';
  try {
    await api('/api/sync/hsr', { method: 'POST' });
    toast('星穹铁道数据已同步');
    await load();
  } catch (err) {
    toast(err.message, false);
    btn.disabled = false;
    btn.textContent = '🔄 米游社同步';
  }
}

/* ---------- 启动 ---------- */
async function load() {
  try {
    const data = isShare
      ? await api(`/api/share/${encodeURIComponent(shareId)}`)
      : await api('/api/me');
    render(data);
  } catch (err) {
    $('#player-name').textContent = '加载失败';
    $('#updated-at').textContent = err.message;
    toast(err.message, false);
  }
}

load();
