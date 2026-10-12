const $ = id => document.getElementById(id);
const token = location.pathname.startsWith('/sign/') ? decodeURIComponent(location.pathname.split('/')[2] || '') : new URLSearchParams(location.search).get('token');
const base = '/api';
async function call(path, options = {}) { const r = await fetch(`${base}${path}`, {headers:{'Content-Type':'application/json',...(options.headers||{})}, ...options}); const data = await r.json().catch(()=>({})); if(!r.ok) throw new Error(data.error || `HTTP ${r.status}`); return data; }
async function init() {
  if (!token) return;
  $('landing').hidden = true; $('signing').hidden = false;
  try { const data = await call(`/signature/invite?token=${encodeURIComponent(token)}`); $('title').textContent = `${data.contract.title || '合約'}｜${data.invite.role} 簽署／Signing`; $('summary').textContent = `${data.contract.summary || ''} 期限／Expires: ${new Date(data.invite.expiresAt).toLocaleString()}`; } catch (e) { $('title').textContent = '邀請無效／Invalid invitation'; $('result').textContent = e.message; ['sign','changes','decline'].forEach(id => $(id).disabled = true); return; }
  async function action(kind) { const name=$('name').value.trim(), reason=$('reason').value.trim(); if(kind==='sign' && (!name || !$('consent').checked)) return $('result').textContent='請填姓名並同意電子簽署／Name and consent are required.'; if(kind!=='sign' && !reason) return $('result').textContent='請填寫原因／A reason is required.'; try { const result=await call('/signature/action',{method:'POST',body:JSON.stringify({token,action:kind,name,reason,consent:$('consent').checked})}); $('result').className='ok'; $('result').textContent=`完成／Completed: ${result.inviteStatus}. Token 已失效，不能重複操作／The token is now consumed.`; ['sign','changes','decline'].forEach(id=>$(id).disabled=true); } catch(e) { $('result').textContent=e.message; } }
  $('sign').onclick=()=>action('sign'); $('changes').onclick=()=>action('request_changes'); $('decline').onclick=()=>action('decline');
}
init();
