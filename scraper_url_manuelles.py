"""
Scraper URLs manuelles — Affaire Valérie Bacot
===============================================
Scrape directement une liste d'URLs connues via trafilatura.
Pas de Google News, pas de résolution de redirections — on va
directement chercher le texte sur chaque site source.

Installation :
    pip install trafilatura pandas requests

Usage :
    python scraper_urls_manuelles.py
"""

import json
import time
import logging
import pandas as pd
import trafilatura
import requests
from trafilatura.settings import use_config
from datetime import datetime
from pathlib import Path

# ─── Liste de tes URLs ────────────────────────────────────────────────────────

URLS = [
    "https://www.lamontagne.fr/mauriac-15200/actualites/valerie-bacot-est-venue-raconter-ses-31-annees-de-violences-sexuelles-et-psychologiques-aux-lyceens-de-mauriac-cantal_14118795/",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/recit-femme-battue-violee-prostituee-valerie-bacot-tue-son-mari-23-victime-qui-ne-manque-personne-1854240.html",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/saone-et-loire/chalon-sur-saone/direct-valerie-bacot-femme-battue-qui-a-tue-son-mari-le-proces-commence-aux-assises-de-saone-et-loire-2142121.html",
    "https://www.rtl.fr/actu/justice-faits-divers/crime-de-la-clayette-la-seconde-affaire-jacqueline-sauvage-7791251037",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/saone-et-loire/macon/macon-6-mois-prison-sursis-requis-contre-enfants-affaire-clayette-1752567.html",
    "https://madame.lefigaro.fr/societe/valerie-bacot-proces-livre-femme-battue-violee-prostituee-par-son-mari-tout-le-monde-savait-230621-197039",
    "https://www.info-chalon.com/articles/2021/06/21/50534/assises-de-saone-et-loire-est-ce-que-mme-bacot-vous-avez-voulu-tuer-votre-mari-non-non-vous-vouliez-quoi-me-proteger-de-quoi-de-tout",
    "https://www.lejsl.com/faits-divers-justice/2021/06/23/suivez-le-proces-de-valerie-bacot",
    "https://web.archive.org/web/20210624204110/https://www.sudradio.fr/societe/la-mere-de-valerie-bacot-parle-damour-avec-son-mari-proxenete/",
    "https://www.bfmtv.com/police-justice/une-petition-demande-la-liberte-pour-valerie-bacot-accusee-d-avoir-tue-son-mari-violent_AN-202101190267.html",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/saone-et-loire/macon/valerie-bacot-a-nouveau-face-a-la-justice-suite-a-la-plainte-de-sa-mere-pour-diffamation-2308621.html",
    "https://www.lepoint.fr/societe/la-mere-de-valerie-bacot-porte-plainte-contre-elle-pour-diffamation-15-07-2021-2435635_23.php",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/recit-battue-violee-prostituee-valerie-bacot-tue-son-mari-13-epouse-victime-accusee-1854434.html",
    "https://www.20minutes.fr/justice/3064991-20210621-violences-conjugales-valerie-bacot-femme-battue-jugee-assassinat-mari-violent",
    "https://www.bfmtv.com/police-justice/proces/en-direct-valerie-bacot-jugee-pour-avoir-tue-son-mari-proxenete-suivez-le-proces_LN-202106210135.html",
    "https://www.tf1info.fr/justice-faits-divers/video-replay-tf1-sept-a-huit-l-interview-bouleversante-de-valerie-bacot-jugee-pour-avoir-tue-son-mari-qui-la-tyrannisait-2185510.html",
    "https://www.lefigaro.fr/faits-divers/affaire-valerie-bacot-une-petition-pour-obtenir-la-grace-d-une-femme-que-personne-n-a-jamais-protegee-20210121",
    "https://www.senat.fr/compte-rendu-commissions/20211101/ddf_bacot.html",
    "https://france3-regions.franceinfo.fr/bourgogne-franche-comte/saone-et-loire/chalon-sur-saone/direct-valerie-bacot-elle-est-non-coupable-clame-l-un-des-enfants-de-la-femme-qui-a-tue-son-mari-violent-2147332.html",
]

# ─── Configuration ────────────────────────────────────────────────────────────

DELAY     = 2.0     # secondes entre deux requêtes
MIN_WORDS = 100     # longueur minimale pour garder un article
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
        logging.FileHandler("scraper_manuelles.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# ─── Config trafilatura ────────────────────────────────────────────────────────

newconfig = use_config()
newconfig.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


# ─── Scraping ─────────────────────────────────────────────────────────────────

def scrape_article(url: str) -> dict | None:
    """
    Télécharge et extrait le texte propre d'un article via trafilatura.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            # Tentative alternative avec requests si trafilatura échoue
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                downloaded = response.text
            else:
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
            "url":         url,
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Déduplique la liste (ton fichier avait lejsl.com en double)
    urls_uniques = list(dict.fromkeys(URLS))
    log.info(f"URLs à scraper : {len(urls_uniques)} (après déduplication)")

    corpus = []
    failed = []

    for i, url in enumerate(urls_uniques, 1):
        log.info(f"[{i}/{len(urls_uniques)}] {url[:80]}...")

        article = scrape_article(url)

        if article:
            article.update({
                "source":     "manuel",
                "scraped_at": datetime.utcnow().isoformat(),
                "word_count": len(article.get("text", "").split()),
            })

            if article["word_count"] >= MIN_WORDS:
                corpus.append(article)
                log.info(
                    f"  ✓ {article['word_count']} mots "
                    f"| {article.get('sitename', '?')} "
                    f"| {article.get('title', '')[:50]}"
                )
            else:
                log.info(f"  ✗ Trop court ({article['word_count']} mots)")
                failed.append({"url": url, "reason": "too_short"})
        else:
            log.info("  ✗ Échec extraction")
            failed.append({"url": url, "reason": "extraction_failed"})

        time.sleep(DELAY)

    # ── Sauvegarde ──

    # Si un corpus Google News existe déjà, on fusionne
    json_gnews = OUTPUT_DIR / "corpus_bacot.json"
    if json_gnews.exists():
        with open(json_gnews, encoding="utf-8") as f:
            corpus_gnews = json.load(f)
        log.info(f"Fusion avec corpus Google News existant ({len(corpus_gnews)} articles)")

        # Déduplication par URL
        urls_existantes = {a["url"] for a in corpus_gnews}
        nouveaux = [a for a in corpus if a["url"] not in urls_existantes]
        corpus_fusion = corpus_gnews + nouveaux
        log.info(f"Après fusion et déduplication : {len(corpus_fusion)} articles")
    else:
        corpus_fusion = corpus

    # Sauvegarde JSON complet
    with open(OUTPUT_DIR / "corpus_bacot.json", "w", encoding="utf-8") as f:
        json.dump(corpus_fusion, f, ensure_ascii=False, indent=2)

    # Sauvegarde CSV des articles manuels seuls (pour vérification)
    df = pd.DataFrame(corpus)
    if not df.empty:
        meta_cols = ["url", "title", "author", "date", "sitename", "word_count", "scraped_at"]
        meta_cols = [c for c in meta_cols if c in df.columns]
        df[meta_cols].to_csv(
            OUTPUT_DIR / "corpus_manuelles_meta.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with open(OUTPUT_DIR / "failed_manuelles.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         RÉSUMÉ — URLS MANUELLES                  ║
╠══════════════════════════════════════════════════╣
║  URLs traitées      : {len(urls_uniques):>5}                   ║
║  Articles extraits  : {len(corpus):>5}                   ║
║  Échecs             : {len(failed):>5}                   ║
║  Taux de succès     : {len(corpus)/max(len(urls_uniques),1)*100:>5.1f}%                  ║
╠══════════════════════════════════════════════════╣
║  Corpus total fusionné : {len(corpus_fusion):>4} articles          ║
╚══════════════════════════════════════════════════╝
→ Corpus complet : {OUTPUT_DIR}/corpus_bacot.json
→ Métadonnées   : {OUTPUT_DIR}/corpus_manuelles_meta.csv
→ Échecs        : {OUTPUT_DIR}/failed_manuelles.json
    """)


if __name__ == "__main__":
    run()