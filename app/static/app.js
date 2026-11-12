/* StarWaves 前端逻辑：管理页与分享页共用一套渲染。
   游戏卡片、更新弹窗页签、主题色全部由后端注册表（/api/games）动态渲染，
   新增游戏无需改动本文件。 */

const KEY_NAME = 'starwaves_api_key';
let apiKey = localStorage.getItem(KEY_NAME) || '';

const params = new URLSearchParams(location.search);
const pathShare = location.pathname.match(/^\/share\/([A-Za-z0-9_-]+)/);
const shareId = params.get('share') || (pathShare ? decodeURIComponent(pathShare[1]) : null);
const isShare = Boolean(shareId);

const $ = (sel) => document.querySelector(sel);

let REGISTRY = [];

/* 注册表接口不可用时的兜底主题（与后端 games.py 保持一致） */
const FALLBACK_THEMES = {
  hsr: { label: '星穹铁道', emoji: '🚂', c1: '#fcd34d', c2: '#8b5cf6', stamina_name: '开拓力', cap: 240, syncable: true },
  wuwa: { label: '鸣潮', emoji: '🌊', c1: '#67e8f9', c2: '#3b82f6', stamina_name: '结晶波片', cap: 240, syncable: false },
  zzz: { label: '绝区零', emoji: '⚡', c1: '#fbbf24', c2: '#06b6d4', stamina_name: '电量', cap: 240, syncable: false },
};

function specOf(key) {
  const spec = REGISTRY.find((g) => g.key === key);
  if (spec) return spec;
  const fallback = FALLBACK_THEMES[key] || {};
  return {
    key,
    label: fallback.label || key,
    emoji: fallback.emoji || '🎮',
    tagline: '',
    stamina_name: fallback.stamina_name || '体力',
    cap: fallback.cap || 240,
    syncable: Boolean(fallback.syncable),
    custom: false,
    launchable: true,
    news: true,
    colors: { a: fallback.c1 || '#a78bfa', b: fallback.c2 || '#67e8f9' },
    resource_labels: {},
  };
}

const ELEMENT_COLORS = {
  物理: '#e5e7eb', 风: '#4ade80', 雷: '#a78bfa', 冰: '#7dd3fc', 火: '#f87171',
  量子: '#c084fc', 虚数: '#fde047',
  冷凝: '#7dd3fc', 热熔: '#f87171', 导电: '#a78bfa', 衍射: '#fde047', 气动: '#4ade80', 湮灭: '#94a3b8',
  电: '#a78bfa', 以太: '#c084fc',
};

const RESOURCE_LABELS = {
  jades: '星琼', credits: '信用点', starlight: '星芒', embers: '余烬',
  special_pass: '星轨专票', star_pass: '星轨通票',
  astrites: '星声', shell_credits: '贝币', waveplates: '结晶波片',
  polychrome: '菲林', denny: '丁尼', master_tape: '加密母带',
  boopons: '邦布券', battery: '电量',
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

async function loadRegistry() {
  try {
    const res = await fetch('/api/games');
    if (res.ok) REGISTRY = (await res.json()).games || [];
  } catch (e) {
    REGISTRY = [];
  }
  buildGameTabs();
}

function buildGameTabs() {
  const box = $('#game-tabs');
  if (!box) return;
  box.innerHTML = REGISTRY.map(
    (g) => `<button type="button" data-game="${esc(g.key)}" class="game-tab rounded-xl border py-2.5 text-sm font-semibold transition ${g.key === editorGame ? 'border-violet-400/60 bg-gradient-to-r from-violet-500/30 to-cyan-500/30' : 'border-white/10 bg-white/5'}">${esc(g.emoji)} ${esc(g.label)}</button>`
  ).join('');
  box.querySelectorAll('.game-tab').forEach((btn) =>
    btn.addEventListener('click', () => setGameTab(btn.dataset.game))
  );
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

function applyBackground() {
  const img = new Image();
  img.onload = () => {
    document.body.style.backgroundImage =
      `linear-gradient(rgba(5,7,15,.78), rgba(5,7,15,.78)), url('/api/background?t=${Date.now()}')`;
    document.body.style.backgroundSize = 'cover';
    document.body.style.backgroundPosition = 'center';
    document.body.style.backgroundAttachment = 'fixed';
  };
  img.src = '/api/background';
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
    $('#share-hint').textContent = `分享链接：${location.origin}/share/${data.player.share_id}`;
  }
  $('#updated-at').textContent = data.updated_at ? `最后更新：${fmtTime(data.updated_at)}` : '';

  const games = data.games || {};
  const keys = REGISTRY.map((g) => g.key);
  Object.keys(games).forEach((k) => { if (!keys.includes(k)) keys.push(k); });
  if (!keys.length) keys.push('hsr', 'wuwa');

  const grid = $('#games-grid');
  grid.className = `mt-6 grid gap-6 ${keys.length >= 3 ? 'md:grid-cols-2 xl:grid-cols-3' : 'md:grid-cols-2'}`;
  grid.innerHTML = keys.map((k) => `<div id="game-${esc(k)}"></div>`).join('');
  keys.forEach((k) => renderGame(specOf(k), games[k]));
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
function renderGame(spec, game) {
  const key = spec.key;
  const root = $(`#game-${key}`);
  if (!root) return;
  const a = spec.colors.a;
  const b = spec.colors.b;
  const theme = { c1: a, c2: b };
  const cardStyle = `border-color:${a}45;box-shadow:0 18px 50px -18px ${b}66`;

  if (!game) {
    const syncButton = spec.syncable && !isShare
      ? `<button class="sync-btn mt-2 rounded-lg border px-4 py-1.5 text-sm transition" style="border-color:${a}55;color:${a};background:${a}14" data-game="${key}">🔄 米游社同步</button>`
      : '';
    const removeButton = spec.custom && !isShare
      ? `<button class="remove-btn rounded-lg border border-red-400/30 bg-red-400/10 px-2.5 py-1 text-[11px] text-red-300 hover:bg-red-400/20 transition" data-game="${key}" title="移除该游戏">✕</button>`
      : '';
    const launchButton = spec.launchable !== false && !isShare
      ? `<button class="launch-btn rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">🚀 启动游戏</button>`
      : '';
    root.innerHTML = `
      <div class="rounded-2xl border bg-white/[0.04] backdrop-blur p-6 flex flex-col items-center justify-center text-center min-h-[280px]" style="${cardStyle}">
        <div class="self-end -mt-2 -mr-2">${removeButton}</div>
        <p class="text-3xl">${esc(spec.emoji)}</p>
        <p class="mt-3 font-bold">${esc(spec.label)}</p>
        <p class="text-xs text-slate-500 mt-1">${esc(spec.tagline || '还没有数据')}${spec.custom ? ' · 自定义接入' : ''}</p>
        ${isShare ? '' : `<div class="mt-4 flex gap-2 flex-wrap justify-center"><button class="update-btn rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">⬆ 更新数据</button>${syncButton}${launchButton}</div>`}
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
  const labels = Object.assign({}, RESOURCE_LABELS, spec.resource_labels || {});
  const resources = Object.entries(game.resources || {});
  const resourceHtml = resources.length
    ? resources.map(([k, v]) => `<span class="rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] text-slate-300">${esc(labels[k] || k)} <b class="text-slate-100">${Number(v || 0).toLocaleString()}</b></span>`).join('')
    : '<span class="text-[11px] text-slate-600">暂无资源数据</span>';

  const syncButton = spec.syncable && !isShare
    ? `<button class="sync-btn rounded-lg border px-2.5 py-1 text-[11px] transition" style="border-color:${a}55;color:${a};background:${a}14" data-game="${key}">🔄 米游社同步</button>`
    : '';
  const launchButton = spec.launchable !== false && !isShare
    ? `<button class="launch-btn rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] hover:bg-white/10 transition" data-game="${key}">🚀 启动游戏</button>`
    : '';
  const removeButton = spec.custom && !isShare
    ? `<button class="remove-btn rounded-lg border border-red-400/30 bg-red-400/10 px-2 py-0.5 text-[11px] text-red-300 hover:bg-red-400/20 transition" data-game="${key}" title="移除该游戏">✕</button>`
    : '';
  const chartHtml = renderChart(key, game.history, theme);

  root.innerHTML = `
    <div class="rounded-2xl border bg-white/[0.04] backdrop-blur p-5" style="${cardStyle}">
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-center gap-2">
          <span class="text-xl">${esc(spec.emoji)}</span>
          <div>
            <h3 class="font-bold">${esc(spec.label)}${p.nickname ? ` · ${esc(p.nickname)}` : ''}${spec.custom ? ` <span class="rounded-full border px-1.5 py-0.5 text-[10px] font-normal" style="color:${a};border-color:${a}55;background:${a}15">自定义</span>` : ''}</h3>
            <p class="text-xs text-slate-500">UID ${esc(p.uid) || '未绑定'}</p>
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          ${launchButton}
          ${removeButton}
          ${syncButton}
          ${game.last_update ? `<span class="rounded-full border px-2 py-0.5 text-[11px]" style="color:${a};border-color:${a}55;background:${a}15">${sourceLabel}</span>` : ''}
        </div>
      </div>

      <div class="mt-4 rounded-xl border border-white/10 bg-black/25 p-4">
        <div class="flex items-end justify-between">
          <div>
            <p class="text-xs text-slate-500">${esc(st.name || spec.stamina_name)}</p>
            <p class="text-2xl font-black mt-0.5">${st.current}<span class="text-sm font-medium text-slate-500"> / ${st.max}</span></p>
          </div>
          <p id="cd-${key}" class="text-xs text-slate-400">${st.full ? '已回满 ✓' : '计算中…'}</p>
        </div>
        <div class="mt-2 h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full transition-all duration-700" style="width:${pct}%;background:linear-gradient(90deg,${a},${b})"></div>
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
  for (const key of Object.keys(data.games || {})) {
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
  editorGame = game || (REGISTRY[0] && REGISTRY[0].key) || editorGame;
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
  const spec = specOf(game);
  document.querySelectorAll('.game-tab').forEach((btn) => {
    const active = btn.dataset.game === game;
    btn.className = `game-tab rounded-xl border py-2.5 text-sm font-semibold transition ${
      active ? 'border-violet-400/60 bg-gradient-to-r from-violet-500/30 to-cyan-500/30'
             : 'border-white/10 bg-white/5'
    }`;
  });
  if ($('#lbl-level')) $('#lbl-level').textContent = `${spec.label}等级`;
  if ($('#lbl-stamina')) $('#lbl-stamina').textContent = `${spec.stamina_name}当前`;
  if ($('#lbl-stamina-max')) $('#lbl-stamina-max').textContent = `${spec.stamina_name}上限`;
  $('#f-stamina-max').value = spec.cap || 240;
}

function clearForm() {
  for (const id of ['f-uid', 'f-nickname', 'f-level', 'f-days', 'f-ach', 'f-stamina', 'f-resources']) {
    $(`#${id}`).value = '';
  }
  $('#f-stamina-max').value = specOf(editorGame).cap || 240;
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
  $('#f-stamina-max').value = parsed.stamina_max ?? (specOf(editorGame).cap || 240);
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
    stamina_max: Number($('#f-stamina-max').value) || (specOf(editorGame).cap || 240),
    resources,
    characters: chars,
    source: ocrUsed ? 'ocr' : 'manual',
  };
}

/* ---------- 事件绑定 ---------- */
$('#btn-update')?.addEventListener('click', () => openModal());
$('#btn-share')?.addEventListener('click', async () => {
  try {
    const data = await api('/api/me');
    const url = `${location.origin}/share/${data.player.share_id}`;
    await navigator.clipboard.writeText(url);
    toast('分享链接已复制到剪贴板');
  } catch (err) {
    toast(`复制失败：${err.message}`, false);
  }
});

document.querySelectorAll('[data-close]').forEach((el) =>
  el.addEventListener('click', closeModal)
);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
    $('#add-game-modal')?.classList.add('hidden');
  }
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
  const removeBtn = e.target.closest('.remove-btn');
  if (removeBtn) removeGame(removeBtn);
  const syncBtn = e.target.closest('.sync-btn');
  if (syncBtn) syncGame(syncBtn);
  const launchBtn = e.target.closest('.launch-btn');
  if (launchBtn) launchGame(launchBtn);
});

/* ---------- 接入游戏 ---------- */
$('#btn-add-game')?.addEventListener('click', () => {
  $('#add-game-form').reset();
  $('#ag-cap').value = '240';
  $('#ag-minutes').value = '6';
  $('#ag-color-a').value = '#a78bfa';
  $('#ag-color-b').value = '#67e8f9';
  $('#add-game-modal').classList.remove('hidden');
});
document.querySelectorAll('[data-add-game-close]').forEach((el) =>
  el.addEventListener('click', () => $('#add-game-modal').classList.add('hidden'))
);

$('#add-game-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  let resourceLabels = {};
  const raw = $('#ag-resources').value.trim();
  if (raw) {
    try {
      resourceLabels = JSON.parse(raw);
    } catch (err) {
      toast('资源标签 JSON 格式错误，请检查后重试', false);
      return;
    }
  }
  const payload = {
    key: $('#ag-key').value.trim().toLowerCase(),
    label: $('#ag-label').value.trim(),
    tagline: $('#ag-tagline').value.trim(),
    emoji: $('#ag-emoji').value.trim() || '🎮',
    stamina_name: $('#ag-stamina').value.trim() || '体力',
    minutes_per_point: Number($('#ag-minutes').value) || 6,
    cap: Number($('#ag-cap').value) || 240,
    color_a: $('#ag-color-a').value,
    color_b: $('#ag-color-b').value,
    resource_labels: resourceLabels,
  };
  try {
    await api('/api/games', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    $('#add-game-modal').classList.add('hidden');
    toast(`✓ 已接入 ${payload.label}，现在就能录入数据`);
    await loadRegistry();
    await load();
  } catch (err) {
    toast(err.message, false);
  }
});

async function removeGame(btn) {
  const key = btn.dataset.game;
  const label = specOf(key).label;
  if (!confirm(`确定移除「${label}」吗？已有游戏数据时无法移除（避免历史记录丢失）。`)) return;
  btn.disabled = true;
  try {
    await api(`/api/games/${encodeURIComponent(key)}`, { method: 'DELETE' });
    toast(`已移除 ${label}`);
    await loadRegistry();
    await load();
  } catch (err) {
    toast(err.message, false);
    btn.disabled = false;
  }
}

async function syncGame(btn) {
  const game = btn.dataset.game;
  const label = specOf(game).label;
  btn.disabled = true;
  btn.textContent = '同步中…';
  try {
    await api(`/api/sync/${game}`, { method: 'POST' });
    toast(`${label}数据已同步`);
    await load();
  } catch (err) {
    toast(err.message, false);
    btn.disabled = false;
    btn.textContent = '🔄 米游社同步';
  }
}

async function launchGame(btn) {
  btn.disabled = true;
  const game = btn.dataset.game;
  const label = specOf(game).label;
  btn.textContent = '启动中…';
  try {
    await api(`/api/launch/${game}`, { method: 'POST' });
    toast(`🚀 ${label}已启动`);
    setTimeout(() => { btn.disabled = false; btn.textContent = '🚀 启动游戏'; }, 2500);
  } catch (err) {
    toast(err.message, false);
    btn.disabled = false;
    btn.textContent = '🚀 启动游戏';
  }
}

/* ---------- 背景设置 ---------- */
$('#btn-bg')?.addEventListener('click', () => {
  $('#bg-modal').classList.remove('hidden');
});
document.querySelectorAll('[data-bg-close]').forEach((el) =>
  el.addEventListener('click', () => $('#bg-modal').classList.add('hidden'))
);
const bgDz = $('#bg-dropzone');
const bgInput = $('#bg-input');
bgDz.addEventListener('click', () => bgInput.click());
bgDz.addEventListener('dragover', (e) => { e.preventDefault(); bgDz.classList.add('border-violet-400/70'); });
bgDz.addEventListener('dragleave', () => bgDz.classList.remove('border-violet-400/70'));
bgDz.addEventListener('drop', (e) => { e.preventDefault(); bgDz.classList.remove('border-violet-400/70'); uploadBackground(e.dataTransfer.files[0]); });
bgInput.addEventListener('change', () => { uploadBackground(bgInput.files[0]); bgInput.value = ''; });

async function uploadBackground(file) {
  if (!file) return;
  const status = $('#bg-status');
  status.textContent = '⏳ 正在上传…';
  status.className = 'mt-3 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm';
  status.classList.remove('hidden');
  const fd = new FormData();
  fd.append('file', file);
  try {
    await api('/api/background', { method: 'POST', body: fd });
    applyBackground();
    status.textContent = '✓ 背景已更新';
    status.className = 'mt-3 rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200';
    toast('背景已更新');
  } catch (err) {
    status.textContent = `❌ ${err.message}`;
    status.className = 'mt-3 rounded-xl border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-200';
  }
}

$('#btn-bg-reset')?.addEventListener('click', async () => {
  try {
    await api('/api/background', { method: 'DELETE' });
    document.body.style.backgroundImage = '';
    $('#bg-status').classList.add('hidden');
    toast('已恢复默认背景');
  } catch (err) {
    toast(err.message, false);
  }
});

/* ---------- 启动 ---------- */
async function load() {
  try {
    if (!REGISTRY.length) await loadRegistry();
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

applyBackground();
load();
