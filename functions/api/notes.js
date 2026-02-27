async function ghGet(env) {
  const owner = env.GITHUB_OWNER;
  const repo = env.GITHUB_REPO;
  const token = env.GITHUB_TOKEN;
  const path = env.NOTES_PATH || 'notes.txt';
  const branch = env.GITHUB_BRANCH || 'main';
  if (!owner || !repo || !token) return null;
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}?ref=${encodeURIComponent(branch)}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } });
  if (!r.ok) return null;
  const j = await r.json();
  const c = j && j.content ? j.content : '';
  const bin = atob(c);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const text = new TextDecoder('utf-8').decode(bytes);
  return { text, sha: j.sha };
}
async function ghPut(env, content, sha) {
  const owner = env.GITHUB_OWNER;
  const repo = env.GITHUB_REPO;
  const token = env.GITHUB_TOKEN;
  const path = env.NOTES_PATH || 'notes.txt';
  const branch = env.GITHUB_BRANCH || 'main';
  if (!owner || !repo || !token) return false;
  const bytes = new TextEncoder().encode(content);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const base64 = btoa(bin);
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(path)}`;
  const body = { message: 'Update notes', content: base64, branch };
  if (sha) body.sha = sha;
  const r = await fetch(url, { method: 'PUT', headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' }, body: JSON.stringify(body) });
  return r.ok;
}
export async function onRequestGet({ env }) {
  try {
    const hasGh = !!(env.GITHUB_OWNER && env.GITHUB_REPO && env.GITHUB_TOKEN);
    if (hasGh) {
      const gh = await ghGet(env);
      if (gh) return new Response(JSON.stringify({ content: gh.text || '' }), { headers: { 'content-type': 'application/json' } });
    }
    if (env.NOTES_BUCKET) {
      const obj = await env.NOTES_BUCKET.get('notes.txt');
      const text = obj ? await obj.text() : '';
      return new Response(JSON.stringify({ content: text || '' }), { headers: { 'content-type': 'application/json' } });
    }
    if (env.NOTES) {
      const v = await env.NOTES.get('main');
      return new Response(JSON.stringify({ content: v || '' }), { headers: { 'content-type': 'application/json' } });
    }
    return new Response(JSON.stringify({ error: hasGh ? 'storage_unavailable' : 'missing_github_env' }), { status: 503, headers: { 'content-type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'read_error' }), { status: 500, headers: { 'content-type': 'application/json' } });
  }
}
export async function onRequestPost({ request, env }) {
  try {
    const data = await request.json();
    const content = data && data.content ? data.content : '';
    const hasGh = !!(env.GITHUB_OWNER && env.GITHUB_REPO && env.GITHUB_TOKEN);
    if (hasGh) {
      const ghMeta = await ghGet(env);
      if (await ghPut(env, content, ghMeta ? ghMeta.sha : undefined)) {
        return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' } });
      }
      return new Response(JSON.stringify({ ok: false, error: 'github_write_failed' }), { status: 502, headers: { 'content-type': 'application/json' } });
    }
    if (env.NOTES_BUCKET) {
      await env.NOTES_BUCKET.put('notes.txt', content, { httpMetadata: { contentType: 'text/plain; charset=utf-8' } });
      return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' } });
    }
    if (env.NOTES) {
      await env.NOTES.put('main', content);
      return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' } });
    }
    return new Response(JSON.stringify({ ok: false, error: 'missing_github_env' }), { status: 503, headers: { 'content-type': 'application/json' } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: 'write_error' }), { status: 500, headers: { 'content-type': 'application/json' } });
  }
}
export const onRequestPut = onRequestPost;
