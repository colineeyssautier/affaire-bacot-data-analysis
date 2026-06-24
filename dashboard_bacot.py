"""
Dashboard Streamlit — Analyse des narratifs, Affaire Valérie Bacot
===================================================================
Interface interactive pour explorer le corpus et les résultats
de la classification lexicale.

Installation :
    pip install streamlit plotly pandas

Usage :
    streamlit run dashboard_bacot.py

Structure attendue dans le même dossier :
    corpus_bacot/corpus_bacot.json  (ou corpus_final.json)
    analyse_bacot/resultats_classification.csv
    analyse_bacot/resume_narratifs.csv
    analyse_bacot/resume_clusters.csv
    analyse_bacot/  (dossier avec les .png)
"""

import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path
from collections import Counter

# ─── Configuration page ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Narratifs Bacot — Analyse",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_PATHS = [
    Path("corpus_bacot/corpus_final.json"),
    Path("corpus_bacot/corpus_bacot.json"),
]
ANALYSE_DIR  = Path("analyse_bacot")
CSV_RESULTATS = ANALYSE_DIR / "resultats_classification.csv"
CSV_NARRATIFS = ANALYSE_DIR / "resume_narratifs.csv"
CSV_CLUSTERS  = ANALYSE_DIR / "resume_clusters.csv"

# ─── Constantes ───────────────────────────────────────────────────────────────

LABELS_FR = {
    'soutien_victime':        '💙 Soutien à la victime',
    'remise_en_question':     '❓ Remise en question',
    'legitime_defense':       '⚖️ Légitime défense',
    'discours_feministe':     '✊ Discours féministe',
    'emprise_psychologique':  '🔗 Emprise psychologique',
    'silence_collectif':      '🤫 Silence collectif',
    'sensationnalisme':       '📺 Sensationnalisme',
    'jugement_moral':         '🔍 Jugement moral',
    'non_classe':             '❔ Non classé',
}

DESCRIPTIONS = {
    'soutien_victime':        "Compassion, solidarité, validation du geste comme acte de survie.",
    'remise_en_question':     "Doute sur les choix, évocation d'alternatives, peut aller jusqu'à la condamnation.",
    'legitime_defense':       "Cadre juridique, légitime défense différée, précédent Jacqueline Sauvage.",
    'discours_feministe':     "Approche systémique — patriarcat, féminicide, continuum des violences.",
    'emprise_psychologique':  "Mécanisme d'emprise, contrôle coercitif, traumatisme, prostitution forcée.",
    'silence_collectif':      "Complicité passive — 'tout le monde savait' — entourage, institutions.",
    'sensationnalisme':       "Fait divers spectaculaire, true crime, sans dimension critique.",
    'jugement_moral':         "Jugement sur la légitimité de la peine, culpabilité morale.",
    'non_classe':             "Documents hors-sujet ou trop courts pour être classifiés.",
}

COULEURS = {
    'soutien_victime':        '#4e9af1',
    'remise_en_question':     '#f1764e',
    'legitime_defense':       '#4ef18a',
    'discours_feministe':     '#b44ef1',
    'emprise_psychologique':  '#f14eb4',
    'silence_collectif':      '#f1c44e',
    'sensationnalisme':       '#f14e4e',
    'jugement_moral':         '#f19a4e',
    'non_classe':             '#aaaaaa',
}

CATEGORIES = list(LABELS_FR.keys())[:-1]  # sans non_classe

# ─── Chargement des données ───────────────────────────────────────────────────

@st.cache_data
def charger_corpus():
    for path in CORPUS_PATHS:
        if path.exists():
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    return []

@st.cache_data
def charger_csv():
    df_r = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig') if CSV_RESULTATS.exists() else pd.DataFrame()
    df_n = pd.read_csv(CSV_NARRATIFS, encoding='utf-8-sig') if CSV_NARRATIFS.exists() else pd.DataFrame()
    df_c = pd.read_csv(CSV_CLUSTERS,  encoding='utf-8-sig') if CSV_CLUSTERS.exists()  else pd.DataFrame()
    return df_r, df_n, df_c

CSV_COMMENTAIRES_YT = Path("data/resultats_commentaires_youtube.csv")

@st.cache_data
def charger_commentaires_yt():
    if not CSV_COMMENTAIRES_YT.exists():
        return pd.DataFrame()
    df = pd.read_csv(CSV_COMMENTAIRES_YT, encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df

# ─── CSS personnalisé ─────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1F3864;
        margin-bottom: 0;
    }
    .subtitle {
        font-size: 1rem;
        color: #666;
        margin-top: 0.2rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        border-left: 4px solid #2E75B6;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #1F3864;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
    }
    .narratif-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        color: white;
        background: #2E75B6;
    }
    .citation-box {
        background: #fffbea;
        border-left: 4px solid #f1c44e;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        font-style: italic;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    .source-tag {
        font-size: 0.75rem;
        color: #888;
        margin-top: 0.3rem;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1F3864;
        border-bottom: 2px solid #2E75B6;
        padding-bottom: 0.3rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .stSelectbox label { font-weight: 600; }
    .stSlider label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ─── Chargement ───────────────────────────────────────────────────────────────

corpus   = charger_corpus()
df_r, df_n, df_c = charger_csv()

# Articles de presse uniquement (df_r contient aussi les commentaires YouTube)
df_articles = df_r[df_r['type_doc'] == 'article'].copy() if not df_r.empty else pd.DataFrame()

corpus_index = {doc.get('url',''): doc for doc in corpus}

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/110px-Python-logo-notext.svg.png", width=40)
    st.markdown("## ⚖️ Narratifs Bacot")
    st.markdown("*Analyse computationnelle des discours*")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Vue d'ensemble", "📊 Narratifs", "🔵 Clusters",
         "💬 Explorer le corpus", "📈 Évolution temporelle",
         "🎬 Commentaires YouTube",
         "🔍 Recherche qualitative"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(f"**Corpus :** {len(corpus)} documents")
    if not df_r.empty:
        n_art = (df_r['type_doc'] == 'article').sum()
        n_cmt = (df_r['type_doc'] == 'commentaire').sum()
        st.markdown(f"📰 {n_art} articles de presse")
        st.markdown(f"💬 {n_cmt} commentaires YouTube")
    st.divider()
    st.caption("Projet SciLit · Prototype v1.0")

# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 : VUE D'ENSEMBLE
# ════════════════════════════════════════════════════════════════════════════

if page == "🏠 Vue d'ensemble":

    st.markdown('<p class="main-title">⚖️ Affaire Valérie Bacot</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Analyse computationnelle des narratifs · Articles de presse 2017–2023 · Commentaires YouTube analysés séparément</p>', unsafe_allow_html=True)

    # Métriques
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Documents total", len(corpus))
    with col2:
        n_art = int((df_r['type_doc'] == 'article').sum()) if not df_r.empty else 0
        st.metric("Articles de presse", n_art)
    with col3:
        n_cmt = int((df_r['type_doc'] == 'commentaire').sum()) if not df_r.empty else 0
        st.metric("Commentaires YouTube", n_cmt)
    with col4:
        st.metric("Catégories narratifs", 8)
    with col5:
        st.metric("Clusters identifiés", 6)

    st.divider()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<p class="section-header">Distribution des narratifs — Articles de presse</p>', unsafe_allow_html=True)

        if not df_articles.empty:
            df_plot = (df_articles.groupby('categorie_dominante').size()
                       .reset_index(name='n_documents'))
            df_plot = df_plot[df_plot['categorie_dominante'] != 'non_classe'].copy()
            df_plot['label'] = df_plot['categorie_dominante'].map(LABELS_FR)
            df_plot = df_plot.sort_values('n_documents', ascending=True)

            fig = px.bar(
                df_plot,
                x='n_documents',
                y='label',
                orientation='h',
                color='categorie_dominante',
                color_discrete_map=COULEURS,
                text='n_documents',
                labels={'n_documents': 'Nombre d\'articles', 'label': ''},
            )
            fig.update_traces(textposition='outside', showlegend=False)
            fig.update_layout(
                height=380,
                margin=dict(l=0, r=40, t=10, b=10),
                plot_bgcolor='white',
                xaxis=dict(showgrid=True, gridcolor='#eee'),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown('<p class="section-header">Répartition des narratifs</p>', unsafe_allow_html=True)

        if not df_articles.empty:
            df_pie = (df_articles.groupby('categorie_dominante').size()
                      .reset_index(name='n_documents'))
            df_pie = df_pie[df_pie['categorie_dominante'] != 'non_classe'].copy()
            df_pie['label'] = df_pie['categorie_dominante'].map(LABELS_FR)

            fig2 = px.pie(
                df_pie,
                values='n_documents',
                names='label',
                color='categorie_dominante',
                color_discrete_map=COULEURS,
                hole=0.4,
            )
            fig2.update_traces(textposition='inside', textinfo='percent')
            fig2.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=10, b=10),
                showlegend=True,
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Contexte
    st.divider()
    st.markdown('<p class="section-header">Contexte analytique</p>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.info("**Affaire Valérie Bacot**\n\nValérie Bacot a tué son mari Daniel Polette en 2012, après 25 ans de viols, violences et proxénétisme. Jugée en juin 2021, elle a été condamnée à 4 ans dont 3 avec sursis — et libérée le jour même du verdict.")
    with col_b:
        st.warning("**Enjeux juridiques**\n\nL'affaire a relancé le débat sur la notion de **légitime défense différée** — absente du droit français, contrairement au droit anglo-saxon. La pétition en sa faveur a récolté plus de 600 000 signatures.")
    with col_c:
        st.success("**Dimension sociétale**\n\nL'affaire révèle les angles morts du droit face aux violences conjugales, la complicité passive de l'entourage ('tout le monde savait'), et les biais du système judiciaire face aux victimes d'emprise.")


# ════════════════════════════════════════════════════════════════════════════
# PAGE 2 : NARRATIFS
# ════════════════════════════════════════════════════════════════════════════

elif page == "📊 Narratifs":

    st.markdown('<p class="main-title">📊 Analyse des narratifs</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Classification lexicale en 8 catégories · Articles de presse uniquement · Comparaison par source</p>', unsafe_allow_html=True)

    if df_articles.empty:
        st.error("Aucun article de presse trouvé dans les données de classification.")
        st.stop()

    # Heatmap narratifs × sources
    st.markdown('<p class="section-header">Intensité des narratifs par type de source — Articles de presse</p>', unsafe_allow_html=True)
    st.caption("Score moyen des termes caractéristiques par catégorie, selon le type de source. Plus la valeur est élevée, plus ce narratif est présent dans cette source.")

    score_cols = [f"score_{c}" for c in CATEGORIES if f"score_{c}" in df_articles.columns]
    pivot = df_articles.groupby('type_source')[score_cols].mean().round(1)
    pivot = pivot[pivot.index != 'youtube_video']
    pivot.columns = [c.replace('score_', '').replace('_', ' ') for c in pivot.columns]

    fig_heat = px.imshow(
        pivot,
        color_continuous_scale='YlOrRd',
        aspect='auto',
        text_auto=True,
        labels=dict(color="Score moyen"),
    )
    fig_heat.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=10),
        xaxis=dict(tickangle=-30),
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    st.divider()

    # Détail par catégorie
    st.markdown('<p class="section-header">Détail par catégorie de narratif</p>', unsafe_allow_html=True)

    cat_choisie = st.selectbox(
        "Choisir une catégorie",
        options=CATEGORIES,
        format_func=lambda x: LABELS_FR.get(x, x),
    )

    if cat_choisie:
        col_desc, col_stats = st.columns([2, 1])

        with col_desc:
            st.markdown(f"**{LABELS_FR[cat_choisie]}**")
            st.markdown(DESCRIPTIONS.get(cat_choisie, ''))

        with col_stats:
            n_docs = int((df_articles['categorie_dominante'] == cat_choisie).sum())
            pct = n_docs / len(df_articles) * 100
            st.metric("Articles dans cette catégorie", n_docs)
            st.metric("Part du corpus presse", f"{pct:.1f}%")

        subset = df_articles[df_articles['categorie_dominante'] == cat_choisie]

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            src_type = subset['type_source'].value_counts().reset_index()
            src_type.columns = ['source', 'n']
            fig_type = px.pie(
                src_type.head(6), values='n', names='source',
                title="Répartition par type de source",
                hole=0.3,
            )
            fig_type.update_layout(height=280, margin=dict(t=30, b=0))
            st.plotly_chart(fig_type, use_container_width=True)

        with col_g2:
            src_counts = subset['sitename'].value_counts().head(8).reset_index()
            src_counts.columns = ['source', 'n']
            fig_src = px.bar(
                src_counts, x='n', y='source',
                orientation='h',
                title="Top titres de presse",
                color_discrete_sequence=['#4e9af1'],
                text='n',
            )
            fig_src.update_traces(textposition='outside')
            fig_src.update_layout(
                height=280,
                margin=dict(l=0, r=30, t=30, b=0),
                showlegend=False,
                plot_bgcolor='white',
            )
            st.plotly_chart(fig_src, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 3 : CLUSTERS
# ════════════════════════════════════════════════════════════════════════════

elif page == "🔵 Clusters":

    st.markdown('<p class="main-title">🔵 Clustering K-Means</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">6 groupes naturels identifiés par similarité lexicale globale</p>', unsafe_allow_html=True)

    if df_c.empty:
        st.error("Fichier resume_clusters.csv introuvable.")
        st.stop()

    st.info("Le clustering regroupe les documents par similarité lexicale **sans catégories prédéfinies**. Il révèle des patterns que la classification supervisée n'aurait pas anticipés.")

    # Tableau des clusters
    st.markdown('<p class="section-header">Résumé des clusters</p>', unsafe_allow_html=True)

    INTERP_CLUSTERS = {
        0: "Presse dense — articles longs sur le procès. Journalisme de fond, profil des protagonistes.",
        1: "Commentaires de soutien directs — courts, émotionnels, adressés à Valérie personnellement.",
        2: "Articles factuels — couverture standard du procès, faits et chronologie.",
        3: "Commentaires engagés — plus longs, mêlent soutien et réflexion sur justice et société.",
        4: "Cluster pétition/mobilisation — liés à la campagne de soutien, signatures.",
        5: "Encouragements — très courts, adressés directement à Valérie.",
    }

    for _, row in df_c.iterrows():
        cluster_id = int(row['cluster'])
        with st.expander(
            f"**Cluster {cluster_id}** — {int(row['n_documents'])} documents · "
            f"Narratif dominant : {LABELS_FR.get(row['narratif_dominant'], row['narratif_dominant'])}",
            expanded=(cluster_id == 0),
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Documents", int(row['n_documents']))
            with col2:
                st.metric("% Articles", f"{row['pct_articles']:.0f}%")
            with col3:
                st.metric("% Commentaires", f"{row['pct_commentaires']:.0f}%")

            st.markdown(f"**Mots caractéristiques :** `{row['mots_cles']}`")
            st.markdown(f"**Interprétation :** {INTERP_CLUSTERS.get(cluster_id, '')}")

    st.divider()

    # Graphique composition des clusters
    st.markdown('<p class="section-header">Composition des clusters</p>', unsafe_allow_html=True)

    fig_cl = go.Figure()
    fig_cl.add_trace(go.Bar(
        name='Articles', x=[f"Cluster {int(r['cluster'])}" for _, r in df_c.iterrows()],
        y=df_c['pct_articles'], marker_color='#2E75B6',
    ))
    fig_cl.add_trace(go.Bar(
        name='Commentaires', x=[f"Cluster {int(r['cluster'])}" for _, r in df_c.iterrows()],
        y=df_c['pct_commentaires'], marker_color='#f1c44e',
    ))
    fig_cl.update_layout(
        barmode='stack', height=320,
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor='white',
        yaxis_title="% du cluster",
        legend=dict(orientation='h', y=1.1),
    )
    st.plotly_chart(fig_cl, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 4 : EXPLORER LE CORPUS
# ════════════════════════════════════════════════════════════════════════════

elif page == "💬 Explorer le corpus":

    st.markdown('<p class="main-title">💬 Explorer le corpus</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Articles de presse · Filtres par narratif, source et longueur · Les commentaires YouTube sont dans la page dédiée</p>', unsafe_allow_html=True)

    if df_articles.empty:
        st.error("Données de classification introuvables.")
        st.stop()

    # Filtres
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        filtre_narratif = st.multiselect(
            "Narratif",
            options=list(LABELS_FR.keys()),
            format_func=lambda x: LABELS_FR.get(x, x),
            default=[]
        )
    with col_f2:
        filtre_source = st.multiselect(
            "Type de source",
            options=sorted(df_articles['type_source'].dropna().unique().tolist()),
            default=[]
        )
    with col_f3:
        filtre_sitename = st.multiselect(
            "Titre de presse",
            options=sorted(df_articles['sitename'].dropna().unique().tolist()),
            default=[]
        )
    with col_f4:
        min_mots = st.slider("Longueur minimale (mots)", 0, 2000, 0, step=50)

    # Application des filtres
    df_filtered = df_articles.copy()
    if filtre_narratif:
        df_filtered = df_filtered[df_filtered['categorie_dominante'].isin(filtre_narratif)]
    if filtre_source:
        df_filtered = df_filtered[df_filtered['type_source'].isin(filtre_source)]
    if filtre_sitename:
        df_filtered = df_filtered[df_filtered['sitename'].isin(filtre_sitename)]
    if min_mots > 0:
        df_filtered = df_filtered[df_filtered['word_count'] >= min_mots]

    st.caption(f"**{len(df_filtered)} documents** correspondent aux filtres")
    st.divider()

    # Affichage des documents
    if df_filtered.empty:
        st.warning("Aucun document ne correspond aux filtres.")
    else:
        # Pagination
        docs_par_page = 10
        n_pages = max(1, (len(df_filtered) - 1) // docs_par_page + 1)
        page_num = st.number_input("Page", min_value=1, max_value=n_pages, value=1)
        debut = (page_num - 1) * docs_par_page
        fin   = debut + docs_par_page

        for _, row in df_filtered.iloc[debut:fin].iterrows():
            url  = row.get('url', '')
            doc  = corpus_index.get(url, {})
            texte = doc.get('text', '')

            with st.container():
                col_badge, col_info = st.columns([1, 5])

                with col_badge:
                    cat = row.get('categorie_dominante', '')
                    couleur = COULEURS.get(cat, '#aaa')
                    st.markdown(
                        f'<span class="narratif-badge" style="background:{couleur}">'
                        f'{LABELS_FR.get(cat, cat)}</span>',
                        unsafe_allow_html=True
                    )
                    type_emoji = "📰" if row.get('type_doc') == 'article' else "💬"
                    st.caption(f"{type_emoji} {row.get('type_doc', '')}")
                    st.caption(f"Score : {int(row.get('score_total', 0))}")

                with col_info:
                    titre = row.get('titre', url[:60])
                    st.markdown(f"**{titre}**")
                    st.caption(
                        f"📅 {row.get('date', '?')[:10]}  ·  "
                        f"🔗 {row.get('sitename', row.get('type_source', '?'))}  ·  "
                        f"📝 {int(row.get('word_count', 0))} mots"
                    )

                    if texte:
                        extrait = texte[:300].strip()
                        if len(texte) > 300:
                            extrait += "..."
                        st.markdown(
                            f'<div class="citation-box">{extrait}</div>',
                            unsafe_allow_html=True
                        )

                    if url:
                        st.markdown(f"[🔗 Source originale]({url})", unsafe_allow_html=False)

                st.divider()


# ════════════════════════════════════════════════════════════════════════════
# PAGE 5 : ÉVOLUTION TEMPORELLE
# ════════════════════════════════════════════════════════════════════════════

elif page == "📈 Évolution temporelle":

    st.markdown('<p class="main-title">📈 Évolution temporelle des narratifs</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Articles de presse uniquement · Évolution 2017–2023 · Pour les commentaires YouTube voir la page dédiée</p>', unsafe_allow_html=True)

    if df_articles.empty:
        st.error("Données introuvables.")
        st.stop()

    df_dates = df_articles[df_articles['date'].notna() & (df_articles['date'] != '')].copy()
    df_dates['date_parsed'] = pd.to_datetime(df_dates['date'], errors='coerce')
    df_dates = df_dates.dropna(subset=['date_parsed'])
    df_dates['annee_mois'] = df_dates['date_parsed'].dt.to_period('M').astype(str)

    if df_dates.empty:
        st.warning("Pas assez d'articles datés pour l'analyse temporelle.")
        st.stop()

    pivot = df_dates.groupby(['annee_mois', 'categorie_dominante']).size().unstack(fill_value=0)
    pivot = pivot.reset_index()

    fig_time = go.Figure()
    for cat in CATEGORIES:
        if cat in pivot.columns:
            fig_time.add_trace(go.Scatter(
                x=pivot['annee_mois'],
                y=pivot[cat],
                name=LABELS_FR.get(cat, cat),
                line=dict(color=COULEURS.get(cat, '#aaa')),
                mode='lines+markers',
                marker=dict(size=4),
            ))

    fig_time.update_layout(
        height=450,
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='#eee', tickangle=-45),
        yaxis=dict(showgrid=True, gridcolor='#eee', title='Nombre de documents'),
        legend=dict(orientation='v', x=1.01, y=1),
        hovermode='x unified',
    )

    st.plotly_chart(fig_time, use_container_width=True)

    # Moments clés
    st.markdown('<p class="section-header">Moments clés de l\'affaire</p>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("**Décembre 2012**\nMort de Daniel Polette. Arrestation de Valérie Bacot.")
    with col2:
        st.warning("**Janvier 2021**\nLancement de la pétition de soutien (600 000 signatures).")
    with col3:
        st.error("**Juin 2021**\nProcès aux Assises de Saône-et-Loire. Verdict : 4 ans dont 3 avec sursis.")
    with col4:
        st.success("**Septembre 2021**\nPublication du livre *Tout le monde savait*. Relance du débat.")


# ════════════════════════════════════════════════════════════════════════════
# PAGE 6 : COMMENTAIRES YOUTUBE
# ════════════════════════════════════════════════════════════════════════════

elif page == "🎬 Commentaires YouTube":

    st.markdown('<p class="main-title">🎬 Commentaires YouTube</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Analyse des 25 503 commentaires · 93 chaînes · 5 axes comparables à la presse</p>', unsafe_allow_html=True)

    df_yt = charger_commentaires_yt()

    if df_yt.empty:
        st.error("Données commentaires introuvables. Lancez d'abord : `python analyser_commentaires_youtube.py`")
        st.stop()

    # ── Métriques ──
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Commentaires", f"{len(df_yt):,}")
    with col2:
        st.metric("Vidéos uniques", df_yt['video_url'].nunique() if 'video_url' in df_yt.columns else "—")
    with col3:
        st.metric("Chaînes", df_yt['chaine'].nunique() if 'chaine' in df_yt.columns else "—")
    with col4:
        n_classe = (df_yt['narratif'] != 'non_classe').sum() if 'narratif' in df_yt.columns else 0
        st.metric("Avec narratif", f"{n_classe:,}")
    with col5:
        likes_med = int(df_yt['likes'].median()) if 'likes' in df_yt.columns else 0
        st.metric("Likes médians", likes_med)

    st.divider()

    onglets = st.tabs([
        "① Narratifs vs Presse",
        "② Évolution temporelle",
        "③ Polarité & affect",
        "④ Clusters",
        "⑤ Engagement",
    ])

    # ── Onglet 1 : Narratifs vs Presse ──
    with onglets[0]:
        st.markdown('<p class="section-header">Comparaison des narratifs : Commentaires vs Articles</p>', unsafe_allow_html=True)

        categories_yt = [c for c in CATEGORIES if c in df_yt.get('narratif', pd.Series()).unique() or True]

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("**Commentaires YouTube**")
            pct_yt = (df_yt['narratif'].value_counts(normalize=True) * 100
                      ).reindex(CATEGORIES + ['non_classe'], fill_value=0).reset_index()
            pct_yt.columns = ['narratif', 'pct']
            pct_yt['label'] = pct_yt['narratif'].map(LABELS_FR)
            pct_yt['couleur'] = pct_yt['narratif'].map(COULEURS)
            pct_yt = pct_yt.sort_values('pct', ascending=True)
            fig_yt = px.bar(pct_yt, x='pct', y='label', orientation='h',
                            color='narratif', color_discrete_map=COULEURS,
                            text=pct_yt['pct'].map('{:.1f}%'.format),
                            labels={'pct': '% des commentaires', 'label': ''})
            fig_yt.update_traces(textposition='outside', showlegend=False)
            fig_yt.update_layout(height=380, margin=dict(l=0, r=50, t=5, b=5),
                                 plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#eee'))
            st.plotly_chart(fig_yt, use_container_width=True)

        with col_r:
            st.markdown("**Articles de presse**")
            if not df_r.empty and 'categorie_dominante' in df_r.columns:
                df_art = df_r[df_r.get('type_doc', pd.Series(['article'] * len(df_r))) != 'commentaire'] if 'type_doc' in df_r.columns else df_r
                pct_art = (df_art['categorie_dominante'].value_counts(normalize=True) * 100
                           ).reindex(CATEGORIES + ['non_classe'], fill_value=0).reset_index()
                pct_art.columns = ['narratif', 'pct']
                pct_art['label'] = pct_art['narratif'].map(LABELS_FR)
                pct_art = pct_art.sort_values('pct', ascending=True)
                fig_art = px.bar(pct_art, x='pct', y='label', orientation='h',
                                 color='narratif', color_discrete_map=COULEURS,
                                 text=pct_art['pct'].map('{:.1f}%'.format),
                                 labels={'pct': '% des articles', 'label': ''})
                fig_art.update_traces(textposition='outside', showlegend=False)
                fig_art.update_layout(height=380, margin=dict(l=0, r=50, t=5, b=5),
                                      plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#eee'))
                st.plotly_chart(fig_art, use_container_width=True)
            else:
                st.info("Lancez `python Classifier_bacot.py` pour charger les résultats presse.")

        # Heatmap de comparaison
        if not df_r.empty and 'categorie_dominante' in df_r.columns:
            st.markdown('<p class="section-header">Écart commentaires − presse (en points de %)</p>', unsafe_allow_html=True)
            df_art2 = df_r[df_r.get('type_doc', pd.Series(['article']*len(df_r))) != 'commentaire'] if 'type_doc' in df_r.columns else df_r
            pct_yt_s  = df_yt['narratif'].value_counts(normalize=True) * 100
            pct_art_s = df_art2['categorie_dominante'].value_counts(normalize=True) * 100
            ecart = (pct_yt_s.reindex(CATEGORIES, fill_value=0) -
                     pct_art_s.reindex(CATEGORIES, fill_value=0)).rename('écart (pp)').reset_index()
            ecart.columns = ['narratif', 'ecart']
            ecart['label'] = ecart['narratif'].map(LABELS_FR)
            ecart = ecart.sort_values('ecart', ascending=True)
            colors_ecart = ['#e74c3c' if v < 0 else '#27ae60' for v in ecart['ecart']]
            fig_ecart = go.Figure(go.Bar(
                x=ecart['ecart'], y=ecart['label'], orientation='h',
                marker_color=colors_ecart, opacity=0.85,
                text=ecart['ecart'].map('{:+.1f} pp'.format), textposition='outside',
            ))
            fig_ecart.add_vline(x=0, line_color='#333', line_width=1)
            fig_ecart.update_layout(height=320, margin=dict(l=0, r=80, t=5, b=5),
                                    plot_bgcolor='white',
                                    xaxis=dict(showgrid=True, gridcolor='#eee', title='points de pourcentage'),
                                    yaxis=dict(title=''))
            st.plotly_chart(fig_ecart, use_container_width=True)
            st.caption("Vert = sur-représenté dans les commentaires · Rouge = sur-représenté dans la presse")

    # ── Onglet 2 : Évolution temporelle ──
    with onglets[1]:
        st.markdown('<p class="section-header">Évolution mensuelle des commentaires</p>', unsafe_allow_html=True)

        df_t = df_yt[df_yt['date'].notna()].copy()
        df_t['mois'] = df_t['date'].dt.to_period('M').astype(str)
        pivot_t = df_t.groupby(['mois', 'narratif']).size().unstack(fill_value=0).reset_index()

        fig_t = go.Figure()
        for cat in CATEGORIES:
            if cat in pivot_t.columns:
                fig_t.add_trace(go.Scatter(
                    x=pivot_t['mois'], y=pivot_t[cat],
                    name=LABELS_FR.get(cat, cat),
                    line=dict(color=COULEURS.get(cat, '#aaa')),
                    mode='lines', stackgroup='one', fill='tonexty',
                ))
        # Dates clés
        for date_str, label in [("2021-06", "Procès"), ("2021-07", "Verdict")]:
            fig_t.add_vline(x=date_str, line_dash="dash", line_color="#e74c3c", opacity=0.7,
                            annotation_text=label, annotation_position="top left")
        fig_t.update_layout(
            height=420, margin=dict(l=0, r=0, t=10, b=10),
            plot_bgcolor='white',
            xaxis=dict(showgrid=True, gridcolor='#eee', tickangle=-45),
            yaxis=dict(showgrid=True, gridcolor='#eee', title='Nb commentaires/mois'),
            hovermode='x unified',
            legend=dict(orientation='v', x=1.01, y=1, font=dict(size=10)),
        )
        st.plotly_chart(fig_t, use_container_width=True)

        # Narratifs par période
        st.markdown('<p class="section-header">Narratifs par période clé</p>', unsafe_allow_html=True)

        if 'periode' in df_yt.columns:
            periodes_ordre = ["Avant procès", "Procès (juin 2021)", "Verdict + été 2021", "2022", "2023", "2024+"]
            pivot_p = df_yt.groupby(['periode', 'narratif']).size().unstack(fill_value=0)
            pivot_p = pivot_p.reindex([p for p in periodes_ordre if p in pivot_p.index])
            pivot_p_pct = pivot_p.div(pivot_p.sum(axis=1), axis=0) * 100

            fig_p = go.Figure()
            for cat in CATEGORIES:
                if cat in pivot_p_pct.columns:
                    fig_p.add_trace(go.Bar(
                        name=LABELS_FR.get(cat, cat),
                        x=pivot_p_pct.index.tolist(),
                        y=pivot_p_pct[cat].values,
                        marker_color=COULEURS.get(cat, '#aaa'),
                    ))
            fig_p.update_layout(
                barmode='stack', height=380,
                margin=dict(l=0, r=0, t=10, b=10),
                plot_bgcolor='white',
                yaxis=dict(title='% des commentaires de la période'),
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    # ── Onglet 3 : Polarité & affect ──
    with onglets[2]:
        st.markdown('<p class="section-header">Polarité et affect des commentaires</p>', unsafe_allow_html=True)

        if 'polarite' not in df_yt.columns:
            st.warning("Colonne 'polarite' absente — relancez analyser_commentaires_youtube.py")
        else:
            COULEURS_POL = {
                'positif': '#27ae60', 'negatif': '#e74c3c',
                'empathique': '#3498db', 'hostile': '#e67e22', 'neutre': '#95a5a6',
            }
            col_g, col_d = st.columns([1, 2])

            with col_g:
                pol_counts = df_yt['polarite'].value_counts().reset_index()
                pol_counts.columns = ['polarite', 'n']
                pol_counts['couleur'] = pol_counts['polarite'].map(COULEURS_POL)
                fig_pol = px.pie(pol_counts, values='n', names='polarite',
                                 color='polarite', color_discrete_map=COULEURS_POL,
                                 hole=0.4, title='Distribution globale')
                fig_pol.update_traces(textposition='inside', textinfo='percent+label')
                fig_pol.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0),
                                      showlegend=False)
                st.plotly_chart(fig_pol, use_container_width=True)

            with col_d:
                pivot_pol_n = df_yt.groupby(['narratif', 'polarite']).size().unstack(fill_value=0)
                pivot_pol_n_pct = pivot_pol_n.div(pivot_pol_n.sum(axis=1), axis=0) * 100
                cats_ord = [c for c in CATEGORIES + ['non_classe'] if c in pivot_pol_n_pct.index]
                pivot_pol_n_pct = pivot_pol_n_pct.loc[cats_ord]

                fig_pol2 = go.Figure()
                for pol in ['positif', 'empathique', 'neutre', 'hostile', 'negatif']:
                    if pol in pivot_pol_n_pct.columns:
                        fig_pol2.add_trace(go.Bar(
                            name=pol, x=[LABELS_FR.get(c, c) for c in pivot_pol_n_pct.index],
                            y=pivot_pol_n_pct[pol].values,
                            marker_color=COULEURS_POL.get(pol, '#aaa'),
                        ))
                fig_pol2.update_layout(
                    barmode='stack', height=320,
                    title='Tonalité par narratif dominant',
                    margin=dict(l=0, r=0, t=40, b=10),
                    plot_bgcolor='white',
                    yaxis=dict(title='%'),
                    xaxis=dict(tickangle=-30),
                    legend=dict(font=dict(size=9)),
                )
                st.plotly_chart(fig_pol2, use_container_width=True)

            # Top commentaires positifs et négatifs
            col_pos, col_neg = st.columns(2)
            with col_pos:
                st.markdown("**Top 5 commentaires positifs (par likes)**")
                top_pos = df_yt[df_yt['polarite'] == 'positif'].nlargest(5, 'likes')[['texte', 'likes', 'chaine_courte']]
                for _, row in top_pos.iterrows():
                    st.markdown(f'<div class="citation-box">"{str(row["texte"])[:200]}..."<br>'
                                f'<span class="source-tag">{row.get("chaine_courte", "")} · {int(row["likes"])} likes</span></div>',
                                unsafe_allow_html=True)
            with col_neg:
                st.markdown("**Top 5 commentaires négatifs (par likes)**")
                top_neg = df_yt[df_yt['polarite'] == 'negatif'].nlargest(5, 'likes')[['texte', 'likes', 'chaine_courte']]
                for _, row in top_neg.iterrows():
                    st.markdown(f'<div class="citation-box">"{str(row["texte"])[:200]}..."<br>'
                                f'<span class="source-tag">{row.get("chaine_courte", "")} · {int(row["likes"])} likes</span></div>',
                                unsafe_allow_html=True)

    # ── Onglet 4 : Clusters ──
    with onglets[3]:
        st.markdown('<p class="section-header">Clustering TF-IDF / K-Means</p>', unsafe_allow_html=True)

        if 'cluster' not in df_yt.columns or df_yt['cluster'].isna().all():
            st.info("Clusters non disponibles — relancez analyser_commentaires_youtube.py")
        else:
            df_cl = df_yt[df_yt['cluster'].notna()].copy()
            df_cl['cluster'] = df_cl['cluster'].astype(int)

            # Distribution
            cl_counts = df_cl.groupby(['cluster', 'cluster_mots']).size().reset_index(name='n')
            cl_counts['label'] = cl_counts.apply(lambda r: f"C{int(r['cluster'])}: {str(r['cluster_mots'])[:40]}", axis=1)

            col_cl1, col_cl2 = st.columns([1, 2])
            with col_cl1:
                fig_cl = px.bar(cl_counts, x='n', y='label', orientation='h',
                                color='n', color_continuous_scale='Blues',
                                labels={'n': 'Commentaires', 'label': ''},
                                title='Taille des clusters')
                fig_cl.update_traces(showlegend=False)
                fig_cl.update_layout(height=320, margin=dict(l=0, r=20, t=40, b=10),
                                     plot_bgcolor='white', coloraxis_showscale=False)
                st.plotly_chart(fig_cl, use_container_width=True)

            with col_cl2:
                pivot_cl = df_cl.groupby(['cluster', 'narratif']).size().unstack(fill_value=0)
                pivot_cl_pct = pivot_cl.div(pivot_cl.sum(axis=1), axis=0) * 100
                fig_cl2 = go.Figure()
                for cat in CATEGORIES:
                    if cat in pivot_cl_pct.columns:
                        fig_cl2.add_trace(go.Bar(
                            name=LABELS_FR.get(cat, cat),
                            x=[f"C{c}" for c in pivot_cl_pct.index],
                            y=pivot_cl_pct[cat].values,
                            marker_color=COULEURS.get(cat, '#aaa'),
                        ))
                fig_cl2.update_layout(
                    barmode='stack', height=320, title='Composition en narratifs par cluster',
                    margin=dict(l=0, r=0, t=40, b=10),
                    plot_bgcolor='white',
                    yaxis=dict(title='%'),
                    legend=dict(font=dict(size=9)),
                )
                st.plotly_chart(fig_cl2, use_container_width=True)

            # Exemples par cluster
            st.markdown('<p class="section-header">Exemples par cluster</p>', unsafe_allow_html=True)
            cluster_sel = st.selectbox("Cluster", sorted(df_cl['cluster'].unique()),
                                       format_func=lambda c: f"Cluster {c} — {df_cl[df_cl['cluster']==c]['cluster_mots'].iloc[0][:50]}")
            exemples = df_cl[df_cl['cluster'] == cluster_sel].nlargest(5, 'likes')[['texte', 'likes', 'narratif', 'chaine_courte']]
            for _, row in exemples.iterrows():
                cat = row.get('narratif', '')
                st.markdown(
                    f'<div class="citation-box">{str(row["texte"])[:300]}'
                    f'<br><span class="source-tag">{row.get("chaine_courte", "")} · '
                    f'{int(row["likes"])} likes · {LABELS_FR.get(cat, cat)}</span></div>',
                    unsafe_allow_html=True,
                )

    # ── Onglet 5 : Engagement ──
    with onglets[4]:
        st.markdown('<p class="section-header">Sociologie de l\'engagement</p>', unsafe_allow_html=True)

        col_e1, col_e2 = st.columns(2)

        with col_e1:
            # Likes moyens par narratif
            likes_n = (df_yt.groupby('narratif')['likes']
                       .agg(moy='mean', med='median', total='sum', n='count')
                       .sort_values('moy', ascending=True).reset_index())
            likes_n['label'] = likes_n['narratif'].map(LABELS_FR)
            fig_eng = px.bar(likes_n, x='moy', y='label', orientation='h',
                             color='narratif', color_discrete_map=COULEURS,
                             text=likes_n['moy'].map('{:.1f}'.format),
                             labels={'moy': 'Likes moyens/commentaire', 'label': ''},
                             title='Likes moyens par narratif')
            fig_eng.update_traces(textposition='outside', showlegend=False)
            fig_eng.update_layout(height=360, margin=dict(l=0, r=60, t=40, b=10),
                                  plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#eee'))
            st.plotly_chart(fig_eng, use_container_width=True)

        with col_e2:
            # Top chaînes : volume + likes
            top_ch = df_yt.groupby('chaine_courte').agg(
                n=('likes', 'count'),
                likes_moy=('likes', 'mean'),
                likes_total=('likes', 'sum'),
            ).sort_values('n', ascending=False).head(12).reset_index()

            fig_ch = px.scatter(top_ch, x='n', y='likes_moy',
                                size='likes_total', text='chaine_courte',
                                labels={'n': 'Nb commentaires', 'likes_moy': 'Likes moyens',
                                        'likes_total': 'Likes totaux'},
                                title='Chaînes : volume vs engagement',
                                color='likes_moy', color_continuous_scale='Blues')
            fig_ch.update_traces(textposition='top center', textfont_size=8)
            fig_ch.update_layout(height=360, margin=dict(l=0, r=0, t=40, b=10),
                                 plot_bgcolor='white', coloraxis_showscale=False)
            st.plotly_chart(fig_ch, use_container_width=True)

        # Top commentaires globaux
        st.markdown('<p class="section-header">Top 10 commentaires les plus likés</p>', unsafe_allow_html=True)
        top10 = df_yt.nlargest(10, 'likes')[['texte', 'likes', 'chaine_courte', 'narratif', 'polarite', 'date']]
        for _, row in top10.iterrows():
            cat = row.get('narratif', '')
            pol = row.get('polarite', '')
            couleur_cat = COULEURS.get(cat, '#aaa')
            st.markdown(
                f'<div class="citation-box">'
                f'{str(row["texte"])[:280]}'
                f'<br><span class="source-tag">'
                f'{row.get("chaine_courte", "")} · {int(row["likes"])} likes · '
                f'<span class="narratif-badge" style="background:{couleur_cat}">{LABELS_FR.get(cat, cat)}</span>'
                f'</span></div>',
                unsafe_allow_html=True,
            )

        # Filtre par narratif
        st.divider()
        st.markdown("**Explorer par narratif**")
        narratif_sel = st.selectbox("Filtrer par narratif", ['(tous)'] + CATEGORIES,
                                    format_func=lambda x: LABELS_FR.get(x, x))
        n_afficher = st.slider("Nombre de commentaires", 5, 50, 10)
        df_filtree = df_yt if narratif_sel == '(tous)' else df_yt[df_yt['narratif'] == narratif_sel]
        for _, row in df_filtree.nlargest(n_afficher, 'likes').iterrows():
            cat = row.get('narratif', '')
            couleur_cat = COULEURS.get(cat, '#aaa')
            date_str = str(row['date'])[:10] if pd.notna(row.get('date')) else ''
            st.markdown(
                f'<div class="citation-box">'
                f'{str(row["texte"])[:300]}'
                f'<br><span class="source-tag">'
                f'{row.get("chaine_courte", "")} · {date_str} · {int(row["likes"])} likes · '
                f'<span class="narratif-badge" style="background:{couleur_cat}">{LABELS_FR.get(cat, cat)}</span>'
                f'</span></div>',
                unsafe_allow_html=True,
            )


# ════════════════════════════════════════════════════════════════════════════
# PAGE 7 : RECHERCHE QUALITATIVE
# ════════════════════════════════════════════════════════════════════════════

elif page == "🔍 Recherche qualitative":

    st.markdown('<p class="main-title">🔍 Recherche qualitative</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Cherche un mot ou une expression dans le corpus et explore les résultats</p>', unsafe_allow_html=True)

    if not corpus:
        st.error("Corpus introuvable.")
        st.stop()

    query = st.text_input(
        "Mot ou expression à rechercher",
        placeholder="ex : emprise, légitime défense, tout le monde savait...",
    )

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        filtre_type_q = st.radio(
            "Type de document",
            ['Tous', 'Articles uniquement', 'Commentaires uniquement'],
            horizontal=True,
        )
    with col_opt2:
        max_results = st.slider("Nombre max de résultats", 5, 50, 20)

    if query and len(query) >= 2:
        query_lower = query.lower()
        resultats = []

        for doc in corpus:
            texte = doc.get('text', '')
            if not texte or query_lower not in texte.lower():
                continue

            source = doc.get('source', '')
            type_doc = 'commentaire' if source == 'youtube_commentaire' else 'article'

            if filtre_type_q == 'Articles uniquement' and type_doc != 'article':
                continue
            if filtre_type_q == 'Commentaires uniquement' and type_doc != 'commentaire':
                continue

            # Trouve le passage avec le mot en contexte
            idx = texte.lower().find(query_lower)
            debut_ctx = max(0, idx - 150)
            fin_ctx   = min(len(texte), idx + 250)
            contexte  = texte[debut_ctx:fin_ctx].strip()

            # Met en gras le terme trouvé
            contexte_html = contexte.replace(
                query, f"**{query}**"
            ).replace(
                query.lower(), f"**{query.lower()}**"
            ).replace(
                query.capitalize(), f"**{query.capitalize()}**"
            )

            # Récupère le narratif depuis le CSV
            url = doc.get('url', '')
            narratif = 'non_classe'
            if not df_r.empty and url in df_r['url'].values:
                narratif = df_r[df_r['url'] == url]['categorie_dominante'].values[0]

            resultats.append({
                'url':      url,
                'titre':    doc.get('title', doc.get('video_titre', ''))[:80],
                'date':     doc.get('date', '')[:10],
                'sitename': doc.get('sitename', doc.get('chaine', '')),
                'type':     type_doc,
                'narratif': narratif,
                'contexte': contexte_html,
                'nb_occur': texte.lower().count(query_lower),
            })

        resultats.sort(key=lambda x: x['nb_occur'], reverse=True)
        resultats = resultats[:max_results]

        if not resultats:
            st.warning(f"Aucun document ne contient « {query} ».")
        else:
            st.success(f"**{len(resultats)} documents** contiennent « {query} »")

            for res in resultats:
                cat = res['narratif']
                couleur = COULEURS.get(cat, '#aaa')
                type_emoji = "📰" if res['type'] == 'article' else "💬"

                with st.container():
                    col_b, col_c = st.columns([1, 5])
                    with col_b:
                        st.markdown(
                            f'<span class="narratif-badge" style="background:{couleur}">'
                            f'{LABELS_FR.get(cat, cat)}</span>',
                            unsafe_allow_html=True
                        )
                        st.caption(f"{type_emoji} {res['type']}")
                        st.caption(f"🔁 {res['nb_occur']} occurrence(s)")
                    with col_c:
                        st.markdown(f"**{res['titre']}**")
                        st.caption(f"📅 {res['date']}  ·  🔗 {res['sitename']}")
                        st.markdown(
                            f'<div class="citation-box">...{res["contexte"]}...</div>',
                            unsafe_allow_html=True
                        )
                        if res['url']:
                            st.markdown(f"[🔗 Source]({res['url']})")
                    st.divider()

    elif query and len(query) < 2:
        st.caption("Entrez au moins 2 caractères.")

