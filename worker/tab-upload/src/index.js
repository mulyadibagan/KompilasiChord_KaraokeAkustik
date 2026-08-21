import { timingSafeEqual } from 'node:crypto';

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const YOUTUBE_RE = /(?:youtu\.be\/|youtube(?:-nocookie)?\.com\/(?:watch\?.*?v=|embed\/|shorts\/))([\w-]{11})/i;

function json(body, status, origin, env) {
  const headers = new Headers({ 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  addCors(headers, origin, env);
  return new Response(JSON.stringify(body), { status, headers });
}

function addCors(headers, origin, env) {
  if (origin === env.ALLOWED_ORIGIN || origin === env.ALLOWED_ORIGIN_SECONDARY) {
    headers.set('access-control-allow-origin', origin);
    headers.set('vary', 'Origin');
  }
}

function authorized(request, env) {
  const supplied = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '');
  const expected = env.ADMIN_KEY || '';
  const left = new TextEncoder().encode(supplied);
  const right = new TextEncoder().encode(expected);
  return left.byteLength === right.byteLength && left.byteLength > 0 && timingSafeEqual(left, right);
}

function slugify(value) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function githubHeaders(env) {
  return {
    accept: 'application/vnd.github+json',
    authorization: `Bearer ${env.GITHUB_TOKEN}`,
    'content-type': 'application/json',
    'user-agent': 'kompilasichord-tab-upload-worker',
    'x-github-api-version': '2022-11-28',
  };
}

function base64(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  let binary = '';
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, Math.min(index + chunk, bytes.length)));
  }
  return btoa(binary);
}

async function githubError(response) {
  const text = await response.text();
  try { return JSON.parse(text).message || text; } catch { return text; }
}

async function submit(request, env) {
  const origin = request.headers.get('origin') || '';
  if (origin !== env.ALLOWED_ORIGIN && origin !== env.ALLOWED_ORIGIN_SECONDARY) {
    return json({ ok: false, error: 'Origin tidak diizinkan.' }, 403, origin, env);
  }
  if (!authorized(request, env)) return json({ ok: false, error: 'Kunci admin salah.' }, 401, origin, env);
  const contentLength = Number(request.headers.get('content-length') || 0);
  if (contentLength && contentLength > MAX_FILE_BYTES + 100_000) {
    return json({ ok: false, error: 'Ukuran permintaan terlalu besar.' }, 413, origin, env);
  }

  let form;
  try { form = await request.formData(); } catch { return json({ ok: false, error: 'Form upload tidak valid.' }, 400, origin, env); }
  const file = form.get('gp5');
  const youtubeUrl = String(form.get('youtube_url') || '').trim();
  const title = String(form.get('title') || '').trim();
  const artist = String(form.get('artist') || '').trim();
  const requestedSlug = String(form.get('slug') || '').trim();
  if (!(file instanceof File)) return json({ ok: false, error: 'File Guitar Pro belum dipilih.' }, 400, origin, env);
  if (file.size < 32 || file.size > MAX_FILE_BYTES) return json({ ok: false, error: 'File harus berukuran 32 byte–5 MB.' }, 400, origin, env);
  const extension = (file.name.match(/\.(gp3|gp4|gp5)$/i) || [])[1];
  if (!extension) return json({ ok: false, error: 'Ekstensi harus .gp3, .gp4, atau .gp5.' }, 400, origin, env);
  if (!YOUTUBE_RE.test(youtubeUrl)) return json({ ok: false, error: 'URL YouTube tidak valid.' }, 400, origin, env);

  const bytes = await file.arrayBuffer();
  const head = new Uint8Array(bytes, 0, Math.min(bytes.byteLength, 64));
  if (head[0] === 0x50 && head[1] === 0x4b) return json({ ok: false, error: 'File adalah GP7/GPX berbentuk ZIP. Ekspor ulang sebagai GP5.' }, 400, origin, env);
  const signature = String.fromCharCode(...head);
  if (!signature.includes('FICHIER GUITAR PRO')) return json({ ok: false, error: 'Signature Guitar Pro 3/4/5 tidak ditemukan.' }, 400, origin, env);

  const slug = slugify(requestedSlug || `${artist || 'tab'}-${title || file.name.replace(/\.[^.]+$/, '')}`);
  if (!slug) return json({ ok: false, error: 'Slug tidak valid.' }, 400, origin, env);
  const filename = `${slug}.${extension.toLowerCase()}`;
  const path = `input/${filename}`;
  const apiRoot = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}`;
  const existing = await fetch(`${apiRoot}/contents/${encodeURI(path)}?ref=${encodeURIComponent(env.GITHUB_BRANCH)}`, { headers: githubHeaders(env) });
  if (existing.ok) return json({ ok: false, error: `File ${path} sudah ada. Gunakan slug lain.` }, 409, origin, env);
  if (existing.status !== 404) return json({ ok: false, error: `GitHub gagal memeriksa file: ${await githubError(existing)}` }, 502, origin, env);

  const upload = await fetch(`${apiRoot}/contents/${encodeURI(path)}`, {
    method: 'PUT', headers: githubHeaders(env), body: JSON.stringify({
      message: `Upload GP5: ${slug}`, content: base64(bytes), branch: env.GITHUB_BRANCH,
    }),
  });
  if (!upload.ok) return json({ ok: false, error: `Upload GitHub gagal: ${await githubError(upload)}` }, 502, origin, env);
  const uploaded = await upload.json();

  const dispatch = await fetch(`${apiRoot}/actions/workflows/build-tab-music.yml/dispatches`, {
    method: 'POST', headers: githubHeaders(env), body: JSON.stringify({
      ref: env.GITHUB_BRANCH,
      inputs: { gp5_path: path, youtube_url: youtubeUrl, title, artist, slug },
    }),
  });
  if (!dispatch.ok) return json({ ok: false, error: `File terunggah, tetapi workflow gagal dimulai: ${await githubError(dispatch)}` }, 502, origin, env);

  console.log(JSON.stringify({ event: 'tab_upload', slug, size: file.size, commit: uploaded.commit?.sha }));
  return json({
    ok: true, slug, path,
    commitUrl: uploaded.commit?.html_url,
    actionsUrl: `https://github.com/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/build-tab-music.yml`,
  }, 202, origin, env);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('origin') || '';
    if (request.method === 'OPTIONS') {
      const headers = new Headers({
        'access-control-allow-headers': 'authorization, content-type',
        'access-control-allow-methods': 'POST, OPTIONS',
        'access-control-max-age': '600',
      });
      addCors(headers, origin, env);
      return new Response(null, { status: 204, headers });
    }
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/health') return json({ ok: true }, 200, origin, env);
    if (request.method !== 'POST' || url.pathname !== '/submit') return json({ ok: false, error: 'Not found.' }, 404, origin, env);
    try { return await submit(request, env); }
    catch (error) {
      console.error(JSON.stringify({ event: 'tab_upload_error', message: error instanceof Error ? error.message : String(error) }));
      return json({ ok: false, error: 'Terjadi kesalahan internal.' }, 500, origin, env);
    }
  },
};
