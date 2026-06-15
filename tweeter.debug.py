"""
debug_twitter.py — Diagnostic du scraper X
===========================================
Ouvre la page de recherche et attend que tu confirmes manuellement
ce qui est visible, puis affiche le HTML pour identifier les bons sélecteurs.

Usage :
    python debug_twitter.py
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFIL = Path("playwright_profile").absolute()
PROFIL.mkdir(exist_ok=True)

URL_TEST = "https://x.com/search?q=Bacot%20audience%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=top"

with sync_playwright() as p:
    print("Lancement du navigateur...")
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFIL),
        headless=False,
        slow_mo=50,
        args=["--disable-blink-features=AutomationControlled"],
    )

    page = context.new_page()

    print("Navigation vers X...")
    page.goto("https://x.com", timeout=30000)
    time.sleep(3)

    print(f"URL actuelle : {page.url}")

    # Si page de login, attendre connexion manuelle
    if "login" in page.url.lower() or page.query_selector('input[autocomplete="username"]'):
        print("\n" + "="*50)
        print("PAGE DE CONNEXION DÉTECTÉE")
        print("Connecte-toi à X dans la fenêtre ouverte.")
        print("Quand tu es sur la page d'accueil X, appuie sur Entrée ici.")
        print("="*50)
        input(">>> Entrée quand connecté : ")
    else:
        print("Déjà connecté ✓")

    print(f"\nNavigation vers la recherche...")
    page.goto(URL_TEST, timeout=30000)

    print("Attente chargement (10 secondes)...")
    time.sleep(10)

    print(f"URL finale : {page.url}")

    # Essaie plusieurs sélecteurs
    selecteurs = [
        'article[data-testid="tweet"]',
        'article',
        '[data-testid="tweet"]',
        '[data-testid="tweetText"]',
        'div[data-testid="cellInnerDiv"]',
        'li[role="listitem"]',
    ]

    print("\n--- Test des sélecteurs ---")
    for sel in selecteurs:
        elements = page.query_selector_all(sel)
        print(f"  {sel:<45} : {len(elements)} éléments")

    # Extrait le HTML visible pour analyse
    print("\n--- HTML de la zone principale (premiers 3000 chars) ---")
    try:
        main = page.query_selector('main')
        if main:
            html = main.inner_html()[:3000]
            print(html)
        else:
            print(page.content()[:3000])
    except Exception as e:
        print(f"Erreur : {e}")

    print("\n--- Texte visible sur la page ---")
    try:
        texte = page.inner_text('body')[:1000]
        print(texte)
    except Exception as e:
        print(f"Erreur : {e}")

    input("\nAppuie sur Entrée pour fermer...")
    context.close()