/* StarWaves 前端逻辑：管理页与分享页共用一套渲染。
   游戏卡片、更新弹窗页签、主题色全部由后端注册表（/api/games）动态渲染，
   新增游戏无需改动本文件。 */

const KEY_NAME = 'starwaves_api_key';
const TOKEN_KEY = 'starwaves_token';
const USER_KEY = 'starwaves_user';
let apiKey = localStorage.getItem(KEY_NAME) || '';
let authToken = localStorage.getItem(TOKEN_KEY) || '';

/* API 基址：本机直接走相对路径；托管在 GitHub Pages 时回落调用本机后端（需本机服务已启动）。 */
const API_BASE = /^(127\.0\.0\.1|localhost)$/.test(location.hostname) ? '' : 'http://127.0.0.1:8000';

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
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  const resp = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
  if (resp.status === 401 && !options.retried) {
    let detail = '';
    try { detail = (await resp.json()).detail || ''; } catch (e) { /* ignore */ }
    if (detail && detail.includes('API Key')) {
    const key = prompt('该服务开启了 API Key 保护，请输入 API Key：');
    if (key) {
      apiKey = key.trim();
      localStorage.setItem(KEY_NAME, apiKey);
      return api(path, Object.assign({}, options, { retried: true }));
    }
    } else if (!isShare && !options.silent) {
      setLoggedOut('登录已失效，请重新登录', true);
      throw new Error('请先登录');
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
    const res = await fetch(API_BASE + '/api/games');
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

/* ---------- 账号：登录 / 手机验证码注册 / 退出 ---------- */
function showAuthModal(tab = 'login') {
  $('#auth-modal').classList.remove('hidden');
  setAuthTab(tab);
}

function setAuthTab(tab) {
  const isLogin = tab === 'login';
  $('#auth-tab-login').className = `auth-tab rounded-lg py-2 text-sm font-semibold transition ${isLogin ? 'bg-gradient-to-r from-violet-500/40 to-cyan-500/40 text-white' : 'text-slate-400 hover:text-white'}`;
  $('#auth-tab-register').className = `auth-tab rounded-lg py-2 text-sm font-semibold transition ${!isLogin ? 'bg-gradient-to-r from-violet-500/40 to-cyan-500/40 text-white' : 'text-slate-400 hover:text-white'}`;
  $('#login-form').classList.toggle('hidden', !isLogin);
  $('#register-form').classList.toggle('hidden', isLogin);
  $('#login-error').classList.add('hidden');
  $('#register-error').classList.add('hidden');
}

function updateAuthUI(user) {
  if (!user || !authToken) {
    $('#btn-login').classList.remove('hidden');
    $('#auth-userbox').classList.add('hidden');
    $('#auth-userbox').classList.remove('flex');
    return;
  }
  $('#btn-login').classList.add('hidden');
  $('#auth-userbox').classList.remove('hidden');
  $('#auth-userbox').classList.add('flex');
  $('#auth-user').textContent = `👤 ${user.username}`;
}

function setLoggedOut(message, openModal = false) {
  authToken = '';
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  updateAuthUI(null);
  if (!isShare) showLocked();
  if (message) toast(message, false);
  if (openModal) showAuthModal('login');
}

function showLocked() {
  $('#admin-actions').classList.add('hidden');
  $('#admin-actions').classList.remove('flex');
  $('#share-hint').classList.add('hidden');
  $('#player-name').textContent = '未登录';
  $('#updated-at').textContent = '登录后可查看和管理你的游戏档案';
  $('#games-grid').innerHTML = '';
  $('#locked-view').classList.remove('hidden');
}

function enterSession(data) {
  authToken = data.token;
  localStorage.setItem(TOKEN_KEY, authToken);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  updateAuthUI(data.user);
  $('#auth-modal').classList.add('hidden');
  $('#locked-view').classList.add('hidden');
  toast(`✓ 欢迎，${data.user.username}`);
  loadRegistry();
  load();
}

let sendCooldown = 0;

async function handleSendCode() {
  const phone = $('#re-phone').value.trim();
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    $('#register-error').textContent = '请输入正确的 11 位手机号';
    $('#register-error').classList.remove('hidden');
    return;
  }
  const btn = $('#btn-send-code');
  btn.disabled = true;
  try {
    const res = await api('/api/auth/send-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone }),
      silent: true,
    });
    $('#code-hint').textContent = `开发模式验证码：${res.dev_code}（未接入短信服务，生产环境请接入真实短信）`;
    $('#code-hint').classList.remove('hidden');
    $('#register-error').classList.add('hidden');
    toast('验证码已发送（开发模式）');
    sendCooldown = 60;
    btn.textContent = `${sendCooldown}s`;
    const timer = setInterval(() => {
      sendCooldown -= 1;
      if (sendCooldown <= 0) {
        clearInterval(timer);
        btn.disabled = false;
        btn.textContent = '发送验证码';
      } else {
        btn.textContent = `${sendCooldown}s`;
      }
    }, 1000);
  } catch (err) {
    btn.disabled = false;
    $('#register-error').textContent = err.message;
    $('#register-error').classList.remove('hidden');
  }
}

$('#btn-login')?.addEventListener('click', () => showAuthModal('login'));
$('#btn-login-locked')?.addEventListener('click', () => showAuthModal('login'));
$('#auth-tab-login')?.addEventListener('click', () => setAuthTab('login'));
$('#auth-tab-register')?.addEventListener('click', () => setAuthTab('register'));
$('#btn-send-code')?.addEventListener('click', handleSendCode);
document.querySelectorAll('[data-auth-close]').forEach((el) =>
  el.addEventListener('click', () => $('#auth-modal').classList.add('hidden'))
);

$('#login-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account: $('#li-account').value.trim(), password: $('#li-password').value }),
      silent: true,
    });
    enterSession(data);
  } catch (err) {
    $('#login-error').textContent = err.message;
    $('#login-error').classList.remove('hidden');
  }
});

$('#register-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const phone = $('#re-phone').value.trim();
  const code = $('#re-code').value.trim();
  const password = $('#re-password').value;
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    $('#register-error').textContent = '请输入正确的 11 位手机号';
    $('#register-error').classList.remove('hidden');
    return;
  }
  if (!/^\d{6}$/.test(code)) {
    $('#register-error').textContent = '请输入 6 位验证码';
    $('#register-error').classList.remove('hidden');
    return;
  }
  if (password.length < 6) {
    $('#register-error').textContent = '密码至少 6 位';
    $('#register-error').classList.remove('hidden');
    return;
  }
  try {
    const data = await api('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, code, username: $('#re-username').value.trim(), password }),
      silent: true,
    });
    enterSession(data);
  } catch (err) {
    $('#register-error').textContent = err.message;
    $('#register-error').classList.remove('hidden');
  }
});

$('#btn-logout')?.addEventListener('click', async () => {
  try {
    await api('/api/auth/logout', { method: 'POST', silent: true });
  } catch (e) { /* token 可能已失效，忽略 */ }
  setLoggedOut('已退出登录');
});

function applyBackground() {
  const img = new Image();
  img.onload = () => {
    document.body.style.backgroundImage =
      `linear-gradient(rgba(5,7,15,.78), rgba(5,7,15,.78)), url('${API_BASE}/api/background?t=${Date.now()}')`;
    document.body.style.backgroundSize = 'cover';
    document.body.style.backgroundPosition = 'center';
    document.body.style.backgroundAttachment = 'fixed';
  };
  img.src = API_BASE + '/api/background';
}

function shareUrlOf(shareId) {
  const base = API_BASE || location.origin;
  return `${base}/share/${shareId}`;
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
let CURRENT = null;

function render(data) {
  CURRENT = data;
  $('#player-name').textContent = data.player.nickname;
  $('#locked-view').classList.add('hidden');
  if (isShare) {
    $('#share-banner').classList.remove('hidden');
    $('#share-owner').textContent = data.player.nickname;
  } else {
    if (data.user) updateAuthUI(data.user);
    $('#admin-actions').classList.remove('hidden');
    $('#admin-actions').classList.add('flex');
    $('#share-hint').classList.remove('hidden');
    $('#share-hint').textContent = `分享链接：${shareUrlOf(data.player.share_id)}`;
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

function renderChallenges(challenges, theme) {
  const entries = Object.entries(challenges || {});
  if (!entries.length) return '';
  const sections = entries.map(([key, sec]) => {
    if (!sec || !sec.name) return '';
    const progress = sec.progress || {};
    let head = '';
    if (progress.max > 0) {
      const pct = Math.min(100, Math.round(((progress.current || 0) / progress.max) * 100));
      head = `<div class="mt-2 h-1.5 rounded-full bg-white/10 overflow-hidden"><div class="h-full rounded-full transition-all duration-700" style="width:${pct}%;background:linear-gradient(90deg,${theme.c1},${theme.c2})"></div></div>`;
    }
    const nodes = (sec.nodes || []).map((n) => {
      let mark = `<b>${Number(n.value || 0)}</b>`;
      if (progress.unit === '星') {
        const filled = '★'.repeat(Math.max(0, Math.min(n.value || 0, n.max || 0)));
        const empty = '☆'.repeat(Math.max(0, (n.max || 0) - (n.value || 0)));
        mark = `<span class="text-amber-300">${filled}</span><span class="text-slate-600">${empty}</span>`;
      }
      return `<div class="flex items-center justify-between gap-2 text-[11px] py-0.5"><span class="text-slate-400 truncate">${esc(n.name)}</span><span class="text-slate-200 whitespace-nowrap">${mark}${n.max ? ` <span class="text-slate-600">/${n.max}</span>` : ''}</span></div>`;
    }).join('');
    const stats = (sec.stats || []).map((s) =>
      `<span class="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300">${esc(s.label)} <b class="text-slate-100">${Number(s.value || 0).toLocaleString()}</b></span>`
    ).join('');
    const records = (sec.records || []).map((r) =>
      `<div class="flex items-center justify-between gap-2 text-[11px] py-0.5"><span class="text-slate-400 truncate">${esc(r.name)}</span><span class="text-slate-200 whitespace-nowrap">${r.finished ? '✓ ' : ''}${Number(r.score || 0).toLocaleString()}</span></div>`
    ).join('');
    const progressText = progress.max ? `${progress.current} / ${progress.max} ${progress.unit}` : '';
    return `<div class="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div class="flex items-center justify-between gap-2">
        <p class="text-xs font-semibold">⚔ ${esc(sec.name)}</p>
        <span class="text-[10px] text-slate-500 whitespace-nowrap">${sec.season ? esc(sec.season) + ' · ' : ''}${progressText}</span>
      </div>
      ${head}
      ${nodes}
      ${stats ? `<div class="mt-2 flex flex-wrap gap-1.5">${stats}</div>` : ''}
      ${records}
    </div>`;
  }).filter(Boolean).join('');
  if (!sections) return '';
  return `<div class="mt-4"><p class="text-xs text-slate-500 mb-2">挑战进度</p>${sections}</div>`;
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
    const bindButton = !isShare
      ? `<button class="bind-btn rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">🔗 接入</button>`
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
        ${isShare ? '' : `<div class="mt-4 flex gap-2 flex-wrap justify-center"><button class="bind-btn rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">🔗 接入</button><button class="update-btn rounded-lg border border-white/15 bg-white/5 px-4 py-1.5 text-sm hover:bg-white/10 transition" data-game="${key}">⬆ 更新数据</button>${syncButton}${launchButton}</div>`}
      </div>`;
    return;
  }
  const p = game.profile;
  const st = game.stamina;
  const pct = st.max > 0 ? Math.min(100, Math.round((st.current / st.max) * 100)) : 0;
  const sourceLabel = { manual: '手动录入', ocr: '截图 OCR', sync: '自动同步' }[game.last_update?.source] || '历史数据';
  const chars = (game.characters || []).slice(0, 12);
  const charHtml = chars.length
    ? chars.map((c) => {
        const el = ELEMENT_COLORS[c.element] || '#94a3b8';
        const eidolon = Number(c.eidolon || 0);
        const path = c.extra && c.extra.path ? c.extra.path : '';
        return `
        <div class="shrink-0 w-[92px] rounded-xl border bg-white/[0.03] p-2 text-center" style="border-color:${el}55">
          <div class="text-amber-300 text-[13px] leading-none">${'★'.repeat(Math.max(1, Math.min(5, c.rarity)))}</div>
          <div class="text-sm font-semibold truncate mt-1.5" style="color:${el}">${esc(c.name)}</div>
          <div class="text-[11px] text-slate-500">Lv.${c.level}</div>
          <div class="mt-1 flex items-center justify-center gap-1 flex-wrap">
            ${c.element ? elementBadge(c.element) : ''}
            ${path ? `<span class="text-[10px] px-1.5 py-0.5 rounded border" style="color:#e2e8f0;border-color:#ffffff30;background:#ffffff10">${esc(path)}</span>` : ''}
          </div>
          ${eidolon > 0 ? `<div class="mt-1 text-[10px] tracking-tighter" style="color:${el}">${'◆'.repeat(eidolon)}</div>` : ''}
        </div>`;
      }).join('')
    : '<p class="text-xs text-slate-500 py-4">暂无角色数据（🔗 接入后可自动同步角色柜台）</p>';
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
  const challengesHtml = renderChallenges(game.challenges, theme);

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
          ${isShare ? '' : `<button class="bind-btn rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] hover:bg-white/10 transition" data-game="${key}">🔗 重新绑定</button>`}
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

      ${challengesHtml}

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
$('#btn-refresh')?.addEventListener('click', async () => {
  const btn = $('#btn-refresh');
  if (btn.disabled) return;
  btn.disabled = true;
  btn.textContent = '⏳ 刷新中…';
  try {
    if (!REGISTRY.length) await loadRegistry();
    await load();
    toast('✓ 数据已刷新');
  } catch (err) {
    toast(err.message, false);
  }
  btn.disabled = false;
  btn.textContent = '🔄 刷新';
});
$('#btn-force-refresh')?.addEventListener('click', () => {
  const sep = location.search ? '&' : '?';
  location.replace(location.pathname + location.search + sep + '_t=' + Date.now());
});
$('#btn-share')?.addEventListener('click', async () => {
  try {
    const data = await api('/api/me');
    const url = shareUrlOf(data.player.share_id);
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
    $('#bind-modal')?.classList.add('hidden');
    $('#auth-modal')?.classList.add('hidden');
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
  const bindBtn = e.target.closest('.bind-btn');
  if (bindBtn) openBindModal(bindBtn.dataset.game);
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

/* ---------- 官方接入：输入 UID 自动同步 / 本地 JSON 导入 ---------- */
let bindGame = 'hsr';

function setBindStatus(message, ok = null) {
  const el = $('#bind-status');
  el.textContent = message;
  el.className = `mt-3 rounded-xl border px-4 py-3 text-sm ${
    ok === false ? 'border-red-400/30 bg-red-400/10 text-red-200'
      : ok === true ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
        : 'border-white/10 bg-white/5 text-slate-300'
  }`;
  el.classList.remove('hidden');
}

function buildBindTabs() {
  const box = $('#bind-game-tabs');
  if (!box) return;
  box.innerHTML = REGISTRY.map(
    (g) => `<button type="button" data-bind-game="${esc(g.key)}" class="bind-tab rounded-xl border py-2 text-sm font-semibold transition">${esc(g.emoji)} ${esc(g.label)}</button>`
  ).join('');
  box.querySelectorAll('.bind-tab').forEach((btn) =>
    btn.addEventListener('click', () => setBindGame(btn.dataset.bindGame))
  );
}

function setBindGame(game) {
  bindGame = game;
  const spec = specOf(game);
  document.querySelectorAll('.bind-tab').forEach((btn) => {
    const active = btn.dataset.bindGame === game;
    btn.className = `bind-tab rounded-xl border py-2 text-sm font-semibold transition ${
      active ? 'border-violet-400/60 bg-gradient-to-r from-violet-500/30 to-cyan-500/30' : 'border-white/10 bg-white/5'
    }`;
  });
  $('#bind-status').classList.add('hidden');
  const bound = CURRENT && CURRENT.games && CURRENT.games[game];
  const boundUid = (bound && bound.profile && bound.profile.uid) || '';
  $('#bind-uid').value = boundUid;
  $('#bind-uid').placeholder = boundUid ? '已绑定 UID，可输入新 UID 更换' : '输入对应游戏 UID，如 100000001';
  $('#btn-bind-unbind').classList.toggle('hidden', !boundUid);
  $('#bind-json').value = '';
  if (spec.syncable) {
    $('#btn-bind-sync').classList.remove('hidden');
    $('#bind-cookie-box').classList.remove('hidden');
    $('#bind-auto-box').classList.remove('hidden');
    $('#bind-uid-note').textContent = `${spec.label}：输入 UID 后自动拉取米游社战绩（等级 / 活跃天数 / 成就 / 角色 / 忘却之庭 / 虚构叙事 / 末日幻影 / 模拟宇宙），需先配置 Cookie。`;
    loadCookieStatus();
  } else {
    $('#btn-bind-sync').classList.add('hidden');
    $('#bind-cookie-box').classList.add('hidden');
    $('#bind-auto-box').classList.add('hidden');
    $('#bind-uid-note').textContent = `${spec.label}没有公开的玩家数据接口，无法按 UID 自动同步。请用下方「本地导出 JSON」导入，或回到看板用截图 OCR / 手动录入。`;
  }
}

async function loadCookieStatus() {
  try {
    const res = await api('/api/settings/hoyolab-cookie');
    $('#bind-cookie').value = res.value || '';
    $('#bind-cookie-status').textContent = res.configured ? `已配置（尾号 ${res.tail}）` : '未配置';
    $('#bind-cookie-status').className = res.configured ? 'text-[11px] text-emerald-300' : 'text-[11px] text-amber-300';
  } catch (err) {
    $('#bind-cookie-status').textContent = '读取失败';
  }
}

function openBindModal(game) {
  if (!REGISTRY.length) loadRegistry().then(() => openBindModal(game));
  else {
    buildBindTabs();
    setBindGame(game || (REGISTRY[0] && REGISTRY[0].key));
    $('#bind-modal').classList.remove('hidden');
  }
}

$('#btn-save-cookie')?.addEventListener('click', async () => {
  try {
    const res = await api('/api/settings/hoyolab-cookie', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookie: $('#bind-cookie').value.trim() }),
    });
    if (res.configured) {
      $('#bind-cookie-status').textContent = `✓ Cookie 已保存（尾号 ${res.tail}）`;
      $('#bind-cookie-status').className = 'text-[11px] font-semibold text-emerald-300';
      setBindStatus('✅ Cookie 已保存！输入 UID 后点「🔄 自动同步」即可拉取战绩。', true);
      toast('✓ Cookie 已保存（仅存本机数据库）');
    } else {
      $('#bind-cookie-status').textContent = '已清除';
      $('#bind-cookie-status').className = 'text-[11px] text-amber-300';
      toast('Cookie 已清除');
    }
  } catch (err) {
    toast(err.message, false);
  }
});

const FILL_TEMPLATES = {
  hsr: {
    nickname: '开拓者',
    characters: [
      { name: '黄泉', rarity: 5, level: 80, element: '雷', eidolon: 1, extra: { path: '虚无' } },
      { name: '流萤', rarity: 5, level: 80, element: '火', eidolon: 0, extra: { path: '毁灭' } },
      { name: '三月七', rarity: 4, level: 70, element: '冰', eidolon: 6, extra: { path: '存护' } },
    ],
    resources: { jades: 8000, special_pass: 20, star_pass: 10 },
    challenges: {
      moc: {
        name: '忘却之庭', season: '本期·混沌回忆',
        progress: { current: 27, max: 36, unit: '星' },
        nodes: [{ name: '第11层', value: 3, max: 3 }, { name: '第12层', value: 1, max: 3 }],
      },
      su: { name: '模拟宇宙', stats: [{ label: '最高积分', value: 60000 }] },
    },
  },
  wuwa: {
    nickname: '漂泊者',
    characters: [
      { name: '忌炎', rarity: 5, level: 80, element: '气动', eidolon: 1 },
      { name: '卡卡罗', rarity: 5, level: 80, element: '导电', eidolon: 0 },
      { name: '散华', rarity: 4, level: 70, element: '冷凝', eidolon: 6 },
    ],
    resources: { astrites: 6000, waveplates: 180, shell_credits: 120000 },
    challenges: {
      tower: {
        name: '逆境深塔', season: '1.4 版本',
        progress: { current: 24, max: 30, unit: '星' },
        nodes: [{ name: '左塔', value: 10, max: 12 }, { name: '右塔', value: 10, max: 12 }],
      },
    },
  },
};

function fillJson(json) {
  $('#bind-json').value = JSON.stringify(json, null, 2);
  setBindStatus('已自动填入 JSON，检查数字后点「导入 JSON 并保存」即可。');
}

$('#btn-fill-template')?.addEventListener('click', () => {
  const tpl = FILL_TEMPLATES[bindGame] || {
    nickname: '示例玩家',
    characters: [{ name: '示例角色', rarity: 5, level: 80, element: '', eidolon: 0 }],
    resources: {},
    challenges: {},
  };
  fillJson({
    uid: $('#bind-uid').value.trim() || '',
    nickname: tpl.nickname,
    level: 60,
    active_days: 300,
    achievements: 400,
    stamina: { current: 120, max: specOf(bindGame).cap || 240 },
    resources: tpl.resources,
    characters: tpl.characters,
    challenges: tpl.challenges,
  });
});

$('#btn-fill-current')?.addEventListener('click', () => {
  const game = CURRENT && CURRENT.games && CURRENT.games[bindGame];
  if (!game || !game.profile || !game.profile.uid) {
    toast('该游戏还没有档案数据，可先点「✨ 填入模板」', false);
    return;
  }
  fillJson({
    uid: game.profile.uid,
    nickname: game.profile.nickname,
    level: game.profile.level,
    active_days: game.profile.active_days,
    achievements: game.profile.achievements,
    stamina: { current: game.stamina.current, max: game.stamina.max },
    resources: game.resources || {},
    characters: (game.characters || []).map((c) => ({
      name: c.name, rarity: c.rarity, level: c.level, element: c.element,
      eidolon: c.eidolon || 0, extra: c.extra || {},
    })),
    challenges: game.challenges || {},
  });
  setBindStatus('已把当前档案序列化为 JSON 填入，可修改后导入。');
});

$('#btn-bind-sync')?.addEventListener('click', async () => {
  const uid = $('#bind-uid').value.trim();
  if (!uid) {
    setBindStatus('请先填写游戏 UID', false);
    return;
  }
  const btn = $('#btn-bind-sync');
  btn.disabled = true;
  btn.textContent = '同步中…';
  setBindStatus('⏳ 正在拉取米游社战绩…');
  try {
    await api(`/api/bind/${encodeURIComponent(bindGame)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid }),
    });
    $('#bind-modal').classList.add('hidden');
    toast(`✓ ${specOf(bindGame).label} 已接入并同步`);
    await load();
  } catch (err) {
    setBindStatus(`❌ ${err.message}`, false);
  }
  btn.disabled = false;
  btn.textContent = '🔄 自动同步（米游社战绩）';
});

$('#btn-bind-import')?.addEventListener('click', async () => {
  let data;
  try {
    data = JSON.parse($('#bind-json').value.trim());
  } catch (err) {
    setBindStatus('JSON 格式错误，请检查后重试', false);
    return;
  }
  const btn = $('#btn-bind-import');
  btn.disabled = true;
  btn.textContent = '导入中…';
  try {
    await api(`/api/import/${encodeURIComponent(bindGame)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    $('#bind-modal').classList.add('hidden');
    toast(`✓ ${specOf(bindGame).label} 数据已导入`);
    await load();
  } catch (err) {
    setBindStatus(`❌ ${err.message}`, false);
  }
  btn.disabled = false;
  btn.textContent = '导入 JSON 并保存';
});

$('#btn-bind-unbind')?.addEventListener('click', async () => {
  const label = specOf(bindGame).label;
  if (!confirm(`确定解除「${label}」的绑定吗？该游戏档案、角色与挑战数据将被清空。`)) return;
  const btn = $('#btn-bind-unbind');
  btn.disabled = true;
  btn.textContent = '解除中…';
  try {
    await api(`/api/bind/${encodeURIComponent(bindGame)}`, { method: 'DELETE' });
    $('#bind-modal').classList.add('hidden');
    toast(`✓ 已解除 ${label} 绑定，可重新接入`);
    await load();
  } catch (err) {
    setBindStatus(`❌ ${err.message}`, false);
    btn.disabled = false;
    btn.textContent = '解除绑定';
  }
});

let autoLoginPoll = null;

const AUTO_STEP_LABELS = {
  opening: '正在启动浏览器…',
  waiting: '等待登录完成…',
  filling: '正在自动填写账号密码…',
  submitting: '正在提交登录…',
  captcha: '需要人机验证：请在弹出的窗口中手动完成滑块/拼图，完成后自动继续',
  sms: '需要短信验证：请输入手机收到的 6 位验证码，其余自动完成',
  logged_in: '检测到已登录，正在复用登录态…',
  captured: '登录成功，Cookie 已保存',
  syncing: '正在同步游戏数据…',
  done: '全部完成',
  failed: '失败',
};

$('#btn-auto-login')?.addEventListener('click', async () => {
  const uid = $('#bind-uid').value.trim();
  const account = $('#auto-account').value.trim();
  const password = $('#auto-password').value;
  if (!uid) {
    setBindStatus('请先在上方填写游戏 UID', false);
    return;
  }
  if (!account || !password) {
    setBindStatus('请填写米游社账号和密码，后续步骤会自动完成', false);
    return;
  }
  const btn = $('#btn-auto-login');
  btn.disabled = true;
  btn.textContent = '⏳ 接入中…';
  setBindStatus('⏳ 正在尝试账号密码直登（无需人工操作）…');
  clearInterval(autoLoginPoll);
  try {
    const res = await api('/api/hoyolab/auto-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, account, password }),
    });
    if (res.status === 'synced') {
      $('#bind-modal').classList.add('hidden');
      toast('✓ 已自动登录并同步 UID ' + uid);
      await load();
    } else if (res.status === 'auto') {
      setBindStatus('🤖 已启动自动接入：自动填表 → 提交 → 抓取 Cookie → 同步；若出现人机验证，请在弹窗中手动完成一次');
      let tries = 0;
      autoLoginPoll = setInterval(async () => {
        tries += 1;
        try {
          const st = await api('/api/hoyolab/auto-login/status');
          const label = AUTO_STEP_LABELS[st.step] || AUTO_STEP_LABELS[st.status] || '处理中…';
          if (st.status === 'waiting') {
            setBindStatus(`🤖 ${label}（已运行 ${st.elapsed} 秒）`);
          } else if (st.status === 'captured' || st.status === 'syncing') {
            setBindStatus(`🤖 ${label}${st.message ? '：' + st.message : ''}`);
          } else if (st.status === 'done') {
            clearInterval(autoLoginPoll);
            $('#bind-modal').classList.add('hidden');
            setBindStatus('✅ 全部完成');
            toast('✓ 已自动登录并同步 UID ' + uid);
            await load();
          } else if (st.status === 'failed') {
            clearInterval(autoLoginPoll);
            setBindStatus(`❌ 自动抓取失败：${st.message || '请重试'}`, false);
          }
        } catch (e) { /* 轮询期间接口抖动忽略 */ }
        if (tries >= 360) {
          clearInterval(autoLoginPoll);
          setBindStatus('⏱ 自动接入超时（12 分钟），请重新尝试', false);
        }
      }, 2000);
    }
  } catch (err) {
    setBindStatus(`❌ ${err.message}`, false);
  }
  btn.disabled = false;
  btn.textContent = '🔑 自动登录并接入';
});

document.querySelectorAll('[data-bind-close]').forEach((el) =>
  el.addEventListener('click', () => $('#bind-modal').classList.add('hidden'))
);

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
  if (!isShare && !authToken) {
    showLocked();
    return;
  }
  try {
    if (!REGISTRY.length) await loadRegistry();
    const data = isShare
      ? await api(`/api/share/${encodeURIComponent(shareId)}`)
      : await api('/api/me');
    render(data);
  } catch (err) {
    if (err.message === '请先登录') return;
    if (isShare) {
      $('#player-name').textContent = '加载失败';
      $('#updated-at').textContent = err.message;
    }
    toast(err.message, false);
  }
}

applyBackground();
load();
