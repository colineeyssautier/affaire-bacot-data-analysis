"""
scraper_twitter_bacot.py — Scraper tweets procès Bacot via Playwright
=====================================================================
Scrape les tweets de la recherche X sur le procès Bacot (juin 2021)
en réutilisant ta session Chrome existante (déjà connectée).

Installation :
    pip install playwright
    playwright install chromium

Usage :
    python scraper_twitter_bacot.py

Produit :
    corpus_bacot/tweets_bacot.json
    corpus_bacot/tweets_bacot.csv
"""

import json
import time
import re
import sys
import csv
import logging
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("Playwright non installé. Lance : pip install playwright && playwright install chromium")
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────────────────────

# URLs de recherche — on scrape les 4 jours du procès + réactions post-verdict
RECHERCHES = [
    {
        "label": "procès_j1",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-21%20until%3A2021-06-22&src=typed_query&f=top",
        "description": "Jour 1 du procès (21 juin 2021)",
    },
    {
        "label": "procès_j2",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-22%20until%3A2021-06-23&src=typed_query&f=top",
        "description": "Jour 2 du procès (22 juin 2021)",
    },
    {
        "label": "procès_j3",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-23%20until%3A2021-06-24&src=typed_query&f=top",
        "description": "Jour 3 du procès (23 juin 2021)",
    },
    {
        "label": "verdict",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-25%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Verdict (25 juin 2021)",
    },
    {
        "label": "audience_retranscription",
        "url": "https://x.com/search?q=Bacot%20audience%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Retranscriptions directes audiences",
    },
]

OUTPUT_DIR    = Path("corpus_bacot")
OUTPUT_JSON   = OUTPUT_DIR / "tweets_bacot.json"
OUTPUT_CSV    = OUTPUT_DIR / "tweets_bacot.csv"

MAX_SCROLLS   = 50     # scrolls max par recherche
SCROLL_PAUSE  = 3.0    # secondes entre chaque scroll
MIN_CHARS     = 30     # longueur minimale d'un tweet à garder

# ─── Requêtes de recherche ────────────────────────────────────────────────────

RECHERCHES = [
    {
        "label": "procès_j1",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-21%20until%3A2021-06-22&src=typed_query&f=top",
        "description": "Jour 1 du procès (21 juin 2021)",
    },
    {
        "label": "procès_j2",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-22%20until%3A2021-06-23&src=typed_query&f=top",
        "description": "Jour 2 du procès (22 juin 2021)",
    },
    {
        "label": "procès_j3",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-23%20until%3A2021-06-24&src=typed_query&f=top",
        "description": "Jour 3 du procès (23 juin 2021)",
    },
    {
        "label": "verdict",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-25%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Verdict (25 juin 2021)",
    },
    {
        "label": "audience_retranscription",
        "url": "https://x.com/search?q=Bacot%20audience%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Retranscriptions directes audiences",
    },
    {
        "label": "reactions_verdict",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-25%20until%3A2021-06-28&src=typed_query&f=top",
        "description": "Réactions après le verdict (25-28 juin)",
    },
    {
        "label": "petition",
        "url": "https://x.com/search?q=Bacot%20p%C3%A9tition%20since%3A2021-01-01%20until%3A2021-06-21&src=typed_query&f=top",
        "description": "Pétition de soutien (janvier-juin 2021)",
    },
    {
        "label": "livre",
        "url": "https://x.com/search?q=Bacot%20livre%20since%3A2021-09-01%20until%3A2021-10-31&src=typed_query&f=top",
        "description": "Sortie du livre Tout le monde savait",
    },
    {
        "label": "senat_tweets",
        "url": "https://x.com/search?q=Bacot%20s%C3%A9nat%20since%3A2021-10-01%20until%3A2021-12-01&src=typed_query&f=top",
        "description": "Déposition au Sénat (nov 2021)",
    },
    {
        "label": "hashtag_bacot",
        "url": "https://x.com/search?q=%23Val%C3%A9rieBacot%20since%3A2021-06-01%20until%3A2021-07-31&src=typed_query&f=top",
        "description": "Hashtag #ValérieBacot",
    },
    {
        "label": "legitime_defense_bacot",
        "url": "https://x.com/search?q=Bacot%20l%C3%A9gitime%20d%C3%A9fense%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Bacot + légitime défense",
    },
    {
        "label": "emprise_bacot",
        "url": "https://x.com/search?q=Bacot%20emprise%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Bacot + emprise",
    },
    {
        "label": "feminisme_bacot",
        "url": "https://x.com/search?q=Bacot%20f%C3%A9minisme%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Bacot + féminisme",
    },
    {
        "label": "nous_toutes_bacot",
        "url": "https://x.com/search?q=Bacot%20NousToutes%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Bacot + NousToutes",
    },
    {
        "label": "jacqueline_sauvage",
        "url": "https://x.com/search?q=Bacot%20Sauvage%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Bacot + Jacqueline Sauvage",
    },
    {
        "label": "tout_le_monde_savait",
        "url": "https://x.com/search?q=%22tout%20le%20monde%20savait%22%20Bacot%20since%3A2021-01-01%20until%3A2022-06-01&src=typed_query&f=top",
        "description": "Tout le monde savait + Bacot",
    },
    {
        "label": "bacot_2022_2023",
        "url": "https://x.com/search?q=Val%C3%A9rie%20Bacot%20since%3A2022-01-01%20until%3A2023-12-31&src=typed_query&f=top",
        "description": "Valérie Bacot 2022-2023",
    },
    {
        "label": "proces_recents",
        "url": "https://x.com/search?q=Val%C3%A9rie%20Bacot%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=latest",
        "description": "Onglet Récents — semaine du procès",
    },
    {
        "label": "verdict_recents",
        "url": "https://x.com/search?q=Bacot%20verdict%20since%3A2021-06-25%20until%3A2021-06-27&src=typed_query&f=latest",
        "description": "Onglet Récents — verdict",
    },
]

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_twitter.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# ─── Extraction des tweets ────────────────────────────────────────────────────

def extraire_tweets_page(page) -> list[dict]:
    """
    Extrait tous les tweets visibles sur la page courante.
    """
    tweets = []

    # Sélecteurs pour les articles tweet
    articles = page.query_selector_all('article[data-testid="tweet"]')

    for article in articles:
        try:
            # Texte du tweet
            texte_el = article.query_selector('[data-testid="tweetText"]')
            texte = texte_el.inner_text() if texte_el else ""

            if not texte or len(texte) < MIN_CHARS:
                continue

            # Auteur
            auteur_el = article.query_selector('[data-testid="User-Name"]')
            auteur = auteur_el.inner_text() if auteur_el else ""

            # Handle (@username)
            handle_el = article.query_selector('a[href*="/status/"]')
            handle = ""
            url_tweet = ""
            if handle_el:
                href = handle_el.get_attribute("href") or ""
                url_tweet = f"https://x.com{href}" if href.startswith("/") else href
                # Extrait le handle depuis l'URL
                parts = href.strip("/").split("/")
                if parts:
                    handle = "@" + parts[0]

            # Date
            time_el = article.query_selector("time")
            date = time_el.get_attribute("datetime") if time_el else ""

            # Métriques (likes, retweets)
            likes = 0
            retweets = 0
            try:
                like_el = article.query_selector('[data-testid="like"] span')
                rt_el   = article.query_selector('[data-testid="retweet"] span')
                if like_el:
                    likes = int(like_el.inner_text().replace(",", "").replace(" ", "") or 0)
                if rt_el:
                    retweets = int(rt_el.inner_text().replace(",", "").replace(" ", "") or 0)
            except Exception:
                pass

            tweets.append({
                "texte":    texte.strip(),
                "auteur":   auteur.strip().split("\n")[0],
                "handle":   handle,
                "date":     date[:10] if date else "",
                "datetime": date,
                "url":      url_tweet,
                "likes":    likes,
                "retweets": retweets,
                "nb_mots":  len(texte.split()),
            })

        except Exception as e:
            log.debug(f"Erreur extraction tweet : {e}")
            continue

    return tweets


def est_pertinent(tweet: dict) -> bool:
    """
    Double filtre : doit contenir 'bacot' ET un terme contextuel.
    Évite les faux positifs sur d'autres personnes nommées Bacot.
    """
    texte = tweet.get("texte", "").lower()

    # Doit contenir "bacot" ou "valérie bacot"
    if "bacot" not in texte and "valérie bacot" not in texte:
        return False

    # ET au moins un terme contextuel lié à l'affaire
    CONTEXTE = [
        "polette", "clayette", "procès", "proces", "audience",
        "assises", "verdict", "proxénète", "proxenete",
        "tomasini", "légitime", "legitime", "emprise",
        "violence", "conjugal", "victime", "pétition", "petition",
        "tout le monde savait", "chalon", "saône", "saone",
        "féminicide", "feminicide", "feminisme", "féminisme",
        "nous toutes", "noustoutes", "sauvage", "jacqueline",
        "condamn", "acquitt", "sursis", "prison",
        "livre", "sénat", "senat", "tomasini", "défense",
    ]

    return any(mot in texte for mot in CONTEXTE)


def dedupliquer(tweets: list[dict]) -> list[dict]:
    """Supprime les doublons par URL et par texte similaire."""
    vus_urls  = set()
    vus_texte = set()
    uniques   = []

    for t in tweets:
        url  = t.get("url", "")
        texte = t.get("texte", "")[:100]  # premiers 100 chars comme signature

        if url and url in vus_urls:
            continue
        if texte in vus_texte:
            continue

        if url:
            vus_urls.add(url)
        vus_texte.add(texte)
        uniques.append(t)

    return uniques


# ─── Scraping d'une recherche ─────────────────────────────────────────────────

def scraper_recherche(page, recherche: dict) -> list[dict]:
    """
    Scrape une page de résultats X avec défilement automatique.
    """
    label = recherche["label"]
    url   = recherche["url"]
    desc  = recherche["description"]

    log.info(f"\n{'='*50}")
    log.info(f"Recherche : {desc}")
    log.info(f"URL : {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)  # attend le chargement initial

        # Vérifie qu'on est bien connecté
        if "login" in page.url.lower() or page.query_selector('[data-testid="loginButton"]'):
            log.error("X demande une connexion — vérifie que tu es connecté dans Chrome")
            return []

    except PWTimeout:
        log.warning("Timeout chargement page — on continue quand même")

    tous_tweets = []
    tweets_avant = 0

    for scroll_n in range(MAX_SCROLLS):
        # Extrait les tweets visibles
        tweets_page = extraire_tweets_page(page)
        tous_tweets.extend(tweets_page)
        tous_tweets = dedupliquer(tous_tweets)

        n_nouveaux = len(tous_tweets) - tweets_avant
        tweets_avant = len(tous_tweets)

        log.info(f"  Scroll {scroll_n+1:>2}/{MAX_SCROLLS} — {len(tous_tweets)} tweets (+{n_nouveaux})")

        # Si plus de nouveaux tweets depuis 3 scrolls, on arrête
        if scroll_n > 3 and n_nouveaux == 0:
            log.info("  → Plus de nouveaux tweets, arrêt du défilement")
            break

        # Défilement
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)

        # Gère les éventuels popups
        try:
            close_btn = page.query_selector('[aria-label="Close"]')
            if close_btn:
                close_btn.click()
        except Exception:
            pass

    # Filtre les tweets pertinents
    pertinents = [t for t in tous_tweets if est_pertinent(t)]

    log.info(f"\n  Total : {len(tous_tweets)} tweets · {len(pertinents)} pertinents")

    return pertinents


# ─── Sauvegarde ───────────────────────────────────────────────────────────────

def sauvegarder(tous_tweets: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Fusionne avec tweets existants si présents
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existants = json.load(f)
        urls_existantes = {t.get("url", "") for t in existants}
        nouveaux = [t for t in tous_tweets if t.get("url", "") not in urls_existantes]
        tous_tweets = existants + nouveaux
        log.info(f"Fusion : {len(existants)} existants + {len(nouveaux)} nouveaux = {len(tous_tweets)} total")

    # JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tous_tweets, f, ensure_ascii=False, indent=2)

    # CSV
    if tous_tweets:
        cols = ["texte", "auteur", "handle", "date", "datetime", "url", "likes", "retweets", "nb_mots"]
        with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(tous_tweets)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         TWEETS SCRAPÉS ✓                         ║
╠══════════════════════════════════════════════════╣
║  Tweets total   : {len(tous_tweets):>5}                   ║
╚══════════════════════════════════════════════════╝
→ {OUTPUT_JSON}
→ {OUTPUT_CSV}
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    log.info("Démarrage du scraper Twitter/X — Procès Bacot")
    log.info("Utilise ta session Chrome existante (déjà connectée)")

    OUTPUT_DIR.mkdir(exist_ok=True)
    tous_tweets = []

    with sync_playwright() as p:
        # Utilise le profil Chrome existant pour réutiliser la session
        # Cherche le profil Chrome par défaut selon l'OS
        import os
        chrome_profile = None

        # Chemins possibles du profil Chrome sur Windows
        chemins_chrome = [
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data"),
            os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data"),
        ]

        for chemin in chemins_chrome:
            if os.path.exists(chemin):
                chrome_profile = chemin
                log.info(f"Profil navigateur trouvé : {chemin}")
                break

        # Crée un profil dédié au scraping dans le dossier du projet
        # (évite le conflit avec le profil Chrome par défaut)
        profil_scraping = Path("playwright_profile").absolute()
        profil_scraping.mkdir(exist_ok=True)

        log.info(f"Profil Playwright : {profil_scraping}")
        log.info("Si c'est la première fois, tu devras te connecter à X manuellement.")

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profil_scraping),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            slow_mo=50,
        )

        page = context.new_page()

        # Vérifie la connexion
        log.info("Vérification de la connexion X...")
        page.goto("https://x.com/home", timeout=30000)
        time.sleep(3)

        if "login" in page.url.lower() or page.query_selector('input[name="text"]'):
            log.info("="*50)
            log.info("Connecte-toi à X dans la fenêtre qui s'est ouverte.")
            log.info("Une fois connecté et sur la page d'accueil, appuie sur Entrée ici.")
            log.info("="*50)
            input(">>> Appuie sur Entrée quand tu es connecté : ")
            page.goto("https://x.com/home", timeout=30000)
            time.sleep(3)

        log.info("Connexion confirmée ✓")

        # Scrape chaque recherche
        for recherche in RECHERCHES:
            tweets = scraper_recherche(page, recherche)

            # Ajoute le label de recherche
            for t in tweets:
                t["recherche"] = recherche["label"]
                t["source"]    = "twitter_x"

            tous_tweets.extend(tweets)
            tous_tweets = dedupliquer(tous_tweets)

            log.info(f"  Cumul total : {len(tous_tweets)} tweets")
            time.sleep(2)

        context.close()

    sauvegarder(tous_tweets)


if __name__ == "__main__":
    run()