"""
integrer_nouveaux_commentaires.py
==================================
Intègre commentaires_nouvelles_videos.csv dans l'architecture du corpus.

Actions :
1. Lit et déduplique commentaires_nouvelles_videos.csv
2. Filtre les commentaires déjà présents dans le corpus
3. Applique la classification lexicale (8 catégories)
4. Met à jour :
   - corpus_bacot/corpus_final.json
   - analyse_bacot/resultats_classification.csv
   - data/corpus_youtube_commentaires.csv
5. Reconstruit la base SQLite (API_bacot/bacot.db)

Usage :
    python integrer_nouveaux_commentaires.py
"""

import json
import csv
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import pandas as pd

# ─── Chemins ──────────────────────────────────────────────────────────────────

BASE_DIR         = Path(__file__).parent
INPUT_CSV        = BASE_DIR / "commentaires_nouvelles_videos.csv"
CORPUS_JSON      = BASE_DIR / "corpus_bacot" / "corpus_final.json"
CSV_RESULTATS    = BASE_DIR / "analyse_bacot" / "resultats_classification.csv"
CSV_COMMENTAIRES = BASE_DIR / "data" / "corpus_youtube_commentaires.csv"
DB_SCRIPT        = BASE_DIR / "API_bacot" / "database.py"

# ─── Lexique de classification (8 catégories) ─────────────────────────────────

LEXIQUE = {
    "soutien_victime": [
        "victime", "survie", "survivante", "courage", "brave", "innocente",
        "défendre", "protéger", "soutien", "soutenir", "solidarité",
        "comprendre", "normal", "logique", "aurait fait pareil", "a bien fait",
        "avait raison", "méritait", "libre", "libération", "pétition",
        "justice", "enfin libre", "bravo", "respect", "admire", "force",
    ],
    "remise_en_question": [
        "partir", "quitter", "fuir", "appeler", "police", "gendarmerie",
        "signaler", "porter plainte", "pourquoi pas", "mais quand même",
        "meurtre", "meurtrière", "tuer", "assassin", "assassinat",
        "préméditation", "aurait pu", "pouvait", "choix", "autre solution",
        "pas excusable", "même si", "incompréhensible",
    ],
    "legitime_defense": [
        "légitime défense", "défense différée", "loi", "juridique",
        "jurisprudence", "droit", "code pénal", "jacqueline sauvage",
        "grâce présidentielle", "réforme", "changer la loi",
        "angleterre", "canada", "syndrome", "état de nécessité",
        "défense", "défendre", "défendu", "autodéfense", "défen",
    ],
    "discours_feministe": [
        "féminicide", "feminicide", "féministe", "féminisme", "patriarcat",
        "sexisme", "domination", "oppression", "violences faites aux femmes",
        "violences conjugales", "violence domestique", "emprise",
        "cycle de la violence", "contrôle coercitif", "nous toutes", "metoo",
        "systémique", "structurel", "inégalité", "droits des femmes",
    ],
    "emprise_psychologique": [
        "emprise", "manipulation", "contrôle", "isolement", "peur", "terreur",
        "traumatisme", "syndrome", "dépendance", "soumission", "proxénétisme",
        "prostituée", "forcée", "obligée", "menace", "chantage", "survie",
    ],
    "silence_collectif": [
        "savait", "savaient", "tout le monde savait", "silence", "taire",
        "complice", "complicité", "voisin", "entourage", "famille",
        "institution", "école", "médecin", "signalement", "protection",
        "enfants", "témoin", "inaction", "rien fait", "fermé les yeux",
    ],
    "sensationnalisme": [
        "choquant", "horrible", "atroce", "terrifiant", "incroyable",
        "hallucinant", "fou", "dingue", "true crime", "crime", "fait divers",
        "story", "documentaire", "reportage", "film", "série", "regarder",
        "abonner", "like", "partager", "chaîne", "vidéo",
    ],
    "jugement_moral": [
        "mérite", "méritait", "punir", "punition", "condamner", "condamnation",
        "coupable", "responsable", "faute", "moral", "morale", "éthique",
        "pardon", "pardonner", "compassion", "pitié", "sévère", "clément",
        "juste", "injuste", "verdict", "sentence", "peine", "prison",
    ],
}

CATEGORIES = list(LEXIQUE.keys())


def scorer_texte(texte: str) -> dict:
    """Calcule les scores narratifs d'un texte (comptage lexical)."""
    t = texte.lower()
    scores = {cat: sum(t.count(terme) for terme in termes)
              for cat, termes in LEXIQUE.items()}
    total = sum(scores.values())
    dominant = max(scores, key=scores.get) if total > 0 else "non_classe"
    return scores, total, dominant


def normaliser_date(date_str: str) -> str:
    """Normalise une date ISO 8601 en YYYY-MM-DD."""
    if not date_str:
        return ""
    return str(date_str)[:10]


def construire_url(video_id: str, commentaire_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}#comment_{commentaire_id}"


# ─── Chargement des données existantes ────────────────────────────────────────

def charger_urls_existantes() -> set:
    """Retourne l'ensemble des URLs déjà dans le corpus et dans le CSV de résultats."""
    urls = set()

    if CORPUS_JSON.exists():
        with open(CORPUS_JSON, encoding="utf-8") as f:
            corpus = json.load(f)
        urls.update(doc.get("url", "") for doc in corpus)
        print(f"  corpus_final.json       : {len(corpus)} documents existants")

    if CSV_RESULTATS.exists():
        df = pd.read_csv(CSV_RESULTATS, encoding="utf-8-sig")
        urls.update(df["url"].dropna().tolist())
        print(f"  resultats_classification: {len(df)} lignes existantes")

    return urls


def charger_corpus() -> list:
    if CORPUS_JSON.exists():
        with open(CORPUS_JSON, encoding="utf-8") as f:
            return json.load(f)
    return []


def charger_resultats() -> pd.DataFrame:
    if CSV_RESULTATS.exists():
        return pd.read_csv(CSV_RESULTATS, encoding="utf-8-sig")
    return pd.DataFrame()


def charger_commentaires_csv() -> pd.DataFrame:
    if CSV_COMMENTAIRES.exists():
        return pd.read_csv(CSV_COMMENTAIRES, encoding="utf-8")
    return pd.DataFrame()


# ─── Traitement ───────────────────────────────────────────────────────────────

def traiter_nouveaux_commentaires(urls_existantes: set) -> tuple[list, list, list]:
    """
    Lit le CSV source, déduplique, filtre les doublons, classe et retourne
    (nouvelles_entrees_corpus, nouvelles_lignes_resultats, nouvelles_lignes_commentaires_csv)
    """
    print(f"\nLecture de {INPUT_CSV} ...")
    df_src = pd.read_csv(INPUT_CSV, encoding="utf-8")
    print(f"  {len(df_src)} lignes lues")

    # Déduplique par commentaire_id (le CSV contient parfois des doublons)
    df_src = df_src.drop_duplicates(subset="commentaire_id")
    print(f"  {len(df_src)} après déduplication sur commentaire_id")

    nouveaux_corpus   = []
    nouvelles_lignes  = []
    nouvelles_csv     = []
    n_doublon         = 0
    n_vide            = 0

    for _, row in df_src.iterrows():
        texte = str(row.get("texte", "")).strip()
        if not texte or texte == "nan":
            n_vide += 1
            continue

        video_id       = str(row["video_id"])
        commentaire_id = str(row["commentaire_id"])
        url            = construire_url(video_id, commentaire_id)

        if url in urls_existantes:
            n_doublon += 1
            continue

        video_titre = str(row.get("video_titre", "")).strip()
        chaine      = str(row.get("video_chaine", "")).strip()
        auteur      = str(row.get("auteur", "")).strip()
        date        = normaliser_date(str(row.get("date", "")))
        likes       = int(row["likes"]) if pd.notna(row.get("likes")) else 0
        word_count  = len(texte.split())
        sitename    = f"YouTube — {chaine}" if chaine else "YouTube"
        titre       = f"Commentaire sur : {video_titre}" if video_titre else "Commentaire YouTube"

        scores, total, dominant = scorer_texte(texte)

        # ── Entrée corpus JSON ──
        nouveaux_corpus.append({
            "url":         url,
            "text":        texte,
            "title":       titre,
            "author":      auteur,
            "date":        date,
            "description": "",
            "sitename":    sitename,
            "type_source": "youtube_commentaire",
            "source":      "youtube_commentaire",
            "word_count":  word_count,
            "scraped_at":  datetime.now().isoformat(),
            "video_id":    video_id,
            "video_titre": video_titre,
            "chaine":      chaine,
            "likes":       likes,
            "comment_type": str(row.get("type", "commentaire")),
        })

        # ── Ligne resultats_classification.csv ──
        ligne = {
            "url":                  url,
            "titre":                titre,
            "date":                 date,
            "sitename":             sitename,
            "type_source":          "youtube_commentaire",
            "type_doc":             "commentaire",
            "word_count":           word_count,
            "categorie_dominante":  dominant,
            "score_total":          total,
            "cluster":              None,
            "cluster_mots_cles":    None,
        }
        for cat in CATEGORIES:
            ligne[f"score_{cat}"] = scores[cat]
        nouvelles_lignes.append(ligne)

        # ── Ligne corpus_youtube_commentaires.csv ──
        nouvelles_csv.append({
            "url":          url,
            "texte":        texte,
            "auteur":       auteur,
            "date":         date,
            "likes":        likes,
            "video_url":    f"https://www.youtube.com/watch?v={video_id}",
            "video_titre":  video_titre,
            "chaine":       chaine,
            "word_count":   word_count,
        })

        urls_existantes.add(url)

    print(f"  {n_doublon} doublons ignorés (déjà dans le corpus)")
    print(f"  {n_vide} entrées vides ignorées")
    print(f"  -> {len(nouvelles_lignes)} nouveaux commentaires a integrer")

    return nouveaux_corpus, nouvelles_lignes, nouvelles_csv


# ─── Écriture ─────────────────────────────────────────────────────────────────

def sauvegarder(nouveaux_corpus, nouvelles_lignes, nouvelles_csv):

    # ── corpus_final.json ──
    print("\n[1/4] Mise à jour de corpus_final.json ...")
    corpus_existant = charger_corpus()
    corpus_final    = corpus_existant + nouveaux_corpus
    with open(CORPUS_JSON, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)
    print(f"       {len(corpus_existant)} → {len(corpus_final)} documents")

    # ── resultats_classification.csv ──
    print("[2/4] Mise à jour de resultats_classification.csv ...")
    df_existant  = charger_resultats()
    df_nouveaux  = pd.DataFrame(nouvelles_lignes)
    df_final     = pd.concat([df_existant, df_nouveaux], ignore_index=True)
    df_final.to_csv(CSV_RESULTATS, index=False, encoding="utf-8-sig")
    print(f"       {len(df_existant)} → {len(df_final)} lignes")

    # ── corpus_youtube_commentaires.csv ──
    print("[3/4] Mise à jour de data/corpus_youtube_commentaires.csv ...")
    df_cmt_existant = charger_commentaires_csv()
    df_cmt_nouveaux = pd.DataFrame(nouvelles_csv)
    df_cmt_final    = pd.concat([df_cmt_existant, df_cmt_nouveaux], ignore_index=True)
    df_cmt_final.to_csv(CSV_COMMENTAIRES, index=False, encoding="utf-8")
    print(f"       {len(df_cmt_existant)} → {len(df_cmt_final)} commentaires")

    # ── Reconstruction de la base SQLite ──
    print("[4/4] Reconstruction de la base SQLite ...")
    result = subprocess.run(
        [sys.executable, str(DB_SCRIPT)],
        cwd=str(DB_SCRIPT.parent),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print("  ⚠ Erreur lors de la reconstruction de la base :")
        print(result.stderr.strip())


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(" Intégration des nouveaux commentaires YouTube")
    print("=" * 60)

    if not INPUT_CSV.exists():
        print(f"Erreur : fichier source introuvable : {INPUT_CSV}")
        sys.exit(1)

    print("\nChargement des données existantes ...")
    urls_existantes = charger_urls_existantes()
    print(f"  -> {len(urls_existantes)} URLs connues au total")

    nouveaux_corpus, nouvelles_lignes, nouvelles_csv = traiter_nouveaux_commentaires(
        urls_existantes
    )

    if not nouvelles_lignes:
        print("\nAucun nouveau commentaire à intégrer. Le corpus est déjà à jour.")
        return

    sauvegarder(nouveaux_corpus, nouvelles_lignes, nouvelles_csv)

    print("\n" + "=" * 60)
    print(f" ✓ {len(nouvelles_lignes)} commentaires intégrés avec succès")
    print("   Relancez le dashboard : streamlit run dashboard_bacot.py")
    print("   Relancez l'API       : cd API_bacot && uvicorn main:app --reload")
    print("=" * 60)


if __name__ == "__main__":
    main()
