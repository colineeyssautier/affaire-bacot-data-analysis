"""
fusionner_corpus.py — Fusion et nettoyage des sources de corpus Bacot
======================================================================
Lit trois sources, filtre par pertinence, normalise les champs,
déduplique par URL et sauvegarde corpus_bacot/corpus_final.json.

Usage :
    python fusionner_corpus.py
"""

import json
import sys
from pathlib import Path
from collections import Counter

CORPUS_DIR = Path("corpus_bacot")

SOURCES = {
    "corpus_bacot.json":     "article_presse",
    "rss_articles.json":     "article_presse",
    "wayback_articles.json": "archive_web",
    "presse_nouveaux.json":  "article_presse",  # collecteur_urls_presse.py
}

TERMES_PERTINENCE = [
    "bacot", "polette", "tout le monde savait", "clayette",
]

PRESSE_NATIONALE = {
    "le monde", "lemonde", "libération", "liberation", "le figaro", "figaro",
    "l'obs", "obs", "l'express", "lexpress", "marianne", "l'humanité", "humanite",
    "la croix", "les echos", "bfmtv", "bfm", "france info", "franceinfo",
    "france 2", "france 3", "france 5", "tf1", "m6", "lci", "cnews",
    "20 minutes", "20minutes", "le parisien", "parisien", "huffpost",
    "huffington", "slate", "mediapart", "telerama", "télérama",
    "rtl", "europe 1", "rmc", "public sénat", "sénat",
}

PRESSE_REGIONALE = {
    "le bien public", "bienpublic", "l'est républicain", "estrepublicain",
    "le progrès", "leprogres", "le jsl", "lejsl", "jsl",
    "lyon capitale", "lyoncapitale", "france 3 bfc", "france 3 bourgogne",
    "le journal de saône-et-loire", "yonne républicaine",
}


def classer_source(sitename: str) -> str:
    if not sitename:
        return "article_presse"
    s = sitename.lower()
    if any(r in s for r in PRESSE_REGIONALE):
        return "presse_regionale"
    if any(n in s for n in PRESSE_NATIONALE):
        return "presse_nationale"
    return "article_presse"


def est_pertinent(texte: str) -> bool:
    t = texte.lower()
    return any(terme in t for terme in TERMES_PERTINENCE)


def normaliser(doc: dict, source_par_defaut: str) -> dict | None:
    # Récupère le texte quel que soit le nom du champ
    texte = doc.get("text") or doc.get("texte") or doc.get("content") or ""
    est_commentaire = doc.get("source") == "youtube_commentaire"
    seuil = 5 if est_commentaire else 50
    if not texte or len(texte.split()) < seuil:
        return None
    # Les commentaires YouTube viennent de vidéos déjà filtrées — pertinence établie par contexte
    if not est_commentaire and not est_pertinent(texte):
        return None

    sitename = doc.get("sitename", "")
    type_source = classer_source(sitename) if source_par_defaut == "article_presse" else source_par_defaut

    return {
        "url":          doc.get("url", ""),
        "text":         texte,
        "title":        doc.get("title") or doc.get("titre") or "",
        "author":       doc.get("author") or doc.get("auteur") or "",
        "date":         (doc.get("date") or "")[:10],
        "description":  doc.get("description", ""),
        "sitename":     sitename,
        "type_source":  type_source,
        "source":       doc.get("source") or doc.get("source_rss") or "article_presse",
        "word_count":   doc.get("word_count") or doc.get("nb_mots") or len(texte.split()),
        "scraped_at":   doc.get("scraped_at", ""),
        "score_pertinence": doc.get("score_pertinence", None),
    }


def main():
    corpus_final: dict[str, dict] = {}   # url -> doc (déduplique)
    stats: dict[str, Counter] = {}

    for fname, source_defaut in SOURCES.items():
        path = CORPUS_DIR / fname
        if not path.exists():
            print(f"  ABSENT : {fname}")
            continue

        docs = json.loads(path.read_text(encoding="utf-8"))
        n_total = len(docs)
        n_ok = 0
        n_doublons = 0

        for doc in docs:
            d = normaliser(doc, source_defaut)
            if d is None:
                continue
            url = d["url"]
            if not url:
                continue
            if url in corpus_final:
                n_doublons += 1
                continue
            corpus_final[url] = d
            n_ok += 1

        stats[fname] = Counter({"total": n_total, "retenus": n_ok, "doublons": n_doublons})
        print(f"  {fname}: {n_total} lus, {n_ok} retenus, {n_doublons} doublons")

    articles = list(corpus_final.values())
    type_counts = Counter(a["type_source"] for a in articles)

    out = CORPUS_DIR / "corpus_final.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"\ncorpus_final.json : {len(articles)} articles pertinents")
    print("Repartition par type de source :")
    for k, v in type_counts.most_common():
        print(f"  {k}: {v}")
    print(f"\nFichier sauvegarde : {out}")
    print("Lance maintenant : python Classifier_bacot.py")


if __name__ == "__main__":
    print("=== Fusion du corpus Bacot ===")
    main()
