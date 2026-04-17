import time
import json
import os
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
    options.add_argument('--window-size=1920,1080')  # FIX: taille explicite en headless
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(options=options)


def scroll_jusqu_au_bout(driver, max_scrolls=20):
    """Scroll progressif jusqu'à ce que plus rien ne charge."""
    body = driver.find_element(By.TAG_NAME, 'body')
    derniere_hauteur = driver.execute_script("return document.body.scrollHeight")

    for _ in range(max_scrolls):
        body.send_keys(Keys.END)
        time.sleep(2)  # Attendre le chargement lazy
        nouvelle_hauteur = driver.execute_script("return document.body.scrollHeight")
        if nouvelle_hauteur == derniere_hauteur:
            break  # Plus rien à charger
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

        # FIX: scroll complet pour tout charger avant d'extraire
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

                # FIX: ignorer uniquement les vraies lignes d'en-tête
                if len(parts) == 1 and est_ligne_header(parts[0]):
                    continue
                if all(est_ligne_header(p) for p in parts):
                    continue

                # FIX: enlever le numéro de position s'il est présent
                if parts[0].isdigit():
                    parts.pop(0)

                if not parts:
                    continue

                # FIX: détecter le mouvement sans casser l'extraction si absent
                mov = "="
                if len(parts) >= 2:
                    mouv_detecte = parser_mouvement(parts[0])
                    if mouv_detecte is not None:
                        mov = mouv_detecte
                        parts.pop(0)

                title = parts[0] if len(parts) > 0 else "Inconnu"
                artist = parts[1] if len(parts) > 1 else "-"

                # Ignorer les lignes sans titre valide
                if not title or est_ligne_header(title):
                    continue

                compteur += 1

                if compteur > 100:
                    break

                if categorie == "artists":
                    resultats_json.append({"pos": compteur, "name": title, "genres": artist if artist != "-" else "Artiste", "streams": 0})
                elif categorie == "albums":
                    resultats_json.append({"pos": compteur, "title": title, "artist": artist, "type": "Album", "mov": mov})
                else:
                    resultats_json.append({"pos": compteur, "title": title, "artist": artist, "mov": mov, "streams": 0})

                print(f"{compteur}. {title} - {artist} ({mov})")

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

                title = parts[0]
                artist = parts[1] if len(parts) > 1 else "-"

                if not title or est_ligne_header(title):
                    continue

                compteur += 1
                if compteur > 100:
                    break

                if categorie == "artists":
                    resultats_json.append({"pos": compteur, "name": title, "genres": artist if artist != "-" else "Artiste", "streams": 0})
                elif categorie == "albums":
                    resultats_json.append({"pos": compteur, "title": title, "artist": artist, "type": "Album", "mov": "="})
                else:
                    resultats_json.append({"pos": compteur, "title": title, "artist": artist, "mov": "=", "streams": 0})

                print(f"{compteur}. {title} - {artist}")

        if not resultats_json:
            print("⚠️ Aucun élément lisible trouvé.")

    except Exception as e:
        print(f"❌ Erreur : {e}")

    return resultats_json


def main():
    driver = None
    toutes_les_donnees = {"songs": [], "albums": [], "artists": []}

    try:
        driver = initialiser_navigateur()

        for categorie, url in URLS.items():
            data = scraper_page_spotify(driver, categorie, url)
            toutes_les_donnees[categorie] = data
            time.sleep(2)

        os.makedirs("data", exist_ok=True)
        chemin_fichier = os.path.join("data", "spotify_data.json")  # FIX: chemin relatif propre
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(toutes_les_donnees, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Extraction terminée ! Données sauvegardées dans '{chemin_fichier}'")

    except Exception as e:
        print(f" Erreur critique : {e}")
    finally:
        if driver:
            print("\nFermeture du navigateur...")
            driver.quit()

if __name__ == "__main__":
    main()