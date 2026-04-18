// api/chat.js — Chatbot Groq renforcé avec recherche externe
const GROQ_API_KEY = process.env.GROQ_API_KEY;
// On utilise llama-3.3-70b-versatile qui gère très bien les longs contextes (8k tokens)
const GROQ_MODEL   = process.env.GROQ_MODEL || 'llama-3.3-70b-versatile';

//  NOUVEAU : On reçoit directement le contexte texte "Top Max" préparé par le frontend (index.html)
// Au lieu de le reconstruire et de le brider à 30.
function buildChartsContext(ctx) {
  // Si le front-end a envoyé le contexte sous forme de texte brut (le nouveau comportement)
  if (typeof ctx === 'string') {
    return ctx;
  }
  
  // Rétrocompatibilité au cas où (si jamais le front-end envoie l'objet entier)
  const lines = [];
  if (ctx.apple_songs?.length) {
    lines.push('=== APPLE MUSIC CI — TITRES (TOP MAX) ===');
    ctx.apple_songs.forEach(t => lines.push(`#${t.pos} ${t.artist} – ${t.title} (${t.mov})`));
  }
  if (ctx.apple_albums?.length) {
    lines.push('=== APPLE MUSIC CI — ALBUMS ===');
    ctx.apple_albums.slice(0,20).forEach(t => lines.push(`#${t.pos} ${t.artist} – ${t.title} (${t.mov})`));
  }
  if (ctx.youtube?.length) {
    lines.push('=== YOUTUBE CI — STREAMS 48H (TOP MAX) ===');
    ctx.youtube.forEach(t => lines.push(`#${t.pos} ${t.artist} – ${t.title} · ${t.streams?.toLocaleString()} streams`));
  }
  if (ctx.deezer?.length) {
    lines.push('=== DEEZER CI — TOP MAX ===');
    ctx.deezer.forEach(t => lines.push(`#${t.pos} ${t.artist} – ${t.title} (${t.mov})`));
  }
  if (ctx.spotify_songs?.length) {
    lines.push('=== SPOTIFY CI — TOP MAX ===');
    ctx.spotify_songs.forEach(t => lines.push(`#${t.pos} ${t.artist} – ${t.title}`));
  }
  return lines.length ? lines.join('\n') : 'Aucune donnée chargée.';
}

function normalizeText(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function splitArtists(raw) {
  const source = String(raw || '');
  return source
    .split(/\s*(?:,|&|feat\.?|ft\.?|x|\/)\s*/i)
    .map(a => normalizeText(a))
    .filter(Boolean);
}

function extractArtistsFromTextContext(ctxText) {
  const artists = new Set();
  const lineRe = /^#\d+\s+(.+?)\s+-\s+(.+?)(?:\s+\(|\s+·|$)/gm;
  let m;
  while ((m = lineRe.exec(ctxText)) !== null) {
    const artistRaw = m[1];
    splitArtists(artistRaw).forEach(a => artists.add(a));
  }
  return artists;
}

function extractArtistsFromObjectContext(ctxObj) {
  const all = [
    ...(ctxObj.apple_songs || []),
    ...(ctxObj.apple_albums || []),
    ...(ctxObj.youtube || []),
    ...(ctxObj.youtube_weekly || []),
    ...(ctxObj.deezer || []),
    ...(ctxObj.spotify_songs || []),
    ...(ctxObj.spotify_albums || [])
  ];

  const artists = new Set();
  all.forEach(i => {
    splitArtists(i.artist).forEach(a => artists.add(a));
  });

  (ctxObj.spotify_artists || []).forEach(a => {
    splitArtists(a.name).forEach(v => artists.add(v));
  });

  return artists;
}

// Détecte si la question concerne un artiste qui n'est pas dans les charts
function detectArtistQuery(message, ctx) {
  const lq = normalizeText(message);
  const allArtists = typeof ctx === 'string'
    ? extractArtistsFromTextContext(ctx)
    : extractArtistsFromObjectContext(ctx || {});

  const inCharts = [...allArtists].some(a => a.length > 2 && lq.includes(a));
  const isArtistQuery = /qui est|parle.moi|info|biographie|bio|followers|streams|popularit|connu|artiste|chanteur|rappeur|musicien/.test(lq);

  if (isArtistQuery && !inCharts) {
    const originalWords = String(message || '').split(/\s+/);
    const candidate = originalWords.find(w => w.length > 3 && /^[A-ZÀ-Ü]/.test(w));
    return candidate || null;
  }
  return null;
}

async function fetchExternalInfo(artistName, host) {
  try {
    const protocol = host.includes('localhost') ? 'http' : 'https';
    const r = await fetch(`${protocol}://${host}/api/search?q=${encodeURIComponent(artistName)}`, {
      signal: AbortSignal.timeout(10000),
    });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Méthode non autorisée' });

  const { message, context } = req.body || {};
  if (!message) return res.status(400).json({ error: 'message manquant' });
  if (!GROQ_API_KEY) return res.status(503).json({ error: 'GROQ_API_KEY manquante dans Vercel > Environment Variables' });

  // Recherche externe si artiste non trouvé dans les charts
  let externalContext = '';
  const artistCandidate = detectArtistQuery(message, context || {});
  if (artistCandidate) {
    const host = req.headers.host || 'localhost:3000';
    const info = await fetchExternalInfo(artistCandidate, host);
    if (info) {
      if (info.spotify) {
        const sp = info.spotify;
        externalContext += `\n\n=== INFOS SPOTIFY : ${sp.name} ===\n`;
        externalContext += `Followers: ${sp.followers?.toLocaleString()}\n`;
        externalContext += `Popularité: ${sp.popularity}/100\n`;
        externalContext += `Genres: ${sp.genres?.join(', ') || 'N/A'}\n`;
        if (sp.topTracks?.length) {
          externalContext += `Top titres: ${sp.topTracks.map(t => `"${t.title}" (pop.${t.popularity})`).join(', ')}\n`;
        }
      }
      if (info.wikipedia?.extract) {
        externalContext += `\n=== WIKIPEDIA ===\n${info.wikipedia.extract}\n`;
      }
    }
  }

  // L'IA reçoit désormais l'intégralité du classement sans être bridée au Top 30
  const chartsContext = buildChartsContext(context || {});

  const systemPrompt = `Tu es un expert des charts musicaux de Côte d'Ivoire. Tu analyses les classements Apple Music, YouTube, Deezer et Spotify CI en temps réel.

DONNÉES ACTUELLES DES CHARTS CI (TOP MAX) :
${chartsContext}
${externalContext}

RÈGLES :
- Réponds toujours en français
- Tu as accès à l'intégralité des tops. Si l'utilisateur demande la position d'un artiste peu connu, cherche-le bien dans la liste ci-dessus.
- Tu connais parfaitement la scène musicale ivoirienne (afrobeats, coupé-décalé, nouchi pop, zouglou, reggae)
- Pour les artistes dans les charts : donne leurs positions exactes sur toutes les plateformes mentionnées
- Pour les artistes hors charts : utilise les données Wikipedia/Spotify si disponibles, sinon dis-le clairement
- Sois détaillé et informatif
- Pour les classements/stats : sois concis
- Pas de markdown excessif, reste naturel et conversationnel`;

  try {
    const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${GROQ_API_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: GROQ_MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user',   content: message }
        ],
        max_tokens: 800, // Légèrement augmenté pour les réponses plus longues
        temperature: 0.7,
      }),
    });
    const data = await r.json();
    if (!r.ok) return res.status(r.status).json({ error: data.error?.message || 'Erreur Groq' });
    return res.status(200).json({ reply: data.choices?.[0]?.message?.content || 'Pas de réponse.' });
  } catch (e) {
    return res.status(502).json({ error: e.message });
  }
};