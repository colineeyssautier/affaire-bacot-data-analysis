"""
generer_graphiques.py — Données pour les 5 graphiques interactifs
==================================================================
Produit data/graphiques.json avec toutes les données prétraitées
pour les 5 graphiques du frontend.

Graphiques :
  1. Distribution des narratifs (barres empilées articles/commentaires)
  2. Narratifs par source (barres groupées scores moyens)
  3. Heatmap narratifs × sources (matrice de scores)
  4. Clusters PCA (nuage de points 2D avec coordonnées calculées)
  5. Évolution temporelle (courbes par narratif dans le temps)

Usage :
    pip install scikit-learn pandas numpy
    python generer_graphiques.py

Produit : data/graphiques.json
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Chemins ──────────────────────────────────────────────────────────────────

CSV_RESULTATS = Path("analyse_bacot/resultats_classification.csv")
OUTPUT        = Path("data/graphiques.json")

CATEGORIES = [
    'soutien_victime', 'remise_en_question', 'legitime_defense',
    'discours_feministe', 'emprise_psychologique', 'silence_collectif',
    'sensationnalisme', 'jugement_moral',
]

LABELS_FR = {
    'soutien_victime':        'Soutien à la victime',
    'remise_en_question':     'Remise en question',
    'legitime_defense':       'Légitime défense',
    'discours_feministe':     'Discours féministe',
    'emprise_psychologique':  'Emprise psychologique',
    'silence_collectif':      'Silence collectif',
    'sensationnalisme':       'Sensationnalisme',
    'jugement_moral':         'Jugement moral',
}

COULEURS_NARRATIFS = {
    'soutien_victime':        '#2c4a6e',
    'remise_en_question':     '#8b3a2a',
    'legitime_defense':       '#4a6741',
    'discours_feministe':     '#6c3483',
    'emprise_psychologique':  '#b03060',
    'silence_collectif':      '#7a5c1e',
    'sensationnalisme':       '#c0392b',
    'jugement_moral':         '#1a6b8a',
}

COULEURS_CLUSTERS = [
    '#2c4a6e', '#4a6741', '#8b3a2a',
    '#6c3483', '#7a5c1e', '#1a6b8a',
]


# ─── Chargement ───────────────────────────────────────────────────────────────

MEDIA_CHAINES = {
    'BFMTV', 'RMC', 'Le Parisien', 'Le Point', '20 Minutes France',
    'TF1+', 'Europe 1', 'LeHuffPost', 'Public Sénat', 'M6 MediaBank',
}

LABELS_TYPE_SOURCE = {
    'youtube_commentaire': 'Commentaires YouTube',
    'media_youtube':       'Médias (YouTube)',
    'youtube_createur':    'Créateurs YouTube',
    'presse_web':          'Presse web',
    'autre':               'Autre',
}


def _infer_type_source(row) -> str:
    if row.get('type_doc') == 'commentaire':
        return 'youtube_commentaire'
    sn = str(row.get('sitename') or '')
    if 'YouTube' in sn:
        chaine = sn.replace('YouTube — ', '').replace('YouTube - ', '').strip()
        if any(m in chaine for m in MEDIA_CHAINES):
            return 'media_youtube'
        return 'youtube_createur'
    return 'presse_web'


def charger_csv() -> pd.DataFrame:
    if not CSV_RESULTATS.exists():
        raise FileNotFoundError(f"CSV introuvable : {CSV_RESULTATS}")
    df = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig')
    print(f"CSV chargé : {len(df)} documents")
    if df['type_source'].nunique() <= 1:
        df['type_source'] = df.apply(_infer_type_source, axis=1)
        print(f"  type_source inféré : {df['type_source'].value_counts().to_dict()}")
    return df


# ─── Graphique 1 : Distribution des narratifs ─────────────────────────────────

def graphique_distribution(df: pd.DataFrame) -> dict:
    """Barres empilées articles/commentaires par catégorie de narratif."""
    print("  Graphique 1 : distribution narratifs...")

    result = []
    for cat in CATEGORIES:
        subset = df[df['categorie_dominante'] == cat]
        n_articles    = int((subset['type_doc'] == 'article').sum())
        n_commentaires = int((subset['type_doc'] == 'commentaire').sum())
        total = n_articles + n_commentaires
        result.append({
            "categorie":      cat,
            "label":          LABELS_FR[cat],
            "couleur":        COULEURS_NARRATIFS[cat],
            "articles":       n_articles,
            "commentaires":   n_commentaires,
            "total":          total,
            "pct_articles":   round(n_articles / total * 100, 1) if total > 0 else 0,
            "pct_commentaires": round(n_commentaires / total * 100, 1) if total > 0 else 0,
        })

    # Trie par total décroissant
    result.sort(key=lambda x: x['total'], reverse=True)

    return {
        "titre":       "Distribution des narratifs dominants",
        "sous_titre":  "Nombre de documents par catégorie, répartis entre articles et commentaires",
        "type":        "barres_empilees",
        "donnees":     result,
        "total_corpus": len(df),
    }


# ─── Graphique 2 : Narratifs par source ───────────────────────────────────────

def graphique_par_source(df: pd.DataFrame) -> dict:
    """Scores moyens des narratifs par type de source."""
    print("  Graphique 2 : narratifs par source...")

    sources = df['type_source'].dropna().unique().tolist()
    sources = [s for s in sources if s and s != 'youtube_video']
    sources = sorted(sources)

    series = []
    for cat in CATEGORIES:
        col = f"score_{cat}"
        if col not in df.columns:
            continue
        valeurs = []
        for src in sources:
            subset = df[df['type_source'] == src]
            moy = float(subset[col].mean()) if len(subset) > 0 else 0
            valeurs.append(round(moy, 2))

        series.append({
            "categorie": cat,
            "label":     LABELS_FR[cat],
            "couleur":   COULEURS_NARRATIFS[cat],
            "valeurs":   valeurs,
        })

    return {
        "titre":      "Score moyen des narratifs par type de source",
        "sous_titre": "Score moyen des termes caractéristiques par catégorie et par source",
        "type":       "barres_groupees",
        "sources":    sources,
        "series":     series,
    }


# ─── Graphique 3 : Heatmap ────────────────────────────────────────────────────

def graphique_heatmap(df: pd.DataFrame) -> dict:
    """Matrice de scores moyens narratifs × sources."""
    print("  Graphique 3 : heatmap...")

    sources = df['type_source'].dropna().unique().tolist()
    sources = [s for s in sources if s and s != 'youtube_video']
    sources = sorted(sources)

    matrice = []
    for src in sources:
        subset = df[df['type_source'] == src]
        ligne = {"source": src, "label": LABELS_TYPE_SOURCE.get(src, src), "n": len(subset), "scores": {}}
        for cat in CATEGORIES:
            col = f"score_{cat}"
            if col in df.columns:
                moy = float(subset[col].mean()) if len(subset) > 0 else 0
                ligne["scores"][cat] = round(moy, 2)
        matrice.append(ligne)

    # Calcule le max global pour la normalisation des couleurs
    toutes_valeurs = [
        v for ligne in matrice
        for v in ligne["scores"].values()
        if v > 0
    ]
    max_val = max(toutes_valeurs) if toutes_valeurs else 1

    return {
        "titre":      "Intensité des narratifs par type de source",
        "sous_titre": "Score moyen — plus la valeur est élevée, plus le narratif est présent",
        "type":       "heatmap",
        "categories": CATEGORIES,
        "labels":     LABELS_FR,
        "sources":    sources,
        "matrice":    matrice,
        "max_val":    round(max_val, 2),
    }


# ─── Graphique 4 : Carte des narratifs ───────────────────────────────────────

def graphique_carte_narratifs(df: pd.DataFrame) -> dict:
    """Bulles positionnées sur deux axes sémantiques — positions hardcodées."""
    print("  Graphique 4 : carte des narratifs...")

    total_corpus = len(df)

    # TODO : ajuster les coordonnées x/y selon votre lecture sémantique
    # x ∈ [-1, 1] : -1 = centré sur la victime individuelle, +1 = centré sur la société/le système
    # y ∈ [-1, 1] : -1 = registre juridique/politique,      +1 = registre émotionnel
    POSITIONS = {
        'soutien_victime':       {'x': -0.7, 'y':  0.6},
        'emprise_psychologique': {'x': -0.5, 'y':  0.2},
        'legitime_defense':      {'x': -0.3, 'y': -0.6},
        'discours_feministe':    {'x':  0.3, 'y':  0.4},
        'silence_collectif':     {'x':  0.6, 'y':  0.1},
        'jugement_moral':        {'x':  0.2, 'y':  0.5},
        'remise_en_question':    {'x':  0.1, 'y': -0.3},
        'sensationnalisme':      {'x': -0.1, 'y':  0.7},
    }

    bulles = []
    for cat in CATEGORIES:
        pos = POSITIONS[cat]
        n = int((df['categorie_dominante'] == cat).sum())
        pct = round(n / total_corpus * 100, 1) if total_corpus > 0 else 0

        col = f"score_{cat}"
        score_moyen = round(float(df[col].mean()), 3) if col in df.columns else 0.0

        bulles.append({
            "categorie":   cat,
            "label":       LABELS_FR[cat],
            "couleur":     COULEURS_NARRATIFS[cat],
            "x":           pos['x'],
            "y":           pos['y'],
            "n":           n,
            "pct":         pct,
            "score_moyen": score_moyen,
        })

    # Trie par n décroissant pour le rendu (bulles plus grandes en premier)
    bulles.sort(key=lambda b: b['n'], reverse=True)

    return {
        "titre":      "Carte des narratifs",
        "sous_titre": "Chaque bulle représente un narratif — taille proportionnelle au nombre de documents",
        "type":       "carte_narratifs",
        "axes": {
            "x": {
                "label_negatif": "Centré sur la victime individuelle",
                "label_positif": "Centré sur la société / le système",
            },
            "y": {
                "label_negatif": "Registre juridique / politique",
                "label_positif": "Registre émotionnel",
            },
        },
        "bulles":        bulles,
        "total_corpus":  total_corpus,
    }


# ─── Graphique 4 (DEPRECATED) : PCA Clusters ─────────────────────────────────
# DEPRECATED - remplacé par graphique_carte_narratifs

# def graphique_pca(df: pd.DataFrame) -> dict:
#     """Nuage de points 2D via PCA sur les scores narratifs."""
#     print("  Graphique 4 : PCA clusters...")
#
#     # Matrice des scores narratifs
#     score_cols = [f"score_{cat}" for cat in CATEGORIES if f"score_{cat}" in df.columns]
#     X = df[score_cols].fillna(0).values
#
#     # Normalisation
#     scaler = StandardScaler()
#     X_scaled = scaler.fit_transform(X)
#
#     # PCA 2D
#     pca = PCA(n_components=2, random_state=42)
#     coords = pca.fit_transform(X_scaled)
#
#     variance_expliquee = [
#         round(float(v) * 100, 1)
#         for v in pca.explained_variance_ratio_
#     ]
#
#     # Construit la liste de points
#     points = []
#     for i, (_, row) in enumerate(df.iterrows()):
#         cluster = int(row.get('cluster', 0)) if pd.notna(row.get('cluster')) else 0
#         cat     = str(row.get('categorie_dominante', 'non_classe'))
#         points.append({
#             "x":        round(float(coords[i, 0]), 3),
#             "y":        round(float(coords[i, 1]), 3),
#             "cluster":  cluster,
#             "categorie": cat,
#             "type_doc": str(row.get('type_doc', '')),
#             "titre":    str(row.get('titre', ''))[:60],
#             "source":   str(row.get('sitename', '') or row.get('type_source', '')),
#             "couleur":  COULEURS_CLUSTERS[cluster % len(COULEURS_CLUSTERS)],
#         })
#
#     # Centres des clusters (centroïdes)
#     centroides = []
#     for c in range(6):
#         pts_cluster = [p for p in points if p['cluster'] == c]
#         if pts_cluster:
#             cx = round(sum(p['x'] for p in pts_cluster) / len(pts_cluster), 3)
#             cy = round(sum(p['y'] for p in pts_cluster) / len(pts_cluster), 3)
#             centroides.append({
#                 "cluster": c,
#                 "x": cx,
#                 "y": cy,
#                 "n": len(pts_cluster),
#                 "couleur": COULEURS_CLUSTERS[c % len(COULEURS_CLUSTERS)],
#             })
#
#     print(f"    Variance expliquée : PC1={variance_expliquee[0]}%, PC2={variance_expliquee[1]}%")
#
#     return {
#         "titre":      "Clustering K-Means — Représentation PCA 2D",
#         "sous_titre": f"Chaque point = 1 document · PC1 explique {variance_expliquee[0]}% de la variance · PC2 {variance_expliquee[1]}%",
#         "type":       "scatter_pca",
#         "variance_pc1": variance_expliquee[0],
#         "variance_pc2": variance_expliquee[1],
#         "points":     points,
#         "centroides": centroides,
#         "n_clusters": 6,
#         "couleurs_clusters": COULEURS_CLUSTERS,
#     }


# ─── Graphique 5 : Évolution temporelle ───────────────────────────────────────

def graphique_temporel(df: pd.DataFrame) -> dict:
    """Courbes d'évolution des narratifs par mois."""
    print("  Graphique 5 : évolution temporelle...")

    # Travaille uniquement sur les documents avec une date valide
    df_dates = df[
        df['date'].notna() &
        (df['date'] != '') &
        (df['date'].astype(str).str.len() >= 7)
    ].copy()

    df_dates['date_str'] = df_dates['date'].astype(str).str[:7]

    # Filtre les dates aberrantes (garde 2017-2024)
    df_dates = df_dates[
        df_dates['date_str'].between('2017-01', '2024-12')
    ]

    print(f"    Documents avec date valide : {len(df_dates)}/{len(df)}")

    if df_dates.empty:
        return {
            "titre":   "Évolution temporelle",
            "erreur":  "Pas assez de documents avec dates valides",
            "series":  [],
            "periodes": [],
        }

    # Liste des périodes (mois) présentes
    periodes = sorted(df_dates['date_str'].unique().tolist())

    # Moments clés de l'affaire
    moments_cles = [
        {"date": "2021-01", "label": "Pétition", "desc": "Lancement de la pétition (600k signatures)"},
        {"date": "2021-06", "label": "Procès",   "desc": "Procès aux Assises de Saône-et-Loire"},
        {"date": "2021-09", "label": "Livre",    "desc": "Publication de 'Tout le monde savait'"},
        {"date": "2021-11", "label": "Sénat",    "desc": "Déposition au Sénat"},
    ]

    # Série par narratif
    series = []
    for cat in CATEGORIES:
        valeurs = []
        for p in periodes:
            n = int(((df_dates['date_str'] == p) & (df_dates['categorie_dominante'] == cat)).sum())
            valeurs.append(n)

        # N'inclut la série que si elle a au moins quelques valeurs non nulles
        if sum(valeurs) > 0:
            series.append({
                "categorie": cat,
                "label":     LABELS_FR[cat],
                "couleur":   COULEURS_NARRATIFS[cat],
                "valeurs":   valeurs,
                "total":     sum(valeurs),
            })

    # Trie par total décroissant
    series.sort(key=lambda x: x['total'], reverse=True)

    return {
        "titre":         "Évolution temporelle des narratifs",
        "sous_titre":    "Nombre de documents par mois et par catégorie de narratif dominante",
        "type":          "courbes_temporelles",
        "periodes":      periodes,
        "series":        series,
        "moments_cles":  moments_cles,
        "n_docs_dates":  len(df_dates),
        "n_docs_total":  len(df),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    Path("data").mkdir(exist_ok=True)

    print("Chargement du CSV...")
    df = charger_csv()

    print("\nGénération des données graphiques...")
    output = {}

    try:
        output["g1_distribution"]  = graphique_distribution(df)
        print("    ✓")
    except Exception as e:
        print(f"    ✗ Erreur : {e}")

    try:
        output["g2_par_source"]    = graphique_par_source(df)
        print("    ✓")
    except Exception as e:
        print(f"    ✗ Erreur : {e}")

    try:
        output["g3_heatmap"]       = graphique_heatmap(df)
        print("    ✓")
    except Exception as e:
        print(f"    ✗ Erreur : {e}")

    try:
        output["g4_carte_narratifs"] = graphique_carte_narratifs(df)
        print("    ✓")
    except Exception as e:
        print(f"    ✗ Erreur : {e}")

    try:
        output["g5_temporel"]      = graphique_temporel(df)
        print("    ✓")
    except Exception as e:
        print(f"    ✗ Erreur : {e}")

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    taille = OUTPUT.stat().st_size / 1024
    print(f"""
╔══════════════════════════════════════════════════╗
║       GRAPHIQUES.JSON GÉNÉRÉ ✓                   ║
╠══════════════════════════════════════════════════╣
║  Graphique 1 : distribution narratifs            ║
║  Graphique 2 : narratifs par source              ║
║  Graphique 3 : heatmap                           ║
║  Graphique 4 : carte des narratifs               ║
║  Graphique 5 : évolution temporelle              ║
╠══════════════════════════════════════════════════╣
║  Taille fichier : {taille:>6.1f} Ko                     ║
╚══════════════════════════════════════════════════╝
→ data/graphiques.json
    """)


if __name__ == "__main__":
    run()