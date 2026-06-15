"""
Scraper DuckDuckGo + trafilatura — Affaire Valérie Bacot
=========================================================
Interroge DuckDuckGo sur plusieurs requêtes, extrait les URLs
des résultats, puis scrappe chaque article.

Installation :
    pip install requests beautifulsoup4 trafilatura pandas

Usage :
    python scraper_bing_bacot.py
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
from urllib.parse import urlencode, unquote

# ─── Requêtes de recherche ────────────────────────────────────────────────────

QUERIES = [
    "affaire Valérie Bacot",
    "procès Valérie Bacot 2021",
    "Valérie Bacot violence conjugale féminicide",
    "Valérie Bacot Daniel Polette jugement",
    "Bacot acquittement légitime défense",
    "Bacot livre témoignage",
    "Bacot pétition libération",
    "Bacot condamnation verdict",
]

# ─── Configuration ────────────────────────────────────────────────────────────

PAGES_PAR_REQUETE  = 4
DELAY_DDG          = 4.0    # DuckDuckGo est sensible aux requêtes trop rapides
DELAY_SCRAPE       = 2.0
MIN_WORDS          = 100
OUTPUT_DIR         = Path("corpus_bacot")

DOMAINES_BLACKLIST = [
    "youtube.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "tiktok.com", "wikipedia.org",
    "amazon.com", "amazon.fr", "fnac.com", "duckduckgo.com",
    "bing.com", "google.com",
]

DOMAINES_PRIORITAIRES = [
    "lemonde.fr", "liberation.fr", "lefigaro.fr", "leparisien.fr",
    "20minutes.fr", "bfmtv.com", "rtl.fr", "franceinter.fr",
    "france3-regions.franceinfo.fr", "francetvinfo.fr",
    "tf1info.fr", "europe1.fr", "lepoint.fr", "lexpress.fr",
    "lejsl.com", "bienpublic.com", "leprogres.fr",
    "mediapart.fr", "humanite.fr", "causette.fr",
    "madmoizelle.com", "slate.fr", "marianne.net",
    "senat.fr", "assemblee-nationale.fr",
    "info-chalon.com", "lamontagne.fr",
]

# Headers réalistes pour DuckDuckGo
HEADERS_DDG = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

HEADERS_SCRAPE = {
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
        logging.FileHandler("scraper_ddg.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ─── Config trafilatura ────────────────────────────────────────────────────────

newconfig = use_config()
newconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


# ─── Étape 1 : scraping DuckDuckGo ────────────────────────────────────────────

def est_blackliste(url: str) -> bool:
    return any(d in url for d in DOMAINES_BLACKLIST)

def est_prioritaire(url: str) -> bool:
    return any(d in url for d in DOMAINES_PRIORITAIRES)

def extraire_urls_ddg_html(html: str) -> list[str]:
    """
    Extrait les URLs de résultats depuis le HTML de DuckDuckGo.
    DDG encode ses URLs dans des attributs data-href ou href.
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    # Méthode 1 : liens dans les résultats organiques DDG
    # Structure : <a class="result__a" href="...">
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        if href and href.startswith("http") and not est_blackliste(href):
            urls.append(href)

    # Méthode 2 : liens dans data-href (format alternatif DDG)
    if not urls:
        for a in soup.find_all("a", {"data-href": True}):
            href = a.get("data-href", "")
            if href and href.startswith("http") and not est_blackliste(href):
                urls.append(href)

    # Méthode 3 : cherche dans tous les liens h2/h3
    if not urls:
        for tag in soup.find_all(["h2", "h3"]):
            a = tag.find("a", href=True)
            if a:
                href = a["href"]
                if href.startswith("http") and not est_blackliste(href):
                    urls.append(href)

    return urls


def scraper_ddg(query: str, page: int, session: requests.Session) -> list[str]:
    """
    Scrappe une page de résultats DuckDuckGo.
    DDG utilise le paramètre 's' pour la pagination (0, 30, 60...).
    """
    # DDG pagination : s=0 (page 1), s=30 (page 2), s=60 (page 3)...
    offset = (page - 1) * 30

    params = {
        "q":  query,
        "kl": "fr-fr",      # langue française
        "kad": "fr_FR",
    }
    if offset > 0:
        params["s"] = str(offset)
        params["dc"] = str(offset + 1)
        params["api"] = "d.js"

    try:
        url = "https://html.duckduckgo.com/html/"
        response = session.post(
            url,
            data=params,
            headers=HEADERS_DDG,
            timeout=15,
        )

        if response.status_code != 200:
            log.warning(f"  DDG HTTP {response.status_code} page {page}")
            return []

        urls = extraire_urls_ddg_html(response.text)
        return urls

    except Exception as e:
        log.warning(f"  Erreur DDG page {page} : {e}")
        return []


def collecter_urls(queries: list[str]) -> list[dict]:
    """
    Pour chaque requête, scrappe plusieurs pages DDG.
    """
    all_urls = {}
    session = requests.Session()

    for query in queries:
        log.info(f"DuckDuckGo — recherche : '{query}'")
        trouvees_total = 0

        for page in range(1, PAGES_PAR_REQUETE + 1):
            urls_page = scraper_ddg(query, page, session)
            log.info(f"  Page {page} : {len(urls_page)} résultats")

            for url in urls_page:
                if url not in all_urls:
                    all_urls[url] = {
                        "url":           url,
                        "query_trigger": query,
                        "page":          page,
                        "prioritaire":   est_prioritaire(url),
                    }
                    trouvees_total += 1

            time.sleep(DELAY_DDG)

        log.info(f"  → {trouvees_total} nouvelles URLs collectées")
        time.sleep(2)

    urls_list = list(all_urls.values())
    urls_list.sort(key=lambda x: (0 if x["prioritaire"] else 1, x["page"]))

    log.info(f"Total URLs uniques : {len(urls_list)}")
    log.info(f"  dont prioritaires : {sum(1 for u in urls_list if u['prioritaire'])}")
    return urls_list


# ─── Étape 2 : scraping des articles ──────────────────────────────────────────

def scrape_article(url: str) -> dict | None:
    try:
        downloaded = trafilatura.fetch_url(url)

        if not downloaded:
            response = requests.get(url, headers=HEADERS_SCRAPE, timeout=15)
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
        log.info(f"Fusion : {len(corpus_existant)} + {len(nouveaux)} nouveaux = {len(corpus_final)} total")
    else:
        corpus_final = corpus_nouveau

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)

    df = pd.DataFrame(corpus_nouveau)
    if not df.empty:
        meta_cols = ["url", "title", "author", "date", "sitename",
                     "query_trigger", "word_count", "scraped_at"]
        meta_cols = [c for c in meta_cols if c in df.columns]
        df[meta_cols].to_csv(
            OUTPUT_DIR / "corpus_ddg_meta.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with open(OUTPUT_DIR / "failed_ddg.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         RÉSUMÉ — SCRAPER DUCKDUCKGO              ║
╠══════════════════════════════════════════════════╣
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
    log.info("ÉTAPE 1 — Collecte des URLs via DuckDuckGo")
    log.info("=" * 60)

    url_list = collecter_urls(QUERIES)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "urls_ddg.json", "w", encoding="utf-8") as f:
        json.dump(url_list, f, ensure_ascii=False, indent=2)

    if not url_list:
        log.error("Aucune URL collectée. Vérifie ta connexion.")
        return

    # Filtre URLs déjà connues
    json_path = OUTPUT_DIR / "corpus_bacot.json"
    urls_connues = set()
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            corpus_existant = json.load(f)
        urls_connues = {a.get("url", "") for a in corpus_existant}
        log.info(f"{len(urls_connues)} URLs déjà connues — ignorées")

    urls_nouvelles = [u for u in url_list if u["url"] not in urls_connues]
    log.info(f"{len(urls_nouvelles)} URLs nouvelles à scraper")

    log.info("=" * 60)
    log.info("ÉTAPE 2 — Scraping des articles")
    log.info("=" * 60)

    corpus  = []
    failed  = []
    hashes  = set()

    for i, meta in enumerate(urls_nouvelles, 1):
        url = meta["url"]
        star = "★" if meta.get("prioritaire") else " "
        log.info(f"[{i}/{len(urls_nouvelles)}] {star} {url[:75]}...")

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
                "url":           url,
                "query_trigger": meta.get("query_trigger", ""),
                "scraped_at":    datetime.utcnow().isoformat(),
                "word_count":    nb_mots,
            })
            corpus.append(article)
            log.info(
                f"  ✓ {nb_mots} mots "
                f"| {article.get('sitename', '?')} "
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