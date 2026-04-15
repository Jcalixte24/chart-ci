import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# Les URLs exactes que vous souhaitez scraper
URLS = {
    "songs": "https://open.spotify.com/intl-fr/popular-all/trending-songs/ci",
    "albums": "https://open.spotify.com/intl-fr/popular-all/popular-albums/ci",
    "artists": "https://open.spotify.com/intl-fr/popular-all/popular-artists/ci"
}

def initialiser_navigateur():
    print("Lancement du navigateur (cela peut prendre quelques secondes)...")
    options = Options()
    options.add_argument('--headless') # Décommentez pour cacher la fenêtre Chrome (utile pour l'automatisation)
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(options=options)

def scraper_page_spotify(driver, categorie, url):
    print(f"\n{'='*60}\n💿 EXTRACTION : {categorie.upper()}\n🔗 URL : {url}\n{'='*60}")
    driver.get(url)
    
    resultats_json = []
    
    try:
        # On attend que la page charge son contenu principal
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='grid-container'], div[data-testid='tracklist-row'], div[role='row']"))
        )
        time.sleep(4)
        
        # Scroll pour charger les éléments (Lazy loading)
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            for _ in range(8):
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(1)
        except Exception:
            pass
        
        resultats = []
        lignes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='tracklist-row']")
        
        if not lignes:
            lignes = driver.find_elements(By.CSS_SELECTOR, "div[role='row'][aria-rowindex]")
            
        if lignes:
            debut = 1 if len(lignes) > 0 and ("Titre" in lignes[0].text or "Title" in lignes[0].text) else 0
            for idx, ligne in enumerate(lignes[debut:100 + debut], 1):
                texte = ligne.text.replace('\n', ' - ') 
                if texte.strip():
                    resultats.append((idx, texte))
        
        if not resultats:
            cartes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='grid-container'] > div")
            for idx, carte in enumerate(cartes[:100], 1):
                texte = carte.text.replace('\n', ' - ')
                
                if not texte.strip():
                    elements_internes = carte.find_elements(By.CSS_SELECTOR, "a, img, div")
                    textes_trouves = []
                    for el in elements_internes:
                        val = el.get_attribute('title') or el.get_attribute('aria-label')
                        if val and val not in textes_trouves:
                            textes_trouves.append(val)
                    texte = " - ".join(textes_trouves)
                    
                if texte.strip():
                    resultats.append((idx, texte.strip()))

        # Formatage des résultats pour l'application web
        if resultats:
            for idx, res in resultats:
                parts = res.split(' - ')
                title = parts[0].strip() if len(parts) > 0 else res
                artist = " - ".join(parts[1:]).strip() if len(parts) > 1 else "-"
                
                if categorie == "artists":
                    resultats_json.append({"pos": idx, "name": title, "genres": artist if artist != "-" else "Artiste", "streams": 0})
                elif categorie == "albums":
                    resultats_json.append({"pos": idx, "title": title, "artist": artist, "type": "Album", "mov": "="})
                else:
                    resultats_json.append({"pos": idx, "title": title, "artist": artist, "mov": "=", "streams": 0})
                
                print(f"{idx}. {res}")
        else:
            print("Aucun élément lisible trouvé.")
            
    except Exception as e:
        print(f"Erreur lors de la lecture de la page : {e}")
        
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
            
        # Création du dossier 'data' s'il n'existe pas et sauvegarde du JSON
        os.makedirs("data", exist_ok=True)
        with open("data/spotify_data.json", "w", encoding="utf-8") as f:
            json.dump(toutes_les_donnees, f, ensure_ascii=False, indent=2)
            
        print("\n✅ Extraction terminée ! Données sauvegardées dans 'data/spotify_data.json'")
        
    except Exception as e:
        print(f"Erreur critique du script : {e}")
    finally:
        if driver:
            print("\nFermeture du navigateur...")
            driver.quit()

if __name__ == "__main__":
    main()