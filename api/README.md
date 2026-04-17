# CI Charts 🇨🇮

Classements musicaux de Côte d'Ivoire – Apple Music, YouTube, Deezer.

## Pourquoi un serveur local ?

Les proxies CORS publics (allorigins.win, corsproxy.io…) sont instables et
bloqués par certains navigateurs. Le serveur Express local élimine ces problèmes
en fetchant kworb.net côté serveur, sans CORS.

## Installation

```bash
# 1. Installer les dépendances (une seule fois)
npm install

# 2. Lancer le serveur
npm start
# → http://localhost:3000
```

## Corrections apportées

### ❌ Erreur 1 — CORS / "Unexpected token '<'"
**Cause** : `api.allorigins.win` renvoyait du HTML (`<!DOCTYPE`) au lieu de JSON.  
**Fix** : Proxy local `/proxy?url=...` en priorité. La fonction `pfetch()` détecte
maintenant le `Content-Type` de la réponse pour décider si elle doit parser du
JSON ou du HTML brut (corsproxy.io renvoie du HTML direct).

### ❌ Erreur 2 — Service Worker "chrome-extension scheme unsupported"
**Cause** : Le SW tentait de mettre en cache des URLs `chrome-extension://`
et des réponses opaque des proxies tiers.  
**Fix** : `sw.js` filtre maintenant tout scheme non-`http(s)`, ignore les
requêtes vers les proxies tiers, et ne cache que les réponses `status 200`
non-opaques.

## Structure

```
ci-charts/
├── server.js      ← Proxy Express (nouveau)
├── index.html     ← App corrigée
├── sw.js          ← Service Worker corrigé
├── manifest.json  ← PWA manifest
└── package.json
```
