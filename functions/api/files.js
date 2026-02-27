export async function onRequestGet({ env }) {
  const owner = env.GITHUB_OWNER;
  const repo = env.GITHUB_REPO;
  const token = env.GITHUB_TOKEN;
  const branch = env.GITHUB_BRANCH || 'main';
  const dir = env.DOWNLOADS_PATH || 'downloads';
  if (!owner || !repo || !token) {
    return new Response(JSON.stringify({ error: 'missing_github_env' }), { status: 503, headers: { 'content-type': 'application/json' } });
  }
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(dir)}?ref=${encodeURIComponent(branch)}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json' } });
  if (!r.ok) {
    return new Response(JSON.stringify({ error: 'github_list_failed' }), { status: 502, headers: { 'content-type': 'application/json' } });
  }
  const items = await r.json();
  const files = Array.isArray(items) ? items.filter(x => x && x.type === 'file').map(x => ({ name: x.name, path: `${dir}/${x.name}`, desc: '点击下载' })) : [];
  return new Response(JSON.stringify(files), { headers: { 'content-type': 'application/json' } });
}
