(() => {
'use strict';
const $ = (id) => document.getElementById(id);
const KEY = 'mca_demo_v1';
const ROLES = [['甲方', 'owner@example.com'], ['乙方', 'partner@example.com'], ['丙方', 'reviewer@example.com']];
const STATUS_TEXT = { pending: '待簽署', signed: '已簽署', declined: '已拒絕', changes_requested: '退回修改', expired: '已逾期' };

/* ---------- 共用工具 ---------- */
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; } };
const save = (s) => localStorage.setItem(KEY, JSON.stringify(s));
const nowMs = () => Date.now();
const fmt = (ms) => new Date(ms).toLocaleString('zh-TW', { hour12: false });
const rand = (n) => Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => b.toString(16).padStart(2, '0')).join('');
const enc = (o) => btoa(unescape(encodeURIComponent(JSON.stringify(o)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const dec = (t) => { try { const b = t.replace(/-/g, '+').replace(/_/g, '/'); return JSON.parse(decodeURIComponent(escape(atob(b + '='.repeat((4 - b.length % 4) % 4))))); } catch { return null; } };
const toast = (msg) => { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 1800); };
const el = (tag, props = {}, ...kids) => { const e = document.createElement(tag); Object.entries(props).forEach(([k, v]) => { if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v); }); kids.forEach((k) => k && e.append(k)); return e; };
const linkOf = (p, s) => `${location.origin}${location.pathname}#/sign/${enc({ c: s.id, t: p.token, r: p.role, ti: s.title, su: s.summary, ex: p.expiresAt })}`;
const partyStatus = (p) => (p.status === 'pending' && p.expiresAt <= nowMs() ? 'expired' : p.status);
const addLog = (s, text) => { s.log.unshift({ at: nowMs(), text }); s.log = s.log.slice(0, 80); };

function contractStatus(s) {
  const st = s.parties.map(partyStatus);
  const signed = st.filter((x) => x === 'signed').length;
  if (st.includes('declined')) return ['已拒絕', 'declined', '有簽署人拒絕簽署，合約需由管理者重新處理。'];
  if (st.includes('changes_requested')) return ['待修改', 'changes_requested', '有簽署人要求修改內容，合約進入「待管理者審閱」。'];
  if (signed === st.length) return ['已全數簽署', 'signed', `${st.length === 2 ? '雙方' : '三方'}皆已完成電子簽署，合約生效（示範）。`];
  const expired = st.filter((x) => x === 'expired').length;
  const base = signed ? `簽署中 ${signed}/${st.length}` : '已發出邀請';
  return [expired ? `${base}（含逾期）` : base, expired ? 'expired' : 'pending', expired ? '有連結已逾期，需重新發送邀請。' : '等待簽署人點開專屬連結。'];
}

/* ---------- 管理者頁 ---------- */
function mailText(p, s, reminder) {
  const url = linkOf(p, s);
  return `收件人：${p.email}\n主旨：${reminder ? '提醒簽署' : '簽署邀請'}／${reminder ? 'Signing reminder' : 'Signing invitation'}: ${s.title}\n\n請使用專屬連結完成簽署／Use your private signing link:\n${url}\n\n期限／Expires: ${new Date(p.expiresAt).toISOString()}`;
}

function renderManager() {
  const s = load();
  ['parties-card', 'remind-card', 'log-card'].forEach((id) => { $(id).hidden = !s; });
  if (!s) return;
  const [label, cls, hint] = contractStatus(s);
  $('contract-status').textContent = label;
  $('contract-status').className = `status ${cls === 'signed' ? 'complete' : cls === 'pending' ? 'draft' : cls}`;
  $('contract-state').textContent = `《${s.title}》｜${hint}`;
  const box = $('parties'); box.replaceChildren();
  s.parties.forEach((p) => {
    const st = partyStatus(p);
    const url = linkOf(p, s);
    const card = el('article', { class: `contract party${st === 'signed' ? ' selected' : ''}` },
      el('div', { class: 'party-head' }, el('span', { class: 'role', text: p.role }), el('span', { class: `status ${st}`, text: STATUS_TEXT[st] })),
      el('div', { class: 'contract-meta', style: 'border:0;padding:0;margin:0' }, el('span', { text: p.email }), el('span', { text: `期限 ${fmt(p.expiresAt)}` })),
      el('div', { class: 'link-box', text: url }),
      el('div', { class: 'row-btns' },
        el('a', { class: 'btn', href: url, target: '_blank', rel: 'noopener', text: '開新分頁簽署' }),
        el('button', { class: 'secondary', onclick: async () => { try { await navigator.clipboard.writeText(url); toast(`已複製${p.role}連結`); } catch { prompt('請手動複製連結', url); } }, text: '複製連結' })),
      el('details', {}, el('summary', { text: '查看邀請信內容' }), el('div', { class: 'mail', text: mailText(p, s, false) })));
    if (p.decision) {
      const d = p.decision;
      card.append(el('p', { class: 'muted', style: 'margin:0;font-size:13px', text: `${d.name ? d.name + '・' : ''}${fmt(d.at)}${d.reason ? '・原因：' + d.reason : ''}` }));
      if (d.sig) card.append(el('img', { src: d.sig, alt: '手寫簽名', style: 'max-width:160px;border:1px solid #dce3ee;border-radius:8px;background:#fff' }));
    }
    box.append(card);
  });
  const ol = $('log'); ol.replaceChildren();
  s.log.forEach((l) => ol.append(el('li', { text: `${fmt(l.at)}　${l.text}` })));
}

function generate() {
  const title = $('d-title').value.trim() || '全球服務合作合約';
  const summary = $('d-summary').value.trim() || '請確認合約內容後選擇簽署決定。';
  const days = Number($('d-days').value) || 7;
  const n = Number($('d-parties').value) === 2 ? 2 : 3;
  const exp = nowMs() + days * 86400000;
  const s = { id: 'demo-' + rand(4), title, summary, createdAt: nowMs(), log: [],
    parties: ROLES.slice(0, n).map(([role, email]) => ({ role, email, token: rand(16), status: 'pending', expiresAt: exp })) };
  addLog(s, `建立${n === 2 ? '兩方' : '三方'}合約《${title}》並產生 ${s.parties.length} 份一次性簽署連結（期限 ${days} 天）`);
  s.parties.forEach((p) => addLog(s, `已寄出${p.role}簽署邀請（示範，未實際寄信）`));
  save(s); renderManager();
  $('gen-msg').textContent = `已產生。下方 ${n} 張卡片各有專屬連結，點「開新分頁簽署」就能體驗。`;
  $('parties-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function remind() {
  const s = load(); if (!s) return;
  const targets = s.parties.filter((p) => partyStatus(p) === 'pending');
  const box = $('remind-mails'); box.replaceChildren();
  if (!targets.length) { $('remind-msg').textContent = '目前沒有「待簽署」的邀請，沒人需要被催（難得的和平）。'; return; }
  targets.forEach((p) => { p.expiresAt = nowMs() + 86400000; p.reminderCount = (p.reminderCount || 0) + 1; });
  targets.forEach((p) => { box.append(el('details', { open: '' }, el('summary', { text: `${p.role}的提醒信` }), el('div', { class: 'mail', text: mailText(p, s, true) }))); addLog(s, `提醒信已送出給${p.role}（第 ${p.reminderCount} 次，示範）`); });
  save(s); renderManager();
  $('remind-msg').textContent = `本次已寄出 ${targets.length} 封提醒（示範）。`;
}

function expireAll() {
  const s = load(); if (!s) return;
  let n = 0;
  s.parties.forEach((p) => { if (p.status === 'pending' && p.expiresAt > nowMs()) { p.expiresAt = nowMs() - 1000; n++; } });
  if (n) addLog(s, `模擬逾期：${n} 份待簽連結已失效`);
  save(s); renderManager();
  $('remind-msg').textContent = n ? `${n} 份待簽連結已逾期。現在去點它，會看到「簽署邀請無效」。` : '沒有待簽連結可逾期。';
}

function initManager() {
  $('manager-page').hidden = false;
  $('gen').onclick = generate;
  $('reset').onclick = () => { if (confirm('要清除目前的示範資料並重新開始嗎？')) { localStorage.removeItem(KEY); Object.keys(localStorage).filter((k) => k.startsWith('mca_used_')).forEach((k) => localStorage.removeItem(k)); $('remind-mails').replaceChildren(); $('remind-msg').textContent = ''; $('gen-msg').textContent = '已重設。'; renderManager(); } };
  $('remind').onclick = remind;
  $('expire').onclick = expireAll;
  window.addEventListener('storage', (e) => { if (e.key === KEY) renderManager(); });
  setInterval(renderManager, 30000);
  renderManager();
}

/* ---------- 簽署人頁 ---------- */
function initSigning(payload) {
  $('manager-page').hidden = true; $('signing-page').hidden = false;
  const lock = () => ['sign-action', 'change-action', 'decline-action'].forEach((id) => { $(id).disabled = true; });
  const bad = (msg) => { $('sign-title').textContent = '簽署邀請無效'; $('sign-result').textContent = msg; lock(); };
  if (!payload || !payload.t) return bad('此連結格式不正確，請向合約管理者重新索取。');
  const used = localStorage.getItem('mca_used_' + payload.t);
  const getState = () => { const s = load(); return s && s.id === payload.c ? s : null; };
  const findParty = (s) => s && s.parties.find((p) => p.token === payload.t);
  const s0 = getState(), p0 = findParty(s0);
  const expiresAt = p0 ? p0.expiresAt : payload.ex;
  const roleName = payload.r || '簽署人';
  $('sign-title').textContent = `${payload.ti || '合約'}｜${roleName}簽署`;
  $('sign-summary').textContent = payload.su || '請確認合約內容後選擇簽署決定。';
  $('sign-role').textContent = `身分：${roleName}`;
  $('sign-expiry').textContent = `期限：${fmt(expiresAt)}`;
  if (used || (p0 && p0.status !== 'pending')) return bad('此連結已使用，Token 已失效，不能重複操作。');
  if (expiresAt <= nowMs()) return bad('此連結已逾期，請向合約管理者重新索取邀請。');

  // 手寫簽名板
  const cv = $('sig'), ctx = cv.getContext('2d'); let drawing = false, drawn = false;
  ctx.lineWidth = 2.4; ctx.lineCap = 'round'; ctx.strokeStyle = '#172033';
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; };
  cv.addEventListener('pointerdown', (e) => { drawing = true; cv.setPointerCapture(e.pointerId); const [x, y] = pos(e); ctx.beginPath(); ctx.moveTo(x, y); });
  cv.addEventListener('pointermove', (e) => { if (!drawing) return; const [x, y] = pos(e); ctx.lineTo(x, y); ctx.stroke(); drawn = true; });
  ['pointerup', 'pointercancel'].forEach((ev) => cv.addEventListener(ev, () => { drawing = false; }));
  $('sig-clear').onclick = () => { ctx.clearRect(0, 0, cv.width, cv.height); drawn = false; };

  const act = (action) => {
    const name = $('sign-name').value.trim(), reason = $('sign-reason').value.trim();
    if (action === 'sign' && (!$('sign-consent').checked || !name || !drawn)) { $('sign-result').textContent = '請填寫姓名、勾選電子簽署同意，並在簽名欄手寫簽名。'; return; }
    if (action !== 'sign' && !reason) { $('sign-result').textContent = '拒絕或退回修改請填寫原因，讓合約管理者不用通靈。'; return; }
    const s = getState(), p = findParty(s);
    if (p && (p.status !== 'pending' || p.expiresAt <= nowMs())) { bad('此連結已使用或已逾期，不能重複操作。'); return; }
    const status = action === 'sign' ? 'signed' : action === 'decline' ? 'declined' : 'changes_requested';
    const decision = { action, name, reason, at: nowMs(), sig: action === 'sign' && drawn ? cv.toDataURL('image/png') : '' };
    localStorage.setItem('mca_used_' + payload.t, status);
    if (s && p) { p.status = status; p.decision = decision; addLog(s, `${roleName}${{ signed: '完成電子簽署', declined: '拒絕簽署', changes_requested: '要求退回修改' }[status]}${name ? '（' + name + '）' : ''}`); save(s); }
    const label = s ? contractStatus(s)[0] : { signed: '已簽署', declined: '已拒絕', changes_requested: '待修改' }[status];
    $('sign-result').className = 'muted';
    $('sign-result').textContent = `已完成：${STATUS_TEXT[status]}。合約狀態：${label}。此 Token 已失效，不能重複操作。${s ? '' : '（此裝置沒有管理者頁面的資料，進度不會回寫到其他裝置。）'}`;
    lock();
  };
  $('sign-action').onclick = () => act('sign');
  $('change-action').onclick = () => act('request_changes');
  $('decline-action').onclick = () => act('decline');
}

/* ---------- 路由 ---------- */
function route() {
  const m = location.hash.match(/^#\/sign\/(.+)$/);
  if (m) initSigning(dec(m[1])); else initManager();
}
window.addEventListener('hashchange', () => location.reload());
route();
})();
