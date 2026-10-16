(() => {
'use strict';
const API_BASE = 'https://mycontractapp-911.web.app/api';
const $ = (id) => document.getElementById(id);
const ERR = {
  invite_not_found: '找不到這份簽署邀請，請確認連結是否完整。',
  invite_already_consumed: '此連結已使用過，Token 已失效，不能重複操作。',
  invite_not_pending: '此邀請目前無法簽署。',
  invite_expired: '此連結已逾期，請向合約管理者重新索取邀請。',
  invalid_expiration: '此邀請的期限設定有誤，請聯絡合約管理者。',
  token_required: '連結缺少簽署 Token。',
  name_and_consent_required: '請填寫姓名並勾選電子簽署同意。',
  reason_required: '退回或拒絕時請填寫原因。',
  contract_closed: '此合約已結案或已被拒絕／退回，無法再簽署。'
};
const DONE = { signed: '已完成電子簽署', declined: '已拒絕簽署', changes_requested: '已退回修改' };
const CONTRACT = { partially_signed: '部分簽署', fully_signed: '已全數簽署', declined: '已被拒絕', changes_requested: '待修改' };

// Token 放在網址 # 後面（不會送到伺服器記錄），也相容 ?t= 形式
const token = decodeURIComponent((location.hash.replace(/^#\/?/, '') || new URLSearchParams(location.search).get('t') || '').trim());

const state = (cls, html) => { $('state').innerHTML = `<div class="${cls}">${html}</div>`; };

async function call(path, opts) {
  const res = await fetch(API_BASE + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(data.error || `HTTP ${res.status}`); e.status = res.status; throw e; }
  return data;
}

/* 簽名板 */
const cv = $('sig');
const ctx = cv.getContext('2d');
let drawing = false;
let drawn = false;
ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.strokeStyle = '#172033';
const pos = (e) => { const r = cv.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return [(p.clientX - r.left) * cv.width / r.width, (p.clientY - r.top) * cv.height / r.height]; };
const start = (e) => { e.preventDefault(); drawing = true; const [x, y] = pos(e); ctx.beginPath(); ctx.moveTo(x, y); };
const move = (e) => { if (!drawing) return; e.preventDefault(); const [x, y] = pos(e); ctx.lineTo(x, y); ctx.stroke(); drawn = true; };
const end = () => { drawing = false; };
cv.addEventListener('mousedown', start); cv.addEventListener('mousemove', move); window.addEventListener('mouseup', end);
cv.addEventListener('touchstart', start, { passive: false }); cv.addEventListener('touchmove', move, { passive: false }); cv.addEventListener('touchend', end);
$('sig-clear').onclick = () => { ctx.clearRect(0, 0, cv.width, cv.height); drawn = false; };

const lock = () => ['sign-action', 'change-action', 'decline-action', 'sign-name', 'sign-reason', 'sign-consent', 'sig-clear'].forEach((id) => { $(id).disabled = true; });

async function load() {
  if (!token) { $('sign-title').textContent = '簽署邀請無效'; state('bad', ERR.token_required); return; }
  try {
    const data = await call('/signature/invite?token=' + encodeURIComponent(token));
    const c = data.contract || {};
    const inv = data.invite || {};
    $('sign-title').textContent = `${c.title || '合約'}｜${inv.role || '簽署人'}簽署`;
    $('sign-role').textContent = inv.role || '簽署人';
    $('sign-email').textContent = inv.email || '';
    $('sign-summary').textContent = c.summary || '';
    $('sign-expiry').hidden = false;
    $('sign-expiry').textContent = '期限 ' + new Date(inv.expiresAt).toLocaleString('zh-TW', { hour12: false });
    $('form').hidden = false;
  } catch (e) {
    $('sign-title').textContent = '簽署邀請無效';
    state('bad', ERR[e.message] || ('無法載入簽署邀請：' + e.message));
  }
}

async function act(action) {
  const name = $('sign-name').value.trim();
  const reason = $('sign-reason').value.trim();
  const consent = $('sign-consent').checked;
  const out = $('sign-result');
  out.className = 'error';
  if (action === 'sign' && (!name || !consent || !drawn)) { out.textContent = '請填寫姓名、勾選電子簽署同意，並在簽名欄手寫簽名。'; return; }
  if (action !== 'sign' && !reason) { out.textContent = ERR.reason_required; return; }
  if (action === 'decline' && !confirm('確定要拒絕簽署嗎？送出後此連結將失效。')) return;
  lock();
  out.className = 'muted';
  out.textContent = '送出中…';
  try {
    const r = await call('/signature/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, action, name, reason, consent }) });
    out.textContent = '';
    $('form').hidden = true;
    state('done', `<b>${DONE[r.inviteStatus] || '已完成'}</b>。合約狀態：${CONTRACT[r.status] || r.status}。<br>此連結已失效，不能重複操作。感謝您的配合。`);
  } catch (e) {
    out.className = 'error';
    out.textContent = '操作未完成：' + (ERR[e.message] || e.message);
    if (!['invite_already_consumed', 'invite_expired', 'invite_not_found'].includes(e.message)) {
      ['sign-action', 'change-action', 'decline-action', 'sign-name', 'sign-reason', 'sign-consent', 'sig-clear'].forEach((id) => { $(id).disabled = false; });
    }
  }
}
$('sign-action').onclick = () => act('sign');
$('change-action').onclick = () => act('request_changes');
$('decline-action').onclick = () => act('decline');
load();
})();
