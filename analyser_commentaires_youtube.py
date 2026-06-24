"""
Analyse des commentaires YouTube — Affaire Valérie Bacot
=========================================================
5 axes d'analyse comparables au corpus presse :
  1. Classification des narratifs (même lexique que les articles)
  2. Analyse temporelle (procès juin 2021, verdict, anniversaires)
  3. Polarité et affect (lexique de sentiment construit sur le corpus)
  4. Clustering non supervisé TF-IDF / K-Means
  5. Sociologie de l'engagement (likes, chaînes, narratifs mobilisateurs)

Usage :
    python analyser_commentaires_youtube.py

Entrée  : data/corpus_youtube_commentaires.csv
Sortie  : analyse_bacot/commentaires/  +  data/resultats_commentaires_youtube.csv
"""

import re
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize

# ─── Chemins ──────────────────────────────────────────────────────────────────

CSV_COMMENTAIRES  = Path("data/corpus_youtube_commentaires.csv")
CSV_ARTICLES      = Path("analyse_bacot/resultats_classification.csv")  # pour comparaison
OUTPUT_DIR        = Path("analyse_bacot/commentaires")
CSV_SORTIE        = Path("data/resultats_commentaires_youtube.csv")

N_CLUSTERS = 6

# ─── Périodes clés de l'affaire ───────────────────────────────────────────────

PERIODES = {
    "Avant procès":        ("2000-01-01", "2021-06-20"),
    "Procès (juin 2021)":  ("2021-06-21", "2021-06-25"),
    "Verdict + été 2021":  ("2021-06-26", "2021-12-31"),
    "2022":                ("2022-01-01", "2022-12-31"),
    "2023":                ("2023-01-01", "2023-12-31"),
    "2024+":               ("2024-01-01", "2099-12-31"),
}

DATES_CLES = {
    "2021-06-21": "Ouverture\nprocès",
    "2021-06-25": "Verdict\n(sursis)",
}

# ─── Lexique de narratifs (même que Classifier_bacot.py) ─────────────────────

LEXIQUE = {
    "soutien_victime": [
        "victime", "survie", "survivante", "courage", "brave",
        "innocente", "défendre", "protéger",
        "soutien", "soutenir", "solidarité", "empathie",
        "comprendre", "comprends", "normal", "logique",
        "aurait fait pareil", "j'aurais fait pareil",
        "a bien fait", "avait raison", "méritait", "libre",
        "libération", "pétition", "justice", "enfin libre",
        "applaudir", "bravo", "respect", "admire",
        "force", "courageuse", "admirable",
    ],
    "remise_en_question": [
        "partir", "quitter", "fuir", "s'enfuir", "appeler",
        "police", "gendarmerie", "signaler", "porter plainte",
        "pourquoi pas", "mais quand même", "n'empêche",
        "meurtre", "meurtrière", "tuer", "tueuse", "assassin",
        "assassinat", "préméditation", "prémédité",
        "aurait pu", "pouvait", "devait", "choix",
        "elle avait le choix", "solution", "autre solution",
        "pas normale", "pas excusable", "même si",
        "comprends pas", "incompréhensible",
    ],
    "legitime_defense": [
        "légitime défense", "legitime defense",
        "défense différée", "defense differee",
        "loi", "juridique", "jurisprudence",
        "droit", "code pénal", "article",
        "jacqueline sauvage", "sauvage",
        "grâce présidentielle", "grace presidentielle",
        "réforme", "changer la loi", "modifier",
        "angleterre", "canada", "étranger", "pays",
        "reconnaître", "reconnu", "syndrome",
        "état de nécessité", "etat de necessite",
        "contrainte", "inévitable", "inevitab",
    ],
    "discours_feministe": [
        "féminicide", "feminicide", "feministe", "féministe",
        "féminisme", "feminisme", "patriarcat", "patriarcal",
        "sexisme", "sexiste", "domination", "oppression",
        "violences faites aux femmes", "violences conjugales",
        "violence domestique", "emprise", "emprise psychologique",
        "cycle de la violence", "contrôle coercitif",
        "nous toutes", "noustoutes", "metoo", "me too",
        "systémique", "systemique", "structurel",
        "inégalité", "inegalite", "gender", "genre",
        "droits des femmes", "droits femmes",
    ],
    "emprise_psychologique": [
        "emprise", "manipulation", "manipulateur", "contrôle",
        "isolement", "isolée", "peur", "terreur", "terrifiée",
        "traumatisme", "traumatisée", "syndrome",
        "dépendance", "dependance", "soumission",
        "proxénétisme", "proxenete", "prostitution",
        "prostituée", "forcée", "obligée", "contrainte",
        "menace", "menacée", "chantage", "survie",
        "conditionnée", "lavage de cerveau",
        "stockholm", "résignation",
    ],
    "silence_collectif": [
        "savait", "savaient", "tout le monde savait",
        "silence", "taire", "se taire", "tu",
        "complice", "complicité", "passif", "passive",
        "voisin", "voisins", "entourage", "famille",
        "institution", "école", "médecin", "assistante sociale",
        "signalement", "signaler", "protection",
        "enfants", "enfant", "témoin", "témoins",
        "inaction", "inactif", "rien fait", "n'a rien fait",
        "fermé les yeux", "ignoré",
    ],
    "sensationnalisme": [
        "choquant", "horrible", "atroce", "terrifiant",
        "incroyable", "hallucinant", "fou", "folle",
        "dingue", "ouf", "waouh", "wow",
        "true crime", "crime", "fait divers",
        "story", "histoire", "affaire",
        "documentaire", "reportage", "téléfilm",
        "film", "série", "replay", "regarder",
        "abonner", "like", "partager", "commentaire",
        "chaîne", "vidéo",
    ],
    "jugement_moral": [
        "mérite", "méritait", "méritent", "punir",
        "punition", "condamner", "condamnation",
        "coupable", "responsable", "faute",
        "moral", "morale", "éthique", "bien", "mal",
        "dieu", "religion", "pardon", "pardonner",
        "compassion", "pitié", "indulgence",
        "sévère", "clément", "juste", "injuste",
        "verdict", "sentence", "peine", "prison",
    ],
}

# ─── Lexique de sentiment (construit sur le corpus Bacot) ────────────────────

SENTIMENT = {
    "positif": [
        "bravo", "merci", "magnifique", "admirable", "courage",
        "courageuse", "fort", "forte", "libre", "liberté", "enfin",
        "respect", "touchant", "émouvant", "bouleversant", "beau",
        "belle", "bien", "juste", "normal", "logique", "justice",
        "heureuse", "heureux", "soulagement", "espoir", "solidarité",
        "soutien", "ensemble", "humanité", "humaniste", "bienveillant",
        "compréhensif", "empathie", "empathique", "amour", "paix",
        "protéger", "défendre", "survivre", "survivante",
    ],
    "negatif": [
        "honte", "scandale", "inadmissible", "révoltant", "inacceptable",
        "criminel", "criminelle", "meurtrière", "assassin", "monstres",
        "lâche", "lâcheté", "irresponsable", "manipulatrice",
        "menteuse", "coupable", "condamner", "punir", "prison",
        "horrible", "atroce", "dégueulasse", "nul", "nulle",
        "hypocrite", "hypocrisie", "faux", "fausse", "complot",
        "choquant", "incroyable", "ignoble", "immonde",
        "danger", "dangereux", "dangereuse", "violence", "violent",
    ],
    "empathique": [
        "comprends", "comprendre", "comprension", "compréhension",
        "imagine", "imaginer", "à ta place", "à sa place",
        "j'aurais", "elle a dû", "il a fallu", "tellement difficile",
        "pauvre", "malheureuse", "malheureux", "triste", "tristesse",
        "souffrance", "souffrir", "enfer", "cauchemar", "traumatisme",
        "victime", "enfants", "petits", "innocents", "protéger",
        "pensées", "prières", "soutiens", "avec elle", "avec toi",
    ],
    "hostile": [
        "n'importe quoi", "ridicule", "absurde", "foutaises",
        "bobards", "mensonges", "manipulée", "arnaque", "escroquerie",
        "féministe", "féminazis", "idéologie", "propagande",
        "victimisation", "victimaire", "excuse", "excuses",
        "laxisme", "laxiste", "trop facile", "commode",
        "irresponsable", "inconsciente", "complice", "profiter",
    ],
}

STOPWORDS_FR = set([
    "le", "la", "les", "un", "une", "des", "du", "de", "d",
    "et", "en", "au", "aux", "à", "a", "avec", "pour", "par",
    "sur", "sous", "dans", "qui", "que", "qu", "ce", "cette",
    "ces", "il", "elle", "ils", "elles", "on", "nous", "vous",
    "je", "tu", "me", "te", "se", "lui", "leur", "leurs",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "est", "sont", "était", "ont", "avoir", "être", "fait",
    "plus", "très", "bien", "aussi", "mais", "ou", "donc",
    "car", "ni", "ne", "pas", "plus", "jamais", "rien",
    "tout", "tous", "toute", "toutes", "même", "autre",
    "après", "avant", "quand", "comme", "si", "dont",
    "où", "comment", "pourquoi", "quoi", "quel", "quelle",
    "ya", "ca", "ça", "c'est", "c'était", "j'ai", "j'avais",
])

COULEURS_NARRATIFS = {
    "soutien_victime":       "#4e9af1",
    "remise_en_question":    "#f1764e",
    "legitime_defense":      "#4ef18a",
    "discours_feministe":    "#b44ef1",
    "emprise_psychologique": "#f14eb4",
    "silence_collectif":     "#f1c44e",
    "sensationnalisme":      "#f14e4e",
    "jugement_moral":        "#f19a4e",
    "non_classe":            "#aaaaaa",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ─── Prétraitement ────────────────────────────────────────────────────────────

def nettoyer(texte: str) -> str:
    if not isinstance(texte, str):
        return ""
    texte = texte.lower()
    texte = texte.replace("'", " ").replace("'", " ").replace("‛", " ")
    texte = re.sub(r"[^a-zàâäéèêëîïôùûüç\s\-]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def sans_stopwords(texte: str) -> str:
    return " ".join(w for w in texte.split() if w not in STOPWORDS_FR and len(w) > 2)


def scorer_narratif(texte: str) -> dict:
    t = texte.lower()
    return {cat: sum(t.count(terme) for terme in termes) for cat, termes in LEXIQUE.items()}


def categorie_dominante(scores: dict) -> str:
    if all(v == 0 for v in scores.values()):
        return "non_classe"
    return max(scores, key=scores.get)


def scorer_sentiment(texte: str) -> dict:
    t = texte.lower()
    return {pol: sum(t.count(mot) for mot in mots) for pol, mots in SENTIMENT.items()}


def polarite_dominante(scores: dict) -> str:
    if all(v == 0 for v in scores.values()):
        return "neutre"
    return max(scores, key=scores.get)


def assigner_periode(date) -> str:
    if pd.isna(date):
        return "Inconnue"
    for label, (debut, fin) in PERIODES.items():
        if debut <= str(date)[:10] <= fin:
            return label
    return "Inconnue"


# ─── Axe 1 — Classification des narratifs ────────────────────────────────────

def axe1_classification(df: pd.DataFrame, df_articles: pd.DataFrame, output_dir: Path):
    log.info("Axe 1 — Classification des narratifs")

    categories = list(LEXIQUE.keys()) + ["non_classe"]
    pct_comm = (df["narratif"].value_counts(normalize=True).reindex(categories, fill_value=0) * 100)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    # Commentaires
    couleurs = [COULEURS_NARRATIFS.get(c, "#aaa") for c in categories]
    vals = pct_comm.values
    bars = axes[0].barh(categories, vals, color=couleurs, alpha=0.85)
    axes[0].bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    axes[0].set_xlabel("% des commentaires")
    axes[0].set_title(f"Commentaires YouTube\n(n={len(df):,})", fontweight="bold")
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)

    # Articles (comparaison)
    if df_articles is not None and not df_articles.empty and "categorie_dominante" in df_articles.columns:
        df_art = df_articles[df_articles.get("type_doc", "article") != "commentaire"] if "type_doc" in df_articles.columns else df_articles
        pct_art = (df_art["categorie_dominante"].value_counts(normalize=True).reindex(categories, fill_value=0) * 100)
        vals_art = pct_art.values
        bars2 = axes[1].barh(categories, vals_art, color=couleurs, alpha=0.85)
        axes[1].bar_label(bars2, fmt="%.1f%%", padding=3, fontsize=9)
        axes[1].set_title(f"Articles presse\n(n={len(df_art):,})", fontweight="bold")
    else:
        axes[1].text(0.5, 0.5, "Résultats articles\nnon disponibles\n(lancer Classifier_bacot.py)", ha="center", va="center", transform=axes[1].transAxes, fontsize=11, color="#888")
        axes[1].set_title("Articles presse", fontweight="bold")
    axes[1].set_xlabel("% des articles")
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)

    plt.suptitle("Comparaison des narratifs : Commentaires YouTube vs Articles presse\nAffaire Valérie Bacot", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "01_narratifs_commentaires_vs_presse.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("  ✓ 01_narratifs_commentaires_vs_presse.png")


# ─── Axe 2 — Analyse temporelle ───────────────────────────────────────────────

def axe2_temporel(df: pd.DataFrame, output_dir: Path):
    log.info("Axe 2 — Analyse temporelle")

    df_t = df[df["date"].notna()].copy()
    df_t["mois"] = df_t["date"].dt.to_period("M")
    df_t = df_t.dropna(subset=["mois"])

    # Volume mensuel + répartition des narratifs
    pivot = df_t.groupby(["mois", "narratif"]).size().unstack(fill_value=0)
    pivot.index = pivot.index.to_timestamp()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True)

    # Volume total
    total = pivot.sum(axis=1)
    ax1.fill_between(total.index, total.values, alpha=0.3, color="#2E75B6")
    ax1.plot(total.index, total.values, color="#2E75B6", linewidth=1.5)
    ax1.set_ylabel("Nb commentaires/mois", fontsize=10)
    ax1.set_title("Volume mensuel des commentaires", fontsize=11, fontweight="bold")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Marquer dates clés
    for date_str, label in DATES_CLES.items():
        d = pd.Timestamp(date_str)
        if total.index.min() <= d <= total.index.max():
            for ax in (ax1, ax2):
                ax.axvline(d, color="#e74c3c", linewidth=1.2, linestyle="--", alpha=0.7)
            ax1.text(d, total.max() * 0.95, label, ha="center", va="top",
                     fontsize=7.5, color="#e74c3c",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7))

    # Narratifs empilés
    cats_plot = [c for c in list(LEXIQUE.keys()) if c in pivot.columns]
    couleurs_plot = [COULEURS_NARRATIFS.get(c, "#aaa") for c in cats_plot]
    pivot[cats_plot].plot(kind="area", stacked=True, ax=ax2, alpha=0.75,
                          color=couleurs_plot, linewidth=0)
    ax2.set_ylabel("Nb commentaires/mois", fontsize=10)
    ax2.set_xlabel("Période", fontsize=10)
    ax2.set_title("Répartition des narratifs dans le temps", fontsize=11, fontweight="bold")
    ax2.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)

    plt.suptitle("Évolution temporelle des commentaires YouTube\nAffaire Valérie Bacot", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "02_evolution_temporelle.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Graphique par période clé
    fig, ax = plt.subplots(figsize=(14, 6))
    pivot_periode = df_t.groupby(["periode", "narratif"]).size().unstack(fill_value=0)
    ordre = list(PERIODES.keys())
    pivot_periode = pivot_periode.reindex([p for p in ordre if p in pivot_periode.index])
    cats_p = [c for c in list(LEXIQUE.keys()) if c in pivot_periode.columns]
    couleurs_p = [COULEURS_NARRATIFS.get(c, "#aaa") for c in cats_p]
    pivot_periode[cats_p].plot(kind="bar", stacked=True, ax=ax, color=couleurs_p, alpha=0.85, width=0.7)
    ax.set_xlabel("")
    ax.set_ylabel("Nb commentaires")
    ax.set_title("Narratifs par période clé\nAffaire Valérie Bacot", fontsize=12, fontweight="bold")
    ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "02b_narratifs_par_periode.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("  ✓ 02_evolution_temporelle.png + 02b_narratifs_par_periode.png")


# ─── Axe 3 — Polarité et affect ───────────────────────────────────────────────

def axe3_sentiment(df: pd.DataFrame, output_dir: Path):
    log.info("Axe 3 — Polarité et affect")

    polarites = ["positif", "negatif", "empathique", "hostile", "neutre"]
    couleurs_pol = {
        "positif":   "#27ae60",
        "negatif":   "#e74c3c",
        "empathique":"#3498db",
        "hostile":   "#e67e22",
        "neutre":    "#95a5a6",
    }

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Distribution globale
    pol_counts = df["polarite"].value_counts().reindex(polarites, fill_value=0)
    couleurs_bars = [couleurs_pol[p] for p in polarites]
    bars = axes[0].bar(polarites, pol_counts.values, color=couleurs_bars, alpha=0.85)
    axes[0].bar_label(bars, padding=3, fontsize=9)
    axes[0].set_title("Distribution globale\nde la tonalité", fontweight="bold")
    axes[0].set_ylabel("Nb commentaires")
    axes[0].spines["top"].set_visible(False)
    axes[0].spines["right"].set_visible(False)
    plt.setp(axes[0].xaxis.get_majorticklabels(), rotation=30, ha="right")

    # Sentiment par narratif dominant
    pivot_sent = df.groupby(["narratif", "polarite"]).size().unstack(fill_value=0)
    pivot_sent = pivot_sent.reindex(columns=polarites, fill_value=0)
    cats_ordre = [c for c in list(LEXIQUE.keys()) + ["non_classe"] if c in pivot_sent.index]
    pivot_sent = pivot_sent.loc[cats_ordre]
    pivot_sent_pct = pivot_sent.div(pivot_sent.sum(axis=1), axis=0) * 100
    pivot_sent_pct[[p for p in polarites if p in pivot_sent_pct.columns]].plot(
        kind="barh", stacked=True, ax=axes[1],
        color=[couleurs_pol[p] for p in polarites if p in pivot_sent_pct.columns],
        alpha=0.85, width=0.7
    )
    axes[1].set_title("Tonalité par narratif\n(% de la catégorie)", fontweight="bold")
    axes[1].set_xlabel("% des commentaires")
    axes[1].legend(fontsize=8)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)

    # Évolution de la tonalité dans le temps
    df_t = df[df["date"].notna()].copy()
    df_t["mois"] = df_t["date"].dt.to_period("M").dt.to_timestamp()
    pivot_pol_t = df_t.groupby(["mois", "polarite"]).size().unstack(fill_value=0)
    pivot_pol_t_pct = pivot_pol_t.div(pivot_pol_t.sum(axis=1), axis=0) * 100
    for pol in ["positif", "negatif", "empathique"]:
        if pol in pivot_pol_t_pct.columns:
            axes[2].plot(pivot_pol_t_pct.index, pivot_pol_t_pct[pol],
                         label=pol, color=couleurs_pol[pol], linewidth=1.5, alpha=0.85)
    for date_str, label in DATES_CLES.items():
        d = pd.Timestamp(date_str)
        if not pivot_pol_t_pct.empty and pivot_pol_t_pct.index.min() <= d <= pivot_pol_t_pct.index.max():
            axes[2].axvline(d, color="#e74c3c", linewidth=1, linestyle="--", alpha=0.6)
    axes[2].set_title("Évolution de la tonalité\n(% mensuel)", fontweight="bold")
    axes[2].set_xlabel("Période")
    axes[2].set_ylabel("% des commentaires du mois")
    axes[2].legend(fontsize=8)
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(axes[2].xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
    axes[2].spines["top"].set_visible(False)
    axes[2].spines["right"].set_visible(False)

    plt.suptitle("Polarité et affect — Commentaires YouTube\nAffaire Valérie Bacot", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "03_sentiment.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Heatmap chaîne × tonalité
    pivot_chaine_pol = df.groupby(["chaine_courte", "polarite"]).size().unstack(fill_value=0)
    pivot_chaine_pol = pivot_chaine_pol.reindex(columns=polarites, fill_value=0)
    pivot_chaine_pol_pct = pivot_chaine_pol.div(pivot_chaine_pol.sum(axis=1), axis=0) * 100
    top_chaines = df["chaine_courte"].value_counts().head(12).index
    pivot_chaine_pol_pct = pivot_chaine_pol_pct.loc[
        pivot_chaine_pol_pct.index.isin(top_chaines)
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(pivot_chaine_pol_pct, annot=True, fmt=".0f", cmap="RdYlGn",
                ax=ax, linewidths=0.5, cbar_kws={"label": "% commentaires"})
    ax.set_title("Tonalité par chaîne (% des commentaires)\nAffaire Valérie Bacot", fontsize=12, fontweight="bold")
    ax.set_xlabel("Polarité")
    ax.set_ylabel("")
    plt.tight_layout()
    plt.savefig(output_dir / "03b_sentiment_par_chaine.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("  ✓ 03_sentiment.png + 03b_sentiment_par_chaine.png")


# ─── Axe 4 — Clustering TF-IDF / K-Means ─────────────────────────────────────

def axe4_clustering(df: pd.DataFrame, output_dir: Path):
    log.info("Axe 4 — Clustering TF-IDF / K-Means")

    # Ne garder que les commentaires avec assez de contenu
    df_long = df[df["word_count"] >= 5].copy().reset_index(drop=True)
    if len(df_long) < N_CLUSTERS * 10:
        log.warning("  Pas assez de documents pour le clustering")
        return df

    vectorizer = TfidfVectorizer(
        max_features=2000,
        min_df=3,
        max_df=0.95,
        ngram_range=(1, 2),
        stop_words=list(STOPWORDS_FR),
    )
    tfidf = vectorizer.fit_transform(df_long["texte_sans_sw"])
    log.info(f"  Matrice TF-IDF : {tfidf.shape[0]} × {tfidf.shape[1]}")

    tfidf_norm = normalize(tfidf)
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    df_long["cluster"] = kmeans.fit_predict(tfidf_norm)

    feature_names = vectorizer.get_feature_names_out()
    cluster_labels = {}
    log.info("  Mots caractéristiques par cluster :")
    for cid in range(N_CLUSTERS):
        top = kmeans.cluster_centers_[cid].argsort()[-10:][::-1]
        mots = [feature_names[i] for i in top]
        cluster_labels[cid] = ", ".join(mots[:5])
        log.info(f"    Cluster {cid} : {', '.join(mots)}")
    df_long["cluster_mots"] = df_long["cluster"].map(cluster_labels)

    # Visualisation PCA
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(tfidf.toarray())
    couleurs_c = plt.cm.tab10(np.linspace(0, 1, N_CLUSTERS))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    for cid in range(N_CLUSTERS):
        mask = df_long["cluster"] == cid
        label = f"C{cid}: {cluster_labels[cid][:30]} (n={mask.sum()})"
        ax1.scatter(coords[mask, 0], coords[mask, 1],
                    c=[couleurs_c[cid]], label=label, alpha=0.4, s=15)
    ax1.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
    ax1.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    ax1.set_title("Clusters (PCA 2D)\nCommentaires YouTube", fontweight="bold")
    ax1.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Composition en narratifs de chaque cluster
    pivot_cn = df_long.groupby(["cluster", "narratif"]).size().unstack(fill_value=0)
    pivot_cn_pct = pivot_cn.div(pivot_cn.sum(axis=1), axis=0) * 100
    cats = [c for c in list(LEXIQUE.keys()) if c in pivot_cn_pct.columns]
    pivot_cn_pct[cats].plot(
        kind="bar", stacked=True, ax=ax2, width=0.7,
        color=[COULEURS_NARRATIFS.get(c, "#aaa") for c in cats], alpha=0.85
    )
    ax2.set_xlabel("Cluster")
    ax2.set_ylabel("% des commentaires du cluster")
    ax2.set_title("Composition en narratifs\npar cluster", fontweight="bold")
    ax2.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=0)

    plt.suptitle("Clustering des commentaires YouTube\nAffaire Valérie Bacot", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "04_clusters.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("  ✓ 04_clusters.png")

    # Propager les clusters sur le df principal (NaN pour les courts)
    df["cluster"]       = np.nan
    df["cluster_mots"]  = ""
    df.loc[df_long.index, "cluster"]      = df_long["cluster"].values
    df.loc[df_long.index, "cluster_mots"] = df_long["cluster_mots"].values
    return df


# ─── Axe 5 — Sociologie de l'engagement ──────────────────────────────────────

def axe5_engagement(df: pd.DataFrame, output_dir: Path):
    log.info("Axe 5 — Sociologie de l'engagement")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 5a — Likes moyens par narratif
    likes_narratif = (df.groupby("narratif")["likes"]
                        .agg(["mean", "median", "sum", "count"])
                        .sort_values("mean", ascending=True))
    cats = likes_narratif.index.tolist()
    couleurs_b = [COULEURS_NARRATIFS.get(c, "#aaa") for c in cats]
    bars = axes[0, 0].barh(cats, likes_narratif["mean"], color=couleurs_b, alpha=0.85)
    axes[0, 0].bar_label(bars, fmt="%.1f", padding=3, fontsize=8)
    axes[0, 0].set_xlabel("Likes moyens par commentaire")
    axes[0, 0].set_title("Engagement moyen par narratif\n(likes/commentaire)", fontweight="bold")
    axes[0, 0].spines["top"].set_visible(False)
    axes[0, 0].spines["right"].set_visible(False)

    # 5b — Volume et engagement par chaîne (top 12)
    top_chaines = df["chaine_courte"].value_counts().head(12).index
    df_top = df[df["chaine_courte"].isin(top_chaines)]
    chaine_stats = df_top.groupby("chaine_courte").agg(
        n=("likes", "count"),
        likes_moy=("likes", "mean"),
        likes_total=("likes", "sum"),
    ).sort_values("n", ascending=True)
    axes[0, 1].barh(chaine_stats.index, chaine_stats["n"], color="#3498db", alpha=0.7, label="Nb commentaires")
    ax_r = axes[0, 1].twiny()
    ax_r.plot(chaine_stats["likes_moy"], chaine_stats.index, "o-", color="#e74c3c", linewidth=1.5, markersize=5, label="Likes moy.")
    axes[0, 1].set_xlabel("Nb commentaires", color="#3498db")
    ax_r.set_xlabel("Likes moyens", color="#e74c3c")
    axes[0, 1].set_title("Volume et engagement\npar chaîne (top 12)", fontweight="bold")
    axes[0, 1].spines["top"].set_visible(False)
    axes[0, 1].spines["right"].set_visible(False)

    # 5c — Distribution des likes (top 5% exclu pour lisibilité)
    seuil = df["likes"].quantile(0.95)
    df_likes = df[df["likes"] <= seuil]
    axes[1, 0].hist(df_likes["likes"], bins=40, color="#2E75B6", alpha=0.75, edgecolor="white")
    axes[1, 0].axvline(df["likes"].median(), color="#e74c3c", linewidth=1.5, linestyle="--",
                       label=f"Médiane : {df['likes'].median():.0f}")
    axes[1, 0].axvline(df["likes"].mean(), color="#f39c12", linewidth=1.5, linestyle="--",
                       label=f"Moyenne : {df['likes'].mean():.1f}")
    axes[1, 0].set_xlabel("Likes (top 5% exclus)")
    axes[1, 0].set_ylabel("Nb commentaires")
    axes[1, 0].set_title("Distribution des likes", fontweight="bold")
    axes[1, 0].legend(fontsize=9)
    axes[1, 0].spines["top"].set_visible(False)
    axes[1, 0].spines["right"].set_visible(False)

    # 5d — Top 10 commentaires les plus likés
    top10 = df.nlargest(10, "likes")[["texte", "likes", "chaine_courte", "narratif", "date"]].copy()
    axes[1, 1].axis("off")
    table_data = []
    for _, row in top10.iterrows():
        extrait = (row["texte"][:70] + "…") if len(str(row["texte"])) > 70 else str(row["texte"])
        table_data.append([
            f"{int(row['likes']):,}",
            row["chaine_courte"][:20],
            row["narratif"].replace("_", " ")[:18],
            extrait,
        ])
    table = axes[1, 1].table(
        cellText=table_data,
        colLabels=["Likes", "Chaîne", "Narratif", "Extrait (70 car.)"],
        cellLoc="left",
        loc="center",
        bbox=[0, 0, 1, 1],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor("#2E75B6")
            cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#f0f4f8")
    axes[1, 1].set_title("Top 10 commentaires les plus likés", fontweight="bold", pad=12)

    plt.suptitle("Sociologie de l'engagement — Commentaires YouTube\nAffaire Valérie Bacot", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_dir / "05_engagement.png", dpi=150, bbox_inches="tight")
    plt.close()

    # Heatmap narratif × chaîne (% de likes cumulés)
    top_chaines_12 = df["chaine_courte"].value_counts().head(12).index
    df_hm = df[df["chaine_courte"].isin(top_chaines_12)]
    pivot_hm = df_hm.groupby(["chaine_courte", "narratif"])["likes"].sum().unstack(fill_value=0)
    pivot_hm_pct = pivot_hm.div(pivot_hm.sum(axis=1), axis=0) * 100
    cats_hm = [c for c in list(LEXIQUE.keys()) if c in pivot_hm_pct.columns]
    fig, ax = plt.subplots(figsize=(13, 7))
    sns.heatmap(pivot_hm_pct[cats_hm], annot=True, fmt=".0f", cmap="Blues",
                ax=ax, linewidths=0.5, cbar_kws={"label": "% likes totaux"})
    ax.set_title("Répartition des likes par narratif et chaîne\n(% des likes de la chaîne)", fontsize=12, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.xticks(rotation=30, ha="right", fontsize=9)
    plt.tight_layout()
    plt.savefig(output_dir / "05b_likes_narratif_chaine.png", dpi=150, bbox_inches="tight")
    plt.close()
    log.info("  ✓ 05_engagement.png + 05b_likes_narratif_chaine.png")


# ─── Export CSV ───────────────────────────────────────────────────────────────

def exporter(df: pd.DataFrame):
    cols = [
        "url", "texte", "auteur", "date", "likes", "video_url", "video_titre",
        "chaine", "chaine_courte", "word_count", "periode",
        "narratif", "score_narratif_total",
        "polarite", "score_positif", "score_negatif", "score_empathique", "score_hostile",
        "cluster", "cluster_mots",
    ] + [f"score_{c}" for c in LEXIQUE]
    cols_dispo = [c for c in cols if c in df.columns]
    df[cols_dispo].to_csv(CSV_SORTIE, index=False, encoding="utf-8-sig")
    log.info(f"  ✓ Export : {CSV_SORTIE} ({len(df):,} lignes)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info("CHARGEMENT DES DONNÉES")
    log.info("=" * 60)

    if not CSV_COMMENTAIRES.exists():
        log.error(f"Fichier introuvable : {CSV_COMMENTAIRES}")
        return

    df = pd.read_csv(CSV_COMMENTAIRES, encoding="utf-8")
    df = df[df["texte"].notna() & (df["texte"].str.strip() != "")].copy()
    log.info(f"Commentaires chargés : {len(df):,}")

    # Normaliser la chaîne (version courte pour affichage)
    df["chaine_courte"] = df["chaine"].str.replace(r"YouTube\s*[—–-]\s*", "", regex=True).str[:35]

    # Dates
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Période
    df["periode"] = df["date"].apply(assigner_periode)

    # Textes nettoyés
    df["texte_nettoye"] = df["texte"].apply(nettoyer)
    df["texte_sans_sw"] = df["texte_nettoye"].apply(sans_stopwords)

    # ── Axe 1 : classification narratifs ──
    log.info("=" * 60)
    log.info("ÉTAPE 1 — Classification des narratifs")
    log.info("=" * 60)

    scores_n = df["texte"].apply(scorer_narratif)
    for cat in LEXIQUE:
        df[f"score_{cat}"] = scores_n.apply(lambda s: s[cat])
    df["score_narratif_total"] = df[[f"score_{c}" for c in LEXIQUE]].sum(axis=1)
    df["narratif"] = scores_n.apply(categorie_dominante)

    log.info("Distribution des narratifs :")
    for cat, n in df["narratif"].value_counts().items():
        log.info(f"  {cat:<30} : {n:>5} ({n/len(df)*100:.1f}%)")

    # ── Axe 3 : sentiment (calculé avant les graphiques) ──
    log.info("=" * 60)
    log.info("ÉTAPE 3 — Polarité et affect")
    log.info("=" * 60)

    scores_s = df["texte"].apply(scorer_sentiment)
    for pol in SENTIMENT:
        df[f"score_{pol}"] = scores_s.apply(lambda s: s[pol])
    df["polarite"] = scores_s.apply(polarite_dominante)

    log.info("Distribution des polarités :")
    for pol, n in df["polarite"].value_counts().items():
        log.info(f"  {pol:<15} : {n:>5} ({n/len(df)*100:.1f}%)")

    # ── Chargement articles pour comparaison ──
    df_articles = None
    if CSV_ARTICLES.exists():
        try:
            df_articles = pd.read_csv(CSV_ARTICLES, encoding="utf-8-sig")
            log.info(f"Articles chargés pour comparaison : {len(df_articles):,}")
        except Exception as e:
            log.warning(f"Impossible de charger les résultats articles : {e}")

    # ── Génération des graphiques ──
    log.info("=" * 60)
    log.info("GÉNÉRATION DES GRAPHIQUES")
    log.info("=" * 60)

    axe1_classification(df, df_articles, OUTPUT_DIR)
    axe2_temporel(df, OUTPUT_DIR)
    axe3_sentiment(df, OUTPUT_DIR)
    df = axe4_clustering(df, OUTPUT_DIR)
    axe5_engagement(df, OUTPUT_DIR)

    # ── Export ──
    log.info("=" * 60)
    log.info("EXPORT")
    log.info("=" * 60)
    exporter(df)

    # ── Résumé ──
    log.info(f"""
╔═══════════════════════════════════════════════════════════════╗
║       ANALYSE COMMENTAIRES YOUTUBE — AFFAIRE BACOT            ║
╠═══════════════════════════════════════════════════════════════╣
║  Commentaires analysés : {len(df):>6,}                           ║
║  Vidéos uniques        : {df['video_url'].nunique():>6,}                           ║
║  Chaînes               : {df['chaine'].nunique():>6,}                           ║
╠═══════════════════════════════════════════════════════════════╣
║  Graphiques (analyse_bacot/commentaires/) :                   ║
║  01 — Narratifs commentaires vs presse                        ║
║  02 — Évolution temporelle + périodes clés                    ║
║  03 — Polarité et affect (global + par chaîne)                ║
║  04 — Clusters TF-IDF/K-Means                                 ║
║  05 — Engagement (likes par narratif et chaîne)               ║
╠═══════════════════════════════════════════════════════════════╣
║  Données : data/resultats_commentaires_youtube.csv            ║
╚═══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    run()
