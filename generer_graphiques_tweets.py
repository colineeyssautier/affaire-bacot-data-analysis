"""
generer_graphiques_tweets.py — Analyse spécifique des tweets (affaire Valérie Bacot)
========================================================================================
Produit data/graphiques_tweets.json avec 7 graphiques :
  T1 à T5 : analyse des tweets seuls
  C1 à C2 : comparaison tweets vs médias

Prérequis : les tweets doivent être classifiés dans le CSV principal avec
type_source == 'twitter_x' (colonne type_source de resultats_classification.csv).

Usage :
    python generer_graphiques_tweets.py

Produit : data/graphiques_tweets.json
"""

import sys
import json
import pandas as pd
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Chemins ──────────────────────────────────────────────────────────────────

CSV_RESULTATS    = Path("analyse_bacot/resultats_classification.csv")
OUTPUT           = Path("data/graphiques_tweets.json")
SEUIL_MIN_TWEETS = 50

# ─── Constantes narratifs ─────────────────────────────────────────────────────

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

POLE_SOUTIEN  = ['soutien_victime', 'emprise_psychologique', 'discours_feministe', 'legitime_defense']
POLE_CRITIQUE = ['remise_en_question', 'jugement_moral', 'sensationnalisme', 'silence_collectif']

PERIODES_DEF = [
    {'cle': 'avant_proces',         'label': 'Avant le procès',       'debut': None,         'fin': '2021-06-21'},
    {'cle': 'pendant_proces',        'label': 'Pendant le procès',     'debut': '2021-06-21', 'fin': '2021-06-26'},
    {'cle': 'post_verdict_immediat', 'label': 'Post-verdict immédiat', 'debut': '2021-06-26', 'fin': '2021-09-01'},
    {'cle': 'livre_senat',           'label': 'Livre & Sénat',         'debut': '2021-09-01', 'fin': '2022-01-01'},
    {'cle': 'long_terme',            'label': 'Long terme',            'debut': '2022-01-01', 'fin': None},
]


# ─── Utilitaires ──────────────────────────────────────────────────────────────

def _to_datetime(s) -> pd.Timestamp:
    """Parse YYYY-MM-DD ou YYYY-MM en Timestamp."""
    s = str(s).strip()
    if len(s) == 7:
        s += '-01'
    try:
        return pd.to_datetime(s)
    except Exception:
        return pd.NaT


def _assigner_periode(dt) -> str | None:
    """Retourne la clé de période pour un Timestamp."""
    if pd.isna(dt):
        return None
    if dt < pd.Timestamp('2021-06-21'):
        return 'avant_proces'
    if dt < pd.Timestamp('2021-06-26'):
        return 'pendant_proces'
    if dt < pd.Timestamp('2021-09-01'):
        return 'post_verdict_immediat'
    if dt < pd.Timestamp('2022-01-01'):
        return 'livre_senat'
    return 'long_terme'


# ─── Chargement ───────────────────────────────────────────────────────────────

def charger_csv() -> pd.DataFrame:
    if not CSV_RESULTATS.exists():
        raise FileNotFoundError(f"CSV introuvable : {CSV_RESULTATS}")
    df = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig')
    df['_dt'] = df['date'].apply(_to_datetime)
    print(f"CSV chargé : {len(df)} documents")
    return df


# ─── T1 : Évolution pendant le procès (jour par jour) ────────────────────────

def graphique_t1_proces(df_tweets: pd.DataFrame) -> dict:
    """Courbes jour par jour du 21 au 30 juin 2021."""
    print("  T1 : évolution pendant le procès...")

    debut = pd.Timestamp('2021-06-21')
    fin   = pd.Timestamp('2021-06-30')
    df_p  = df_tweets[(df_tweets['_dt'] >= debut) & (df_tweets['_dt'] <= fin)].copy()

    jours    = pd.date_range(debut, fin, freq='D')
    periodes = [j.strftime('%Y-%m-%d') for j in jours]

    series = []
    for cat in CATEGORIES:
        valeurs = [
            int(((df_p['_dt'].dt.date == j.date()) & (df_p['categorie_dominante'] == cat)).sum())
            for j in jours
        ]
        if sum(valeurs) > 0:
            series.append({
                "categorie": cat,
                "label":     LABELS_FR[cat],
                "couleur":   COULEURS_NARRATIFS[cat],
                "valeurs":   valeurs,
            })

    series.sort(key=lambda s: sum(s['valeurs']), reverse=True)

    return {
        "titre":             "Évolution jour par jour pendant le procès",
        "sous_titre":        "Nombre de tweets par narratif dominant, du 21 au 30 juin 2021",
        "type":              "courbes_temporelles",
        "periodes":          periodes,
        "series":            series,
        "moments_cles": [
            {"date": "2021-06-21", "label": "J1 – Audience", "desc": "Première audience, début du procès"},
            {"date": "2021-06-22", "label": "J2",            "desc": "Deuxième journée d'audience"},
            {"date": "2021-06-23", "label": "J3",            "desc": "Troisième journée d'audience"},
            {"date": "2021-06-25", "label": "Verdict",       "desc": "Verdict : 4 ans de prison avec sursis"},
        ],
        "n_tweets_periode": len(df_p),
    }


# ─── T2 : Évolution long terme post-verdict ───────────────────────────────────

def graphique_t2_long_terme(df_tweets: pd.DataFrame) -> dict:
    """Semaines pour 2021, mois ensuite — après le 26 juin 2021."""
    print("  T2 : évolution long terme post-verdict...")

    df_lt = df_tweets[df_tweets['_dt'] >= pd.Timestamp('2021-06-26')].copy()

    def _granularite(dt) -> str | None:
        if pd.isna(dt):
            return None
        if dt.year == 2021:
            # Début de la semaine ISO (lundi)
            lundi = dt - pd.Timedelta(days=dt.weekday())
            return lundi.strftime('%Y-%m-%d')
        return dt.strftime('%Y-%m')

    df_lt['_periode'] = df_lt['_dt'].apply(_granularite)
    df_lt = df_lt[df_lt['_periode'].notna()]
    periodes = sorted(df_lt['_periode'].unique().tolist())

    series = []
    for cat in CATEGORIES:
        valeurs = [
            int(((df_lt['_periode'] == p) & (df_lt['categorie_dominante'] == cat)).sum())
            for p in periodes
        ]
        if sum(valeurs) > 0:
            series.append({
                "categorie": cat,
                "label":     LABELS_FR[cat],
                "couleur":   COULEURS_NARRATIFS[cat],
                "valeurs":   valeurs,
            })

    series.sort(key=lambda s: sum(s['valeurs']), reverse=True)

    return {
        "titre":      "Évolution long terme post-verdict",
        "sous_titre": "Semaines (2021) puis mois — tweets après le 26 juin 2021",
        "type":       "courbes_temporelles",
        "periodes":   periodes,
        "series":     series,
        "moments_cles": [
            {"date": "2021-09-01", "label": "Livre",  "desc": "Publication de 'Tout le monde savait'"},
            {"date": "2021-11-01", "label": "Sénat",  "desc": "Déposition de Valérie Bacot au Sénat"},
            {"date": "2022-06-25", "label": "1 an",   "desc": "1er anniversaire du verdict"},
            {"date": "2023-06-25", "label": "2 ans",  "desc": "2e anniversaire du verdict"},
            {"date": "2024-06-25", "label": "3 ans",  "desc": "3e anniversaire du verdict"},
            {"date": "2025-06-25", "label": "4 ans",  "desc": "4e anniversaire du verdict"},
        ],
        "note_granularite": "Semaines (format YYYY-MM-DD lundi) pour 2021, mois (format YYYY-MM) pour 2022+",
        "n_tweets_total": len(df_lt),
    }


# ─── T3 : Comparaison par périodes ────────────────────────────────────────────

def graphique_t3_periodes(df_tweets: pd.DataFrame) -> dict:
    """Distribution des narratifs dominants par période de l'affaire."""
    print("  T3 : comparaison par périodes...")

    df = df_tweets[df_tweets['_dt'].notna()].copy()
    df['_periode'] = df['_dt'].apply(_assigner_periode)

    periodes_out = []
    for p in PERIODES_DEF:
        sous    = df[df['_periode'] == p['cle']]
        n_total = len(sous)
        distribution = []
        for cat in CATEGORIES:
            n   = int((sous['categorie_dominante'] == cat).sum())
            pct = round(n / n_total * 100, 1) if n_total > 0 else 0.0
            distribution.append({
                "categorie": cat,
                "label":     LABELS_FR[cat],
                "couleur":   COULEURS_NARRATIFS[cat],
                "n":         n,
                "pct":       pct,
            })
        periodes_out.append({
            "cle":          p['cle'],
            "label":        p['label'],
            "n_tweets":     n_total,
            "distribution": distribution,
        })

    return {
        "titre":      "Répartition des narratifs par période",
        "sous_titre": "Distribution (%) des narratifs dominants selon la période de l'affaire",
        "type":       "barres_groupees_periodes",
        "categories": CATEGORIES,
        "labels":     LABELS_FR,
        "periodes":   periodes_out,
    }


# ─── T4 : Carte des narratifs (tweets seuls) ──────────────────────────────────

def graphique_t4_carte(df_tweets: pd.DataFrame) -> dict:
    """Bulles sur deux axes sémantiques — tweets uniquement, avec période dominante."""
    print("  T4 : carte des narratifs tweets...")

    total = len(df_tweets)
    df_p  = df_tweets[df_tweets['_dt'].notna()].copy()
    df_p['_periode'] = df_p['_dt'].apply(_assigner_periode)
    labels_periodes  = {p['cle']: p['label'] for p in PERIODES_DEF}

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
        pos         = POSITIONS[cat]
        n           = int((df_tweets['categorie_dominante'] == cat).sum())
        pct         = round(n / total * 100, 1) if total > 0 else 0.0
        col         = f"score_{cat}"
        score_moyen = round(float(df_tweets[col].mean()), 3) if col in df_tweets.columns else 0.0

        # Période où ce narratif concentre le plus de tweets dominants
        sous = df_p[df_p['categorie_dominante'] == cat]
        periode_dominante = None
        if len(sous) > 0 and sous['_periode'].notna().any():
            cle_dominante    = sous['_periode'].value_counts().idxmax()
            periode_dominante = labels_periodes.get(cle_dominante, cle_dominante)

        bulles.append({
            "categorie":         cat,
            "label":             LABELS_FR[cat],
            "couleur":           COULEURS_NARRATIFS[cat],
            "x":                 pos['x'],
            "y":                 pos['y'],
            "n":                 n,
            "pct":               pct,
            "score_moyen":       score_moyen,
            "periode_dominante": periode_dominante,
        })

    bulles.sort(key=lambda b: b['n'], reverse=True)

    return {
        "titre":      "Carte des narratifs — tweets uniquement",
        "sous_titre": "Taille proportionnelle au nombre de tweets · couleur = narratif · info-bulle = période la plus active",
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
        "bulles":       bulles,
        "total_tweets": total,
    }


# ─── T5 : Polarité des réactions ──────────────────────────────────────────────

def graphique_t5_polarite(df_tweets: pd.DataFrame) -> dict:
    """Ratio soutien / (soutien + critique) en % par mois."""
    print("  T5 : polarité temporelle...")

    df = df_tweets[df_tweets['_dt'].notna()].copy()
    df['_mois'] = df['_dt'].dt.to_period('M').astype(str)
    mois_list = sorted(df['_mois'].unique().tolist())

    valeurs = []
    for m in mois_list:
        sous       = df[df['_mois'] == m]
        n_soutien  = int(sous['categorie_dominante'].isin(POLE_SOUTIEN).sum())
        n_critique = int(sous['categorie_dominante'].isin(POLE_CRITIQUE).sum())
        n_total    = n_soutien + n_critique
        ratio      = round(n_soutien / n_total * 100, 1) if n_total > 0 else None
        valeurs.append({
            "periode":          m,
            "n_soutien":        n_soutien,
            "n_critique":       n_critique,
            "n_total":          n_total,
            "ratio_soutien_pct": ratio,
        })

    return {
        "titre":      "Polarité des réactions dans le temps",
        "sous_titre": "% de tweets dans le pôle soutien vs distance/critique — ligne de base à 50%",
        "type":       "courbe_polarite",
        "baseline":   50,
        "pole_soutien":  POLE_SOUTIEN,
        "pole_critique": POLE_CRITIQUE,
        "labels_poles": {
            "soutien":  "Soutien (victime, féministe, défense, emprise)",
            "critique": "Distance / critique (remise en question, jugement, sensationnalisme, silence)",
        },
        "periodes": mois_list,
        "valeurs":  valeurs,
    }


# ─── C1 : Divergence tweets vs médias ────────────────────────────────────────

def graphique_c1_divergence(df_tweets: pd.DataFrame, df_medias: pd.DataFrame) -> dict:
    """% de documents par narratif dominant : tweets vs médias, trié par écart."""
    print("  C1 : divergence tweets vs médias...")

    n_tw = len(df_tweets)
    n_me = len(df_medias)

    donnees = []
    for cat in CATEGORIES:
        n_tw_cat = int((df_tweets['categorie_dominante'] == cat).sum())
        n_me_cat = int((df_medias['categorie_dominante'] == cat).sum())
        pct_tw   = round(n_tw_cat / n_tw * 100, 1) if n_tw > 0 else 0.0
        pct_me   = round(n_me_cat / n_me * 100, 1) if n_me > 0 else 0.0
        donnees.append({
            "categorie":  cat,
            "label":      LABELS_FR[cat],
            "couleur":    COULEURS_NARRATIFS[cat],
            "pct_tweets": pct_tw,
            "pct_medias": pct_me,
            "ecart_pts":  round(pct_tw - pct_me, 1),
            "n_tweets":   n_tw_cat,
            "n_medias":   n_me_cat,
        })

    # Narratifs les plus divergents en premier
    donnees.sort(key=lambda r: abs(r['ecart_pts']), reverse=True)

    return {
        "titre":      "Divergence des narratifs : tweets vs médias",
        "sous_titre": "% de documents avec ce narratif dominant — écart trié par ampleur absolue",
        "type":       "dumbbell",
        "n_tweets":   n_tw,
        "n_medias":   n_me,
        "donnees":    donnees,
    }


# ─── C2 : Évolution comparée ──────────────────────────────────────────────────

def graphique_c2_evolution_comparee(df_tweets: pd.DataFrame, df_medias: pd.DataFrame) -> dict:
    """Narratif dominant par mois dans les tweets vs dans les médias."""
    print("  C2 : évolution comparée tweets vs médias...")

    df_tw = df_tweets[df_tweets['_dt'].notna()].copy()
    df_me = df_medias[df_medias['_dt'].notna()].copy()

    df_tw['_mois'] = df_tw['_dt'].dt.to_period('M').astype(str)
    df_me['_mois'] = df_me['_dt'].dt.to_period('M').astype(str)

    # Union des mois présents, à partir de 2021-06
    seuil = pd.Period('2021-06', 'M')
    tous_mois = sorted(
        {m for m in set(df_tw['_mois'].unique()) | set(df_me['_mois'].unique())
         if pd.Period(m, 'M') >= seuil}
    )

    donnees = []
    for m in tous_mois:
        tw_m = df_tw[df_tw['_mois'] == m]
        me_m = df_me[df_me['_mois'] == m]

        def _narratif_dominant(sous):
            if len(sous) == 0:
                return None, 0
            vc = sous['categorie_dominante'].value_counts()
            return (vc.idxmax(), int(vc.iloc[0])) if len(vc) > 0 else (None, 0)

        dom_tw, n_dom_tw = _narratif_dominant(tw_m)
        dom_me, n_dom_me = _narratif_dominant(me_m)
        diverge = dom_tw is not None and dom_me is not None and dom_tw != dom_me

        donnees.append({
            "periode":            m,
            "narratif_tweets":    dom_tw,
            "label_tweets":       LABELS_FR.get(dom_tw, '') if dom_tw else '',
            "couleur_tweets":     COULEURS_NARRATIFS.get(dom_tw, '#999') if dom_tw else '#999',
            "n_tweets":           len(tw_m),
            "n_tweets_dominant":  n_dom_tw,
            "narratif_medias":    dom_me,
            "label_medias":       LABELS_FR.get(dom_me, '') if dom_me else '',
            "couleur_medias":     COULEURS_NARRATIFS.get(dom_me, '#999') if dom_me else '#999',
            "n_medias":           len(me_m),
            "n_medias_dominant":  n_dom_me,
            "diverge":            diverge,
        })

    return {
        "titre":              "Évolution comparée : narratif dominant par mois",
        "sous_titre":         "Tweets vs médias — mois divergents = narratifs dominants différents",
        "type":               "evolution_comparee",
        "periodes":           tous_mois,
        "donnees":            donnees,
        "n_mois_divergents":  sum(1 for d in donnees if d['diverge']),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    Path("data").mkdir(exist_ok=True)

    print("Chargement du CSV...")
    df = charger_csv()

    df_tweets = df[df['type_source'] == 'twitter_x'].copy()
    df_medias  = df[df['type_source'] != 'twitter_x'].copy()
    n_tweets   = len(df_tweets)
    n_medias   = len(df_medias)

    print(f"\nCorpus tweets  : {n_tweets} documents")
    print(f"Corpus médias  : {n_medias} documents")

    if n_tweets < SEUIL_MIN_TWEETS:
        print(f"\n[ARRÊT] Seulement {n_tweets} tweets classifiés (seuil minimum : {SEUIL_MIN_TWEETS}).")
        print("  → Classifiez les tweets avec Classifier_bacot.py avant de relancer ce script.")
        print("  → Fichier source attendu : corpus_bacot/tweets_bacot.csv")
        print("  → Les tweets doivent apparaître dans le CSV avec type_source == 'twitter_x'.")
        return

    print("\nGénération des données graphiques tweets...")
    output = {}

    for cle, fn, args in [
        ("t1_proces_jour_par_jour",   graphique_t1_proces,           (df_tweets,)),
        ("t2_evolution_post_verdict", graphique_t2_long_terme,        (df_tweets,)),
        ("t3_periodes_comparaison",   graphique_t3_periodes,          (df_tweets,)),
        ("t4_carte_narratifs_tweets", graphique_t4_carte,             (df_tweets,)),
        ("t5_polarite_temporelle",    graphique_t5_polarite,          (df_tweets,)),
        ("c1_divergence_tweets_medias", graphique_c1_divergence,      (df_tweets, df_medias)),
        ("c2_evolution_comparee",     graphique_c2_evolution_comparee, (df_tweets, df_medias)),
    ]:
        try:
            output[cle] = fn(*args)
            print("    ✓")
        except Exception as e:
            print(f"    ✗ Erreur {cle} : {e}")

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    taille     = OUTPUT.stat().st_size / 1024
    dt_min     = df_tweets['_dt'].min()
    dt_max     = df_tweets['_dt'].max()
    periode_str = (
        f"{dt_min.date()} → {dt_max.date()}"
        if pd.notna(dt_min) and pd.notna(dt_max) else "N/A"
    )

    print("""
╔══════════════════════════════════════════════════════╗
║        GRAPHIQUES_TWEETS.JSON GÉNÉRÉ ✓               ║
╠══════════════════════════════════════════════════════╣
║  T1 : évolution pendant le procès (jour/jour)        ║
║  T2 : évolution long terme post-verdict              ║
║  T3 : comparaison avant/pendant/après                ║
║  T4 : carte des narratifs (tweets seuls)             ║
║  T5 : polarité des réactions                         ║
║  C1 : divergence tweets vs médias                    ║
║  C2 : évolution comparée                             ║
╚══════════════════════════════════════════════════════╝""")
    print(f"  Tweets analysés  : {n_tweets}")
    print(f"  Documents médias : {n_medias}")
    print(f"  Période tweets   : {periode_str}")
    print(f"  Taille fichier   : {taille:.1f} Ko")
    print("→ data/graphiques_tweets.json")


if __name__ == "__main__":
    run()
