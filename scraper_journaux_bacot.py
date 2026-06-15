"""
Scraper pages de recherche internes — Affaire Valérie Bacot
============================================================
Va directement sur les moteurs de recherche internes des
grands journaux français pour récupérer les articles sur
l'affaire Bacot, sans passer par Google/Bing/DDG.

Installation :
    pip install requests beautifulsoup4 trafilatura pandas

Usage :
    python scraper_journaux_bacot.py
"""

import json
import time
import logging
import hashlib
import requests
import trafilatura
import pandas as pd
from bs4 import BeautifulSoup
from trafilatura.settings import use_config
from datetime import datetime
from pathlib import Path

# ─── Sources : pages de recherche internes des journaux ──────────────────────
#
# Chaque entrée définit :
#   - nom       : nom du journal
#   - url       : URL de la page de résultats (avec le terme de recherche)
#   - selecteur : sélecteur CSS pour trouver les liens d'articles
#   - base      : domaine de base pour construire les URLs relatives
#   - pages     : nombre de pages à scraper
#   - page_param: paramètre GET pour paginer (None si pas de pagination)
#   - page_start: valeur de départ pour la pagination

SOURCES = [
    {
        "nom": "20 Minutes",
        "url": "https://www.20minutes.fr/search/query/valerie+bacot",
        "selecteur": "article a, .search-result a, h2 a, h3 a",
        "base": "https://www.20minutes.fr",
        "pages": 3,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "BFM TV",
        "url": "https://www.bfmtv.com/recherche/?q=val%C3%A9rie+bacot",
        "selecteur": "article a, .search-result a, h2 a, h3 a, .article a",
        "base": "https://www.bfmtv.com",
        "pages": 3,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "France Inter",
        "url": "https://www.radiofrance.fr/recherche?p[terme]=val%C3%A9rie+bacot",
        "selecteur": "article a, h2 a, h3 a, .card a",
        "base": "https://www.radiofrance.fr",
        "pages": 3,
        "page_param": "p[page]",
        "page_start": 1,
    },
    {
        "nom": "RTL",
        "url": "https://www.rtl.fr/search?q=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a, .teaser a",
        "base": "https://www.rtl.fr",
        "pages": 3,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "Le Parisien",
        "url": "https://www.leparisien.fr/recherche/?q=val%C3%A9rie+bacot&s=recency",
        "selecteur": "article a, h2 a, h3 a, .story a",
        "base": "https://www.leparisien.fr",
        "pages": 3,
        "page_param": "p",
        "page_start": 1,
    },
    {
        "nom": "France 3 Bourgogne",
        "url": "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/saone-et-loire/",
        "selecteur": "article a, h2 a, h3 a",
        "base": "https://france3-regions.franceinfo.fr",
        "pages": 1,
        "page_param": None,
        "page_start": 1,
        "filtre_mot": "bacot",  # filtre supplémentaire sur le texte du lien
    },
    {
        "nom": "Franceinfo",
        "url": "https://www.francetvinfo.fr/faits-divers/crime/valerie-bacot/",
        "selecteur": "article a, h2 a, h3 a, .teaser a",
        "base": "https://www.francetvinfo.fr",
        "pages": 2,
        "page_param": None,
        "page_start": 1,
    },
    {
        "nom": "L'Express",
        "url": "https://www.lexpress.fr/search/?q=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a",
        "base": "https://www.lexpress.fr",
        "pages": 2,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "Le JSL",
        "url": "https://www.lejsl.com/recherche?q=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a, .article-title a",
        "base": "https://www.lejsl.com",
        "pages": 3,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "Bien Public",
        "url": "https://www.bienpublic.com/recherche?q=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a",
        "base": "https://www.bienpublic.com",
        "pages": 2,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "TF1 Info",
        "url": "https://www.tf1info.fr/recherche/?q=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a, .card a",
        "base": "https://www.tf1info.fr",
        "pages": 2,
        "page_param": "page",
        "page_start": 1,
    },
    {
        "nom": "Humanité",
        "url": "https://www.humanite.fr/?s=valerie+bacot",
        "selecteur": "article a, h2 a, h3 a",
        "base": "https://www.humanite.fr",
        "pages": 2,
        "page_param": "paged",
        "page_start": 1,
    },
    {
        "nom": "Slate",
        "url": "https://www.slate.fr/search?q=bacot",
        "selecteur": "article a, h2 a, h3 a, .article a",
        "base": "https://www.slate.fr",
        "pages": 2,
        "page_param": "page",
        "page_start": 1,
    },
]

# ─── Configuration ────────────────────────────────────────────────────────────

DELAY_CRAWL  = 2.5
DELAY_SCRAPE = 2.0
MIN_WORDS    = 100
OUTPUT_DIR   = Path("corpus_bacot")

# Extensions à exclure (pas des articles)
EXTENSIONS_BLACKLIST = [
    ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mp4", ".mp3",
    ".css", ".js", ".xml", ".rss",
]

# Mots-clés obligatoires dans l'URL ou le texte du lien
# pour s'assurer que c'est bien lié à l'affaire Bacot
MOTS_CLES_BACOT = [
    "bacot", "polette", "clayette", "valerie",
    "feminicide", "violence-conjugale", "legitime-defense",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_journaux.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ─── Config trafilatura ────────────────────────────────────────────────────────

newconfig = use_config()
newconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def nettoyer_url(url: str, base: str) -> str | None:
    """Normalise une URL relative en URL absolue."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base.rstrip("/") + url
    if url.startswith("http"):
        return url
    return None


def url_valide(url: str) -> bool:
    """Vérifie qu'une URL est scrapable."""
    if not url:
        return False
    url_lower = url.lower()
    # Exclut les fichiers non-texte
    if any(url_lower.endswith(ext) for ext in EXTENSIONS_BLACKLIST):
        return False
    # Exclut les ancres pures
    if url_lower.startswith("#"):
        return False
    return True


def concerne_bacot(url: str, texte_lien: str = "") -> bool:
    """
    Vérifie si un lien est probablement lié à l'affaire Bacot.
    Regarde l'URL et le texte du lien.
    """
    ref = (url + " " + texte_lien).lower()
    return any(mot in ref for mot in MOTS_CLES_BACOT)


def hash_texte(texte: str) -> str:
    return hashlib.md5(texte[:500].encode("utf-8")).hexdigest()


# ─── Étape 1 : crawl des pages de recherche ───────────────────────────────────

def crawl_source(source: dict) -> list[dict]:
    """
    Scrappe les pages de résultats d'une source et retourne
    les URLs d'articles trouvées.
    """
    nom          = source["nom"]
    url_base_src = source["url"]
    selecteur    = source["selecteur"]
    base         = source["base"]
    pages        = source["pages"]
    page_param   = source.get("page_param")
    page_start   = source.get("page_start", 1)
    filtre_mot   = source.get("filtre_mot", "").lower()

    articles_trouves = {}

    for page_num in range(page_start, page_start + pages):
        # Construction de l'URL paginée
        if page_param and page_num > page_start:
            sep = "&" if "?" in url_base_src else "?"
            url_page = f"{url_base_src}{sep}{page_param}={page_num}"
        else:
            url_page = url_base_src

        log.info(f"  [{nom}] Page {page_num - page_start + 1}/{pages} : {url_page[:70]}...")

        try:
            response = requests.get(
                url_page,
                headers=HEADERS,
                timeout=15,
                allow_redirects=True,
            )

            if response.status_code != 200:
                log.info(f"    HTTP {response.status_code} — ignoré")
                break

            soup = BeautifulSoup(response.text, "html.parser")
            liens_trouves = 0

            for a in soup.select(selecteur):
                href      = a.get("href", "")
                texte     = a.get_text(strip=True)
                url_propre = nettoyer_url(href, base)

                if not url_propre or not url_valide(url_propre):
                    continue

                # Filtre domaine — reste sur le même site
                if base.replace("https://www.", "").replace("https://", "") not in url_propre:
                    continue

                # Filtre optionnel sur mot-clé dans le texte
                if filtre_mot and filtre_mot not in texte.lower() and filtre_mot not in url_propre.lower():
                    continue

                # Pour les pages de recherche dédiées "bacot",
                # on accepte tous les liens d'articles
                # Pour les pages de catégorie générales, on filtre sur Bacot
                if "bacot" not in url_base_src.lower() and not concerne_bacot(url_propre, texte):
                    continue

                if url_propre not in articles_trouves:
                    articles_trouves[url_propre] = {
                        "url":    url_propre,
                        "source": nom,
                        "titre_lien": texte[:100],
                    }
                    liens_trouves += 1

            log.info(f"    → {liens_trouves} liens pertinents trouvés")

        except Exception as e:
            log.warning(f"    Erreur crawl {nom} page {page_num} : {e}")

        time.sleep(DELAY_CRAWL)

    return list(articles_trouves.values())


def collecter_toutes_urls() -> list[dict]:
    """Crawle toutes les sources et retourne une liste dédupliquée d'URLs."""
    toutes = {}

    for source in SOURCES:
        log.info(f"\n{'='*50}")
        log.info(f"Source : {source['nom']}")
        log.info(f"{'='*50}")

        urls = crawl_source(source)
        log.info(f"  Total pour {source['nom']} : {len(urls)} articles")

        for item in urls:
            if item["url"] not in toutes:
                toutes[item["url"]] = item

        time.sleep(1)

    log.info(f"\nTotal URLs uniques collectées : {len(toutes)}")
    return list(toutes.values())


# ─── Étape 2 : scraping des articles ──────────────────────────────────────────

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


# ─── Étape 3 : sauvegarde ─────────────────────────────────────────────────────

def sauvegarder(corpus_nouveau: list[dict], failed: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "corpus_bacot.json"

    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            corpus_existant = json.load(f)
        urls_existantes = {a.get("url", "") for a in corpus_existant}
        nouveaux = [a for a in corpus_nouveau if a["url"] not in urls_existantes]
        corpus_final = corpus_existant + nouveaux
        log.info(f"Fusion : {len(corpus_existant)} existants + {len(nouveaux)} nouveaux = {len(corpus_final)} total")
    else:
        corpus_final = corpus_nouveau

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame(corpus_nouveau)
    if not df.empty:
        meta_cols = ["url", "title", "author", "date", "sitename",
                     "source", "word_count", "scraped_at"]
        meta_cols = [c for c in meta_cols if c in df.columns]
        df[meta_cols].to_csv(
            OUTPUT_DIR / "corpus_journaux_meta.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with open(OUTPUT_DIR / "failed_journaux.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         RÉSUMÉ — SCRAPER JOURNAUX                ║
╠══════════════════════════════════════════════════╣
║  Sources crawlées   : {len(SOURCES):>5}                   ║
║  Articles extraits  : {len(corpus_nouveau):>5}                   ║
║  Échecs             : {len(failed):>5}                   ║
║  Taux de succès     : {len(corpus_nouveau)/max(len(corpus_nouveau)+len(failed),1)*100:>5.1f}%                  ║
╠══════════════════════════════════════════════════╣
║  Corpus total       : {len(corpus_final):>5} articles           ║
╚══════════════════════════════════════════════════╝
→ Corpus : {OUTPUT_DIR}/corpus_bacot.json
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():

    log.info("=" * 60)
    log.info("ÉTAPE 1 — Crawl des pages de recherche des journaux")
    log.info("=" * 60)

    url_list = collecter_toutes_urls()

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "urls_journaux.json", "w", encoding="utf-8") as f:
        json.dump(url_list, f, ensure_ascii=False, indent=2)

    if not url_list:
        log.error("Aucune URL collectée.")
        return

    # Filtre URLs déjà connues
    json_path = OUTPUT_DIR / "corpus_bacot.json"
    urls_connues = set()
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            corpus_existant = json.load(f)
        urls_connues = {a.get("url", "") for a in corpus_existant}
        log.info(f"{len(urls_connues)} URLs déjà dans le corpus — ignorées")

    urls_nouvelles = [u for u in url_list if u["url"] not in urls_connues]
    log.info(f"{len(urls_nouvelles)} nouvelles URLs à scraper")

    log.info("=" * 60)
    log.info("ÉTAPE 2 — Scraping des articles")
    log.info("=" * 60)

    corpus  = []
    failed  = []
    hashes  = set()

    for i, meta in enumerate(urls_nouvelles, 1):
        url = meta["url"]
        log.info(f"[{i}/{len(urls_nouvelles)}] {url[:80]}...")

        article = scrape_article(url)

        if article:
            texte   = article.get("text", "")
            nb_mots = len(texte.split())

            if nb_mots < MIN_WORDS:
                log.info(f"  ✗ Trop court ({nb_mots} mots)")
                failed.append({"url": url, "reason": "too_short"})
                time.sleep(DELAY_SCRAPE)
                continue

            h = hash_texte(texte)
            if h in hashes:
                log.info(f"  ✗ Doublon")
                failed.append({"url": url, "reason": "doublon"})
                time.sleep(DELAY_SCRAPE)
                continue
            hashes.add(h)

            article.update({
                "url":        url,
                "source":     meta.get("source", ""),
                "scraped_at": datetime.utcnow().isoformat(),
                "word_count": nb_mots,
            })
            corpus.append(article)
            log.info(
                f"  ✓ {nb_mots} mots "
                f"| {article.get('sitename', meta.get('source','?'))} "
                f"| {article.get('title', '')[:45]}"
            )
        else:
            log.info("  ✗ Échec extraction")
            failed.append({"url": url, "reason": "extraction_failed"})

        time.sleep(DELAY_SCRAPE)

    log.info("=" * 60)
    log.info("ÉTAPE 3 — Sauvegarde")
    log.info("=" * 60)

    sauvegarder(corpus, failed)


if __name__ == "__main__":
    run()
