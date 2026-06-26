"""
main.py — API FastAPI, Corpus narratifs Valérie Bacot
======================================================
Projet Mythodologie · Prototype v1

Lancement :
    uvicorn main:app --reload

Documentation interactive :
    http://localhost:8000/docs

Endpoints :
    GET  /                          Info générale
    GET  /documents                 Liste des documents (filtres, pagination)
    GET  /documents/{id}            Un document par ID
    GET  /search                    Recherche textuelle dans les titres
    GET  /stats/narratifs           Distribution des 8 narratifs
    GET  /stats/clusters            Résumé des 6 clusters K-Means
    GET  /stats/sources             Répartition par type de source
    POST /classify                  Classifie un texte avec le lexique
"""

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import create_engine, text, select, func
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import re
import os

from database import (
    engine, documents_table, clusters_table, narratifs_table,
    CATEGORIES, init_db, DB_PATH
)

ROOT_DIR = Path(__file__).parent
PROJECT_DIR = ROOT_DIR.parent

# ─── Initialisation ───────────────────────────────────────────────────────────

# Crée la DB si elle n'existe pas encore
if not DB_PATH.exists():
    print("Base de données absente — initialisation automatique...")
    init_db()

app = FastAPI(
    title="API Narratifs Bacot — Projet Mythodologie",
    description=(
        "API d'accès au corpus sur l'affaire Valérie Bacot : articles de presse, "
        "tweets et commentaires YouTube. "
        "Classification lexicale en 8 catégories de narratifs, clustering K-Means."
    ),
    version="1.0.0",
    contact={
        "name": "Projet Mythodologie",
        "url":  "https://github.com/mythodologie/bacot-corpus",
    },
    license_info={
        "name": "CC BY 4.0 (données) / MIT (code)",
        "url":  "https://creativecommons.org/licenses/by/4.0/",
    },
)

# Fichiers statiques
app.mount("/static",       StaticFiles(directory=os.path.dirname(__file__)),           name="static")
app.mount("/data",         StaticFiles(directory=str(PROJECT_DIR / "data")),           name="data")
app.mount("/corpus_bacot", StaticFiles(directory=str(PROJECT_DIR / "corpus_bacot")),   name="corpus_bacot")

# CORS — permet l'accès depuis le dashboard Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─── Lexique pour classification à la volée ───────────────────────────────────

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
        "angleterre", "canada", "syndrome", "état de nécessité", "défense", "défendre", "défendu", "autodéfense", "défen",
    ],
    "discours_feministe": [
        "féminicide", "feminicide", "féministe", "féminisme", "patriarcat",
        "sexisme", "domination", "oppression", "violences faites aux femmes",
        "violences conjugales", "violence domestique", "emprise", "cycle de la violence",
        "contrôle coercitif", "nous toutes", "metoo", "systémique", "structurel",
        "inégalité", "droits des femmes",
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


# ─── Dépendance DB ────────────────────────────────────────────────────────────

def get_db():
    with engine.connect() as conn:
        yield conn


# ─── Utilitaires ──────────────────────────────────────────────────────────────

LABELS_FR = {
    "soutien_victime":        "💙 Soutien à la victime",
    "remise_en_question":     "❓ Remise en question",
    "legitime_defense":       "⚖️ Légitime défense",
    "discours_feministe":     "✊ Discours féministe",
    "emprise_psychologique":  "🔗 Emprise psychologique",
    "silence_collectif":      "🤫 Silence collectif",
    "sensationnalisme":       "📺 Sensationnalisme",
    "jugement_moral":         "🔍 Jugement moral",
    "non_classe":             "❔ Non classé",
}


def row_to_dict(row) -> dict:
    """Convertit une ligne SQLAlchemy en dictionnaire."""
    return dict(row._mapping)


def scorer_texte(texte: str) -> dict:
    """Calcule les scores narratifs d'un texte libre."""
    texte_lower = texte.lower()
    scores = {}
    for cat, termes in LEXIQUE.items():
        scores[cat] = sum(texte_lower.count(t) for t in termes)
    total = sum(scores.values())
    dominant = max(scores, key=scores.get) if total > 0 else "non_classe"
    return {
        "scores":            scores,
        "score_total":       total,
        "categorie_dominante": dominant,
        "label_fr":          LABELS_FR.get(dominant, dominant),
    }


# ════════════════════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════════════════════

# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def read_root():
    """Sert le dashboard HTML interactif."""
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


# ── Info API ──────────────────────────────────────────────────────────────────

@app.get("/info", tags=["Info"])
def root():
    """Informations générales sur l'API et le corpus."""
    with engine.connect() as conn:
        n_docs = conn.execute(
            text("SELECT COUNT(*) FROM documents")
        ).scalar()
        n_articles = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE type_doc = 'article'")
        ).scalar()
        n_comments = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE type_doc = 'commentaire'")
        ).scalar()

    return {
        "projet":      "Mythodologie — Corpus narratifs Valérie Bacot",
        "version":     "1.0.0",
        "description": (
            "Corpus sur l'affaire Valérie Bacot — articles de presse, tweets et "
            "commentaires YouTube. Classification lexicale en 8 catégories de narratifs."
        ),
        "corpus": {
            "total_documents": n_docs,
            "articles_presse": n_articles,
            "commentaires_youtube": n_comments,
            "periode": "2017–2023",
        },
        "endpoints": {
            "documents":    "/documents",
            "recherche":    "/search?q=emprise",
            "stats":        "/stats/narratifs",
            "classifier":   "POST /classify",
            "doc_api":      "/docs",
        },
        "licence":  "CC BY 4.0 (données) / MIT (code)",
        "github":   "https://github.com/mythodologie/bacot-corpus",
    }


# ── Documents ─────────────────────────────────────────────────────────────────

@app.get("/documents", tags=["Documents"])
def list_documents(
    narratif:     Optional[str] = Query(None, description="Filtrer par catégorie dominante (lexical)"),
    narratif_llm: Optional[str] = Query(None, description="Filtrer par catégorie dominante LLM"),
    type_doc:    Optional[str] = Query(None, description="'article' ou 'commentaire'"),
    type_source: Optional[str] = Query(None, description="Type de source"),
    cluster:     Optional[int] = Query(None, description="Numéro de cluster (0-5)"),
    min_mots:    Optional[int] = Query(None, description="Nombre minimum de mots"),
    max_mots:    Optional[int] = Query(None, description="Nombre maximum de mots"),
    limit:       int           = Query(20, ge=1, le=100, description="Résultats par page (max 100)"),
    offset:      int           = Query(0, ge=0, description="Décalage pour la pagination"),
    tri:         str           = Query("score_total", description="Colonne de tri"),
    ordre:       str           = Query("desc", description="'asc' ou 'desc'"),
):
    """
    Liste les documents avec filtres et pagination.

    **Exemples :**
    - `/documents?narratif=discours_feministe&type_doc=article`
    - `/documents?cluster=0&min_mots=500`
    - `/documents?type_source=presse_nationale&limit=50`
    """
    colonnes_valides = {
        "score_total", "word_count", "date", "score_soutien_victime",
        "score_discours_feministe", "score_legitime_defense",
        "score_silence_collectif", "score_emprise_psychologique",
        "score_total_llm", "score_soutien_victime_llm",
        "score_discours_feministe_llm", "score_legitime_defense_llm",
    }
    if tri not in colonnes_valides:
        tri = "score_total"
    if ordre not in ["asc", "desc"]:
        ordre = "desc"

    conditions = []
    params = {}

    if narratif:
        conditions.append("categorie_dominante = :narratif")
        params["narratif"] = narratif
    if narratif_llm:
        conditions.append("categorie_dominante_llm = :narratif_llm")
        params["narratif_llm"] = narratif_llm
    if type_doc:
        conditions.append("type_doc = :type_doc")
        params["type_doc"] = type_doc
    if type_source:
        conditions.append("type_source = :type_source")
        params["type_source"] = type_source
    if cluster is not None:
        conditions.append("cluster = :cluster")
        params["cluster"] = cluster
    if min_mots is not None:
        conditions.append("word_count >= :min_mots")
        params["min_mots"] = min_mots
    if max_mots is not None:
        conditions.append("word_count <= :max_mots")
        params["max_mots"] = max_mots

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM documents {where}"), params
        ).scalar()

        rows = conn.execute(
            text(f"""
                SELECT id, url, titre, date, sitename, type_doc, type_source,
                       word_count, categorie_dominante, score_total, cluster,
                       score_soutien_victime, score_remise_en_question,
                       score_legitime_defense, score_discours_feministe,
                       score_emprise_psychologique, score_silence_collectif,
                       score_sensationnalisme, score_jugement_moral,
                       categorie_dominante_llm, score_total_llm,
                       score_soutien_victime_llm, score_remise_en_question_llm,
                       score_legitime_defense_llm, score_discours_feministe_llm,
                       score_emprise_psychologique_llm, score_silence_collectif_llm,
                       score_sensationnalisme_llm, score_jugement_moral_llm
                FROM documents {where}
                ORDER BY {tri} {ordre}
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset}
        ).fetchall()

    docs = [row_to_dict(r) for r in rows]
    for d in docs:
        d["label_narratif"]     = LABELS_FR.get(d.get("categorie_dominante", ""), "")
        d["label_narratif_llm"] = LABELS_FR.get(d.get("categorie_dominante_llm") or "", "")

    return {
        "total":   total,
        "limit":   limit,
        "offset":  offset,
        "resultats": docs,
    }


@app.get("/documents/{doc_id}", tags=["Documents"])
def get_document(doc_id: int):
    """Récupère un document par son ID."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM documents WHERE id = :id"),
            {"id": doc_id}
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} introuvable")

    doc = row_to_dict(row)
    doc["label_narratif"]     = LABELS_FR.get(doc.get("categorie_dominante", ""), "")
    doc["label_narratif_llm"] = LABELS_FR.get(doc.get("categorie_dominante_llm") or "", "")
    return doc


# ── Recherche ─────────────────────────────────────────────────────────────────

@app.get("/search", tags=["Recherche"])
def search(
    q:        str           = Query(..., min_length=2, description="Terme à rechercher dans les titres"),
    type_doc: Optional[str] = Query(None, description="'article' ou 'commentaire'"),
    limit:    int           = Query(20, ge=1, le=100),
):
    """
    Recherche un terme dans les titres des documents.

    **Exemple :** `/search?q=emprise&type_doc=article`
    """
    conditions = ["titre LIKE :q"]
    params: dict = {"q": f"%{q}%"}

    if type_doc:
        conditions.append("type_doc = :type_doc")
        params["type_doc"] = type_doc

    where = f"WHERE {' AND '.join(conditions)}"

    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT id, url, titre, date, sitename, type_doc,
                       categorie_dominante, score_total, word_count
                FROM documents {where}
                ORDER BY score_total DESC
                LIMIT :limit
            """),
            {**params, "limit": limit}
        ).fetchall()

    resultats = [row_to_dict(r) for r in rows]
    for r in resultats:
        r["label_narratif"] = LABELS_FR.get(r.get("categorie_dominante", ""), "")

    return {
        "query":     q,
        "total":     len(resultats),
        "resultats": resultats,
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats/narratifs", tags=["Statistiques"])
def stats_narratifs():
    """
    Distribution des 8 catégories de narratifs dans le corpus.
    Inclut la répartition articles / commentaires par catégorie.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM narratifs ORDER BY n_documents DESC")
        ).fetchall()

    resultats = []
    for row in rows:
        d = row_to_dict(row)
        d["label_fr"] = LABELS_FR.get(d.get("categorie", ""), d.get("categorie", ""))
        resultats.append(d)

    return {
        "total_categories": len(resultats),
        "narratifs": resultats,
    }


@app.get("/stats/clusters", tags=["Statistiques"])
def stats_clusters():
    """
    Résumé des 6 clusters K-Means identifiés par similarité lexicale.
    """
    INTERPRETATIONS = {
        0: "Presse dense — articles longs sur le procès. Journalisme de fond.",
        1: "Commentaires de soutien directs — courts, émotionnels.",
        2: "Articles factuels — couverture standard du procès.",
        3: "Commentaires engagés — mêlent soutien et réflexion sur la justice.",
        4: "Cluster pétition/mobilisation — campagne de soutien.",
        5: "Encouragements courts — adressés directement à Valérie.",
    }

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM clusters ORDER BY cluster")
        ).fetchall()

    resultats = []
    for row in rows:
        d = row_to_dict(row)
        d["interpretation"] = INTERPRETATIONS.get(d.get("cluster"), "")
        d["label_narratif_dominant"] = LABELS_FR.get(
            d.get("narratif_dominant", ""), d.get("narratif_dominant", "")
        )
        resultats.append(d)

    return {
        "n_clusters": len(resultats),
        "clusters":   resultats,
    }


@app.get("/stats/narratifs_llm", tags=["Statistiques"])
def stats_narratifs_llm():
    """
    Distribution des catégories LLM et comparaison avec la classification lexicale.
    Inclut le taux de concordance LLM/lexical et le nombre de docs classifiés.
    """
    with engine.connect() as conn:
        total_llm = conn.execute(
            text("SELECT COUNT(*) FROM documents WHERE categorie_dominante_llm IS NOT NULL")
        ).scalar()

        dist = conn.execute(text("""
            SELECT categorie_dominante_llm as categorie,
                   COUNT(*) as n_documents,
                   AVG(score_total_llm) as score_moyen_llm,
                   SUM(CASE WHEN type_doc = 'commentaire' THEN 1 ELSE 0 END) as n_commentaires,
                   SUM(CASE WHEN type_doc = 'tweet'       THEN 1 ELSE 0 END) as n_tweets
            FROM documents
            WHERE categorie_dominante_llm IS NOT NULL
            GROUP BY categorie_dominante_llm
            ORDER BY n_documents DESC
        """)).fetchall()

        concordance = conn.execute(text("""
            SELECT COUNT(*) FROM documents
            WHERE categorie_dominante_llm IS NOT NULL
              AND categorie_dominante_llm = categorie_dominante
        """)).scalar()

    resultats = []
    for row in dist:
        d = row_to_dict(row)
        d["label_fr"] = LABELS_FR.get(d.get("categorie", ""), d.get("categorie", ""))
        d["pct"] = round(d["n_documents"] / total_llm * 100, 1) if total_llm else 0
        resultats.append(d)

    taux_concordance = round(concordance / total_llm * 100, 1) if total_llm else 0

    return {
        "n_classes_llm":      total_llm,
        "taux_concordance":   taux_concordance,
        "nb_concordants":     concordance,
        "distribution":       resultats,
    }


@app.get("/stats/sources", tags=["Statistiques"])
def stats_sources():
    """
    Répartition des documents par type de source et par site.
    """
    with engine.connect() as conn:
        par_type = conn.execute(text("""
            SELECT type_source,
                   COUNT(*) as n_documents,
                   AVG(word_count) as mots_moyens,
                   AVG(score_total) as score_moyen
            FROM documents
            WHERE type_source IS NOT NULL
            GROUP BY type_source
            ORDER BY n_documents DESC
        """)).fetchall()

        par_site = conn.execute(text("""
            SELECT sitename,
                   COUNT(*) as n_documents,
                   AVG(score_total) as score_moyen
            FROM documents
            WHERE sitename IS NOT NULL AND sitename != ''
            GROUP BY sitename
            ORDER BY n_documents DESC
            LIMIT 20
        """)).fetchall()

        par_narratif_source = conn.execute(text("""
            SELECT type_source, categorie_dominante, COUNT(*) as n
            FROM documents
            WHERE type_source IS NOT NULL
            GROUP BY type_source, categorie_dominante
            ORDER BY type_source, n DESC
        """)).fetchall()

    return {
        "par_type_source": [row_to_dict(r) for r in par_type],
        "top_20_sites":    [row_to_dict(r) for r in par_site],
        "narratifs_par_source": [row_to_dict(r) for r in par_narratif_source],
    }


@app.get("/stats/temporal", tags=["Statistiques"])
def stats_temporal():
    """
    Distribution temporelle des documents par mois et par narratif.
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT SUBSTR(date, 1, 7) as annee_mois,
                   categorie_dominante,
                   COUNT(*) as n_documents
            FROM documents
            WHERE date IS NOT NULL AND date != '' AND LENGTH(date) >= 7
            GROUP BY annee_mois, categorie_dominante
            ORDER BY annee_mois
        """)).fetchall()

    return {
        "distribution_temporelle": [row_to_dict(r) for r in rows]
    }


# ── Classification ────────────────────────────────────────────────────────────

@app.post("/classify", tags=["Classification"])
def classify_text(body: dict):
    """
    Classifie un texte libre avec le lexique de narratifs.

    **Corps de la requête :**
    ```json
    { "texte": "Valérie Bacot a agi par légitime défense, elle était sous emprise..." }
    ```

    **Retourne :** les scores pour chaque catégorie de narratif + la catégorie dominante.
    """
    texte = body.get("texte", "")
    if not texte or len(texte.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="Le champ 'texte' est requis et doit contenir au moins 10 caractères."
        )

    if len(texte) > 50000:
        texte = texte[:50000]

    resultat = scorer_texte(texte)
    resultat["nb_mots"] = len(texte.split())
    resultat["nb_caracteres"] = len(texte)

    return resultat


# ── Lexique ───────────────────────────────────────────────────────────────────

@app.get("/lexique", tags=["Classification"])
def get_lexique():
    """
    Retourne le lexique complet des 8 catégories de narratifs
    avec leurs termes caractéristiques.
    """
    return {
        "description": (
            "Lexique de classification lexicale des narratifs médiatiques "
            "autour de l'affaire Valérie Bacot. Construit manuellement. "
            "Version 1.0 — peut être enrichi."
        ),
        "n_categories": len(LEXIQUE),
        "categories": {
            cat: {
                "label_fr": LABELS_FR.get(cat, cat),
                "n_termes": len(termes),
                "termes":   termes,
            }
            for cat, termes in LEXIQUE.items()
        }
    }


# ── Healthcheck ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["Info"])
def health():
    """Vérifie que l'API et la base de données sont opérationnelles."""
    try:
        with engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        return {"status": "ok", "documents_en_base": n}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
