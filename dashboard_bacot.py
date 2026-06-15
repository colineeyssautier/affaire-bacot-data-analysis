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
    st.markdown('<p class="subtitle">Analyse computationnelle des narratifs médiatiques et populaires · Corpus 2017–2023</p>', unsafe_allow_html=True)

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
        st.markdown('<p class="section-header">Distribution des narratifs dominants</p>', unsafe_allow_html=True)

        if not df_n.empty:
            df_plot = df_n[df_n['categorie_dominante'] != 'non_classe'].copy()
            df_plot['label'] = df_plot['categorie_dominante'].map(LABELS_FR)
            df_plot['couleur'] = df_plot['categorie_dominante'].map(COULEURS)
            df_plot = df_plot.sort_values('n_documents', ascending=True)

            fig = px.bar(
                df_plot,
                x='n_documents',
                y='label',
                orientation='h',
                color='categorie_dominante',
                color_discrete_map=COULEURS,
                text='n_documents',
                labels={'n_documents': 'Nombre de documents', 'label': ''},
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
        st.markdown('<p class="section-header">Répartition par type</p>', unsafe_allow_html=True)

        if not df_n.empty:
            df_pie = df_n[df_n['categorie_dominante'] != 'non_classe'].copy()
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
    st.markdown('<p class="subtitle">Classification lexicale en 8 catégories · Comparaison par type de source</p>', unsafe_allow_html=True)

    if df_r.empty:
        st.error("Fichier resultats_classification.csv introuvable.")
        st.stop()

    # Heatmap narratifs × sources
    st.markdown('<p class="section-header">Intensité des narratifs par type de source</p>', unsafe_allow_html=True)
    st.caption("Score moyen des termes caractéristiques par catégorie, selon le type de source. Plus la valeur est élevée, plus ce narratif est présent dans cette source.")

    score_cols = [f"score_{c}" for c in CATEGORIES if f"score_{c}" in df_r.columns]
    pivot = df_r.groupby('type_source')[score_cols].mean().round(1)
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
            n_docs = int((df_r['categorie_dominante'] == cat_choisie).sum())
            pct = n_docs / len(df_r) * 100
            st.metric("Documents dans cette catégorie", n_docs)
            st.metric("Part du corpus", f"{pct:.1f}%")

        # Distribution articles vs commentaires
        subset = df_r[df_r['categorie_dominante'] == cat_choisie]

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            type_counts = subset['type_doc'].value_counts().reset_index()
            type_counts.columns = ['type', 'n']
            fig_type = px.pie(
                type_counts, values='n', names='type',
                title="Articles vs Commentaires",
                color_discrete_sequence=['#2E75B6', '#f1c44e'],
                hole=0.3,
            )
            fig_type.update_layout(height=280, margin=dict(t=30, b=0))
            st.plotly_chart(fig_type, use_container_width=True)

        with col_g2:
            src_counts = subset['type_source'].value_counts().head(6).reset_index()
            src_counts.columns = ['source', 'n']
            fig_src = px.bar(
                src_counts, x='n', y='source',
                orientation='h',
                title="Top sources",
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
    st.markdown('<p class="subtitle">Navigue dans les 953 documents · Filtres par narratif, source et type</p>', unsafe_allow_html=True)

    if df_r.empty:
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
        filtre_type = st.multiselect(
            "Type de document",
            options=['article', 'commentaire'],
            default=[]
        )
    with col_f3:
        filtre_source = st.multiselect(
            "Type de source",
            options=sorted(df_r['type_source'].dropna().unique().tolist()),
            default=[]
        )
    with col_f4:
        min_mots = st.slider("Longueur minimale (mots)", 0, 2000, 0, step=50)

    # Application des filtres
    df_filtered = df_r.copy()
    if filtre_narratif:
        df_filtered = df_filtered[df_filtered['categorie_dominante'].isin(filtre_narratif)]
    if filtre_type:
        df_filtered = df_filtered[df_filtered['type_doc'].isin(filtre_type)]
    if filtre_source:
        df_filtered = df_filtered[df_filtered['type_source'].isin(filtre_source)]
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
    st.markdown('<p class="subtitle">Comment les discours ont évolué entre 2017 et 2023</p>', unsafe_allow_html=True)

    if df_r.empty:
        st.error("Données introuvables.")
        st.stop()

    df_dates = df_r[df_r['date'].notna() & (df_r['date'] != '')].copy()
    df_dates['date_parsed'] = pd.to_datetime(df_dates['date'], errors='coerce')
    df_dates = df_dates.dropna(subset=['date_parsed'])
    df_dates['annee_mois'] = df_dates['date_parsed'].dt.to_period('M').astype(str)

    if df_dates.empty:
        st.warning("Pas assez de documents datés pour l'analyse temporelle.")
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
# PAGE 6 : RECHERCHE QUALITATIVE
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

