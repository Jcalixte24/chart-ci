import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# Les URLs exactes que vous souhaitez scraper
URLS = {
    "Chansons Tendance": "https://open.spotify.com/intl-fr/popular-all/trending-songs/ci",
    "Albums Populaires": "https://open.spotify.com/intl-fr/popular-all/popular-albums/ci",
    "Artistes Populaires": "https://open.spotify.com/intl-fr/popular-all/popular-artists/ci"
}

def initialiser_navigateur():
    print("Lancement du navigateur (cela peut prendre quelques secondes)...")
    options = Options()
    # options.add_argument('--headless') # Décommentez cette ligne plus tard si vous voulez cacher la fenêtre Chrome
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Avec les versions récentes de Selenium, le driver Chrome est téléchargé automatiquement
    return webdriver.Chrome(options=options)

def scraper_page_spotify(driver, titre, url):
    print(f"\n{'='*60}\n💿 EXTRACTION : {titre}\n🔗 URL : {url}\n{'='*60}")
    driver.get(url)
    
    try:
        # On attend que la page charge son contenu principal (on vérifie plusieurs types de conteneurs possibles)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='grid-container'], div[data-testid='tracklist-row'], div[role='row']"))
        )
        time.sleep(4) # Pause plus longue pour s'assurer que les textes et les images sont bien affichés
        
        # Faire défiler la page pour charger jusqu'à 100 éléments (Spotify utilise le chargement progressif / lazy loading)
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            for _ in range(8): # Scroll vers le bas à plusieurs reprises
                body.send_keys(Keys.PAGE_DOWN)
                time.sleep(1)
        except Exception:
            pass
        
        resultats = []
        
        # 1. Essayer d'extraire sous forme de liste de chansons (Tableau)
        lignes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='tracklist-row']")
        if not lignes:
            # Fallback : Sélecteur plus générique si le data-testid a changé
            lignes = driver.find_elements(By.CSS_SELECTOR, "div[role='row'][aria-rowindex]")
            
        if lignes:
            # On ignore la première ligne si c'est juste un en-tête de tableau ("Titre", "Album", etc.)
            debut = 1 if len(lignes) > 0 and ("Titre" in lignes[0].text or "Title" in lignes[0].text) else 0
            
            for idx, ligne in enumerate(lignes[debut:100 + debut], 1): # On limite au Top 100
                texte = ligne.text.replace('\n', ' - ') 
                if texte.strip():
                    resultats.append(f"{idx}. {texte}")
        
        # 2. Si ce n'est pas une liste, essayer sous forme de cartes (Albums / Artistes en Grille)
        if not resultats:
            cartes = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='grid-container'] > div")
            for idx, carte in enumerate(cartes[:100], 1): # On limite au Top 100
                texte = carte.text.replace('\n', ' - ')
                
                # SÉCURITÉ : Si le texte est toujours vide, on fouille dans les attributs des éléments internes
                if not texte.strip():
                    elements_internes = carte.find_elements(By.CSS_SELECTOR, "a, img, div")
                    textes_trouves = []
                    for el in elements_internes:
                        val = el.get_attribute('title') or el.get_attribute('aria-label')
                        if val and val not in textes_trouves:
                            textes_trouves.append(val)
                    texte = " - ".join(textes_trouves)
                    
                if texte.strip():
                    resultats.append(f"{idx}. {texte.strip()}")

        # Affichage du rendu final
        if resultats:
            for res in resultats:
                print(res)
        else:
            print("Aucun élément lisible trouvé. Spotify a peut-être changé sa structure ou bloqué la vue avec un pop-up.")
            
    except Exception as e:
        print(f"Erreur lors de la lecture de la page : {e}")

def main():
    driver = None
    try:
        driver = initialiser_navigateur()
        
        for titre, url in URLS.items():
            scraper_page_spotify(driver, titre, url)
            time.sleep(2) # Pause pour ne pas spammer le serveur
            
    except Exception as e:
        print(f"Erreur critique du script : {e}")
    finally:
        if driver:
            print("\nFermeture du navigateur...")
            driver.quit()
            print("Terminé !")

if __name__ == "__main__":
    main()