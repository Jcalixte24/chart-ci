// api/search.js — Recherche artiste via Spotify + Wikipedia FR
const CLIENT_ID     = process.env.SPOTIFY_CLIENT_ID;
const CLIENT_SECRET = process.env.SPOTIFY_CLIENT_SECRET;

async function getSpotifyToken() {
  if (!CLIENT_ID || !CLIENT_SECRET) return null;
  try {
    const creds = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString('base64');
    const r = await fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: { 'Authorization': `Basic ${creds}`, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: 'grant_type=client_credentials',
      signal: AbortSignal.timeout(6000),
    });
    const d = await r.json();
    return r.ok ? d.access_token : null;
  } catch { return null; }
}

async function searchSpotifyArtist(token, query) {
  if (!token) return null;
  try {
    const r = await fetch(
      `https://api.spotify.com/v1/search?q=${encodeURIComponent(query)}&type=artist&limit=3`,
      { headers: { 'Authorization': `Bearer ${token}` }, signal: AbortSignal.timeout(8000) }
    );
    const d = await r.json();
    const artist = d.artists?.items?.[0];
    if (!artist) return null;

    // Récupérer les top tracks de l'artiste sur CI
    const tr = await fetch(
      `https://api.spotify.com/v1/artists/${artist.id}/top-tracks?market=CI`,
      { headers: { 'Authorization': `Bearer ${token}` }, signal: AbortSignal.timeout(8000) }
    );
    const td = await tr.json();
    const topTracks = (td.tracks || []).slice(0, 5).map(t => ({
      title:      t.name,
      popularity: t.popularity,
      album:      t.album?.name,
    }));

    return {
      name:       artist.name,
      followers:  artist.followers?.total || 0,
      popularity: artist.popularity,
      genres:     artist.genres?.slice(0, 4) || [],
      image:      artist.images?.[0]?.url || null,
      topTracks,
    };
  } catch { return null; }
}

async function searchWikipedia(query) {
  try {
    // Recherche Wikipedia FR
    const searchR = await fetch(
      `https://fr.wikipedia.org/w/api.php?action=search&list=search&srsearch=${encodeURIComponent(query + ' chanteur musicien')}&format=json&srlimit=1&origin=*`,
      { signal: AbortSignal.timeout(6000) }
    );
    const searchD = await searchR.json();
    const pageTitle = searchD.query?.search?.[0]?.title;
    if (!pageTitle) return null;

    // Récupérer l'extrait
    const pageR = await fetch(
      `https://fr.wikipedia.org/w/api.php?action=query&titles=${encodeURIComponent(pageTitle)}&prop=extracts&exintro=1&explaintext=1&exsentences=5&format=json&origin=*`,
      { signal: AbortSignal.timeout(6000) }
    );
    const pageD = await pageR.json();
    const pages = pageD.query?.pages || {};
    const page  = Object.values(pages)[0];
    if (!page || page.missing) return null;

    return {
      title:   page.title,
      extract: page.extract?.slice(0, 600) || null,
      url:     `https://fr.wikipedia.org/wiki/${encodeURIComponent(page.title)}`,
    };
  } catch { return null; }
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const query = req.query.q;
  if (!query) return res.status(400).json({ error: 'Paramètre q manquant' });

  const token = await getSpotifyToken();
  const [spotify, wikipedia] = await Promise.all([
    searchSpotifyArtist(token, query),
    searchWikipedia(query),
  ]);

  return res.status(200).json({ query, spotify, wikipedia });
};
