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

const LOGIN = `<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login Admin Kompilasi Chord</title><style>body{font-family:system-ui;margin:0;background:#f5f5f5;color:#18181b;display:grid;place-items:center;min-height:100vh}.box{width:min(390px,calc(100% - 28px));background:#fff;border:1px solid #ddd;border-radius:16px;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,.08)}h1{font-size:24px;margin:0 0 6px}p{color:#666;margin:0 0 20px}label{display:block;font-weight:700;margin:12px 0 6px}input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #bbb;border-radius:9px;font-size:16px}input[readonly]{background:#f4f4f5;color:#52525b}button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:9px;background:#b91c1c;color:#fff;font-weight:800;font-size:15px;cursor:pointer}.err{background:#fff1f2;color:#9f1239;padding:10px;border-radius:8px;margin-bottom:14px}</style></head><body><form class="box" method="post" action="/login"><h1>Admin Kompilasi Chord</h1><p>Masuk untuk membuka Formatter SOP.</p>{{ERROR}}<label>Username</label><input name="username" value="admin" autocomplete="username" readonly required><label>Password</label><input name="password" type="password" autocomplete="current-password" required autofocus><button type="submit">Masuk</button></form></body></html>`;

const APP = String.raw`<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Formatter SOP Kompilasi Chord</title><style>:root{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#18181b;background:#f6f6f7}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1200px;margin:auto;padding:24px}h1{margin:0 0 6px;font-size:28px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center}.sub{margin:0 0 20px;color:#666}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#fff;border:1px solid #ddd;border-radius:14px;padding:16px}label{display:block;font-weight:700;margin-bottom:8px}textarea{width:100%;min-height:560px;resize:vertical;border:1px solid #ccc;border-radius:10px;padding:14px;font:15px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre;overflow:auto}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.btn{border:0;border-radius:9px;padding:10px 15px;font-weight:700;cursor:pointer}.primary{background:#b91c1c;color:#fff}.secondary{background:#e5e7eb;color:#111}.keyrow{display:flex;gap:10px;align-items:center;margin-bottom:12px}.keyrow input{width:100px;padding:8px;border:1px solid #ccc;border-radius:8px}.checks{display:grid;gap:8px;margin-top:10px}.ok,.warn{padding:9px 11px;border-radius:8px;font-size:14px}.ok{background:#ecfdf5}.warn{background:#fff7ed}.logout{font:inherit;border:0;background:#eee;padding:8px 12px;border-radius:8px;cursor:pointer}@media(max-width:850px){.grid{grid-template-columns:1fr}.wrap{padding:14px}textarea{min-height:420px}}</style></head><body><div class="wrap"><div class="top"><div><h1>Formatter SOP Kompilasi Chord</h1><p class="sub">Paste chord mentah apa adanya. Sistem membuat format siap Blogger.</p></div><form method="post" action="/logout"><button class="logout">Keluar</button></form></div><div class="keyrow card"><label for="manualKey" style="margin:0">Data-key:</label><input id="manualKey" placeholder="otomatis"><span>Kosongkan agar sistem mendeteksi key awal otomatis.</span></div><div class="actions"><button class="btn primary" id="processBtn">Proses SOP</button><button class="btn secondary" id="copyBtn">Copy untuk Blogger</button><button class="btn secondary" id="clearBtn">Bersihkan</button></div><div class="grid"><div class="card"><label for="input">Chord mentah</label><textarea id="input" spellcheck="false" placeholder="Intro :&#10;Dm Gm Bb A&#10;Dm Gm Bb A&#10;&#10;Reff :&#10;..."></textarea></div><div class="card"><label for="output">Hasil SOP</label><textarea id="output" spellcheck="false" readonly></textarea><div class="checks" id="checks"></div></div></div></div><script>
const $=s=>document.querySelector(s),input=$('#input'),output=$('#output'),checks=$('#checks'),manualKey=$('#manualKey');
const baseChord='[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\\d*(?:\\/[A-G](?:#|b)?)?';
const chordToken=new RegExp('^(?:-?'+baseChord+')(?:-'+baseChord+')*$');
function unwrap(raw){const m=raw.match(/<pre\b[^>]*data-key\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/pre>/i);if(m)return{key:m[1].trim(),body:m[2].replace(/^\n+|\n+$/g,'')};return{key:'',body:raw.replace(/^\s+|\s+$/g,'')}}
function canonicalSection(line){let t=line.trim().replace(/^\[|\]$/g,'').trim();if(/^intro\s*:?$/i.test(t))return'[Intro :]';if(/^(?:int\.?|musik|interlude)\s*:?$/i.test(t))return'[Interlude :]';if(/^(?:reff(?:rain)?|chorus)\s*:?$/i.test(t))return'[Reff :]';if(/^(?:reff\s+overtone|overtone)\s*:?$/i.test(t))return'[Reff Overtone :]';if(/^pre[- ]?(?:reff|chorus)\s*:?$/i.test(t))return'[Pre-Reff :]';if(/^post[- ]?(?:reff|chorus)\s*:?$/i.test(t))return'[Post-Reff :]';if(/^bridge\s*:?$/i.test(t))return'[Bridge :]';if(/^outro\s*:?$/i.test(t))return'[Outro :]';let v=t.match(/^verse\s*(\d+)?\s*:?$/i);return v?('[Verse'+(v[1]?' '+v[1]:'')+' :]'):null}
function splitInputLines(body){const inline=/^\s*\[?((?:reff\s+overtone|pre[- ]?(?:reff|chorus)|post[- ]?(?:reff|chorus)|intro|musik|interlude|reff(?:rain)?|chorus|overtone|bridge|outro|verse\s*\d*))\s*:\]?\s*(.*?)\s*$|^\s*(int)\.\s*(.*?)\s*$/i;let expanded=[],inlineOffset=0;for(const line of body.replace(/\r/g,'').split('\n')){const match=line.match(inline);if(match){const label=match[1]||match[3],remainder=match[2]||match[4]||'';expanded.push(canonicalSection(label+':'));if(remainder){inlineOffset=line.indexOf(remainder);expanded.push(remainder)}else inlineOffset=0;continue}if(!line.trim()){expanded.push(line);inlineOffset=0;continue}if(inlineOffset){const lead=(line.match(/^ */)||[''])[0].length;expanded.push(line.slice(Math.min(lead,inlineOffset)));continue}expanded.push(line)}return expanded}
function isSection(line){return !!canonicalSection(line)}
function removeStandaloneMarkers(lines){return lines.filter(line=>!/^\s*\*\)\s*$/.test(line))}
function normalizeDanglingTransitions(line){return line.replace(/([A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*(?:\/[A-G](?:#|b)?)?)-( +)(?=[A-G])/g,(_,chord,spaces)=>chord+' -'+spaces.slice(1))}
function normalizeChordNotation(line){return normalizeDanglingTransitions(line).replace(/\((-?[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add)?\d*(?:\/[A-G](?:#|b)?)?)\)/g,'$1').replace(/\s*[\[(]\s*\d+\s*x\s*[\])]\s*$/i,'')}
function isLikelyChordLine(line){const t=normalizeChordNotation(line).replace(/\.{2,}/g,m=>' '.repeat(m.length)).trim();if(!t||isSection(t))return false;const parts=t.split(/\s+/);return parts.length>0&&parts.every(p=>chordToken.test(p))}
function expandChordRepeats(lines){let expanded=[];for(const line of lines){const match=line.match(/^(.*?)\s*[\[(]\s*(\d+)\s*x\s*[\])]\s*$/i);if(!match){expanded.push(line);continue}const progression=match[1].replace(/\s+$/,''),count=Number(match[2]);if(!progression.trim()||!Number.isSafeInteger(count)||count<1||!isLikelyChordLine(progression)){expanded.push(line);continue}for(let remaining=count;remaining>0;remaining-=2)expanded.push(remaining>1?progression+' '+progression.trim():progression)}return expanded}
function replaceEllipsisPreserveColumns(line){return line.replace(/\.{2,}/g,m=>' '.repeat(m.length))}
function normalizeTransitionToken(token){return token.replace(/(?<=[A-G0-9#bm])-(?=[A-G])/g,' -')}
function normalizeTransitionChordLine(line){if(!isLikelyChordLine(line))return line;let original=[...line],out='',i=0;while(i<original.length){if(original[i]===' '){out+=' ';i++;continue}let j=i;while(j<original.length&&original[j]!==' ')j++;let tok=original.slice(i,j).join(''),norm=normalizeTransitionToken(tok),delta=norm.length-tok.length;out+=norm;if(delta>0){let k=j,spaces=0;while(k<original.length&&original[k]===' '){spaces++;k++}j+=Math.min(delta,Math.max(0,spaces-1))}i=j}return out}
function normalizeSections(lines){let substantive=false,introSeen=false,verseNumber=0;return lines.map(line=>{const sec=canonicalSection(line);if(sec){if(sec==='[Intro :]'){if(introSeen||substantive)return'[Interlude :]';introSeen=true}const numberedVerse=sec.match(/^\[Verse\s+(\d+)\s*:\]$/i);if(numberedVerse)verseNumber=Math.max(verseNumber,Number(numberedVerse[1]));if(sec==='[Verse :]')return'[Verse '+(++verseNumber)+' :]';return sec}if(line.trim())substantive=true;return line})}
function removeMisplacedVerse2(lines){const firstReff=lines.findIndex(line=>canonicalSection(line)==='[Reff :]');if(firstReff<0)return lines;return lines.filter((line,index)=>!(index<firstReff&&canonicalSection(line)==='[Verse 2 :]'))}
function removeIndentedVerse2(lines){let result=[],i=0;while(i<lines.length){if(!lines[i].trim()){result.push(lines[i++]);continue}let j=i;while(j<lines.length&&lines[j].trim())j++;const block=lines.slice(i,j),startsVerse2=canonicalSection(block[0])==='[Verse 2 :]',lyrics=block.slice(1).filter(line=>line.trim()&&!isSection(line)&&!isLikelyChordLine(line)),indented=lyrics.some(line=>/^\s+/.test(line));result.push(...(startsVerse2&&indented?block.slice(1):block));i=j}return result}
function addImplicitVerses(lines){let result=[],seenReff=false,i=0;const sections=lines.map(canonicalSection).filter(Boolean),hasVerse1=sections.includes('[Verse 1 :]'),hasVerse2=sections.includes('[Verse 2 :]');let verse1Added=hasVerse1,verse2Added=hasVerse2;while(i<lines.length){if(!lines[i].trim()){result.push(lines[i++]);continue}let j=i;while(j<lines.length&&lines[j].trim())j++;const block=lines.slice(i,j),blockSections=block.map(canonicalSection).filter(Boolean),hasSection=blockSections.length>0,hasChord=block.some(isLikelyChordLine),lyricLines=block.filter(line=>line.trim()&&!isSection(line)&&!isLikelyChordLine(line)),hasLyric=lyricLines.length>0,hasIndentedLyric=lyricLines.some(line=>/^\s+/.test(line));if(!hasSection&&hasChord&&hasLyric){if(!seenReff&&!verse1Added){result.push('[Verse 1 :]');verse1Added=true}else if(seenReff&&!verse2Added&&!hasIndentedLyric){result.push('[Verse 2 :]');verse2Added=true}}result.push(...block);if(blockSections.some(sec=>/^\[Verse(?:\s+\d+)?\s*:\]$/i.test(sec))){if(seenReff)verse2Added=true;else verse1Added=true}if(blockSections.some(sec=>/^\[Reff(?:\s+Overtone)?\s*:\]$/i.test(sec)))seenReff=true;i=j}return result}
function shiftChordLyricPair(chord,lyric){const lyricLead=(lyric.match(/^ */)||[''])[0].length;if(!lyricLead)return[chord,lyric];const chordLead=(chord.match(/^ */)||[''])[0].length;if(chordLead<lyricLead)return[chord,lyric];return[chord.slice(lyricLead),lyric.slice(lyricLead)]}
function normalizeChordLyricPairs(lines){for(let i=0;i<lines.length;i++){if(!isLikelyChordLine(lines[i]))continue;let j=i+1;while(j<lines.length&&lines[j].trim()==='')j++;if(j<lines.length&&!isSection(lines[j])&&!isLikelyChordLine(lines[j]))[lines[i],lines[j]]=shiftChordLyricPair(lines[i],lines[j])}return lines}
function formatBody(body){let lines=splitInputLines(body);lines=removeStandaloneMarkers(lines);lines=expandChordRepeats(lines);lines=removeMisplacedVerse2(lines);lines=removeIndentedVerse2(lines);lines=addImplicitVerses(lines);lines=normalizeSections(lines);lines=lines.map(replaceEllipsisPreserveColumns);lines=lines.map(normalizeChordNotation);lines=lines.map(line=>isLikelyChordLine(line)?normalizeTransitionChordLine(line):line);lines=normalizeChordLyricPairs(lines);return lines.map(x=>x.replace(/\s+$/,'')).join('\n').replace(/\n{3,}/g,'\n\n').trim()}
function rootOf(token){let t=token.replace(/^-+/,'').split(/\s+/)[0],m=t.match(/^([A-G](?:#|b)?)(m?)/);return m?m[1]+m[2]:''}
function detectKey(body){for(const line of splitInputLines(body)){const cleaned=normalizeChordNotation(line).replace(/\.{2,}/g,m=>' '.repeat(m.length));if(isLikelyChordLine(cleaned)){const root=rootOf(cleaned.trim().split(/\s+/)[0]);if(root)return root}}return''}
function validate(key,body,detected,hadKey){let items=[];items.push([!!key,key?('✓ data-key: '+key+(!hadKey&&detected?' (otomatis)':'')):'⚠ data-key belum terdeteksi']);items.push([/^\[Intro\s*:\]/m.test(body),'✓ Intro dikenali']);items.push([!/(^|\n)\s*Musik\s*:/im.test(body),'✓ Musik sudah menjadi Interlude']);items.push([!body.match(/\.{2,}/),'✓ Tidak ada ellipsis']);let bad=body.split('\n').filter(isLikelyChordLine).some(l=>/[A-G](?:#|b|m|\d)*(?:\/[A-G](?:#|b)?)?-[A-G]/.test(l));items.push([!bad,'✓ Chord transisi kompatibel transposer (A -G)']);items.push([true,'✓ Output otomatis dibungkus <pre data-key="...">']);checks.innerHTML=items.map(item=>'<div class="'+(item[0]?'ok':'warn')+'">'+item[1]+'</div>').join('')}
function run(){const src=unwrap(input.value),formattedBody=formatBody(src.body),detected=detectKey(src.body),key=(manualKey.value.trim()||src.key||detected||'').trim();output.value='<pre data-key="'+key+'">\n\n'+formattedBody+'\n\n</pre>';validate(key,formattedBody,detected,!!src.key)}
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
      if (!(await safeEqual(username, expectedUser)) || !(await safeEqual(password, env.FORMATTER_PASSWORD))) return html(LOGIN.replace('{{ERROR}}', '<div class="err">Password salah.</div>'), 401);
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
