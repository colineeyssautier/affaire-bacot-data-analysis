"""
Classification lexicale + Clustering — Affaire Valérie Bacot
=============================================================
Pipeline complet :
  1. Charge le corpus final
  2. Applique le lexique de narratifs (classification par catégorie)
  3. Vectorise les textes (TF-IDF)
  4. Clustering K-Means
  5. Génère des visualisations et un rapport CSV

Installation :
    pip install scikit-learn matplotlib seaborn wordcloud pandas

Usage :
    python classifier_bacot.py
"""

import json
import re
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # pas besoin d'interface graphique
import seaborn as sns
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize
from wordcloud import WordCloud

# ─── Configuration ────────────────────────────────────────────────────────────

CORPUS_JSON = Path("corpus_bacot/corpus_final.json")
# Si corpus_final.json n'existe pas, utilise corpus_bacot.json
if not CORPUS_JSON.exists():
    CORPUS_JSON = Path("corpus_bacot/corpus_bacot.json")

TWEETS_JSON = Path("corpus_bacot/tweets_bacot.json")

OUTPUT_DIR  = Path("analyse_bacot")
N_CLUSTERS  = 6   # nombre de clusters K-Means

MOTS_CLES_TWEETS = [
    "bacot", "polette", "libertepourvalerie", "libérezvalérie",
    "justicepourvalerie", "valérie bacot", "valerie bacot", "clayette",
]

# ─── Lexique de narratifs ─────────────────────────────────────────────────────
#
# Chaque catégorie contient des mots et expressions qui la caractérisent.
# Un document reçoit un score par catégorie = nombre d'occurrences des termes.

LEXIQUE = {

    "soutien_victime": [
        "victime", "survie", "survivante", "courage", "brave",
        "innocente", "innocente", "défendre", "protéger",
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

# Stopwords français simples (sans spacy)
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

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ─── Prétraitement ────────────────────────────────────────────────────────────

def nettoyer_texte(texte: str) -> str:
    """Nettoyage basique : minuscules, suppression ponctuation excessive."""
    if not texte:
        return ""
    texte = texte.lower()
    # Remplace les apostrophes typographiques
    texte = texte.replace("'", " ").replace("'", " ").replace("‛", " ")
    # Supprime les caractères non-alphabétiques sauf espaces et tirets
    texte = re.sub(r"[^a-zàâäéèêëîïôùûüç\s\-]", " ", texte)
    # Réduit les espaces multiples
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def supprimer_stopwords(texte: str) -> str:
    """Supprime les stopwords français."""
    mots = texte.split()
    mots_filtres = [m for m in mots if m not in STOPWORDS_FR and len(m) > 2]
    return " ".join(mots_filtres)


# ─── Classification lexicale ──────────────────────────────────────────────────

def scorer_document(texte: str) -> dict:
    """
    Calcule le score de chaque catégorie de narratif pour un document.
    Score = nombre d'occurrences des termes du lexique dans le texte.
    """
    texte_lower = texte.lower()
    scores = {}
    for categorie, termes in LEXIQUE.items():
        score = sum(texte_lower.count(terme) for terme in termes)
        scores[categorie] = score
    return scores


def categorie_dominante(scores: dict) -> str:
    """Retourne la catégorie avec le score le plus élevé."""
    if all(v == 0 for v in scores.values()):
        return "non_classe"
    return max(scores, key=scores.get)


# ─── Visualisations ───────────────────────────────────────────────────────────

def plot_distribution_narratifs(df: pd.DataFrame, output_dir: Path):
    """Distribution des catégories dominantes."""
    fig, ax = plt.subplots(figsize=(12, 6))

    counts = df["categorie_dominante"].value_counts()
    colors = plt.cm.Set3(np.linspace(0, 1, len(counts)))

    bars = ax.barh(counts.index, counts.values, color=colors)
    ax.bar_label(bars, padding=3, fontsize=10)

    ax.set_xlabel("Nombre de documents", fontsize=12)
    ax.set_title("Distribution des narratifs dominants\nAffaire Valérie Bacot", fontsize=14, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_dir / "01_distribution_narratifs.png", dpi=150, bbox_inches='tight')
    plt.close()
    log.info("  ✓ Graphique : distribution des narratifs")


def plot_scores_par_type_source(df: pd.DataFrame, output_dir: Path):
    """Scores moyens par catégorie de narratif, par type de source."""
    categories = list(LEXIQUE.keys())
    types_sources = df["type_source"].dropna().unique()
    types_sources = [t for t in types_sources if t != "youtube_video"]

    fig, axes = plt.subplots(
        len(types_sources), 1,
        figsize=(14, 4 * len(types_sources)),
        sharey=False
    )
    if len(types_sources) == 1:
        axes = [axes]

    for ax, type_src in zip(axes, types_sources):
        subset = df[df["type_source"] == type_src]
        if subset.empty:
            continue

        moyennes = [subset[f"score_{cat}"].mean() for cat in categories]
        colors = ['#e74c3c' if m == max(moyennes) else '#3498db' for m in moyennes]

        bars = ax.bar(
            [c.replace("_", "\n") for c in categories],
            moyennes,
            color=colors,
            alpha=0.8
        )
        ax.set_title(f"Scores moyens — {type_src} (n={len(subset)})", fontsize=11, fontweight='bold')
        ax.set_ylabel("Score moyen")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(axis='x', labelsize=8)

    plt.suptitle("Narratifs par type de source\nAffaire Valérie Bacot", fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(output_dir / "02_narratifs_par_source.png", dpi=150, bbox_inches='tight')
    plt.close()
    log.info("  ✓ Graphique : narratifs par type de source")


def plot_heatmap_sources(df: pd.DataFrame, output_dir: Path):
    """Heatmap des scores moyens par catégorie × type de source."""
    categories = list(LEXIQUE.keys())
    score_cols = [f"score_{c}" for c in categories]

    pivot = df.groupby("type_source")[score_cols].mean()
    pivot.columns = [c.replace("score_", "").replace("_", "\n") for c in pivot.columns]
    pivot = pivot.loc[pivot.index != "youtube_video"]

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        ax=ax,
        linewidths=0.5,
        cbar_kws={"label": "Score moyen"},
    )
    ax.set_title("Intensité des narratifs par type de source\nAffaire Valérie Bacot", fontsize=13, fontweight='bold')
    ax.set_xlabel("")
    ax.set_ylabel("Type de source")
    plt.tight_layout()
    plt.savefig(output_dir / "03_heatmap_narratifs_sources.png", dpi=150, bbox_inches='tight')
    plt.close()
    log.info("  ✓ Graphique : heatmap narratifs × sources")


def plot_clusters_pca(df: pd.DataFrame, tfidf_matrix, output_dir: Path):
    """Visualisation 2D des clusters via PCA."""
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(tfidf_matrix.toarray())

    fig, ax = plt.subplots(figsize=(12, 8))
    colors = plt.cm.tab10(np.linspace(0, 1, N_CLUSTERS))

    for cluster_id in range(N_CLUSTERS):
        mask = df["cluster"] == cluster_id
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            c=[colors[cluster_id]],
            label=f"Cluster {cluster_id} (n={mask.sum()})",
            alpha=0.6,
            s=30,
        )

    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)", fontsize=11)
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)", fontsize=11)
    ax.set_title("Clustering des documents (K-Means + PCA)\nAffaire Valérie Bacot", fontsize=13, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_dir / "04_clusters_pca.png", dpi=150, bbox_inches='tight')
    plt.close()
    log.info("  ✓ Graphique : clusters PCA")


def generer_wordclouds(df: pd.DataFrame, output_dir: Path):
    """Génère un wordcloud par catégorie de narratif dominante."""
    wc_dir = output_dir / "wordclouds"
    wc_dir.mkdir(exist_ok=True)

    for categorie in LEXIQUE.keys():
        subset = df[df["categorie_dominante"] == categorie]
        if subset.empty or len(subset) < 3:
            continue

        texte_combine = " ".join(subset["texte_nettoye"].fillna(""))
        if not texte_combine.strip():
            continue

        wc = WordCloud(
            width=800,
            height=400,
            background_color="white",
            colormap="Blues",
            max_words=80,
            collocations=False,
            stopwords=STOPWORDS_FR,
        ).generate(texte_combine)

        plt.figure(figsize=(10, 5))
        plt.imshow(wc, interpolation="bilinear")
        plt.axis("off")
        plt.title(
            f"Mots fréquents — {categorie.replace('_', ' ').title()}\n(n={len(subset)} documents)",
            fontsize=12, fontweight='bold'
        )
        plt.tight_layout()
        plt.savefig(wc_dir / f"wc_{categorie}.png", dpi=120, bbox_inches='tight')
        plt.close()

    log.info(f"  ✓ Wordclouds générés dans {wc_dir}")


def plot_evolution_temporelle(df: pd.DataFrame, output_dir: Path):
    """Évolution des narratifs dominants dans le temps."""
    df_dates = df[df["date"].notna() & (df["date"] != "")].copy()
    if df_dates.empty:
        return

    df_dates["annee_mois"] = pd.to_datetime(df_dates["date"], errors="coerce").dt.to_period("M")
    df_dates = df_dates.dropna(subset=["annee_mois"])

    if df_dates.empty:
        return

    pivot = df_dates.groupby(["annee_mois", "categorie_dominante"]).size().unstack(fill_value=0)

    fig, ax = plt.subplots(figsize=(14, 6))
    pivot.plot(kind="area", stacked=True, ax=ax, alpha=0.7, colormap="Set3")

    ax.set_xlabel("Période", fontsize=11)
    ax.set_ylabel("Nombre de documents", fontsize=11)
    ax.set_title("Évolution temporelle des narratifs\nAffaire Valérie Bacot", fontsize=13, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_dir / "05_evolution_temporelle.png", dpi=150, bbox_inches='tight')
    plt.close()
    log.info("  ✓ Graphique : évolution temporelle")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Chargement du corpus ──
    log.info("=" * 60)
    log.info("ÉTAPE 1 — Chargement et prétraitement du corpus")
    log.info("=" * 60)

    if not CORPUS_JSON.exists():
        log.error(f"Corpus introuvable : {CORPUS_JSON}")
        return

    with open(CORPUS_JSON, encoding="utf-8") as f:
        corpus = json.load(f)

    log.info(f"Documents chargés : {len(corpus)}")

    # Construction du DataFrame
    rows = []
    for doc in corpus:
        texte = doc.get("text", "")
        if not texte or len(texte.split()) < 10:
            continue
        rows.append({
            "url":         doc.get("url", ""),
            "titre":       doc.get("title", doc.get("video_titre", ""))[:100],
            "date":        doc.get("date", "")[:10],
            "sitename":    doc.get("sitename", doc.get("chaine", "")),
            "type_source": doc.get("type_source", "autre"),
            "source":      doc.get("source", ""),
            "word_count":  doc.get("word_count", len(texte.split())),
            "texte_brut":  texte,
            "type_doc":    ("tweet" if doc.get("source") == "twitter_x"
                            else "commentaire" if doc.get("source") == "youtube_commentaire"
                            else "article"),
        })

    df = pd.DataFrame(rows)
    log.info(f"Documents valides : {len(df)}")
    log.info(f"  dont articles        : {(df['type_doc']=='article').sum()}")
    log.info(f"  dont commentaires YT : {(df['type_doc']=='commentaire').sum()}")
    log.info(f"  dont tweets          : {(df['type_doc']=='tweet').sum()}")

    # Tweets exclus du TF-IDF/K-Means (trop courts) mais classifiés séparément
    df = df[df['type_doc'] != 'tweet'].reset_index(drop=True)

    # ── Chargement et scoring des tweets ──
    df_tweets = pd.DataFrame()
    if TWEETS_JSON.exists():
        with open(TWEETS_JSON, encoding="utf-8") as f:
            tweets_data = json.load(f)
        tweet_rows = []
        for tw in tweets_data:
            texte = tw.get("texte", "").strip()
            if not any(kw in texte.lower() for kw in MOTS_CLES_TWEETS):
                continue
            tweet_rows.append({
                "url":         tw.get("url", ""),
                "titre":       "",
                "date":        (tw.get("date") or tw.get("datetime", ""))[:10],
                "sitename":    tw.get("handle", ""),
                "type_source": "twitter_x",
                "source":      "twitter_x",
                "word_count":  tw.get("nb_mots", len(texte.split())),
                "texte_brut":  texte,
                "type_doc":    "tweet",
            })
        df_tweets = pd.DataFrame(tweet_rows)
        if not df_tweets.empty:
            scores_tw = df_tweets["texte_brut"].apply(scorer_document)
            for categorie in LEXIQUE.keys():
                df_tweets[f"score_{categorie}"] = scores_tw.apply(lambda s: s[categorie])
            df_tweets["score_total"]         = df_tweets[[f"score_{c}" for c in LEXIQUE]].sum(axis=1)
            df_tweets["categorie_dominante"] = scores_tw.apply(categorie_dominante)
            df_tweets["cluster"]             = -1
            df_tweets["cluster_mots_cles"]   = ""
            log.info(f"  dont tweets classifiés : {len(df_tweets)} ({(df_tweets['categorie_dominante'] != 'non_classe').sum()} avec narratif)")

    # Prétraitement
    log.info("Prétraitement des textes...")
    df["texte_nettoye"] = df["texte_brut"].apply(nettoyer_texte)
    df["texte_sans_sw"] = df["texte_nettoye"].apply(supprimer_stopwords)

    # ── Classification lexicale ──
    log.info("=" * 60)
    log.info("ÉTAPE 2 — Classification lexicale")
    log.info("=" * 60)

    scores_tous = df["texte_brut"].apply(scorer_document)
    for categorie in LEXIQUE.keys():
        df[f"score_{categorie}"] = scores_tous.apply(lambda s: s[categorie])

    df["score_total"]          = df[[f"score_{c}" for c in LEXIQUE]].sum(axis=1)
    df["categorie_dominante"]  = scores_tous.apply(categorie_dominante)

    # Stats
    log.info("Distribution des narratifs dominants :")
    for cat, n in df["categorie_dominante"].value_counts().items():
        log.info(f"  {cat:<30} : {n:>4} documents ({n/len(df)*100:.1f}%)")

    # ── Vectorisation TF-IDF ──
    log.info("=" * 60)
    log.info("ÉTAPE 3 — Vectorisation TF-IDF")
    log.info("=" * 60)

    vectorizer = TfidfVectorizer(
        max_features=3000,
        min_df=2,
        max_df=0.95,
        ngram_range=(1, 2),
        stop_words=list(STOPWORDS_FR),
    )

    tfidf_matrix = vectorizer.fit_transform(df["texte_sans_sw"])
    log.info(f"Matrice TF-IDF : {tfidf_matrix.shape[0]} docs × {tfidf_matrix.shape[1]} termes")

    # ── Clustering K-Means ──
    log.info("=" * 60)
    log.info("ÉTAPE 4 — Clustering K-Means")
    log.info("=" * 60)

    tfidf_norm = normalize(tfidf_matrix)
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(tfidf_norm)

    log.info(f"Distribution des clusters :")
    for cluster_id, n in sorted(Counter(df["cluster"]).items()):
        log.info(f"  Cluster {cluster_id} : {n:>4} documents")

    # Mots les plus représentatifs de chaque cluster
    feature_names = vectorizer.get_feature_names_out()
    log.info("\nMots caractéristiques par cluster :")
    cluster_labels = {}
    for cluster_id in range(N_CLUSTERS):
        center = kmeans.cluster_centers_[cluster_id]
        top_indices = center.argsort()[-10:][::-1]
        top_mots = [feature_names[i] for i in top_indices]
        cluster_labels[cluster_id] = ", ".join(top_mots[:5])
        log.info(f"  Cluster {cluster_id} : {', '.join(top_mots)}")

    df["cluster_mots_cles"] = df["cluster"].map(cluster_labels)

    # ── Visualisations ──
    log.info("=" * 60)
    log.info("ÉTAPE 5 — Génération des visualisations")
    log.info("=" * 60)

    plot_distribution_narratifs(df, OUTPUT_DIR)
    plot_scores_par_type_source(df, OUTPUT_DIR)
    plot_heatmap_sources(df, OUTPUT_DIR)
    plot_clusters_pca(df, tfidf_matrix, OUTPUT_DIR)
    generer_wordclouds(df, OUTPUT_DIR)
    plot_evolution_temporelle(df, OUTPUT_DIR)

    # ── Export des résultats ──
    log.info("=" * 60)
    log.info("ÉTAPE 6 — Export des résultats")
    log.info("=" * 60)

    # CSV principal
    cols_export = [
        "url", "titre", "date", "sitename", "type_source", "type_doc",
        "word_count", "categorie_dominante", "score_total", "cluster",
        "cluster_mots_cles",
    ] + [f"score_{c}" for c in LEXIQUE]

    csv_data = Path("data")
    csv_data.mkdir(exist_ok=True)

    df_export = df[cols_export]
    if not df_tweets.empty:
        df_export = pd.concat([df_export, df_tweets[cols_export]], ignore_index=True)
        log.info(f"CSV : {len(df)} articles/commentaires + {len(df_tweets)} tweets = {len(df_export)} lignes")

    df_export.to_csv(
        OUTPUT_DIR / "resultats_classification.csv",
        index=False,
        encoding="utf-8-sig"
    )
    df_export.to_csv(
        csv_data / "resultats_classification.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Résumé par cluster
    resume_cluster = df.groupby("cluster").agg(
        n_documents=("url", "count"),
        mots_cles=("cluster_mots_cles", "first"),
        narratif_dominant=("categorie_dominante", lambda x: x.value_counts().index[0]),
        score_moyen=("score_total", "mean"),
        pct_articles=("type_doc", lambda x: (x=="article").mean()*100),
        pct_commentaires=("type_doc", lambda x: (x=="commentaire").mean()*100),
    ).round(1)

    resume_cluster.to_csv(OUTPUT_DIR / "resume_clusters.csv", encoding="utf-8-sig")

    # Résumé par catégorie de narratif
    resume_narratifs = df.groupby("categorie_dominante").agg(
        n_documents=("url", "count"),
        pct_articles=("type_doc", lambda x: (x=="article").mean()*100),
        mots_moyens=("word_count", "mean"),
        score_moyen=("score_total", "mean"),
    ).round(1).sort_values("n_documents", ascending=False)

    resume_narratifs.to_csv(OUTPUT_DIR / "resume_narratifs.csv", encoding="utf-8-sig")

    log.info(f"""
╔══════════════════════════════════════════════════════════╗
║         ANALYSE TERMINÉE — AFFAIRE VALÉRIE BACOT         ║
╠══════════════════════════════════════════════════════════╣
║  Documents analysés     : {len(df):>5}                       ║
║  Catégories de narratifs: {len(LEXIQUE):>5}                       ║
║  Clusters               : {N_CLUSTERS:>5}                       ║
╠══════════════════════════════════════════════════════════╣
║  Fichiers générés dans : {str(OUTPUT_DIR):<30} ║
║                                                          ║
║  Visualisations :                                        ║
║  01_distribution_narratifs.png                           ║
║  02_narratifs_par_source.png                             ║
║  03_heatmap_narratifs_sources.png                        ║
║  04_clusters_pca.png                                     ║
║  05_evolution_temporelle.png                             ║
║  wordclouds/ (un par catégorie)                          ║
║                                                          ║
║  Données :                                               ║
║  resultats_classification.csv                            ║
║  resume_clusters.csv                                     ║
║  resume_narratifs.csv                                    ║
╚══════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    run()