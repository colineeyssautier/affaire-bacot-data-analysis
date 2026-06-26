"""
fusionner_corpus_llm.py — Corpus texte + classification pour analyse LLM
=========================================================================
Fusionne les scores de classification avec le texte source pour produire
un fichier exploitable directement par un LLM.

Sources :
  • corpus_bacot/corpus_final.json   — texte des commentaires YouTube
  • corpus_bacot/tweets_bacot.json   — texte des tweets
  • analyse_bacot/resultats_classification.csv — scores narratifs

Produit :
  data/corpus_llm.csv   — texte + catégorie + scores (tweets + commentaires)
  data/corpus_llm.json  — même contenu en JSON (pratique pour l'API LLM)

Usage :
    python fusionner_corpus_llm.py
"""

import sys
import json
import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Chemins ──────────────────────────────────────────────────────────────────

BASE            = Path(__file__).parent
CSV_CLASSIF     = BASE / "analyse_bacot" / "resultats_classification.csv"
CORPUS_JSON     = BASE / "corpus_bacot" / "corpus_final.json"
TWEETS_JSON     = BASE / "corpus_bacot" / "tweets_bacot.json"
OUTPUT_CSV      = BASE / "data" / "corpus_llm.csv"
OUTPUT_JSON     = BASE / "data" / "corpus_llm.json"

SCORE_COLS = [
    "score_soutien_victime", "score_remise_en_question", "score_legitime_defense",
    "score_discours_feministe", "score_emprise_psychologique", "score_silence_collectif",
    "score_sensationnalisme", "score_jugement_moral",
]

# ─── Chargement de la classification ──────────────────────────────────────────

print("Chargement de la classification...")
df_classif = pd.read_csv(CSV_CLASSIF)
print(f"  {len(df_classif)} documents classifiés")

# ─── Commentaires YouTube ─────────────────────────────────────────────────────

print("Chargement des commentaires YouTube...")
with open(CORPUS_JSON, encoding="utf-8") as f:
    corpus = json.load(f)

commentaires_index = {
    d["url"]: d.get("text", "")
    for d in corpus
    if d.get("source") == "youtube_commentaire" and d.get("url")
}
print(f"  {len(commentaires_index)} commentaires dans le corpus")

df_comm = df_classif[df_classif["type_doc"] == "commentaire"].copy()
df_comm["texte"] = df_comm["url"].map(commentaires_index)
nb_texte = df_comm["texte"].notna().sum()
print(f"  {nb_texte}/{len(df_comm)} commentaires avec texte retrouvé")

# ─── Tweets ───────────────────────────────────────────────────────────────────

print("Chargement des tweets...")
with open(TWEETS_JSON, encoding="utf-8") as f:
    tweets_raw = json.load(f)

tweets_index = {
    tw["url"]: tw.get("texte", "")
    for tw in tweets_raw
    if tw.get("url")
}
print(f"  {len(tweets_index)} tweets dans le corpus")

df_tw = df_classif[df_classif["type_doc"] == "tweet"].copy()
df_tw["texte"] = df_tw["url"].map(tweets_index)
nb_texte_tw = df_tw["texte"].notna().sum()
print(f"  {nb_texte_tw}/{len(df_tw)} tweets avec texte retrouvé")

# ─── Fusion ───────────────────────────────────────────────────────────────────

print("Fusion...")
cols_sortie = ["texte", "type_doc", "type_source", "date", "sitename",
               "categorie_dominante", "score_total", "cluster"] + SCORE_COLS + ["url"]

df_final = pd.concat([df_comm, df_tw], ignore_index=True)

# Garder seulement les lignes avec texte
df_final = df_final.dropna(subset=["texte"])
df_final = df_final[df_final["texte"].str.strip() != ""]

# Colonnes disponibles seulement
cols_existantes = [c for c in cols_sortie if c in df_final.columns]
df_final = df_final[cols_existantes].reset_index(drop=True)

# ─── Export CSV ───────────────────────────────────────────────────────────────

df_final.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nCSV exporté : {OUTPUT_CSV}")

# ─── Export JSON ──────────────────────────────────────────────────────────────

records = df_final.to_dict(orient="records")
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"JSON exporté : {OUTPUT_JSON}")

# ─── Résumé ───────────────────────────────────────────────────────────────────

print("\n" + "=" * 55)
print(f"  Total documents avec texte : {len(df_final)}")
print(f"  Dont commentaires          : {(df_final['type_doc']=='commentaire').sum()}")
print(f"  Dont tweets                : {(df_final['type_doc']=='tweet').sum()}")
print()
print("  Répartition par catégorie dominante :")
for cat, n in df_final["categorie_dominante"].value_counts().items():
    print(f"    {cat:<30} {n:>5}")
print("=" * 55)
