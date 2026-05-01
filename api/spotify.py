import time
import json
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

URLS = {
    "songs": "https://open.spotify.com/intl-fr/popular-all/trending-songs/ci",
    "albums": "https://open.spotify.com/intl-fr/popular-all/popular-albums/ci",
    "artists": "https://open.spotify.com/intl-fr/popular-all/popular-artists/ci"
}


def initialiser_navigateur():
    print("Lancement du navigateur...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(options=options)


def scroll_jusqu_au_bout(driver, max_scrolls=20):
    """Scroll progressif jusqu'à ce que plus rien ne charge."""
    body = driver.find_element(By.TAG_NAME, 'body')
    derniere_hauteur = driver.execute_script("return document.body.scrollHeight")

    for _ in range(max_scrolls):
        body.send_keys(Keys.END)
        time.sleep(2)
        nouvelle_hauteur = driver.execute_script("return document.body.scrollHeight")
        if nouvelle_hauteur == derniere_hauteur:
            break
        derniere_hauteur = nouvelle_hauteur


def est_ligne_header(texte):
    """Vérifie si une ligne est un en-tête de tableau."""
    mots_cles_header = ["titre", "title", "album", "artiste", "artist", "#", "popularité"]
    texte_lower = texte.lower().strip()
    return any(texte_lower == mot for mot in mots_cles_header)


def parser_mouvement(valeur):
    """Extrait le mouvement si présent, sinon retourne None."""
    v = valeur.strip().upper()
    if v in ["=", "NEW"]:
        return v
    if len(v) > 1 and v[0] in ['+', '-'] and v[1:].isdigit():
        return v
    return None


def nettoyer_artiste(artist):
    """Supprime les artefacts Spotify : icône E (explicit), E en tête, espaces superflus."""
    # Retire "E" isolé en début (badge explicit Spotify affiché comme lettre)
    artist = re.sub(r'^E\s+', '', artist.strip())
    # Retire "E" isolé collé entre virgules/espaces
    artist = re.sub(r',\s*E\s+', ', ', artist)
    # Normalise les espaces multiples
    artist = re.sub(r'\s{2,}', ' ', artist).strip()
    return artist or "-"


def parser_ligne_tracklist(parts, categorie, compteur):
    if not parts:
        return None

    # Retirer numéro de position initial
    if parts[0].isdigit():
        parts.pop(0)
    if not parts:
        return None

    # Ignorer la lettre "E" seule (badge explicit en tête de ligne)
    if parts[0] == "E":
        parts.pop(0)
    if not parts:
        return None

    # Détecter mouvement en tête
    mov = "="
    if parts and parser_mouvement(parts[0]) is not None:
        mov = parser_mouvement(parts[0])
        parts.pop(0)
    if not parts:
        return None

    title = parts[0]
    if est_ligne_header(title):
        return None

    artist_parts = []
    for part in parts[1:]:
        if part == "E":          # badge explicit en milieu de ligne
            continue
        if re.match(r'^\d+:\d+$', part):   # durée type "3:45"
            break
        if re.match(r'^\d+$', part):        # chiffre seul (popularité)
            break
        artist_parts.append(part)

    artist = nettoyer_artiste(" ".join(artist_parts)) if artist_parts else "-"

    if categorie == "artists":
        return {"pos": compteur, "name": title, "genres": "Artiste", "streams": 0}
    elif categorie == "albums":
        return {"pos": compteur, "title": title, "artist": artist, "type": "Album", "mov": mov}
    else:
        return {"pos": compteur, "title": title, "artist": artist, "mov": mov, "streams": 0}


def scraper_page_spotify(driver, categorie, url):
    print(f"\n{'='*60}\n💿 EXTRACTION : {categorie.upper()}\n🔗 URL : {url}\n{'='*60}")
    driver.get(url)

    resultats_json = []

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                "div[data-testid='grid-container'], div[data-testid='tracklist-row'], div[role='row']"))
        )
        time.sleep(3)

        scroll_jusqu_au_bout(driver, max_scrolls=20)
        time.sleep(2)

        # --- Méthode 1 : Lignes de tableau (chansons / albums en liste) ---
        lignes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='tracklist-row']")
        if not lignes:
            lignes = driver.find_elements(By.CSS_SELECTOR, "div[role='row'][aria-rowindex]")

        if lignes:
            compteur = 0
            for ligne in lignes:
                parts = [p.strip() for p in ligne.text.split('\n') if p.strip()]

                if not parts:
                    continue

                # Ignorer les vraies lignes d'en-tête
                if len(parts) == 1 and est_ligne_header(parts[0]):
                    continue
                if all(est_ligne_header(p) for p in parts):
                    continue

                # FIX : utiliser parser_ligne_tracklist pour reconstruire l'artiste complet
                result = parser_ligne_tracklist(parts[:], categorie, compteur + 1)
                if result is None:
                    continue

                compteur += 1
                if compteur > 100:
                    break

                resultats_json.append(result)
                nom_affiche = result.get('title', result.get('name', '?'))
                artiste_affiche = result.get('artist', result.get('genres', '-'))
                mov_affiche = result.get('mov', '')
                print(f"{result['pos']}. {nom_affiche} - {artiste_affiche} ({mov_affiche})")

        # --- Méthode 2 : Grille de cartes (artistes / albums) ---
        if not resultats_json:
            cartes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='grid-container'] > div")
            compteur = 0
            for carte in cartes:
                parts = [p.strip() for p in carte.text.split('\n') if p.strip()]

                if not parts:
                    elements_internes = carte.find_elements(By.CSS_SELECTOR, "a, img, div")
                    for el in elements_internes:
                        val = el.get_attribute('title') or el.get_attribute('aria-label')
                        if val and val.strip() not in parts:
                            parts.append(val.strip())

                if not parts:
                    continue

                # FIX : même logique de reconstruction pour les cartes
                result = parser_ligne_tracklist(parts[:], categorie, compteur + 1)
                if result is None:
                    continue

                compteur += 1
                if compteur > 100:
                    break

                resultats_json.append(result)
                nom_affiche = result.get('title', result.get('name', '?'))
                artiste_affiche = result.get('artist', result.get('genres', '-'))
                print(f"{result['pos']}. {nom_affiche} - {artiste_affiche}")

        if not resultats_json:
            print(" Aucun élément lisible trouvé.")

    except Exception as e:
        print(f" Erreur : {e}")

    return resultats_json


def charger_historique(chemin_historique):
    if not os.path.exists(chemin_historique):
        return []
    try:
        with open(chemin_historique, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def sauvegarder_historique(chemin_historique, historique, limite=60):
    historique_limite = historique[-limite:]
    with open(chemin_historique, "w", encoding="utf-8") as f:
        json.dump(historique_limite, f, ensure_ascii=False, indent=2)


def construire_snapshot(donnees):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "generated_at": now,
        "source": "spotify-web-scrape",
        "country": "ci",
        "songs": donnees.get("songs", []),
        "albums": donnees.get("albums", []),
        "artists": donnees.get("artists", [])
    }


def main():
    driver = None
    toutes_les_donnees = {"songs": [], "albums": [], "artists": []}

    # Toujours sauvegarder dans data/ relatif à la racine du projet
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dossier_data = os.path.join(racine, "data")

    try:
        driver = initialiser_navigateur()

        for categorie, url in URLS.items():
            data = scraper_page_spotify(driver, categorie, url)
            toutes_les_donnees[categorie] = data
            time.sleep(2)

        os.makedirs(dossier_data, exist_ok=True)
        chemin_fichier = os.path.join(dossier_data, "spotify_data.json")
        chemin_historique = os.path.join(dossier_data, "spotify_history.json")

        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(toutes_les_donnees, f, ensure_ascii=False, indent=2)

        snapshot = construire_snapshot(toutes_les_donnees)
        historique = charger_historique(chemin_historique)
        historique.append(snapshot)
        sauvegarder_historique(chemin_historique, historique, limite=60)

        print(f"\nExtraction terminée ! Données sauvegardées dans '{chemin_fichier}'")
        print(f"Historique mis à jour dans '{chemin_historique}' ({len(historique)} snapshots)")

    except Exception as e:
        print(f"Erreur critique : {e}")
    finally:
        if driver:
            print("\nFermeture du navigateur...")
            driver.quit()


if __name__ == "__main__":
    main()