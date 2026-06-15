"""
generer_citations_json.py — Génère data/citations.json
=======================================================
Produit un fichier JSON avec deux types de citations :
  1. Extraits d'articles (presse, institutions) — profondeur analytique
  2. Commentaires YouTube — voix populaires

Usage :
    python generer_citations_json.py

Produit : data/citations.json
"""

import sys
import json
import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_PATHS = [
    Path("corpus_bacot/corpus_final.json"),
    Path("corpus_bacot/corpus_bacot.json"),
]
CSV_RESULTATS = Path("analyse_bacot/resultats_classification.csv")
OUTPUT        = Path("data/citations.json")

# ─── Config ───────────────────────────────────────────────────────────────────

N_ARTICLES_PAR_CAT    = 3   # citations d'articles par catégorie
N_COMMENTAIRES_PAR_CAT = 4  # commentaires YouTube par catégorie
LONGUEUR_EXTRAIT      = 420  # caractères max par extrait d'article
LONGUEUR_MIN_COMMENT  = 80   # longueur minimale d'un commentaire retenu

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

TERMES_PAR_CAT = {
    'soutien_victime':       ['courage', 'victime', 'survie', 'soutien', 'innocente', 'libre', 'méritait', 'avait raison', 'bravo', 'comprends', 'protéger', 'échappatoire'],
    'remise_en_question':    ['pourquoi', 'partir', 'quitter', 'appeler', 'police', 'quand même', 'prémédita', 'choix', 'aurait pu', 'devait', 'autre solution', 'responsable'],
    'legitime_defense':      ['légitime défense', 'défense différée', 'jacqueline sauvage', 'loi', 'réforme', 'juridique', 'droit', 'code pénal', 'différée', 'jurisprudence'],
    'discours_feministe':    ['féminicide', 'patriarcat', 'systémique', 'violences faites', 'féminisme', 'nous toutes', 'metoo', 'structurel', 'domination', 'genre', 'inégalité'],
    'emprise_psychologique': ['emprise', 'contrôle', 'manipulation', 'traumatisme', 'peur', 'terrorisée', 'prostituée', 'forcée', 'obligée', 'conditionnée', 'syndrome', 'dépendance'],
    'silence_collectif':     ['tout le monde savait', 'savaient', 'silence', 'complice', 'entourage', 'institution', 'signalement', 'voisins', 'école', 'médecin', 'rien fait'],
    'sensationnalisme':      ['choquant', 'horrible', 'incroyable', 'true crime', 'abonner', 'like', 'regarder', 'story', 'affaire', 'crime', 'chaîne', 'vidéo'],
    'jugement_moral':        ['mérite', 'méritait', 'coupable', 'punition', 'justice', 'condamner', 'pardon', 'moral', 'responsable', 'faute', 'sévère', 'clément', 'verdict'],
}


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def extraire_passage(texte: str, categorie: str, n_chars: int = LONGUEUR_EXTRAIT) -> str:
    """Extrait le passage le plus riche en termes de la catégorie."""
    if not texte or len(texte.strip()) < 30:
        return ""
    termes = TERMES_PAR_CAT.get(categorie, [])
    texte_lower = texte.lower()
    if len(texte) <= n_chars:
        return texte.strip()
    meilleur_pos, meilleur_score = 0, -1
    pas = max(20, n_chars // 12)
    for i in range(0, len(texte) - n_chars, pas):
        fenetre = texte_lower[i:i + n_chars]
        score = sum(fenetre.count(t) for t in termes)
        if score > meilleur_score:
            meilleur_score = score
            meilleur_pos = i
    extrait = texte[meilleur_pos:meilleur_pos + n_chars].strip()
    for punct in ['. ', '.\n', '? ', '! ']:
        idx = extrait.find(punct)
        if 0 < idx < 100:
            extrait = extrait[idx + len(punct):].strip()
            break
    prefix = "… " if meilleur_pos > 100 else ""
    suffix = " …" if meilleur_pos + n_chars < len(texte) - 100 else ""
    return prefix + extrait + suffix


def charger_corpus() -> dict:
    for path in CORPUS_PATHS:
        if path.exists():
            print(f"Corpus : {path}")
            with open(path, encoding='utf-8') as f:
                corpus = json.load(f)
            print(f"  → {len(corpus)} documents")
            return {doc.get('url', ''): doc for doc in corpus if doc.get('url')}
    print("⚠ Corpus introuvable")
    return {}


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    Path("data").mkdir(exist_ok=True)

    corpus_index = charger_corpus()
    if not corpus_index:
        return

    if not CSV_RESULTATS.exists():
        print(f"⚠ CSV introuvable : {CSV_RESULTATS}")
        return

    df = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig')
    print(f"CSV chargé : {len(df)} documents")

    output = {}

    for cat in CATEGORIES:
        print(f"\nCatégorie : {cat}")
        col = f"score_{cat}"
        if col not in df.columns:
            output[cat] = {"articles": [], "commentaires": []}
            continue

        subset = df[df['categorie_dominante'] == cat].sort_values(col, ascending=False)

        # ── Citations d'articles ──
        articles_cits = []
        for _, row in subset.iterrows():
            if len(articles_cits) >= N_ARTICLES_PAR_CAT:
                break
            if row.get('type_doc') == 'commentaire':
                continue
            url = row.get('url', '')
            doc = corpus_index.get(url, {})
            texte = doc.get('text', '').strip()
            if not texte or len(texte.split()) < 30:
                continue
            passage = extraire_passage(texte, cat)
            if not passage or len(passage) < 40:
                continue

            sitename = str(row.get('sitename', '') or doc.get('sitename', '') or '').strip()
            if not sitename or sitename == 'nan':
                sitename = str(row.get('type_source', '') or '').strip()

            articles_cits.append({
                "texte":   passage,
                "source":  sitename[:50],
                "date":    str(row.get('date', '') or '')[:10],
                "titre":   str(row.get('titre', '') or '')[:100],
                "score":   round(float(row.get(col, 0)), 1),
                "url":     url,
            })

        print(f"  Articles : {len(articles_cits)}")

        # ── Commentaires YouTube ──
        comments_cits = []

        # Prend les commentaires de cette catégorie d'abord
        cmt_subset = df[
            (df['categorie_dominante'] == cat) &
            (df['type_doc'] == 'commentaire')
        ].sort_values(col, ascending=False)

        # Si pas assez, élargit à tous les commentaires avec un score > 0
        if len(cmt_subset) < N_COMMENTAIRES_PAR_CAT:
            cmt_extra = df[
                (df['type_doc'] == 'commentaire') &
                (df[col] > 0) &
                (df['categorie_dominante'] != cat)
            ].sort_values(col, ascending=False)
            cmt_subset = pd.concat([cmt_subset, cmt_extra])

        for _, row in cmt_subset.iterrows():
            if len(comments_cits) >= N_COMMENTAIRES_PAR_CAT:
                break
            url = row.get('url', '')
            doc = corpus_index.get(url, {})
            texte = doc.get('text', '').strip()
            if not texte or len(texte) < LONGUEUR_MIN_COMMENT:
                continue

            # Tronque proprement à 300 caractères
            if len(texte) > 300:
                texte = texte[:300].rsplit(' ', 1)[0] + ' …'

            chaine = str(doc.get('chaine', '') or doc.get('sitename', '') or '').strip()
            if 'YouTube' in chaine:
                chaine = chaine.replace('YouTube — ', '')

            comments_cits.append({
                "texte":       texte,
                "chaine":      chaine[:50],
                "video_titre": str(doc.get('video_titre', '') or '')[:80],
                "date":        str(doc.get('date', '') or '')[:10],
                "score":       round(float(row.get(col, 0)), 1),
                "url":         url,
            })

        print(f"  Commentaires : {len(comments_cits)}")

        output[cat] = {
            "label":        LABELS_FR[cat],
            "articles":     articles_cits,
            "commentaires": comments_cits,
        }

    # Sauvegarde
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_art = sum(len(v['articles']) for v in output.values())
    total_cmt = sum(len(v['commentaires']) for v in output.values())

    print(f"""
╔══════════════════════════════════════════════════╗
║         CITATIONS.JSON GÉNÉRÉ ✓                  ║
╠══════════════════════════════════════════════════╣
║  Citations articles     : {total_art:>5}                ║
║  Citations commentaires : {total_cmt:>5}                ║
║  Catégories             :     8                  ║
╚══════════════════════════════════════════════════╝
→ data/citations.json
    """)


if __name__ == "__main__":
    run()
