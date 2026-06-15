"""
generer_dataset_open.py — Génération du dataset open
=====================================================
Produit les fichiers publiables sur GitHub :

    data/
    ├── corpus_bacot_metadata.csv       Métadonnées des 953 docs (sans textes)
    ├── corpus_youtube_commentaires.csv Textes complets des commentaires YT
    ├── resultats_classification.csv    Scores narratifs (copie nettoyée)
    └── lexique_narratifs.json          Le lexique des 8 catégories

Usage :
    python generer_dataset_open.py
"""

import json
import shutil
import pandas as pd
from pathlib import Path

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_JSON   = Path("corpus_bacot/corpus_bacot.json")
CSV_RESULTATS = Path("analyse_bacot/resultats_classification.csv")
OUTPUT_DIR    = Path("data")

# ─── Lexique complet ──────────────────────────────────────────────────────────

LEXIQUE = {
    "soutien_victime": {
        "label_fr":    "Soutien à la victime",
        "description": "Compassion, solidarité, validation du geste comme acte de survie.",
        "termes": [
            "victime", "survie", "survivante", "courage", "brave", "innocente",
            "défendre", "se défendre", "protéger", "soutien", "soutenir",
            "solidarité", "comprendre", "normal", "logique", "aurait fait pareil",
            "a bien fait", "avait raison", "méritait", "libre", "libération",
            "pétition", "justice", "enfin libre", "bravo", "respect", "admire",
            "force", "courageuse",
        ]
    },
    "remise_en_question": {
        "label_fr":    "Remise en question",
        "description": "Doute sur les choix, évocation d'alternatives, peut aller jusqu'à la condamnation morale.",
        "termes": [
            "partir", "quitter", "fuir", "appeler", "police", "gendarmerie",
            "signaler", "porter plainte", "pourquoi pas", "mais quand même",
            "meurtre", "meurtrière", "tuer", "assassin", "assassinat",
            "préméditation", "aurait pu", "pouvait", "choix", "autre solution",
            "pas excusable", "même si", "incompréhensible", "responsable",
        ]
    },
    "legitime_defense": {
        "label_fr":    "Légitime défense",
        "description": "Cadre juridique, légitime défense différée, précédent Jacqueline Sauvage, réformes.",
        "termes": [
            "légitime défense", "défense différée", "défens", "loi", "juridique",
            "jurisprudence", "droit", "code pénal", "jacqueline sauvage",
            "grâce présidentielle", "réforme", "changer la loi",
            "angleterre", "canada", "syndrome", "état de nécessité", "contrainte",
        ]
    },
    "discours_feministe": {
        "label_fr":    "Discours féministe",
        "description": "Approche systémique — patriarcat, féminicide, continuum des violences faites aux femmes.",
        "termes": [
            "féminicide", "feminicide", "féministe", "féminisme", "patriarcat",
            "sexisme", "domination", "oppression", "violences faites aux femmes",
            "violences conjugales", "violence domestique", "emprise",
            "cycle de la violence", "contrôle coercitif", "nous toutes",
            "metoo", "systémique", "structurel", "inégalité", "droits des femmes",
        ]
    },
    "emprise_psychologique": {
        "label_fr":    "Emprise psychologique",
        "description": "Mécanisme d'emprise, contrôle coercitif, traumatisme, prostitution forcée.",
        "termes": [
            "emprise", "manipulation", "contrôle", "isolement", "peur", "terreur",
            "traumatisme", "syndrome", "dépendance", "soumission", "proxénétisme",
            "prostituée", "forcée", "obligée", "menace", "chantage", "survie",
            "conditionnée", "résignation",
        ]
    },
    "silence_collectif": {
        "label_fr":    "Silence collectif",
        "description": "Complicité passive — 'tout le monde savait' — entourage, institutions.",
        "termes": [
            "savait", "savaient", "tout le monde savait", "silence", "taire",
            "complice", "complicité", "voisin", "entourage", "famille",
            "institution", "école", "médecin", "signalement", "protection",
            "enfants", "témoin", "inaction", "rien fait", "fermé les yeux",
        ]
    },
    "sensationnalisme": {
        "label_fr":    "Sensationnalisme",
        "description": "Traitement comme fait divers spectaculaire, true crime, sans dimension critique.",
        "termes": [
            "choquant", "horrible", "atroce", "terrifiant", "incroyable",
            "hallucinant", "fou", "dingue", "true crime", "crime", "fait divers",
            "story", "documentaire", "reportage", "film", "série", "regarder",
            "abonner", "like", "partager", "chaîne", "vidéo",
        ]
    },
    "jugement_moral": {
        "label_fr":    "Jugement moral",
        "description": "Jugement sur la légitimité de la peine ou la culpabilité morale de Valérie Bacot.",
        "termes": [
            "mérite", "méritait", "punir", "punition", "condamner", "condamnation",
            "coupable", "responsable", "faute", "moral", "morale", "éthique",
            "pardon", "pardonner", "compassion", "pitié", "sévère", "clément",
            "juste", "injuste", "verdict", "sentence", "peine", "prison",
        ]
    },
}


# ─── Génération des fichiers ───────────────────────────────────────────────────

def run():
    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"Génération du dataset open dans : {OUTPUT_DIR}/")
    print()

    # ── 1. Lexique JSON ──
    lexique_path = OUTPUT_DIR / "lexique_narratifs.json"
    with open(lexique_path, "w", encoding="utf-8") as f:
        json.dump({
            "version":     "1.0",
            "projet":      "Mythodologie — Corpus narratifs Valérie Bacot",
            "description": (
                "Lexique de classification lexicale des narratifs médiatiques "
                "autour de l'affaire Valérie Bacot. Construit manuellement. "
                "Applicable à d'autres affaires avec adaptation."
            ),
            "licence":     "CC BY 4.0",
            "categories":  LEXIQUE,
        }, f, ensure_ascii=False, indent=2)
    print(f"  ✓ lexique_narratifs.json ({len(LEXIQUE)} catégories)")

    # ── 2. Résultats classification (copie nettoyée) ──
    if CSV_RESULTATS.exists():
        df = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig')

        # Supprime les colonnes internes inutiles pour le dataset open
        cols_a_supprimer = [c for c in df.columns if c in ["cluster_mots_cles"]]
        df = df.drop(columns=cols_a_supprimer, errors='ignore')

        # Renomme pour clarté
        df.to_csv(
            OUTPUT_DIR / "resultats_classification.csv",
            index=False,
            encoding="utf-8-sig"
        )
        print(f"  ✓ resultats_classification.csv ({len(df)} documents)")
    else:
        print(f"  ⚠ CSV introuvable : {CSV_RESULTATS}")

    # ── 3. Métadonnées corpus (sans textes) ──
    if CORPUS_JSON.exists():
        import json as _json
        with open(CORPUS_JSON, encoding='utf-8') as f:
            corpus = _json.load(f)

        rows_meta = []
        for doc in corpus:
            rows_meta.append({
                "url":        doc.get("url", ""),
                "titre":      doc.get("title", doc.get("video_titre", ""))[:200],
                "auteur":     doc.get("author", doc.get("auteur", "")),
                "date":       doc.get("date", "")[:10],
                "sitename":   doc.get("sitename", doc.get("chaine", "")),
                "type_doc":   "commentaire" if doc.get("source") == "youtube_commentaire" else "article",
                "source_type": doc.get("source", ""),
                "word_count": doc.get("word_count", len(doc.get("text", "").split())),
                "video_url":  doc.get("video_url", ""),
            })

        df_meta = pd.DataFrame(rows_meta)
        df_meta.to_csv(
            OUTPUT_DIR / "corpus_bacot_metadata.csv",
            index=False,
            encoding="utf-8-sig"
        )
        print(f"  ✓ corpus_bacot_metadata.csv ({len(df_meta)} documents, sans textes)")

        # ── 4. Commentaires YouTube (textes complets — publiables) ──
        rows_yt = []
        for doc in corpus:
            if doc.get("source") != "youtube_commentaire":
                continue
            rows_yt.append({
                "url":          doc.get("url", ""),
                "texte":        doc.get("text", ""),
                "auteur":       doc.get("auteur", ""),
                "date":         doc.get("date", "")[:10],
                "likes":        doc.get("likes", 0),
                "video_url":    doc.get("video_url", ""),
                "video_titre":  doc.get("video_titre", "")[:200],
                "chaine":       doc.get("chaine", doc.get("sitename", "")),
                "word_count":   doc.get("word_count", len(doc.get("text", "").split())),
            })

        df_yt = pd.DataFrame(rows_yt)
        df_yt.to_csv(
            OUTPUT_DIR / "corpus_youtube_commentaires.csv",
            index=False,
            encoding="utf-8-sig"
        )
        print(f"  ✓ corpus_youtube_commentaires.csv ({len(df_yt)} commentaires avec textes)")

    else:
        print(f"  ⚠ Corpus JSON introuvable : {CORPUS_JSON}")

    print(f"""
╔══════════════════════════════════════════════════╗
║         DATASET OPEN GÉNÉRÉ ✓                    ║
╠══════════════════════════════════════════════════╣
║  Dossier : data/                                 ║
║                                                  ║
║  lexique_narratifs.json                          ║
║  resultats_classification.csv                    ║
║  corpus_bacot_metadata.csv                       ║
║  corpus_youtube_commentaires.csv                 ║
╚══════════════════════════════════════════════════╝

Ces fichiers sont prêts à être publiés sur GitHub.
Licence : CC BY 4.0
    """)


if __name__ == "__main__":
    run()
