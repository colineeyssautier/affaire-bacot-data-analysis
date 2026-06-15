"""
Tri semi-automatique du corpus — Affaire Valérie Bacot
=======================================================
Deux modes :

  MODE 1 — Génère un fichier de revue CSV (à remplir manuellement)
      python trier_corpus.py --mode generer

  MODE 2 — Applique tes décisions et produit le corpus final propre
      python trier_corpus.py --mode appliquer

Workflow complet :
  1. python trier_corpus.py --mode generer  →  corpus_bacot/a_reviewer.csv
  2. Ouvre a_reviewer.csv dans Excel, remplis la colonne 'garder' (1=oui, 0=non)
  3. Sauvegarde le CSV
  4. python trier_corpus.py --mode appliquer  →  corpus_bacot/corpus_final.json

Installation :
    pip install pandas
"""

import json
import hashlib
import argparse
import logging
import pandas as pd
from pathlib import Path
from collections import defaultdict

# ─── Configuration ────────────────────────────────────────────────────────────

CORPUS_DIR  = Path("corpus_bacot")
INPUT_JSON  = CORPUS_DIR / "corpus_bacot.json"
REVIEW_CSV  = CORPUS_DIR / "a_reviewer.csv"
OUTPUT_JSON = CORPUS_DIR / "corpus_final.json"
OUTPUT_CSV  = CORPUS_DIR / "corpus_final_meta.csv"

# Seuils de longueur minimale — différents selon le type de document
MIN_MOTS_ARTICLE     = 150   # articles de presse
MIN_MOTS_COMMENTAIRE = 20    # commentaires YouTube (naturellement courts)

# Mots-clés obligatoires : au moins UN doit apparaître dans le texte
MOTS_CLES_OBLIGATOIRES = [
    "bacot", "polette", "valérie", "valerie",
    "chalon", "saône-et-loire", "saone-et-loire",
    "clayette",
]

# Mots-clés de pertinence — score +1 par occurrence
MOTS_CLES_PERTINENCE = [
    "bacot", "polette", "féminicide", "feminicide",
    "violence conjugale", "violences conjugales",
    "légitime défense", "legitime defense",
    "procès", "proces", "acquittement", "condamnation",
    "victime", "meurtrier", "mari", "emprise",
    "chalon", "saône", "saone", "clayette",
    "prostituée", "proxénète", "proxenete",
]

# Domaines à exclure automatiquement
DOMAINES_BLACKLIST = [
    "meteo", "weather", "sport", "lequipe", "foot",
    "bourse", "finance", "immobilier", "cuisine",
    "amazon", "ebay", "shopping",
]

# Classification des sources
PRESSE_NATIONALE = [
    "lemonde", "liberation", "lefigaro", "leparisien",
    "20minutes", "bfmtv", "franceinfo", "rtl",
    "lexpress", "lepoint", "nouvelobs", "marianne",
    "humanite", "slate", "huffpost",
]
PRESSE_LOCALE = [
    "bienpublic", "lejsl", "leprogres", "estrepublicain",
    "lyoncapitale", "macommune", "lamontagne", "info-chalon",
]
PRESSE_MILITANTE = [
    "mediapart", "bastamag", "alternatives-economiques",
    "humanite", "politis", "causette", "madmoizelle",
    "neonmag", "feminist",
]
SOURCES_INSTITUTIONNELLES = [
    "senat.fr", "assemblee-nationale", "gouvernement",
    "vie-publique",
]

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def hash_texte(texte: str) -> str:
    return hashlib.md5(texte[:500].encode("utf-8")).hexdigest()


def score_pertinence(texte: str) -> int:
    texte_lower = texte.lower()
    return sum(texte_lower.count(mot) for mot in MOTS_CLES_PERTINENCE)


def contient_mots_cles(texte: str) -> bool:
    texte_lower = texte.lower()
    return any(mot in texte_lower for mot in MOTS_CLES_OBLIGATOIRES)


def detecter_type_source(url: str, sitename: str, source: str) -> str:
    # Commentaire YouTube
    if source == "youtube_commentaire":
        return "youtube_commentaire"
    # Chaîne YouTube (descriptions RSS)
    if "YouTube" in sitename:
        return "youtube_video"
    ref = (url + " " + sitename).lower()
    if any(s in ref for s in SOURCES_INSTITUTIONNELLES):
        return "institutionnel"
    if any(s in ref for s in PRESSE_MILITANTE):
        return "presse_militante"
    if any(s in ref for s in PRESSE_NATIONALE):
        return "presse_nationale"
    if any(s in ref for s in PRESSE_LOCALE):
        return "presse_locale"
    return "autre"


def domaine_blackliste(url: str) -> bool:
    return any(bl in url.lower() for bl in DOMAINES_BLACKLIST)


def extraire_extrait(texte: str, n_mots: int = 40) -> str:
    mots = texte.split()
    extrait = " ".join(mots[:n_mots])
    return extrait + "..." if len(mots) > n_mots else extrait


def est_commentaire(article: dict) -> bool:
    return article.get("source") == "youtube_commentaire"


# ─── Mode 1 : génération du fichier de revue ──────────────────────────────────

def generer_fichier_revue():
    log.info("=" * 60)
    log.info("MODE 1 — Génération du fichier de revue")
    log.info("=" * 60)

    if not INPUT_JSON.exists():
        log.error(f"Fichier introuvable : {INPUT_JSON}")
        return

    with open(INPUT_JSON, encoding="utf-8") as f:
        corpus = json.load(f)

    log.info(f"Documents chargés : {len(corpus)}")

    # ── Filtres automatiques ──
    gardes     = []
    rejetes    = defaultdict(list)
    hashes_vus = set()

    for article in corpus:
        texte   = article.get("text", "")
        url     = article.get("url", "")
        nb_mots = len(texte.split())
        commentaire = est_commentaire(article)

        # Filtre 1 : longueur minimale — seuil différent selon le type
        seuil = MIN_MOTS_COMMENTAIRE if commentaire else MIN_MOTS_ARTICLE
        if nb_mots < seuil:
            rejetes["trop_court"].append(url)
            continue

        # Filtre 2 : domaine blacklisté (uniquement pour les articles)
        if not commentaire and domaine_blackliste(url):
            rejetes["domaine_blackliste"].append(url)
            continue

        # Filtre 3 : mots-clés obligatoires
        if not contient_mots_cles(texte):
            rejetes["hors_sujet"].append(url)
            continue

        # Filtre 4 : doublons de contenu
        h = hash_texte(texte)
        if h in hashes_vus:
            rejetes["doublon"].append(url)
            continue
        hashes_vus.add(h)

        gardes.append(article)

    log.info(f"Après filtres automatiques : {len(gardes)} documents conservés")
    log.info(f"Rejetés — trop courts       : {len(rejetes['trop_court'])}")
    log.info(f"Rejetés — hors sujet        : {len(rejetes['hors_sujet'])}")
    log.info(f"Rejetés — doublons          : {len(rejetes['doublon'])}")
    log.info(f"Rejetés — domaine blacklist : {len(rejetes['domaine_blackliste'])}")

    # Détail par type
    nb_articles = sum(1 for a in gardes if not est_commentaire(a))
    nb_comments = sum(1 for a in gardes if est_commentaire(a))
    log.info(f"  dont articles de presse  : {nb_articles}")
    log.info(f"  dont commentaires YouTube: {nb_comments}")

    # ── Construction du tableau de revue ──
    rows = []
    for article in gardes:
        texte    = article.get("text", "")
        url      = article.get("url", "")
        sitename = article.get("sitename", "")
        source   = article.get("source", "")
        commentaire = est_commentaire(article)

        type_src = detecter_type_source(url, sitename, source)
        score    = score_pertinence(texte)

        rows.append({
            "garder":           "",        # ← À REMPLIR : 1 = oui, 0 = non
            "type":             "commentaire" if commentaire else "article",
            "titre":            article.get("title", article.get("video_titre", ""))[:120],
            "source":           sitename or article.get("chaine", ""),
            "date":             article.get("date", "")[:10],
            "type_source":      type_src,
            "score_pertinence": score,
            "nb_mots":          len(texte.split()),
            "extrait":          extraire_extrait(texte, 40),
            "auteur":           article.get("author", article.get("auteur", "")),
            "url":              url,
        })

    # Tri : articles en haut par score, commentaires ensuite
    rows.sort(key=lambda x: (
        0 if x["type"] == "article" else 1,
        -x["score_pertinence"]
    ))

    df = pd.DataFrame(rows)
    df.to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         FICHIER DE REVUE GÉNÉRÉ                  ║
╠══════════════════════════════════════════════════╣
║  Documents à reviewer   : {len(rows):>5}                ║
║    dont articles        : {nb_articles:>5}                ║
║    dont commentaires YT : {nb_comments:>5}                ║
╚══════════════════════════════════════════════════╝

→ Ouvre ce fichier dans Excel :
  {REVIEW_CSV}

Instructions :
  - Colonne 'garder' : mets 1 pour garder, 0 pour rejeter
  - Laisse vide = sera ignoré (compté comme 0)
  - Les articles sont triés en premier, par score de pertinence
  - Les commentaires YouTube viennent ensuite
  - Colonne 'extrait' : 40 premiers mots pour décider rapidement

Quand tu as fini :
  python trier_corpus.py --mode appliquer
    """)


# ─── Mode 2 : application des décisions ───────────────────────────────────────

def appliquer_decisions():
    log.info("=" * 60)
    log.info("MODE 2 — Application des décisions de revue")
    log.info("=" * 60)

    if not REVIEW_CSV.exists():
        log.error(f"Fichier de revue introuvable : {REVIEW_CSV}")
        log.error("Lance d'abord : python trier_corpus.py --mode generer")
        return

    if not INPUT_JSON.exists():
        log.error(f"Corpus source introuvable : {INPUT_JSON}")
        return

    df_revue = pd.read_csv(REVIEW_CSV, encoding="utf-8-sig")
    with open(INPUT_JSON, encoding="utf-8") as f:
        corpus_brut = json.load(f)

    index_corpus = {a["url"]: a for a in corpus_brut}

    urls_gardees = set(
        df_revue[df_revue["garder"] == 1]["url"].tolist()
    )

    if not urls_gardees:
        log.warning("Aucun document marqué 'garder = 1'.")
        log.warning("Vérifie que tu as bien mis 1 dans la colonne 'garder'.")
        return

    corpus_final = []
    for url in urls_gardees:
        if url in index_corpus:
            article = index_corpus[url]
            row = df_revue[df_revue["url"] == url].iloc[0]
            article["type_source"]      = row.get("type_source", "")
            article["score_pertinence"] = row.get("score_pertinence", 0)
            corpus_final.append(article)

    # Tri final : articles d'abord, puis commentaires, par date
    corpus_final.sort(key=lambda x: (
        0 if x.get("source") != "youtube_commentaire" else 1,
        x.get("date", ""),
    ), reverse=False)

    # Sauvegarde JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)

    # Sauvegarde CSV métadonnées
    df_final = pd.DataFrame([{
        "url":              a.get("url", ""),
        "type":             "commentaire" if a.get("source") == "youtube_commentaire" else "article",
        "titre":            a.get("title", a.get("video_titre", "")),
        "auteur":           a.get("author", a.get("auteur", "")),
        "date":             a.get("date", "")[:10],
        "source":           a.get("sitename", a.get("chaine", "")),
        "type_source":      a.get("type_source", ""),
        "score_pertinence": a.get("score_pertinence", 0),
        "nb_mots":          len(a.get("text", "").split()),
    } for a in corpus_final])

    df_final.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    # Statistiques
    nb_articles  = sum(1 for a in corpus_final if a.get("source") != "youtube_commentaire")
    nb_comments  = sum(1 for a in corpus_final if a.get("source") == "youtube_commentaire")
    stats_type   = df_final["type_source"].value_counts().to_dict()

    log.info(f"""
╔══════════════════════════════════════════════════╗
║           CORPUS FINAL PRÊT                      ║
╠══════════════════════════════════════════════════╣
║  Documents retenus      : {len(corpus_final):>5}                ║
║    dont articles presse : {nb_articles:>5}                ║
║    dont commentaires YT : {nb_comments:>5}                ║
║  Mots total (estimé)    : {df_final['nb_mots'].sum():>7}              ║
╠══════════════════════════════════════════════════╣
║  Par type de source :                            ║""")
    for t, n in stats_type.items():
        log.info(f"║    {t:<25} : {n:>4}               ║")
    log.info(f"""╚══════════════════════════════════════════════════╝

→ Corpus final JSON  : {OUTPUT_JSON}
→ Métadonnées CSV    : {OUTPUT_CSV}

Prochaine étape : classification lexicale + clustering
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tri semi-automatique du corpus Bacot"
    )
    parser.add_argument(
        "--mode",
        choices=["generer", "appliquer"],
        required=True,
        help="'generer' : crée le fichier de revue | 'appliquer' : applique tes décisions"
    )
    args = parser.parse_args()

    if args.mode == "generer":
        generer_fichier_revue()
    elif args.mode == "appliquer":
        appliquer_decisions()