const SESSION_SECONDS = 60 * 60 * 24 * 365;
const SESSION_COOKIE = 'kc_formatter';

function html(body, status = 200, headers = {}) {
  return new Response(body, { status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', ...headers } });
}

function redirect(location, headers = {}) {
  return new Response(null, { status: 302, headers: { location, 'cache-control': 'no-store', ...headers } });
}

function b64url(bytes) {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function fromB64url(value) {
  const s = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = s + '='.repeat((4 - (s.length % 4)) % 4);
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
}

async function hmac(value, secret) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value)));
}

async function makeSession(user, secret) {
  const payload = b64url(new TextEncoder().encode(JSON.stringify({ u: user, exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS })));
  const sig = b64url(await hmac(payload, secret));
  return `${payload}.${sig}`;
}

async function readSession(request, env) {
  const cookie = request.headers.get('cookie') || '';
  const m = cookie.match(new RegExp(`(?:^|;\\s*)${SESSION_COOKIE}=([^;]+)`));
  if (!m || !env.SESSION_SECRET) return null;
  const [payload, sig] = m[1].split('.');
  if (!payload || !sig) return null;
  const expected = await hmac(payload, env.SESSION_SECRET);
  const supplied = fromB64url(sig);
  if (expected.length !== supplied.length) return null;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected[i] ^ supplied[i];
  if (diff !== 0) return null;
  try {
    const data = JSON.parse(new TextDecoder().decode(fromB64url(payload)));
    if (!data.u || !data.exp || data.exp < Math.floor(Date.now() / 1000)) return null;
    return data;
  } catch { return null; }
}

function sessionCookie(token, maxAge = SESSION_SECONDS) {
  return `${SESSION_COOKIE}=${token}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
}

async function safeEqual(a, b) {
  const aa = new TextEncoder().encode(a || '');
  const bb = new TextEncoder().encode(b || '');
  if (aa.length !== bb.length || aa.length === 0) return false;
  let diff = 0;
  for (let i = 0; i < aa.length; i++) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

const LOGIN = `<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login Admin Kompilasi Chord</title><style>body{font-family:system-ui;margin:0;background:#f5f5f5;color:#18181b;display:grid;place-items:center;min-height:100vh}.box{width:min(390px,calc(100% - 28px));background:#fff;border:1px solid #ddd;border-radius:16px;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,.08)}h1{font-size:24px;margin:0 0 6px}p{color:#666;margin:0 0 20px}label{display:block;font-weight:700;margin:12px 0 6px}input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #bbb;border-radius:9px;font-size:16px}button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:9px;background:#b91c1c;color:#fff;font-weight:800;font-size:15px;cursor:pointer}.err{background:#fff1f2;color:#9f1239;padding:10px;border-radius:8px;margin-bottom:14px}</style></head><body><form class="box" method="post" action="/login"><h1>Admin Kompilasi Chord</h1><p>Masuk untuk membuka Formatter SOP.</p>{{ERROR}}<label>Username</label><input name="username" autocomplete="username" required autofocus><label>Password</label><input name="password" type="password" autocomplete="current-password" required><button type="submit">Masuk</button></form></body></html>`;

const APP = `<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Formatter SOP Kompilasi Chord</title><style>:root{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#18181b;background:#f6f6f7}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}h1{margin:0 0 6px;font-size:28px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center}.sub{margin:0 0 20px;color:#666}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#fff;border:1px solid #ddd;border-radius:14px;padding:16px}label{display:block;font-weight:700;margin-bottom:8px}textarea{width:100%;min-height:560px;resize:vertical;border:1px solid #ccc;border-radius:10px;padding:14px;font:15px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre;overflow:auto}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.btn{border:0;border-radius:9px;padding:10px 15px;font-weight:700;cursor:pointer}.primary{background:#b91c1c;color:#fff}.secondary{background:#e5e7eb;color:#111}.keyrow{display:flex;gap:10px;align-items:center;margin-bottom:12px}.keyrow input{width:100px;padding:8px;border:1px solid #ccc;border-radius:8px}.checks{display:grid;gap:8px;margin-top:10px}.ok,.warn{padding:9px 11px;border-radius:8px;font-size:14px}.ok{background:#ecfdf5}.warn{background:#fff7ed}.logout{font:inherit;border:0;background:#eee;padding:8px 12px;border-radius:8px;cursor:pointer}@media(max-width:850px){.grid{grid-template-columns:1fr}.wrap{padding:14px}textarea{min-height:420px}}</style></head><body><div class="wrap"><div class="top"><div><h1>Formatter SOP Kompilasi Chord</h1><p class="sub">Paste chord mentah apa adanya. Sistem membuat format siap Blogger.</p></div><form method="post" action="/logout"><button class="logout">Keluar</button></form></div><div class="keyrow card"><label for="manualKey" style="margin:0">Data-key:</label><input id="manualKey" placeholder="otomatis"><span>Kosongkan agar sistem mendeteksi key awal otomatis.</span></div><div class="actions"><button class="btn primary" id="processBtn">Proses SOP</button><button class="btn secondary" id="copyBtn">Copy untuk Blogger</button><button class="btn secondary" id="clearBtn">Bersihkan</button></div><div class="grid"><div class="card"><label for="input">Chord mentah</label><textarea id="input" spellcheck="false" placeholder="Intro :\nDm Gm Bb A\nDm Gm Bb A\n\nReff :\n..."></textarea></div><div class="card"><label for="output">Hasil SOP</label><textarea id="output" spellcheck="false" readonly></textarea><div class="checks" id="checks"></div></div></div></div><script>
const $=s=>document.querySelector(s),input=$('#input'),output=$('#output'),checks=$('#checks'),manualKey=$('#manualKey');
const token=/^-?[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*(?:\/[A-G](?:#|b)?)?(?:-[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*)*$/;
function section(line){let t=line.trim().replace(/^\[|\]$/g,'').trim();if(/^intro\s*:?$/i.test(t))return'[Intro :]';if(/^(musik|interlude)\s*:?$/i.test(t))return'[Interlude :]';if(/^(reff|chorus)\s*:?$/i.test(t))return'[Reff :]';if(/^(reff\s+overtone|overtone)\s*:?$/i.test(t))return'[Reff Overtone :]';if(/^pre[- ]?(reff|chorus)\s*:?$/i.test(t))return'[Pre-Reff :]';if(/^post[- ]?(reff|chorus)\s*:?$/i.test(t))return'[Post-Reff :]';if(/^bridge\s*:?$/i.test(t))return'[Bridge :]';if(/^outro\s*:?$/i.test(t))return'[Outro :]';let v=t.match(/^verse\s*(\d+)?\s*:?$/i);return v?('[Verse'+(v[1]?' '+v[1]:'')+' :]'):null}
function chordLine(line){const t=line.trim();return !!t&&!section(t)&&t.split(/\s+/).every(x=>token.test(x))}
function normalizeChordLine(line){if(!chordLine(line))return line;let out='';for(let i=0;i<line.length;){if(line[i]===' '){out+=' ';i++;continue}let j=i;while(j<line.length&&line[j]!==' ')j++;let raw=line.slice(i,j),norm=raw.replace(/([A-G](?:#|b)?(?:m|\d|\/|#|b)*)-(?=[A-G])/g,'$1 -'),delta=norm.length-raw.length;out+=norm;if(delta>0){let k=j,n=0;while(k<line.length&&line[k]===' '){n++;k++}j+=Math.min(delta,Math.max(0,n-1))}i=j}return out}
function formatBody(raw){let lines=raw.replace(/\r/g,'').trim().split('\n'),introSeen=false,substantive=false;lines=lines.map(l=>{const s=section(l);if(s){if(s==='[Intro :]'){if(introSeen||substantive)return'[Interlude :]';introSeen=true}return s}if(l.trim())substantive=true;return l});lines=lines.map(l=>chordLine(l)?normalizeChordLine(l):l.replace(/\.{2,}/g,m=>' '.repeat(m.length)));let inReff=false;for(let i=0;i<lines.length;i++){const s=section(lines[i]);if(s){inReff=/^\[Reff(?:\s+Overtone)?\s*:\]$/i.test(s);continue}if(!inReff||!chordLine(lines[i]))continue;let j=i+1;while(j<lines.length&&!lines[j].trim())j++;if(j<lines.length&&!section(lines[j])&&!chordLine(lines[j])){const ll=(lines[j].match(/^ */)||[''])[0].length,cl=(lines[i].match(/^ */)||[''])[0].length,sh=Math.min(ll,cl);lines[i]=lines[i].slice(sh);lines[j]=lines[j].slice(sh)}}return lines.map(x=>x.replace(/\s+$/,'')).join('\n').replace(/\n{3,}/g,'\n\n').trim()}
function root(tok){const m=tok.replace(/^-+/,'').match(/^([A-G](?:#|b)?m?)/);return m?m[1]:''}
function detectKey(raw){const lines=raw.replace(/\r/g,'').split('\n');let intro=false,cs=[];for(const l of lines){const s=section(l);if(s){if(s==='[Intro :]'){intro=true;continue}if(intro)break;continue}if(intro&&chordLine(l))for(const p of l.trim().split(/\s+/)){const r=root(p);if(r)cs.push(r)}}if(!cs.length)for(const l of lines)if(chordLine(l)){const r=root(l.trim().split(/\s+/)[0]);if(r){cs=[r];break}}if(!cs.length)return'';const count={};for(const c of cs)count[c]=(count[c]||0)+1;return Object.entries(count).sort((a,b)=>b[1]-a[1])[0][0]||cs[0]}
function run(){let raw=input.value.trim(),m=raw.match(/<pre\b[^>]*data-key=["']([^"']+)["'][^>]*>([\s\S]*?)<\/pre>/i),key='',body=raw;if(m){key=m[1].trim();body=m[2]}const detected=detectKey(body),finalKey=(manualKey.value.trim()||key||detected).trim(),formatted=formatBody(body);output.value='<pre data-key="'+finalKey+'">\n\n'+formatted+'\n\n</pre>';checks.innerHTML='<div class="'+(finalKey?'ok':'warn')+'">'+(finalKey?'✓ data-key: '+finalKey:'⚠ data-key belum terdeteksi')+'</div><div class="ok">✓ Struktur section distandarkan</div><div class="ok">✓ Ellipsis dihapus tanpa trim alignment global</div><div class="ok">✓ Chord transisi dibuat kompatibel transposer</div>'}
$('#processBtn').onclick=run;$('#copyBtn').onclick=async()=>{if(!output.value)run();await navigator.clipboard.writeText(output.value);$('#copyBtn').textContent='Tersalin ✓';setTimeout(()=>$('#copyBtn').textContent='Copy untuk Blogger',1200)};$('#clearBtn').onclick=()=>{input.value='';output.value='';checks.innerHTML='';manualKey.value='';input.focus()};
</script></body></html>`;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/health') return new Response('ok');
    if (request.method === 'POST' && url.pathname === '/login') {
      const form = await request.formData();
      const username = String(form.get('username') || '');
      const password = String(form.get('password') || '');
      const expectedUser = env.FORMATTER_USER || 'admin';
      if (!env.FORMATTER_PASSWORD || !env.SESSION_SECRET) return html(LOGIN.replace('{{ERROR}}', '<div class="err">Server login belum dikonfigurasi.</div>'), 503);
      if (!(await safeEqual(username, expectedUser)) || !(await safeEqual(password, env.FORMATTER_PASSWORD))) return html(LOGIN.replace('{{ERROR}}', '<div class="err">Username atau password salah.</div>'), 401);
      const token = await makeSession(expectedUser, env.SESSION_SECRET);
      return redirect('/', { 'set-cookie': sessionCookie(token) });
    }
    if (request.method === 'POST' && url.pathname === '/logout') {
      return redirect('/', { 'set-cookie': sessionCookie('', 0) });
    }
    const session = await readSession(request, env);
    if (!session) return html(LOGIN.replace('{{ERROR}}', ''));
    // Sliding one-year session: every authenticated page load replaces both the
    // signed expiry and the persistent cookie expiry.
    const refreshedToken = await makeSession(session.u, env.SESSION_SECRET);
    return html(APP, 200, { 'set-cookie': sessionCookie(refreshedToken) });
  }
};
