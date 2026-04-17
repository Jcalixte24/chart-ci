// api/proxy.js — Vercel Serverless Function (CommonJS)
module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const target = req.query.url;
  if (!target) return res.status(400).json({ error: 'url manquant' });

  try {
    const host = new URL(target).hostname;
    if (host !== 'kworb.net' && !host.endsWith('.kworb.net'))
      return res.status(403).json({ error: 'Domaine non autorisé' });
  } catch {
    return res.status(400).json({ error: 'URL invalide' });
  }

  try {
    const r = await fetch(target, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; CICharts/1.0)',
        'Accept': 'text/html,*/*;q=0.8',
        'Accept-Language': 'fr,en;q=0.5',
      },
      signal: AbortSignal.timeout(15000),
    });
    if (!r.ok) return res.status(r.status).json({ error: `HTTP ${r.status}` });
    return res.status(200).json({ contents: await r.text() });
  } catch (e) {
    return res.status(502).json({ error: e.message });
  }
};
