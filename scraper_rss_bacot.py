"""
Scraper RSS Google News + décodage URLs + trafilatura
======================================================
Utilise feedparser pour lire le RSS Google News et
googlenewsdecoder pour décoder les URLs encodées CBMi...

Installation :
    pip install feedparser trafilatura pandas requests beautifulsoup4 googlenewsdecoder

Usage :
    python scraper_rss_bacot.py
"""

import json
import time
import logging
import hashlib
import feedparser
import trafilatura
import requests
import pandas as pd
from trafilatura.settings import use_config
from datetime import datetime
from pathlib import Path

try:
    from googlenewsdecoder import new_decoderv1
    DECODER_AVAILABLE = True
except ImportError:
    DECODER_AVAILABLE = False
    print("⚠ googlenewsdecoder non installé — lance: pip install googlenewsdecoder")

# ─── Requêtes ─────────────────────────────────────────────────────────────────

QUERIES = [
    "Valérie Bacot",
    "Valérie Bacot procès",
    "Valérie Bacot violence conjugale",
    "Bacot féminicide",
    "Bacot légitime défense",
    "Bacot acquittement",
    "Bacot livre témoignage",
    "Bacot Daniel Polette",
]

# ─── Configuration ────────────────────────────────────────────────────────────

DELAY      = 2.0
MIN_WORDS  = 100
OUTPUT_DIR = Path("corpus_bacot")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_rss.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ─── Config trafilatura ────────────────────────────────────────────────────────

newconfig = use_config()
newconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


# ─── Décodage URL Google News ─────────────────────────────────────────────────

def decoder_url_google(url_google: str) -> str | None:
    """
    Décode une URL encodée Google News (format CBMi...) en vraie URL.
    Utilise googlenewsdecoder si disponible, sinon requests en fallback.
    """
    if not url_google or "google.com" not in url_google:
        return url_google  # déjà une vraie URL

    # Méthode 1 : googlenewsdecoder (la plus fiable)
    if DECODER_AVAILABLE:
        try:
            result = new_decoderv1(url_google)
            if result and result.get("status"):
                decoded = result.get("decoded_url", "")
                if decoded and "google.com" not in decoded:
                    return decoded
        except Exception as e:
            log.debug(f"Erreur decoder : {e}")

    # Méthode 2 : suivre les redirections avec requests
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        # On désactive les redirections auto pour voir où ça pointe
        resp = session.get(url_google, allow_redirects=True, timeout=10)
        final = resp.url
        if final and "google.com" not in final:
            return final
    except Exception as e:
        log.debug(f"Erreur requests fallback : {e}")

    return None


# ─── Collecte RSS ─────────────────────────────────────────────────────────────

def fetch_rss_urls(queries: list[str]) -> list[dict]:
    """
    Interroge le flux RSS Google News pour chaque requête
    et décode les vraies URLs des articles.
    """
    all_articles = {}

    for query in queries:
        query_encoded = query.replace(" ", "+")
        rss_url = (
            f"https://news.google.com/rss/search"
            f"?q={query_encoded}"
            f"&hl=fr&gl=FR&ceid=FR:fr"
        )

        log.info(f"RSS — recherche : '{query}'")

        try:
            feed = feedparser.parse(rss_url)

            if not feed.entries:
                log.info("  → Aucun résultat")
                time.sleep(1)
                continue

            log.info(f"  → {len(feed.entries)} entrées RSS trouvées")
            trouvees = 0

            for entry in feed.entries:
                url_google = entry.get("link", "")
                if not url_google:
                    continue

                # Décode la vraie URL
                url_reelle = decoder_url_google(url_google)

                if not url_reelle or url_reelle in all_articles:
                    continue

                all_articles[url_reelle] = {
                    "url":           url_reelle,
                    "url_google":    url_google,
                    "title":         entry.get("title", ""),
                    "published":     entry.get("published", ""),
                    "query_trigger": query,
                }
                trouvees += 1
                time.sleep(0.3)  # pause légère entre décodages

            log.info(f"  → {trouvees} vraies URLs décodées")
            time.sleep(1.5)

        except Exception as e:
            log.warning(f"  ⚠ Erreur RSS pour '{query}' : {e}")

    log.info(f"Total URLs uniques collectées : {len(all_articles)}")
    return list(all_articles.values())


# ─── Scraping ─────────────────────────────────────────────────────────────────

def scrape_article(url: str) -> dict | None:
    try:
        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                downloaded = response.text
            else:
                return None

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


def hash_texte(texte: str) -> str:
    return hashlib.md5(texte[:500].encode("utf-8")).hexdigest()


# ─── Sauvegarde ───────────────────────────────────────────────────────────────

def save_corpus(corpus: list[dict], failed: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    json_path = OUTPUT_DIR / "corpus_bacot.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            corpus_existant = json.load(f)
        urls_existantes = {a["url"] for a in corpus_existant}
        nouveaux = [a for a in corpus if a["url"] not in urls_existantes]
        corpus_final = corpus_existant + nouveaux
        log.info(f"Fusion : {len(corpus_existant)} existants + {len(nouveaux)} nouveaux = {len(corpus_final)} total")
    else:
        corpus_final = corpus

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame(corpus)
    if not df.empty:
        meta_cols = ["url", "title", "author", "date", "sitename",
                     "query_trigger", "word_count", "scraped_at"]
        meta_cols = [c for c in meta_cols if c in df.columns]
        df[meta_cols].to_csv(
            OUTPUT_DIR / "corpus_rss_meta.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with open(OUTPUT_DIR / "failed_rss.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║           RÉSUMÉ — SCRAPER RSS                   ║
╠══════════════════════════════════════════════════╣
║  Articles extraits  : {len(corpus):>5}                   ║
║  Échecs             : {len(failed):>5}                   ║
║  Taux de succès     : {len(corpus)/max(len(corpus)+len(failed),1)*100:>5.1f}%                  ║
╠══════════════════════════════════════════════════╣
║  Corpus total       : {len(corpus_final):>5} articles           ║
╚══════════════════════════════════════════════════╝
→ Corpus complet : {OUTPUT_DIR}/corpus_bacot.json
→ Métadonnées   : {OUTPUT_DIR}/corpus_rss_meta.csv
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    if not DECODER_AVAILABLE:
        log.error("googlenewsdecoder non installé. Lance : pip install googlenewsdecoder")
        return

    log.info("=" * 60)
    log.info("ÉTAPE 1 — Collecte RSS + décodage URLs Google News")
    log.info("=" * 60)

    url_list = fetch_rss_urls(QUERIES)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "urls_rss.json", "w", encoding="utf-8") as f:
        json.dump(url_list, f, ensure_ascii=False, indent=2)

    if not url_list:
        log.error("Aucune URL collectée.")
        return

    log.info(f"{len(url_list)} URLs prêtes pour le scraping")

    log.info("=" * 60)
    log.info("ÉTAPE 2 — Scraping des articles")
    log.info("=" * 60)

    corpus = []
    failed = []
    hashes = set()

    for i, meta in enumerate(url_list, 1):
        url = meta["url"]
        log.info(f"[{i}/{len(url_list)}] {url[:80]}...")

        article = scrape_article(url)

        if article:
            texte   = article.get("text", "")
            nb_mots = len(texte.split())

            if nb_mots < MIN_WORDS:
                log.info(f"  ✗ Trop court ({nb_mots} mots)")
                failed.append({"url": url, "reason": "too_short"})
                time.sleep(DELAY)
                continue

            h = hash_texte(texte)
            if h in hashes:
                log.info(f"  ✗ Doublon")
                failed.append({"url": url, "reason": "doublon"})
                time.sleep(DELAY)
                continue
            hashes.add(h)

            article.update({
                "url":           url,
                "query_trigger": meta.get("query_trigger", ""),
                "scraped_at":    datetime.utcnow().isoformat(),
                "word_count":    nb_mots,
            })

            corpus.append(article)
            log.info(
                f"  ✓ {nb_mots} mots "
                f"| {article.get('sitename', '?')} "
                f"| {article.get('title', '')[:50]}"
            )
        else:
            log.info("  ✗ Échec extraction")
            failed.append({"url": url, "reason": "extraction_failed"})

        time.sleep(DELAY)

    log.info("=" * 60)
    log.info("ÉTAPE 3 — Sauvegarde")
    log.info("=" * 60)

    save_corpus(corpus, failed)


if __name__ == "__main__":
    run()
