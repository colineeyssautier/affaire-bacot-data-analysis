"""
Scraper Google News + trafilatura — Affaire Valérie Bacot
=========================================================
Pipeline :
  1. Interroge Google News via gnews pour récupérer les URLs
  2. Résout les vraies URLs (décode les redirections Google News)
  3. Télécharge et nettoie chaque article avec trafilatura
  4. Sauvegarde le corpus en JSON + CSV

Installation :
    pip install gnews trafilatura pandas requests

Usage :
    python scraper_bacot.py
"""

import json
import time
import logging
import pandas as pd
import trafilatura
import requests
from trafilatura.settings import use_config
from gnews import GNews
from datetime import datetime
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

QUERIES = [
    "Valérie Bacot",
    "Valérie Bacot procès",
    "Valérie Bacot féminicide",
    "Valérie Bacot Daniel Polette",
    "Bacot meurtre mari violence conjugale",
    "Bacot acquittement légitime défense",
]

DATE_START = (2021, 1, 1)
DATE_END   = (2023, 6, 1)

MAX_RESULTS_PER_QUERY = 100
DELAY = 1.5
MIN_WORDS = 100
OUTPUT_DIR = Path("corpus_bacot")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_bacot.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# Réduit les logs de trafilatura et requests
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ─── Config trafilatura ────────────────────────────────────────────────────────

newconfig = use_config()
newconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


# ─── Étape 1 : collecte des URLs via Google News ──────────────────────────────

def fetch_google_news_urls(queries: list[str]) -> list[dict]:
    """
    Pour chaque requête, interroge Google News et retourne
    une liste dédupliquée d'articles avec métadonnées.
    """
    gn = GNews(
        language="fr",
        country="FR",
        max_results=MAX_RESULTS_PER_QUERY,
        start_date=DATE_START,
        end_date=DATE_END,
    )

    all_articles = {}

    for query in queries:
        log.info(f"Google News — recherche : '{query}'")
        try:
            results = gn.get_news(query)

            if not results:
                log.info("  → Aucun résultat")
                continue

            log.info(f"  → {len(results)} articles trouvés")

            for item in results:
                url = item.get("url", "")
                if not url or url in all_articles:
                    continue

                all_articles[url] = {
                    "url_google": url,
                    "title": item.get("title", ""),
                    "published_date": str(item.get("published date", "")),
                    "publisher": item.get("publisher", {}).get("title", ""),
                    "query_trigger": query,
                }

            time.sleep(1)

        except Exception as e:
            log.warning(f"  ⚠ Erreur pour '{query}' : {e}")

    log.info(f"Total URLs Google News collectées : {len(all_articles)}")
    return list(all_articles.values())


# ─── Étape 2 : résolution des vraies URLs ─────────────────────────────────────

def resoudre_url_google(url_google: str) -> str | None:
    """
    Suit les redirections de l'URL Google News pour obtenir
    la vraie URL de l'article sur le site source.
    Retourne None si la résolution échoue ou reste sur Google.
    """
    try:
        response = requests.get(
            url_google,
            headers=HEADERS,
            allow_redirects=True,
            timeout=15,
        )
        url_finale = response.url

        # Si on est toujours sur un domaine Google, la résolution a échoué
        domaines_google = ["google.com", "consent.google", "accounts.google"]
        if any(d in url_finale for d in domaines_google):
            return None

        return url_finale

    except requests.exceptions.Timeout:
        log.debug(f"Timeout résolution : {url_google[:60]}")
        return None
    except Exception as e:
        log.debug(f"Erreur résolution : {e}")
        return None


# ─── Étape 3 : scraping du texte ─────────────────────────────────────────────

def scrape_article(url: str) -> dict | None:
    """
    Télécharge et extrait le texte propre d'un article via trafilatura.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None

        result = trafilatura.extract(
            downloaded,
            config=newconfig,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            output_format="json",
            with_metadata=True,
        )

        if not result:
            return None

        data = json.loads(result)
        return {
            "text":        data.get("text", ""),
            "title":       data.get("title", ""),
            "author":      data.get("author", ""),
            "date":        data.get("date", ""),
            "description": data.get("description", ""),
            "sitename":    data.get("sitename", ""),
        }

    except Exception as e:
        log.debug(f"Erreur scraping {url} : {e}")
        return None


# ─── Étape 4 : sauvegarde ─────────────────────────────────────────────────────

def save_corpus(corpus: list[dict], failed: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    json_path = OUTPUT_DIR / "corpus_bacot.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame(corpus)
    if not df.empty:
        meta_cols = [
            "url", "title", "author", "date", "sitename",
            "publisher", "query_trigger", "word_count", "scraped_at"
        ]
        meta_cols = [c for c in meta_cols if c in df.columns]
        df[meta_cols].to_csv(
            OUTPUT_DIR / "corpus_bacot_meta.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with open(OUTPUT_DIR / "failed_urls.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║              RÉSUMÉ DU SCRAPING                  ║
╠══════════════════════════════════════════════════╣
║  Articles extraits  : {len(corpus):>5}                   ║
║  Échecs             : {len(failed):>5}                   ║
║  Taux de succès     : {len(corpus)/max(len(corpus)+len(failed),1)*100:>5.1f}%                  ║
╚══════════════════════════════════════════════════╝
→ Corpus complet  : {OUTPUT_DIR}/corpus_bacot.json
→ Métadonnées CSV : {OUTPUT_DIR}/corpus_bacot_meta.csv
→ Échecs          : {OUTPUT_DIR}/failed_urls.json
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():

    # ── Étape 1 : Google News → URLs encodées ──
    log.info("=" * 60)
    log.info("ÉTAPE 1 — Collecte des URLs via Google News")
    log.info("=" * 60)

    url_list = fetch_google_news_urls(QUERIES)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "urls_raw.json", "w", encoding="utf-8") as f:
        json.dump(url_list, f, ensure_ascii=False, indent=2)

    log.info(f"{len(url_list)} URLs collectées, sauvegardées dans urls_raw.json")

    # ── Étape 2 + 3 : résolution + scraping ──
    log.info("=" * 60)
    log.info("ÉTAPE 2+3 — Résolution des URLs et scraping")
    log.info("=" * 60)

    corpus = []
    failed = []

    for i, meta in enumerate(url_list, 1):
        url_google = meta["url_google"]
        log.info(f"[{i}/{len(url_list)}] Résolution en cours...")

        # Résoudre la vraie URL
        url_reelle = resoudre_url_google(url_google)

        if not url_reelle:
            log.info("  ✗ URL non résolue (reste sur Google)")
            failed.append({
                "url_google": url_google,
                "reason": "url_non_resolue",
                "title": meta.get("title", ""),
            })
            time.sleep(DELAY)
            continue

        log.info(f"  ✓ URL résolue : {url_reelle[:80]}...")

        # Scraper l'article
        article = scrape_article(url_reelle)

        if article:
            article.update({
                "url":           url_reelle,
                "url_google":    url_google,
                "publisher":     meta.get("publisher", ""),
                "query_trigger": meta.get("query_trigger", ""),
                "scraped_at":    datetime.utcnow().isoformat(),
                "word_count":    len(article.get("text", "").split()),
            })

            if article["word_count"] >= MIN_WORDS:
                corpus.append(article)
                log.info(
                    f"  ✓ Extrait : {article['word_count']} mots "
                    f"| {article.get('sitename', '?')}"
                )
            else:
                log.info(f"  ✗ Trop court ({article['word_count']} mots)")
                failed.append({
                    "url_google": url_google,
                    "url_reelle": url_reelle,
                    "reason": "too_short",
                })
        else:
            log.info("  ✗ Échec extraction trafilatura")
            failed.append({
                "url_google": url_google,
                "url_reelle": url_reelle,
                "reason": "extraction_failed",
            })

        time.sleep(DELAY)

    # ── Étape 4 : sauvegarde ──
    log.info("=" * 60)
    log.info("ÉTAPE 4 — Sauvegarde du corpus")
    log.info("=" * 60)

    save_corpus(corpus, failed)


if __name__ == "__main__":
    run()
