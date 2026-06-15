"""
preparer_corpus_interface.py — Prépare le corpus nettoyé pour l'interface web
==============================================================================
Fusionne et filtre toutes les sources disponibles :
  • corpus_bacot/corpus_bacot.json     — articles de presse + commentaires YouTube
  • corpus_bacot/wayback_articles.json — articles archivés Wayback Machine (si présent)
  • corpus_bacot/tweets_bacot.json     — tweets (si présent)

Filtre : seuls les documents mentionnant "bacot" ou "polette" sont conservés.
Déduplique par URL (ou par texte pour les commentaires/tweets sans URL stable).

Produit :
  data/articles_interface.json  — corpus structuré prêt pour l'interface

Usage :
    python preparer_corpus_interface.py
"""

import json
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

CORPUS_DIR   = Path("corpus_bacot")
DATA_DIR     = Path("data")
OUTPUT_FILE  = DATA_DIR / "articles_interface.json"

SOURCES_PRESSE = CORPUS_DIR / "corpus_bacot.json"
SOURCES_WB     = CORPUS_DIR / "wayback_articles.json"
SOURCES_RSS    = CORPUS_DIR / "rss_articles.json"
SOURCES_TWEETS = CORPUS_DIR / "tweets_bacot.json"

MOTS_CLES = ["bacot", "polette"]
MOTS_CLES_TWEETS = ["bacot", "polette", "libertepourvalerie", "libérezvalérie",
                    "justicepourvalerie", "valérie bacot", "valerie bacot", "clayette"]

# ─── Utilitaires ──────────────────────────────────────────────────────────────

def est_pertinent(texte: str) -> bool:
    t = texte.lower()
    if "bacot" in t:
        return True
    if "polette" in t and "valérie" in t:
        return True
    return False


def normaliser_date(date_brute: str | None) -> str:
    """Tente de normaliser une date en YYYY-MM-DD, retourne '' sinon."""
    if not date_brute:
        return ""
    date_brute = date_brute.strip()
    # Déjà au bon format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_brute):
        return date_brute
    # YYYY seulement
    if re.match(r"^\d{4}$", date_brute):
        return date_brute + "-01-01"
    # DD/MM/YYYY ou DD-MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", date_brute)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return date_brute


def empreinte(texte: str) -> str:
    """Hash court du texte pour dédupliquer les documents sans URL stable."""
    return hashlib.md5(texte.strip()[:500].encode("utf-8")).hexdigest()[:12]


def source_depuis_url(url: str) -> str:
    """Extrait un nom de source lisible depuis l'URL quand source/sitename sont vides."""
    if not url:
        return "inconnu"
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if not m:
        return "inconnu"
    domaine = m.group(1)
    # Raccourcis lisibles pour les domaines connus
    MAP = {
        "france3-regions.francetvinfo.fr": "France 3",
        "francetvinfo.fr": "France TV Info",
        "bfmtv.com": "BFM TV",
        "leparisien.fr": "Le Parisien",
        "lemonde.fr": "Le Monde",
        "lefigaro.fr": "Le Figaro",
        "liberation.fr": "Libération",
        "lexpress.fr": "L'Express",
        "lepoint.fr": "Le Point",
        "20minutes.fr": "20 Minutes",
        "rtl.fr": "RTL",
        "huffingtonpost.fr": "HuffPost",
        "marianne.net": "Marianne",
        "causette.fr": "Causette",
        "madmoizelle.com": "Madmoizelle",
        "neonmag.fr": "Néon",
        "bienpublic.com": "Bien Public",
        "estrepublicain.fr": "Est Républicain",
        "leprogres.fr": "Le Progrès",
        "lyoncapitale.fr": "Lyon Capitale",
        "jsl.fr": "JSL",
        "tf1info.fr": "TF1 Info",
        "parismatch.com": "Paris Match",
    }
    return MAP.get(domaine, domaine)


def extraire_resume(texte: str, nb_mots: int = 60) -> str:
    mots = texte.split()
    resume = " ".join(mots[:nb_mots])
    return resume + ("…" if len(mots) > nb_mots else "")


# ─── Chargement des sources ───────────────────────────────────────────────────

def charger_corpus_principal() -> tuple[list[dict], list[dict]]:
    """
    Charge corpus_bacot.json.
    Retourne (articles_presse, commentaires).
    """
    if not SOURCES_PRESSE.exists():
        print(f"  [MANQUANT] {SOURCES_PRESSE}")
        return [], []

    with open(SOURCES_PRESSE, encoding="utf-8") as f:
        data = json.load(f)

    presse = []
    commentaires = []

    for item in data:
        source = item.get("source", "")

        if source == "youtube_commentaire":
            commentaires.append({
                "id":        "yt_" + empreinte(item.get("text", "")),
                "texte":     item.get("text", "").strip(),
                "date":      normaliser_date(item.get("date", "")),
                "url":       item.get("url", ""),
                "source":    "youtube",
                "nb_mots":   item.get("word_count", len(item.get("text", "").split())),
            })
        else:
            presse.append({
                "id":        "art_" + empreinte(item.get("url", "") + item.get("title", "")),
                "url":       item.get("url", ""),
                "titre":     item.get("title", "").strip(),
                "auteur":    item.get("author", "") or "",
                "date":      normaliser_date(item.get("date", "")),
                "source":    source or item.get("sitename", "") or source_depuis_url(item.get("url", "")),
                "resume":    extraire_resume(item.get("text", "")),
                "texte":     item.get("text", "").strip(),
                "nb_mots":   item.get("word_count", len(item.get("text", "").split())),
                "type":      "presse",
            })

    print(f"  corpus_bacot.json   : {len(presse)} articles presse, {len(commentaires)} commentaires")
    return presse, commentaires


def charger_wayback() -> list[dict]:
    """Charge wayback_articles.json et filtre les articles pertinents."""
    if not SOURCES_WB.exists():
        print(f"  [MANQUANT] {SOURCES_WB}")
        return []

    with open(SOURCES_WB, encoding="utf-8") as f:
        data = json.load(f)

    articles = []
    for item in data:
        texte_complet = (item.get("text", "") + " " + item.get("title", "")).strip()
        if not est_pertinent(texte_complet):
            continue
        articles.append({
            "id":      "wb_" + empreinte(item.get("url", "") + item.get("title", "")),
            "url":     item.get("url", ""),
            "titre":   item.get("title", "").strip(),
            "auteur":  item.get("author", "") or "",
            "date":    normaliser_date(item.get("date", "")),
            "source":  item.get("sitename", "") or item.get("source", "") or source_depuis_url(item.get("url", "")),
            "resume":  extraire_resume(item.get("text", "")),
            "texte":   item.get("text", "").strip(),
            "nb_mots": item.get("word_count", len(item.get("text", "").split())),
            "type":    "presse",
        })

    print(f"  wayback_articles.json : {len(articles)} articles pertinents")
    return articles


def charger_rss() -> list[dict]:
    """Charge rss_articles.json (scraper_rss_etendu_bacot) et filtre les articles pertinents."""
    if not SOURCES_RSS.exists():
        print(f"  [MANQUANT] {SOURCES_RSS}")
        return []

    with open(SOURCES_RSS, encoding="utf-8") as f:
        data = json.load(f)

    articles = []
    for item in data:
        texte_complet = (item.get("texte", "") + " " + item.get("titre", "")).strip()
        if not est_pertinent(texte_complet):
            continue
        articles.append({
            "id":      "rss_" + empreinte(item.get("url", "") + item.get("titre", "")),
            "url":     item.get("url", ""),
            "titre":   item.get("titre", "").strip(),
            "auteur":  item.get("auteur", "") or "",
            "date":    normaliser_date(item.get("date", "")),
            "source":  item.get("sitename", "") or item.get("source_rss", "") or source_depuis_url(item.get("url", "")),
            "resume":  extraire_resume(item.get("texte", "")),
            "texte":   item.get("texte", "").strip(),
            "nb_mots": item.get("nb_mots", len(item.get("texte", "").split())),
            "type":    "presse",
        })

    print(f"  rss_articles.json     : {len(articles)} articles pertinents")
    return articles


def charger_tweets() -> list[dict]:
    """Charge tweets_bacot.json et filtre les tweets pertinents."""
    if not SOURCES_TWEETS.exists():
        print(f"  [MANQUANT] {SOURCES_TWEETS}")
        return []

    with open(SOURCES_TWEETS, encoding="utf-8") as f:
        data = json.load(f)

    tweets = []
    for item in data:
        texte = item.get("texte", "").strip()
        if not any(kw in texte.lower() for kw in MOTS_CLES_TWEETS):
            continue
        tweets.append({
            "id":        "tw_" + empreinte(item.get("url", "") + texte),
            "texte":     texte,
            "auteur":    item.get("auteur", ""),
            "handle":    item.get("handle", ""),
            "date":      normaliser_date(item.get("date", "") or item.get("datetime", "")),
            "url":       item.get("url", ""),
            "likes":     item.get("likes", 0),
            "retweets":  item.get("retweets", 0),
            "nb_mots":   item.get("nb_mots", len(texte.split())),
            "source":    "twitter",
        })

    print(f"  tweets_bacot.json   : {len(tweets)} tweets pertinents")
    return tweets


# ─── Déduplication ────────────────────────────────────────────────────────────

def dedupliquer_par_url(articles: list[dict]) -> list[dict]:
    """Déduplique une liste d'articles par URL (garde le plus récent si doublon)."""
    vus: dict[str, dict] = {}
    sans_url = []

    for art in articles:
        url = art.get("url", "").strip()
        if not url:
            sans_url.append(art)
            continue
        if url not in vus:
            vus[url] = art
        else:
            # Garde celui dont la date est la plus récente
            if art.get("date", "") > vus[url].get("date", ""):
                vus[url] = art

    return list(vus.values()) + sans_url


def dedupliquer_par_id(items: list[dict]) -> list[dict]:
    """Déduplique une liste par leur champ 'id'."""
    vus: dict[str, dict] = {}
    for item in items:
        vus[item["id"]] = item
    return list(vus.values())


# ─── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    print("=" * 58)
    print("  Préparation du corpus pour l'interface — Affaire Bacot")
    print("=" * 58)
    print("\nChargement des sources :")

    # Chargement
    presse_corpus, commentaires = charger_corpus_principal()
    presse_wb                   = charger_wayback()
    presse_rss                  = charger_rss()
    tweets                      = charger_tweets()

    # Fusion articles de presse (corpus principal + wayback + rss étendu)
    tous_articles = presse_corpus + presse_wb + presse_rss
    tous_articles = dedupliquer_par_url(tous_articles)
    tous_articles.sort(key=lambda a: a.get("date", ""), reverse=True)

    # Déduplication commentaires et tweets
    commentaires = dedupliquer_par_id(commentaires)
    tweets       = dedupliquer_par_id(tweets)
    tweets.sort(key=lambda t: t.get("date", ""), reverse=True)

    # Stats
    sources_presse = Counter(a["source"] for a in tous_articles)
    print(f"\nRésumé :")
    print(f"  Articles de presse  : {len(tous_articles)}")
    for src, n in sources_presse.most_common(10):
        print(f"    {src or 'inconnu':<30} {n}")
    print(f"  Commentaires YouTube : {len(commentaires)}")
    print(f"  Tweets              : {len(tweets)}")
    total = len(tous_articles) + len(commentaires) + len(tweets)
    print(f"  TOTAL               : {total}")

    # Export
    DATA_DIR.mkdir(exist_ok=True)
    sortie = {
        "meta": {
            "genere_le":          datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total":              total,
            "nb_articles_presse": len(tous_articles),
            "nb_commentaires":    len(commentaires),
            "nb_tweets":          len(tweets),
            "sources_presse":     dict(sources_presse),
        },
        "articles_presse": tous_articles,
        "commentaires":    commentaires,
        "tweets":          tweets,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    print(f"\nExport : {OUTPUT_FILE}  ({OUTPUT_FILE.stat().st_size // 1024} Ko)")
    print("=" * 58)


if __name__ == "__main__":
    run()
