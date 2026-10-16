import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import { getAuth, signInAnonymously, onAuthStateChanged } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';
import { getFirestore, doc, setDoc, onSnapshot, serverTimestamp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js';

/* Firebase 公開設定（與 https://mycontractapp-911.web.app/__/firebase/init.json 相同，屬前端公開值） */
const FIREBASE_CONFIG = {
  "apiKey": "AIzaSyB4slm5fCCij89k-K_XP_2bDoS5n7C7wy8",
  "appId": "1:584739816152:web:32b60f9aafbacd08430dad",
  "authDomain": "mycontractapp-911.firebaseapp.com",
  "measurementId": "G-3K67VXBJHB",
  "messagingSenderId": "584739816152",
  "projectId": "mycontractapp-911",
  "storageBucket": "mycontractapp-911.firebasestorage.app"
};
const API_BASE = 'https://mycontractapp-911.web.app/api';
const HISTORY_KEY = 'mca_live_contracts';
const ROLES = ['甲方', '乙方', '丙方'];

const INVITE_TEXT = { pending: '待簽署', signed: '已簽署', declined: '已拒絕', changes_requested: '退回修改', expired: '已逾期', cancelled: '已取消' };
const CONTRACT_TEXT = { draft: '草稿', invited: '已發出邀請', partially_signed: '部分簽署', fully_signed: '已全數簽署', declined: '已被拒絕', changes_requested: '待修改' };
const ERROR_TEXT = {
  authentication_required: '尚未登入，請重新整理頁面。',
  owner_required: '只有建立這份合約的人可以寄送邀請。',
  signers_required: '至少需要一位簽署人。',
  invalid_signer: '簽署人 Email 格式不正確。',
  expiration_must_be_between_now_and_90_days: '簽署期限必須在 90 天內。',
  'permission-denied': 'Firestore 拒絕這次寫入（權限不足），請重新整理後再試。'
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (msg) => { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2200); };
const errText = (e) => ERROR_TEXT[e?.code?.replace('firestore/', '')] || ERROR_TEXT[e?.message] || e?.message || String(e);

const app = initializeApp(FIREBASE_CONFIG);
const auth = getAuth(app);
const db = getFirestore(app);
let user = null;
let unsubs = [];
let parties = {};
let contract = {};
let trackingId = null;
let pollTimer = null;
const tenantId = () => 't-' + user.uid;

function setConn(kind, html, badge) {
  $('conn').className = 'live-banner' + (kind === 'ok' ? '' : ' ' + kind);
  $('conn').innerHTML = html;
  $('conn-badge').textContent = badge;
}

/* ---------- 簽署人欄位：兩方 / 三方 ---------- */
function partyCount() { return Number(document.querySelector('input[name="parties"]:checked').value); }
function renderSignerRows() {
  const n = partyCount();
  const old = [...document.querySelectorAll('.signer-email')].map((i) => i.value);
  $('signer-rows').innerHTML = ROLES.slice(0, n).map((role, i) => `
    <div class="signer-row">
      <label>角色<input class="signer-role" maxlength="20" value="${esc(role)}"></label>
      <label>${esc(role)} Email<input class="signer-email" type="email" autocomplete="off" placeholder="name@company.com" value="${esc(old[i] || '')}"></label>
    </div>`).join('');
}
document.querySelectorAll('input[name="parties"]').forEach((r) => r.addEventListener('change', renderSignerRows));

/* ---------- API ---------- */
async function api(path, body) {
  const token = await user.getIdToken();
  const res = await fetch(API_BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

/* ---------- 建立合約 + 寄送邀請 ---------- */
async function send() {
  const title = $('c-title').value.trim();
  const summary = $('c-summary').value.trim();
  const roles = [...document.querySelectorAll('.signer-role')].map((i) => i.value.trim());
  const emails = [...document.querySelectorAll('.signer-email')].map((i) => i.value.trim().toLowerCase());
  const msg = $('send-msg');
  msg.className = 'error';
  if (!title) { msg.textContent = '請填寫合約名稱。'; return; }
  if (roles.some((r) => !r)) { msg.textContent = '每一方都需要角色名稱。'; return; }
  if (emails.some((e) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))) { msg.textContent = '請為每一方填寫正確的 Email。'; return; }
  if (new Set(emails).size !== emails.length) { msg.textContent = '每一方的 Email 不能重複。'; return; }

  $('send').disabled = true;
  msg.className = 'muted';
  msg.textContent = '建立合約中…';
  const contractId = 'c-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 7);
  try {
    await ensureTenant();
    const partyEmails = Object.fromEntries(roles.map((r, i) => [r, emails[i]]));
    await setDoc(doc(db, 'tenants', tenantId(), 'contracts', contractId), {
      contractId, title, summary, createdBy: user.uid, status: 'draft', partyCount: emails.length, partyEmails, createdAt: serverTimestamp()
    });
    msg.textContent = '寄送簽署邀請中…';
    const days = Number($('c-days').value);
    const expiresAt = new Date(Date.now() + days * 86400000).toISOString();
    const signers = emails.map((email, i) => ({ id: 'signer-' + (i + 1), role: roles[i], email }));
    const data = await api('/signature/invite', { tenantId: tenantId(), contractId, expiresAt, signers });
    const map = {};
    (data.invites || []).forEach((v) => { const tk = v.previewUrl ? (v.previewUrl.split('/sign/')[1] || '') : '';
      map[v.signerId] = { role: v.role, email: v.email, token: tk, url: tk ? signLink(tk) : '', emailStatus: v.emailStatus, status: 'pending', expiresAt: v.expiresAt }; });
    saveHistory({ id: contractId, tenant: tenantId(), title, parties: emails.length, at: Date.now(), map });
    const sent = (data.invites || []).filter((v) => v.emailStatus === 'sent').length;
    msg.textContent = sent
      ? `已建立《${title}》，並寄出 ${sent} 封簽署邀請 Email。`
      : `已建立《${title}》並產生 ${emails.length} 條一次性簽署連結（未設定寄信服務，請直接複製連結傳給對方）。`;
    track(contractId);
  } catch (e) {
    msg.className = 'error';
    msg.textContent = '未完成：' + errText(e);
  } finally {
    $('send').disabled = false;
  }
}

/* ---------- 租戶：使用者自己的工作區（符合現有規則：ownerId 本人、members/{uid} 為 Owner） ---------- */
async function ensureTenant() {
  const flag = 'mca_tenant_ready_' + user.uid;
  if (localStorage.getItem(flag)) return;
  await setDoc(doc(db, 'tenants', tenantId()), { ownerId: user.uid, name: '線上簽約工作區', createdAt: serverTimestamp() });
  await setDoc(doc(db, 'tenants', tenantId(), 'members', user.uid), { uid: user.uid, role: 'Owner', createdAt: serverTimestamp() });
  localStorage.setItem(flag, '1');
}

/* ---------- 即時追蹤 ----------
   合約文件（status / pendingSigners / signatures）由 Firestore 即時推送；
   各方連結狀態以後端公開 API 查詢：200=待簽、409=已使用、410=已逾期。
   連結「已使用」的那一刻，對照合約變化判斷是簽署、拒絕或退回。 */
/* 簽署連結：本站 sign.html，Token 放在 # 之後（不會被伺服器記錄） */
function signLink(tk) { return new URL('sign.html', location.href).href.split('#')[0] + '#' + tk; }
const tokenOf = (url) => (url.includes('#') ? url.split('#')[1] : (url.split('/sign/')[1] || '')).split(/[?#]/)[0];
async function inviteState(url) {
  const res = await fetch(API_BASE + '/signature/invite?token=' + encodeURIComponent(tokenOf(url)));
  if (res.ok) return 'pending';
  if (res.status === 410) return 'expired';
  if (res.status === 409) return 'used';
  return 'unknown';
}
async function poll() {
  if (!trackingId || !user) return;
  const id = trackingId;
  const list = Object.entries(parties).filter(([, p]) => p.status === 'pending' && p.url);
  const states = await Promise.all(list.map(([, p]) => inviteState(p.url).catch(() => 'unknown')));
  if (id !== trackingId) return;
  let changed = false;
  list.forEach(([sid, p], i) => {
    const st = states[i];
    if (st === 'expired') { p.status = 'expired'; changed = true; }
    if (st === 'used') {
      const sigs = contract.signatures || [];
      const taken = new Set(Object.values(parties).filter((x) => x.status === 'signed').map((x) => x.sigIndex));
      const idx = sigs.findIndex((_, k) => !taken.has(k));
      if (idx >= 0) { p.status = 'signed'; p.sigIndex = idx; p.decision = { name: sigs[idx].name || '' }; }
      else if (contract.status === 'declined' || contract.status === 'changes_requested') { p.status = contract.status; }
      else { return; } // 合約尚未同步，下一輪再判斷
      changed = true;
    }
  });
  if (changed) { const h = loadHistory().find((x) => x.id === id); if (h) { h.map = parties; saveHistory(h, false); } }
  render();
}
function render() {
  // 後端在「拒絕／退回」之後若仍有人簽署，會把合約狀態蓋回 partially_signed；
  // 這裡以各方結果為準：任一方拒絕 → 已被拒絕；任一方退回 → 待修改。
  const ps = Object.values(parties).map((p) => p.status);
  const st = ps.includes('declined') ? 'declined'
    : ps.includes('changes_requested') ? 'changes_requested'
    : (contract.status || 'draft');
  $('track-title').textContent = `簽署進度｜${contract.title || ''}`;
  $('contract-status').className = 'status ' + (st === 'fully_signed' ? 'completed' : st);
  $('contract-status').textContent = CONTRACT_TEXT[st] || st;
  const arr = Object.entries(parties).sort((a, b) => a[0].localeCompare(b[0]));
  const total = arr.length || contract.partyCount || 0;
  const signed = (contract.signatures || []).length;
  const tail = st === 'fully_signed' ? '所有簽署方皆已完成電子簽署，合約生效。'
    : st === 'declined' ? '有簽署方拒絕簽署，合約需重新處理。'
    : st === 'changes_requested' ? '有簽署方要求退回修改，請調整後重新發出邀請。'
    : '等待其他簽署方完成（每 5 秒自動更新）。';
  $('contract-state').textContent = `${total} 方簽署｜已簽 ${signed}/${total}｜${tail}`;
  $('parties').innerHTML = arr.map(([, p]) => {
    const linkUi = p.status === 'pending'
      ? (p.url
        ? `<div class="link-box">${esc(p.url)}</div><div class="row-btns"><a class="btn" href="${esc(p.url)}" target="_blank" rel="noopener">開啟簽署頁</a><button class="secondary" data-copy="${esc(p.url)}">複製連結</button></div>`
        : `<p class="muted">${p.emailStatus === 'sent' ? '已寄出 Email 邀請。' : '此瀏覽器沒有保存連結。'}</p>`)
      : '<p class="muted">此連結已使用或失效，不能重複操作。</p>';
    const who = p.decision?.name ? `<p class="muted">簽署人：${esc(p.decision.name)}</p>` : '';
    return `<div class="card party"><div class="party-head"><span class="role">${esc(p.role)}</span><span class="status ${esc(p.status)}">${esc(INVITE_TEXT[p.status] || p.status)}</span></div><p class="muted">${esc(p.email)}｜期限 ${esc(new Date(p.expiresAt).toLocaleString('zh-TW', { hour12: false }))}</p>${who}${linkUi}</div>`;
  }).join('');
  $('parties').querySelectorAll('[data-copy]').forEach((b) => b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.copy); toast('已複製簽署連結'); } catch { prompt('請手動複製連結', b.dataset.copy); } });
}
function track(contractId) {
  unsubs.forEach((u) => u());
  unsubs = [];
  clearInterval(pollTimer);
  const h = loadHistory().find((x) => x.id === contractId);
  if (!h) return;
  trackingId = contractId;
  parties = h.map || {};
  contract = { title: h.title, partyCount: h.parties };
  $('track-card').hidden = false;
  render();
  unsubs.push(onSnapshot(doc(db, 'tenants', h.tenant, 'contracts', contractId),
    (s) => { contract = s.data() || contract; render(); poll(); },
    (e) => { $('contract-state').textContent = '無法讀取合約：' + errText(e); }));
  pollTimer = setInterval(poll, 5000);
  poll();
  $('track-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ---------- 本機歷史（只存合約 ID 與一次性連結，資料本體在 Firestore） ---------- */
function loadHistory() { try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; } }
function saveHistory(item, toTop = true) { const old = loadHistory(); const list = toTop ? [item, ...old.filter((h) => h.id !== item.id)].slice(0, 20) : old.map((h) => (h.id === item.id ? item : h)); localStorage.setItem(HISTORY_KEY, JSON.stringify(list)); renderHistory(); }
function renderHistory() {
  const list = loadHistory().filter((h) => h.map && h.tenant);
  $('history-card').hidden = !list.length;
  $('history').innerHTML = list.map((h) => `<li>${esc(new Date(h.at).toLocaleString('zh-TW'))}｜${esc(h.title)}（${h.parties} 方）<button class="secondary" data-track="${esc(h.id)}">查看進度</button></li>`).join('');
  $('history').querySelectorAll('[data-track]').forEach((b) => b.onclick = () => track(b.dataset.track));
}

/* ---------- 啟動 ---------- */
renderSignerRows();
renderHistory();
$('send').onclick = send;
onAuthStateChanged(auth, (u) => {
  if (!u) return;
  user = u;
  $('uid').textContent = u.uid.slice(0, 10) + '…';
  $('send').disabled = false;
  setConn('ok', '<b>已連線 Firebase 正式後端</b>（匿名登入）。建立的合約與簽署紀錄會寫入 Firestore；簽署連結開在 mycontractapp-911.web.app。', '正式模式');
});
signInAnonymously(auth).catch((e) => {
  setConn('err', '<b>無法登入 Firebase：</b>' + esc(e.code || e.message) + '。請確認 Firebase Authentication 已啟用「匿名」登入方式。', '未連線');
});
