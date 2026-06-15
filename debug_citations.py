"""
Script de debug — vérifie pourquoi les citations sont vides
"""
import json
import pandas as pd
from pathlib import Path

# Chargement
with open('corpus_bacot/corpus_bacot.json', encoding='utf-8') as f:
    corpus = json.load(f)

df = pd.read_csv('analyse_bacot/resultats_classification.csv', encoding='utf-8-sig')
corpus_index = {d.get('url', ''): d for d in corpus}

print(f"Documents corpus  : {len(corpus)}")
print(f"Documents CSV     : {len(df)}")
print()

# Pour chaque catégorie, vérifie les 3 meilleurs documents
categories = [
    'soutien_victime', 'remise_en_question', 'legitime_defense',
    'discours_feministe', 'emprise_psychologique', 'silence_collectif',
    'sensationnalisme', 'jugement_moral'
]

for cat in categories:
    col = f'score_{cat}'
    if col not in df.columns:
        print(f"{cat} : colonne manquante")
        continue

    subset = df[df['categorie_dominante'] == cat].sort_values(col, ascending=False).head(3)
    print(f"=== {cat} ({len(subset)} docs) ===")

    for _, row in subset.iterrows():
        url = row['url']
        doc = corpus_index.get(url, {})
        texte = doc.get('text', '')
        nb_mots = len(texte.split()) if texte else 0
        print(f"  Score={row[col]:.0f} | Mots={nb_mots} | Extrait: {texte[:60]!r}")

    print()
