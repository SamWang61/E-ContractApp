import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js';
import { getAuth, signInAnonymously, onAuthStateChanged, connectAuthEmulator } from 'https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js';

/* Firebase 前端公開設定（與 /__/firebase/init.json 相同） */
const FIREBASE_CONFIG = {
  apiKey: 'AIzaSyB4slm5fCCij89k-K_XP_2bDoS5n7C7wy8',
  appId: '1:584739816152:web:32b60f9aafbacd08430dad',
  authDomain: 'mycontractapp-911.firebaseapp.com',
  messagingSenderId: '584739816152',
  projectId: 'mycontractapp-911',
  storageBucket: 'mycontractapp-911.firebasestorage.app'
};
const LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname);
const API = '/api';
const HISTORY_KEY = 'mca_contracts_v2';
const LANGS = [['zh-TW', '繁體'], ['zh-CN', '简体'], ['en', 'EN']];
const COVERS = [
  ['classic-navy', '經典藏青'], ['business-gold', '商務黑金'], ['minimal-white', '極簡白'],
  ['tech-blue', '科技藍'], ['jade-green', '典雅玉綠'], ['crimson-seal', '朱印契約']
];
const ROLES = ['甲方', '乙方', '丙方'];
const INVITE_TEXT = { pending: '待簽署', signed: '已簽署', declined: '已拒絕', changes_requested: '退回修改', expired: '已逾期', cancelled: '已取消' };
const CONTRACT_TEXT = { draft: '草稿', invited: '已發出邀請', partially_signed: '部分簽署', fully_signed: '已全數簽署', declined: '已被拒絕', changes_requested: '待修改' };
const ERR = {
  authentication_required: '尚未登入，請重新整理頁面。', invalid_auth_token: '登入已失效，請重新整理頁面。',
  owner_required: '只有建立這份合約的人可以執行此操作。', title_required: '請填寫合約名稱。',
  parties_must_be_2_or_3: '簽署方必須是兩方或三方。', invalid_signer: '簽署人 Email 格式不正確。',
  unsupported_file_type: '只接受 PDF、Word（.docx）、TXT、PNG、JPG。', file_too_large: '檔案超過 10 MB。', empty_file: '檔案是空的。',
  document_locked_after_invite: '已發出邀請，不能再更換文件。', invites_already_sent: '這份合約已發出邀請。',
  expiration_must_be_between_now_and_90_days: '簽署期限必須在 1–90 天內。',
  translation_api_not_enabled: '英文翻譯尚未啟用：請在 Google Cloud 啟用「Cloud Translation API」。',
  unsupported_language: '不支援的語言。', invite_not_found: '找不到這份簽署邀請，請確認連結是否完整。',
  invite_already_consumed: '此連結已使用過，不能重複操作。', invite_not_pending: '此邀請目前無法簽署。',
  invite_expired: '此連結已逾期，請向合約管理者重新索取。', contract_closed: '此合約已被拒絕、退回或已完成，無法再簽署。', contract_not_fully_signed: '所有簽署方完成後才能下載已簽署 PDF。', invalid_contract_no: '合約編號格式不正確：2–40 個字元，只能用英數字、減號、底線、點，且以英數字開頭。', contract_no_taken: '這個合約編號已被使用，請換一個。', invalid_tax_id: '統一編號不正確：台灣統編為 8 位數字（請確認檢查碼），外國公司可填 1–20 碼英數字。', contract_not_found: '找不到這份合約（請確認合約編號，或是否用建立合約的同一個瀏覽器開啟）。', signer_only: '只有已簽署的簽署人可以下載。',
  name_and_consent_required: '請填寫姓名並勾選電子簽署同意。', reason_required: '退回或拒絕時請填寫原因。',
  signature_required: '請在簽名欄手寫簽名。', token_required: '連結缺少簽署 Token。', document_not_found: '這份合約沒有上傳文件。'
};
/* 簽署頁介面文字（隨語言切換） */
const UI = {
  'zh-TW': { sign: '確認簽署', change: '退回修改', decline: '拒絕簽署', clear: '清除簽名', name: '簽署人姓名', reason: '備註／原因', consent: '我已閱讀合約內容，並同意以電子方式處理本次簽署。', doc: '合約文件', open: '開啟文件', expires: '期限', parties: '簽署方', summary: '摘要', body: '合約條款', docText: '文件內容（擷取文字）', date: '建立日期', id: '合約編號', kind: 'CONTRACT' },
  'zh-CN': { sign: '确认签署', change: '退回修改', decline: '拒绝签署', clear: '清除签名', name: '签署人姓名', reason: '备注／原因', consent: '我已阅读合同内容，并同意以电子方式处理本次签署。', doc: '合同文件', open: '打开文件', expires: '期限', parties: '签署方', summary: '摘要', body: '合同条款', docText: '文件内容（提取文字）', date: '创建日期', id: '合同编号', kind: 'CONTRACT' },
  en: { sign: 'Sign', change: 'Request changes', decline: 'Decline', clear: 'Clear', name: 'Full name', reason: 'Note / reason', consent: 'I have read this contract and agree to sign electronically.', doc: 'Contract document', open: 'Open document', expires: 'Expires', parties: 'Parties', summary: 'Summary', body: 'Terms', docText: 'Document text (extracted)', date: 'Created', id: 'Contract ID', kind: 'CONTRACT' }
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const toast = (m) => { const t = $('toast'); t.textContent = m; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2400); };
const errText = (e) => ERR[e?.message] || e?.message || String(e);
const fmtDate = (v) => (v ? new Date(v).toLocaleString('zh-TW', { hour12: false }) : '');
const fmtSize = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB');

async function call(path, { method = 'GET', body, token } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const e = new Error(data.error || `HTTP ${res.status}`); e.status = res.status; e.data = data; throw e; }
  return data;
}

/* 封面 HTML（管理台預覽與簽署頁共用） */
function coverHtml(c, lang = 'zh-TW', fields = null) {
  const u = UI[lang] || UI['zh-TW'];
  const f = fields || c;
  const parties = (c.parties || []).map((p) => `<div>${esc(p.role)}：${esc(p.company || p.email)}${p.taxId ? `<small>（${esc(p.taxId)}）</small>` : ''}${p.representative ? `<small>　${esc(p.representative)}</small>` : ''}</div>`).join('');
  return `<div class="cover ${esc(c.coverId || 'classic-navy')}">
    <div class="c-brand">GLOBAL CONTRACT MANAGEMENT</div>
    <div class="c-kind">${u.kind}</div>
    <div class="c-title">${esc(f.title || c.title)}</div>
    <div class="c-sum">${esc(f.summary || '')}</div>
    <div class="c-parties"><b>${u.parties}</b>${parties}</div>
    <div class="c-foot"><span>${u.id} ${esc(c.contractNo || c.id || '—')}</span><span>${u.date} ${esc((c.createdAt || new Date().toISOString()).slice(0, 10))}</span></div>
  </div>`;
}
function contentHtml(c, lang, fields, docBtnId) {
  const u = UI[lang] || UI['zh-TW'];
  const f = fields || c;
  const doc = c.document ? `<div class="doc-box"><b>${u.doc}</b>：${esc(c.document.name)}（${fmtSize(c.document.size)}）
      <div class="row-btns"><button class="secondary" id="${docBtnId}" type="button">${u.open}</button></div>
      ${f.documentText ? `<div class="muted">${u.docText}</div><div class="doc-text">${esc(f.documentText)}</div>` : ''}</div>` : '';
  return `${coverHtml(c, lang, f)}
    ${f.body ? `<h3>${u.body}</h3><div class="contract-body">${esc(f.body)}</div>` : ''}${doc}`;
}
async function openBlob(path, token) {
  const res = await fetch(API + path, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
  if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || `HTTP ${res.status}`); }
  const url = URL.createObjectURL(await res.blob());
  window.open(url, '_blank', 'noopener');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
async function downloadFile(path, token, fallbackName) {
  const res = await fetch(API + path, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
  if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || `HTTP ${res.status}`); }
  const cd = res.headers.get('Content-Disposition') || '';
  const m = cd.match(/filename\*=UTF-8''([^;]+)/);
  const name = m ? decodeURIComponent(m[1]) : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
function langTabs(el, current, onPick) {
  el.innerHTML = LANGS.map(([k, n]) => `<button type="button" data-l="${k}" class="${k === current ? 'on' : ''}">${n}</button>`).join('');
  el.querySelectorAll('button').forEach((b) => (b.onclick = () => onPick(b.dataset.l)));
}

/* =========================== 簽署頁 =========================== */
const signToken = (location.pathname.match(/^\/sign\/([^/?#]+)/) || [])[1];

async function initSigning() {
  $('signing-page').hidden = false;
  $('conn-badge').textContent = '一次性簽署連結';
  $('head-sub').textContent = '此連結僅供受邀簽署人使用一次，完成後立即失效。';
  const token = decodeURIComponent(signToken);
  let lang = null;
  let drawn = false;
  const cv = $('sig');
  const ctx = cv.getContext('2d');
  ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.strokeStyle = '#172033';
  let drawing = false;
  const pos = (e) => { const r = cv.getBoundingClientRect(); const p = e.touches ? e.touches[0] : e; return [(p.clientX - r.left) * cv.width / r.width, (p.clientY - r.top) * cv.height / r.height]; };
  const start = (e) => { e.preventDefault(); drawing = true; const [x, y] = pos(e); ctx.beginPath(); ctx.moveTo(x, y); };
  const move = (e) => { if (!drawing) return; e.preventDefault(); const [x, y] = pos(e); ctx.lineTo(x, y); ctx.stroke(); drawn = true; };
  cv.addEventListener('mousedown', start); cv.addEventListener('mousemove', move); window.addEventListener('mouseup', () => (drawing = false));
  cv.addEventListener('touchstart', start, { passive: false }); cv.addEventListener('touchmove', move, { passive: false }); cv.addEventListener('touchend', () => (drawing = false));
  $('sig-clear').onclick = () => { ctx.clearRect(0, 0, cv.width, cv.height); drawn = false; };

  const pdfBtn = () => '<div class="row-btns"><button id="dl-signed" type="button">下載已簽署 PDF</button></div>';
  const bindPdf = () => { if ($('dl-signed')) $('dl-signed').onclick = () => downloadFile('/signature/signed-pdf?token=' + encodeURIComponent(token), null, 'signed-contract.pdf').catch((e) => toast(errText(e))); };
  const fail = (e) => {
    $('sign-view').hidden = true;
    if (e.data?.signedPdfAvailable) {
      $('sign-title').textContent = '合約已全數簽署完成';
      $('sign-state').innerHTML = `<div class="done">所有簽署方皆已完成簽署，您可以下載已簽署的 PDF 合約。</div>${pdfBtn()}`;
      bindPdf(); return;
    }
    $('sign-title').textContent = '簽署邀請無效';
    $('sign-state').innerHTML = `<div class="bad">${esc(errText(e))}</div>`;
  };

  async function load(pick) {
    try {
      const q = '/signature/invite?token=' + encodeURIComponent(token) + (pick ? '&lang=' + pick : '');
      const data = await call(q);
      const c = data.contract;
      lang = pick || c.language || 'zh-TW';
      const fields = c.translation?.fields || null;
      const u = UI[lang];
      $('sign-title').textContent = `${(fields || c).title}｜${data.invite.role}`;
      $('sign-role').textContent = data.invite.role;
      $('sign-email').textContent = data.invite.email;
      $('sign-expiry').textContent = `${u.expires} ${fmtDate(data.invite.expiresAt)}`;
      $('sign-preview').innerHTML = contentHtml(c, lang, fields, 'sign-doc');
      if ($('sign-doc')) $('sign-doc').onclick = () => openBlob('/signature/document?token=' + encodeURIComponent(token)).catch((e) => toast(errText(e)));
      $('sign-action').textContent = u.sign; $('change-action').textContent = u.change; $('decline-action').textContent = u.decline; $('sig-clear').textContent = u.clear;
      $('sign-name').previousSibling.textContent = u.name; $('sign-reason').previousSibling.textContent = u.reason;
      $('sign-consent').nextSibling.textContent = ' ' + u.consent;
      langTabs($('sign-lang'), lang, (l) => { $('sign-lang').querySelectorAll('button').forEach((b) => (b.disabled = true)); load(l); });
      $('sign-view').hidden = false;
    } catch (e) {
      if (e.message === 'translation_api_not_enabled' || e.message?.startsWith('translation_failed')) { toast(errText(e)); load(null); return; }
      fail(e);
    }
  }

  const lock = (on) => ['sign-action', 'change-action', 'decline-action', 'sign-name', 'sign-reason', 'sign-consent', 'sig-clear'].forEach((id) => ($(id).disabled = on));
  async function act(action) {
    const name = $('sign-name').value.trim();
    const reason = $('sign-reason').value.trim();
    const consent = $('sign-consent').checked;
    const out = $('sign-result');
    out.className = 'error';
    if (action === 'sign' && (!name || !consent || !drawn)) { out.textContent = '請填寫姓名、勾選電子簽署同意，並在簽名欄手寫簽名。'; return; }
    if (action !== 'sign' && !reason) { out.textContent = ERR.reason_required; return; }
    if (action === 'decline' && !confirm('確定要拒絕簽署嗎？送出後此連結將失效。')) return;
    lock(true); out.className = 'muted'; out.textContent = '送出中…';
    try {
      const body = { token, action, name, reason, consent };
      if (action === 'sign') body.signatureImage = cv.toDataURL('image/png');
      const r = await call('/signature/action', { method: 'POST', body });
      const done = { signed: '已完成電子簽署', declined: '已拒絕簽署', changes_requested: '已退回修改' }[r.inviteStatus] || '已完成';
      $('sign-form').hidden = true;
      const full = r.status === 'fully_signed';
      $('sign-state').innerHTML = `<div class="done"><b>${done}</b>。合約狀態：${esc(CONTRACT_TEXT[r.status] || r.status)}。<br>${full ? '所有簽署方皆已完成，可下載已簽署 PDF；之後再開此連結也能下載。' : '此連結已不能再簽署；全部簽署方完成後，再開此連結即可下載已簽署 PDF。'}</div>${full ? pdfBtn() : ''}`;
      bindPdf();
      out.textContent = '';
    } catch (e) {
      out.className = 'error';
      out.textContent = '操作未完成：' + errText(e);
      if (!['invite_already_consumed', 'invite_expired', 'invite_not_found', 'contract_closed'].includes(e.message)) lock(false);
    }
  }
  $('sign-action').onclick = () => act('sign');
  $('change-action').onclick = () => act('request_changes');
  $('decline-action').onclick = () => act('decline');
  load(null);
}

/* =========================== 管理台 =========================== */
let user = null;
let current = null; // { tenantId, contractId, contract }
let pollTimer = null;
let cover = 'classic-navy';

const idToken = () => user.getIdToken();
const loadHistory = () => { try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; } };
function saveHistory(item) {
  const list = [item, ...loadHistory().filter((h) => h.contractId !== item.contractId)].slice(0, 30);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  renderHistory();
}
function patchHistory(contractId, patch) {
  const list = loadHistory().map((h) => (h.contractId === contractId ? { ...h, ...patch } : h));
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
}
function renderHistory() {
  const list = loadHistory();
  $('history-card').hidden = !list.length;
  $('history').innerHTML = list.map((h) => `<div class="history-row"><span>${esc(h.contractNo || '')} ${esc(h.title)}｜${h.parties} 方｜${fmtDate(h.at)}</span> <button class="secondary" data-id="${esc(h.contractId)}">查看</button> <a class="btn secondary" href="/contracts/${encodeURIComponent(h.contractNo || h.contractId)}">合約內容頁</a></div>`).join('');
  $('history').querySelectorAll('button').forEach((b) => (b.onclick = () => openContract(b.dataset.id)));
}

function renderCovers() {
  const sample = { title: $('c-title').value || '合約名稱', summary: '', parties: [], id: 'C-XXXX' };
  $('cover-picker').innerHTML = COVERS.map(([id, label]) => `<button type="button" class="cover-option ${id === cover ? 'on' : ''}" data-c="${id}">${coverHtml({ ...sample, coverId: id })}<span>${label}</span></button>`).join('');
  $('cover-picker').querySelectorAll('.cover-option').forEach((b) => (b.onclick = () => { cover = b.dataset.c; renderCovers(); }));
}
function renderSignerRows() {
  const n = Number(document.querySelector('input[name="parties"]:checked').value);
  const old = [...document.querySelectorAll('.signer-row')].map(readSigner);
  $('signer-rows').innerHTML = ROLES.slice(0, n).map((role, i) => { const o = old[i] || {}; return `<div class="signer-row signer-card">
      <label>角色<input class="signer-role" maxlength="20" value="${esc(o.role || role)}"></label>
      <label>Email（必填）<input class="signer-email" type="email" autocomplete="off" placeholder="name@company.com" value="${esc(o.email || '')}"></label>
      <label>公司名稱<input class="signer-company" maxlength="120" placeholder="例如 全球科技股份有限公司" value="${esc(o.company || '')}"></label>
      <label>統一編號<input class="signer-tax" maxlength="20" inputmode="numeric" placeholder="8 位數字" value="${esc(o.taxId || '')}"></label>
      <label class="wide">公司地址<input class="signer-address" maxlength="200" placeholder="例如 台北市信義區信義路五段 7 號" value="${esc(o.address || '')}"></label>
      <label>代表人<input class="signer-rep" maxlength="60" placeholder="例如 王大明" value="${esc(o.representative || '')}"></label></div>`; }).join('');
}
function readSigner(row) {
  const v = (c) => row.querySelector(c)?.value.trim() || '';
  return { role: v('.signer-role'), email: v('.signer-email').toLowerCase(), company: v('.signer-company'), taxId: v('.signer-tax').toUpperCase().replace(/\s/g, ''), address: v('.signer-address'), representative: v('.signer-rep') };
}
/* 台灣統一編號檢查碼（2023 新制：加權和可被 5 整除；第 7 碼為 7 時加 1 亦可） */
function validTaxId(t) {
  if (!t) return true;
  if (!/^[A-Z0-9-]{1,20}$/.test(t)) return false;
  if (!/^\d{8}$/.test(t)) return true;
  const w = [1, 2, 1, 2, 1, 2, 4, 1];
  const sum = [...t].reduce((a, d, i) => { const x = Number(d) * w[i]; return a + Math.floor(x / 10) + (x % 10); }, 0);
  return sum % 5 === 0 || (t[6] === '7' && (sum + 1) % 5 === 0);
}
function noticeText(c) {
  const n = c.completionNotice?.summary;
  if (c.status !== 'fully_signed') return '';
  if (!n) return '完成通知：尚未寄出';
  if (n.sent === n.total) return `完成通知：已寄給 ${n.total} 位（${c.completionNotice.attached ? '附已簽署 PDF' : '附下載連結'}）`;
  if (n.preview === n.total) return '完成通知：未設定寄信（SMTP），未寄出';
  return `完成通知：成功 ${n.sent}／失敗 ${n.failed}／共 ${n.total}`;
}
async function resendNotice(tenantId, contractId, after) {
  try {
    const r = await call('/contracts/notify-completion', { method: 'POST', body: { tenantId, contractId }, token: await idToken() });
    const n = r.notice || {};
    toast(n.preview === n.total ? '尚未設定 SMTP，無法寄信' : `完成通知已重寄：成功 ${n.sent}／共 ${n.total}`);
    after && after();
  } catch (e) { toast(errText(e)); }
}
function partyOf(c, v) {
  const p = (c.parties || []).find((x) => x.email === v.email || x.role === v.role);
  return p ? partyLine(p) : '';
}
function partyLine(p) {
  return [p.company, p.taxId && `統編 ${p.taxId}`, p.representative && `代表人 ${p.representative}`, p.address].filter(Boolean).map(esc).join('｜');
}
const fileB64 = (file) => new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.onerror = () => no(r.error); r.readAsDataURL(file); });

async function createContract() {
  const msg = $('create-msg');
  msg.className = 'error';
  const title = $('c-title').value.trim();
  const signers = [...document.querySelectorAll('.signer-row')].map(readSigner);
  const roles = signers.map((x) => x.role);
  const emails = signers.map((x) => x.email);
  if (!title) { msg.textContent = ERR.title_required; return; }
  if (roles.some((r) => !r)) { msg.textContent = '每一方都需要角色名稱。'; return; }
  if (emails.some((e) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e))) { msg.textContent = '請填寫每一方正確的 Email。'; return; }
  if (new Set(emails).size !== emails.length) { msg.textContent = '每一方的 Email 不能重複。'; return; }
  const badTax = signers.find((x) => !validTaxId(x.taxId));
  if (badTax) { msg.textContent = `${badTax.role}：${ERR.invalid_tax_id}`; return; }
  const file = $('c-file').files[0];
  if (file && file.size > 10 * 1024 * 1024) { msg.textContent = ERR.file_too_large; return; }
  $('create-btn').disabled = true;
  msg.className = 'muted';
  try {
    const token = await idToken();
    msg.textContent = '建立合約中…';
    const r = await call('/contracts', { method: 'POST', token, body: {
      title, summary: $('c-summary').value.trim(), body: $('c-body').value.trim(), language: $('c-lang').value,
      coverId: cover, parties: signers, contractNo: $('c-no').value.trim()
    } });
    if (file) {
      msg.textContent = `上傳文件 ${file.name}…`;
      await call('/contracts/document', { method: 'POST', token, body: { tenantId: r.tenantId, contractId: r.contractId, fileName: file.name, contentType: file.type, dataBase64: await fileB64(file) } });
    }
    fillNextNumber();
    saveHistory({ tenantId: r.tenantId, contractId: r.contractId, contractNo: r.contractNo, title, parties: emails.length, at: Date.now(), links: {}, days: Number($('c-days').value) || 7 });
    msg.textContent = '';
    await openContract(r.contractId);
    $('preview-card').scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    msg.className = 'error';
    msg.textContent = '未完成：' + errText(e);
  } finally {
    $('create-btn').disabled = false;
  }
}

async function showPreview(lang) {
  const c = current.contract;
  let fields = null;
  langTabs($('owner-lang'), lang, showPreview);
  if (lang !== (c.language || 'zh-TW')) {
    $('owner-preview').innerHTML = '<p class="muted">翻譯中…</p>';
    try {
      const r = await call('/contracts/translate', { method: 'POST', token: await idToken(), body: { tenantId: current.tenantId, contractId: current.contractId, lang } });
      fields = r.fields;
    } catch (e) {
      toast(errText(e));
      return showPreview(c.language || 'zh-TW');
    }
  }
  $('owner-preview').innerHTML = contentHtml(c, lang, fields, 'owner-doc');
  if ($('owner-doc')) $('owner-doc').onclick = () => idToken().then((t) => openBlob(`/contracts/document?tenantId=${encodeURIComponent(current.tenantId)}&contractId=${encodeURIComponent(current.contractId)}`, t)).catch((e) => toast(errText(e)));
}

async function openContract(contractId) {
  const h = loadHistory().find((x) => x.contractId === contractId);
  if (!h) return;
  clearInterval(pollTimer);
  const data = await call(`/contracts/status?tenantId=${encodeURIComponent(h.tenantId)}&contractId=${encodeURIComponent(contractId)}`, { token: await idToken() });
  current = { tenantId: h.tenantId, contractId, contract: data.contract };
  $('preview-card').hidden = false;
  $('send-btn').hidden = data.contract.status !== 'draft';
  $('send-msg').textContent = '';
  await showPreview(data.contract.language || 'zh-TW');
  if (data.contract.status !== 'draft') startTracking(data);
  else $('track-card').hidden = true;
}

async function sendInvites() {
  const h = loadHistory().find((x) => x.contractId === current.contractId);
  const msg = $('send-msg');
  $('send-btn').disabled = true;
  msg.className = 'muted'; msg.textContent = '產生簽署邀請中…';
  try {
    const days = Math.min(90, Math.max(1, Number(h?.days) || 7));
    const r = await call('/signature/invite', { method: 'POST', token: await idToken(), body: { tenantId: current.tenantId, contractId: current.contractId, expiresAt: new Date(Date.now() + days * 86400000).toISOString() } });
    const links = {};
    r.invites.forEach((v) => { if (v.previewUrl) links[v.signerId] = v.previewUrl; });
    patchHistory(current.contractId, { links });
    const mailed = r.invites.filter((v) => v.emailStatus === 'sent').length;
    const failed = r.invites.filter((v) => v.emailStatus === 'failed').length;
    msg.className = failed ? 'error' : 'muted';
    msg.textContent = mailed || failed
      ? `已寄出 ${mailed} 封簽署邀請 Email${failed ? `，${failed} 封寄送失敗（請複製連結自行轉交，並檢查 SMTP 設定）` : ''}。`
      : `已產生 ${r.invites.length} 條一次性簽署連結（未設定寄信服務，請複製連結傳給對方）。`;
    $('send-btn').hidden = true;
    await openContract(current.contractId);
  } catch (e) {
    msg.className = 'error'; msg.textContent = '未完成：' + errText(e);
  } finally {
    $('send-btn').disabled = false;
  }
}

function renderTracking(data) {
  const c = data.contract;
  const h = loadHistory().find((x) => x.contractId === c.id) || { links: {} };
  $('track-card').hidden = false;
  $('track-title').textContent = `簽署進度｜${c.contractNo || ''} ${c.title}`;
  $('contract-status').className = 'status ' + c.status;
  $('contract-status').textContent = CONTRACT_TEXT[c.status] || c.status;
  const total = data.invites.length;
  const tail = c.status === 'fully_signed' ? '所有簽署方皆已完成電子簽署，合約生效。'
    : c.status === 'declined' ? '有簽署方拒絕簽署，合約已鎖定。'
    : c.status === 'changes_requested' ? '有簽署方要求退回修改，合約已鎖定，請修改後重新建立。'
    : '等待其他簽署方完成（每 5 秒自動更新）。';
  $('contract-state').innerHTML = `${esc(`${total} 方簽署｜已簽 ${c.signedCount}/${total}｜${tail}`)}${c.status === 'fully_signed' ? `<p class="notice-line">${esc(noticeText(c))}</p><div class="row-btns"><button id="owner-dl" type="button">下載已簽署 PDF</button> <button id="owner-notify" class="secondary" type="button">重寄完成通知</button></div>` : ''}`;
  if ($('owner-notify')) $('owner-notify').onclick = () => resendNotice(current.tenantId, c.id, () => openContract(c.id));
  if ($('owner-dl')) $('owner-dl').onclick = () => idToken().then((t) => downloadFile(`/contracts/signed-pdf?tenantId=${encodeURIComponent(current.tenantId)}&contractId=${encodeURIComponent(c.id)}`, t, 'signed-contract.pdf')).catch((e) => toast(errText(e)));
  $('parties').innerHTML = data.invites.map((v) => {
    const url = v.link || h.links?.[v.signerId];
    const link = v.status === 'pending'
      ? (url ? `<div class="link-box">${esc(url)}</div><div class="row-btns"><a class="btn" href="${esc(url)}" target="_blank" rel="noopener">開啟簽署頁</a><button class="secondary" data-copy="${esc(url)}">複製連結</button></div>`
             : `<p class="muted">${v.emailStatus === 'sent' ? '已寄出 Email 邀請。' : '連結只保存在建立合約的瀏覽器。'}</p>`)
      : '';
    const d = v.decision ? `<p class="muted">${esc(v.decision.name || '')}${v.decision.reason ? '｜原因：' + esc(v.decision.reason) : ''}｜${fmtDate(v.decision.at)}</p>` : '';
    return `<div class="card party"><div class="party-head"><span class="role">${esc(v.role)}</span><span class="status ${esc(v.status)}">${esc(INVITE_TEXT[v.status] || v.status)}</span></div>
      ${partyOf(c, v) ? `<p class="party-co">${partyOf(c, v)}</p>` : ''}<p class="muted">${esc(v.email)}｜期限 ${fmtDate(v.expiresAt)}｜Email：${({ sent: '已寄出', failed: '寄送失敗', preview: '未寄信（手動轉交）' })[v.emailStatus] || '—'}</p>${d}${link}</div>`;
  }).join('');
  $('parties').querySelectorAll('[data-copy]').forEach((b) => (b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.copy); toast('已複製簽署連結'); } catch { prompt('請手動複製連結', b.dataset.copy); } }));
}
function startTracking(first) {
  renderTracking(first);
  const id = current.contractId;
  const tenantId = current.tenantId;
  pollTimer = setInterval(async () => {
    try {
      const data = await call(`/contracts/status?tenantId=${encodeURIComponent(tenantId)}&contractId=${encodeURIComponent(id)}`, { token: await idToken() });
      if (current?.contractId === id) renderTracking(data);
      if (['fully_signed', 'declined', 'changes_requested'].includes(data.contract.status)) clearInterval(pollTimer);
    } catch { /* 下一輪重試 */ }
  }, 5000);
}

function initManager() {
  $('manager-page').hidden = false;
  renderSignerRows();
  renderCovers();
  document.querySelectorAll('input[name="parties"]').forEach((r) => r.addEventListener('change', renderSignerRows));
  $('c-title').addEventListener('input', renderCovers);
  $('c-file').addEventListener('change', () => { const f = $('c-file').files[0]; $('file-info').textContent = f ? `${f.name}（${fmtSize(f.size)}）` : ''; });
  $('create-btn').onclick = createContract;
  $('send-btn').onclick = sendInvites;
  $('create-btn').disabled = true;
  startAuth(() => { $('create-btn').disabled = false; renderHistory(); fillNextNumber(); }, (e) => { $('create-msg').textContent = '無法登入 Firebase：' + (e.code || e.message); });
}

/* 匿名登入（同一瀏覽器會保留同一個身分，看到的就是這個身分建立的合約） */
function startAuth(onReady, onFail) {
  const auth = getAuth(initializeApp(FIREBASE_CONFIG));
  if (LOCAL) connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
  let done = false;
  onAuthStateChanged(auth, (u) => {
    if (u && !done) { done = true; user = u; $('conn-badge').textContent = '已登入（匿名）'; onReady(); }
  });
  signInAnonymously(auth).catch((e) => { $('conn-badge').textContent = '登入失敗'; onFail?.(e); });
}
async function fillNextNumber() {
  try {
    const r = await call('/contracts/next-number', { token: await idToken() });
    const el = $('c-no');
    if (!el.value || el.dataset.auto === el.value) { el.value = r.contractNo; el.dataset.auto = r.contractNo; }
  } catch { /* 留白則由後端自動編號 */ }
}
function showNav(which) {
  $('top-nav').hidden = false;
  document.querySelectorAll('#top-nav a').forEach((a) => a.classList.toggle('on', a.dataset.nav === which));
}

/* =========================== 瀏覽所有合約 =========================== */
const SWATCH = { 'classic-navy': '#0f1f3d', 'business-gold': '#b8913a', 'minimal-white': '#e2e8f0', 'tech-blue': '#1e3a8a', 'jade-green': '#1f3d2b', 'crimson-seal': '#b42318' };
let listTimer = null;
async function loadList() {
  const q = $('q').value.trim();
  const st = $('q-status').value;
  const url = new URL(location.href);
  if (q) url.searchParams.set('q', q); else url.searchParams.delete('q');
  if (st) url.searchParams.set('status', st); else url.searchParams.delete('status');
  history.replaceState(null, '', url.pathname + url.search);
  $('list-body').innerHTML = '<p class="muted">查詢中…</p>';
  try {
    const r = await call(`/contracts/list?q=${encodeURIComponent(q)}&status=${encodeURIComponent(st)}`, { token: await idToken() });
    $('list-count').textContent = `共 ${r.total} 份`;
    $('list-body').innerHTML = r.contracts.length ? r.contracts.map((c) => `<a class="c-row" href="/contracts/${encodeURIComponent(c.contractNo)}">
        <div class="no">${esc(c.contractNo)}</div>
        <div><div class="t"><span class="swatch" style="background:${SWATCH[c.coverId] || '#0f1f3d'}"></span>${esc(c.title)}</div>
          <div class="sub">${c.parties.map((p) => `${esc(p.role)} ${esc(p.company || p.email)}${p.taxId ? `（${esc(p.taxId)}）` : ''}`).join('｜')}${c.hasDocument ? '｜附件' : ''}</div></div>
        <div class="sub">建立 ${fmtDate(c.createdAt)}</div>
        <div><span class="status ${esc(c.status)}">${esc(CONTRACT_TEXT[c.status] || c.status)}</span><div class="sub">已簽 ${c.signedCount}/${c.partyCount}</div></div>
      </a>`).join('') : `<p class="muted">${q || st ? '沒有符合條件的合約。' : '還沒有合約，請到「建立合約」新增。'}</p>`;
  } catch (e) {
    $('list-body').innerHTML = `<p class="error">${esc(errText(e))}</p>`;
  }
}
function initList() {
  $('list-page').hidden = false;
  showNav('list');
  const params = new URLSearchParams(location.search);
  $('q').value = params.get('q') || '';
  $('q-status').value = params.get('status') || '';
  $('q').addEventListener('input', () => { clearTimeout(listTimer); listTimer = setTimeout(loadList, 350); });
  $('q-status').addEventListener('change', loadList);
  startAuth(loadList, (e) => { $('list-body').innerHTML = `<p class="error">無法登入 Firebase：${esc(e.code || e.message)}</p>`; });
}

/* =========================== 合約內容頁 =========================== */
let detail = null; // { tenantId, contract, invites }
async function detailLang(lang) {
  const c = detail.contract;
  langTabs($('d-lang'), lang, detailLang);
  let fields = null;
  if (lang !== (c.language || 'zh-TW')) {
    $('d-content').innerHTML = '<p class="muted">翻譯中…</p>';
    try {
      fields = (await call('/contracts/translate', { method: 'POST', token: await idToken(), body: { tenantId: detail.tenantId, contractId: c.id, lang } })).fields;
    } catch (e) { toast(errText(e)); return detailLang(c.language || 'zh-TW'); }
  }
  $('d-content').innerHTML = contentHtml(c, lang, fields, 'd-doc');
  if ($('d-doc')) $('d-doc').onclick = () => idToken().then((t) => openBlob(`/contracts/document?tenantId=${encodeURIComponent(detail.tenantId)}&contractId=${encodeURIComponent(c.id)}`, t)).catch((e) => toast(errText(e)));
}
function renderDetail() {
  const { contract: c, invites } = detail;
  document.title = `${c.contractNo}｜${c.title}`;
  $('d-no-label').textContent = c.contractNo;
  $('d-title').textContent = c.title;
  $('d-status').className = 'status ' + c.status;
  $('d-status').textContent = CONTRACT_TEXT[c.status] || c.status;
  $('d-no').value = c.contractNo;
  $('d-msg').className = 'muted';
  $('d-msg').textContent = `內部 ID ${c.id}｜建立 ${fmtDate(c.createdAt)}｜${invites.length ? `已簽 ${c.signedCount}/${invites.length}` : '尚未發出簽署邀請'}`;
  $('d-actions').innerHTML = (c.status === 'fully_signed' ? `<p class="notice-line">${esc(noticeText(c))}</p><button id="d-pdf" type="button">下載已簽署 PDF</button> <button id="d-notify" class="secondary" type="button">重寄完成通知</button>` : '')
    + (c.status === 'draft' ? '<span class="muted">此合約尚未發出邀請：請到「建立合約」頁的歷史紀錄開啟並發送。</span>' : '');
  if ($('d-notify')) $('d-notify').onclick = () => resendNotice(detail.tenantId, c.id, () => loadDetail(c.contractNo || c.id));
  if ($('d-pdf')) $('d-pdf').onclick = () => idToken().then((t) => downloadFile(`/contracts/signed-pdf?tenantId=${encodeURIComponent(detail.tenantId)}&contractId=${encodeURIComponent(c.id)}`, t, `${c.contractNo}.pdf`)).catch((e) => toast(errText(e)));
  $('d-parties').innerHTML = invites.length ? invites.map((v) => {
    const d = v.decision ? `<p class="muted">${esc(v.decision.name || '')}${v.decision.reason ? '｜原因：' + esc(v.decision.reason) : ''}｜${fmtDate(v.decision.at)}</p>` : '';
    const link = v.link ? `<div class="link-box">${esc(v.link)}</div><div class="row-btns"><button class="secondary" data-copy="${esc(v.link)}">複製簽署連結</button></div>` : '';
    return `<div class="card party"><div class="party-head"><span class="role">${esc(v.role)}</span><span class="status ${esc(v.status)}">${esc(INVITE_TEXT[v.status] || v.status)}</span></div>
      ${partyOf(c, v) ? `<p class="party-co">${partyOf(c, v)}</p>` : ''}<p class="muted">${esc(v.email)}｜期限 ${fmtDate(v.expiresAt)}</p>${d}${link}</div>`;
  }).join('') : (c.parties || []).map((p) => `<div class="card party"><div class="party-head"><span class="role">${esc(p.role)}</span><span class="status draft">未發邀請</span></div>${partyLine(p) ? `<p class="party-co">${partyLine(p)}</p>` : ''}<p class="muted">${esc(p.email)}</p></div>`).join('');
  $('d-parties').querySelectorAll('[data-copy]').forEach((b) => (b.onclick = async () => { try { await navigator.clipboard.writeText(b.dataset.copy); toast('已複製簽署連結'); } catch { prompt('請手動複製連結', b.dataset.copy); } }));
}
async function loadDetail(key) {
  const token = await idToken();
  let r;
  try {
    r = await call(`/contracts/status?contractNo=${encodeURIComponent(key)}`, { token });
  } catch (e) {
    if (e.status !== 404) throw e;
    r = await call(`/contracts/status?contractId=${encodeURIComponent(key)}`, { token }); // 舊合約沒有編號時用內部 ID
  }
  detail = { tenantId: r.contract.tenantId, contract: r.contract, invites: r.invites };
  renderDetail();
  await detailLang(r.contract.language || 'zh-TW');
}
async function saveNumber() {
  const no = $('d-no').value.trim();
  if (!no || no === detail.contract.contractNo) return;
  $('d-no-save').disabled = true;
  try {
    const r = await call('/contracts/number', { method: 'POST', token: await idToken(), body: { contractId: detail.contract.id, contractNo: no } });
    detail.contract.contractNo = r.contractNo;
    patchHistory(detail.contract.id, { contractNo: r.contractNo });
    history.replaceState(null, '', '/contracts/' + encodeURIComponent(r.contractNo));
    renderDetail();
    await detailLang(detail.contract.language || 'zh-TW');
    toast('合約編號已更新');
  } catch (e) {
    $('d-msg').className = 'error'; $('d-msg').textContent = errText(e);
  } finally { $('d-no-save').disabled = false; }
}
function initDetail(key) {
  $('detail-page').hidden = false;
  showNav('list');
  $('d-no-save').onclick = saveNumber;
  startAuth(() => loadDetail(key).catch((e) => { $('d-title').textContent = '無法開啟合約'; $('d-msg').className = 'error'; $('d-msg').textContent = errText(e); }),
    (e) => { $('d-msg').textContent = '無法登入 Firebase：' + (e.code || e.message); });
}

const listRoute = /^\/contracts\/?$/.test(location.pathname);
const detailKey = (location.pathname.match(/^\/contracts\/([^/]+)\/?$/) || [])[1];
if (signToken) initSigning();
else if (detailKey) initDetail(decodeURIComponent(detailKey));
else if (listRoute) initList();
else { showNav('new'); initManager(); }
