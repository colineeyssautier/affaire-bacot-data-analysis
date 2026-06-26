"""
database.py — Initialisation SQLite + SQLAlchemy
=================================================
Crée la base de données SQLite à partir des CSV d'analyse.
Lance une seule fois : python database.py

Structure :
    bacot.db
    ├── documents    (métadonnées + scores narratifs)
    ├── clusters     (résumé des clusters K-Means)
    └── narratifs    (résumé par catégorie)
"""

import json
import pandas as pd
from pathlib import Path
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text,
    MetaData, Table, text
)

# ─── Configuration ────────────────────────────────────────────────────────────

DB_PATH           = Path("bacot.db")
CSV_RESULTATS     = Path("../analyse_bacot/resultats_classification.csv")
CSV_CLUSTERS      = Path("../analyse_bacot/resume_clusters.csv")
CSV_NARRATIFS     = Path("../analyse_bacot/resume_narratifs.csv")
CORPUS_LLM_CLASSE = Path("../data/corpus_llm_classe.json")

CATEGORIES = [
    'soutien_victime', 'remise_en_question', 'legitime_defense',
    'discours_feministe', 'emprise_psychologique', 'silence_collectif',
    'sensationnalisme', 'jugement_moral',
]

# ─── Moteur SQLite ────────────────────────────────────────────────────────────

engine   = create_engine(f"sqlite:///{DB_PATH}", echo=False)
metadata = MetaData()

# ─── Définition des tables ────────────────────────────────────────────────────

documents_table = Table("documents", metadata,
    Column("id",                          Integer, primary_key=True, autoincrement=True),
    Column("url",                         Text,    nullable=False, unique=True),
    Column("titre",                       Text),
    Column("date",                        String(20)),
    Column("sitename",                    String(100)),
    Column("type_doc",                    String(20)),
    Column("type_source",                 String(30)),
    Column("word_count",                  Integer),
    Column("categorie_dominante",         String(40)),
    Column("score_total",                 Float),
    Column("cluster",                     Integer),
    Column("cluster_mots_cles",           Text),
    Column("score_soutien_victime",       Float, default=0),
    Column("score_remise_en_question",    Float, default=0),
    Column("score_legitime_defense",      Float, default=0),
    Column("score_discours_feministe",    Float, default=0),
    Column("score_emprise_psychologique", Float, default=0),
    Column("score_silence_collectif",     Float, default=0),
    Column("score_sensationnalisme",      Float, default=0),
    Column("score_jugement_moral",        Float, default=0),
    # Scores LLM (null pour les docs hors échantillon)
    Column("categorie_dominante_llm",         String(40)),
    Column("score_soutien_victime_llm",       Float),
    Column("score_remise_en_question_llm",    Float),
    Column("score_legitime_defense_llm",      Float),
    Column("score_discours_feministe_llm",    Float),
    Column("score_emprise_psychologique_llm", Float),
    Column("score_silence_collectif_llm",     Float),
    Column("score_sensationnalisme_llm",      Float),
    Column("score_jugement_moral_llm",        Float),
    Column("score_total_llm",                 Float),
)

clusters_table = Table("clusters", metadata,
    Column("id",                Integer, primary_key=True),
    Column("cluster",           Integer, unique=True),
    Column("n_documents",       Integer),
    Column("mots_cles",         Text),
    Column("narratif_dominant", String(40)),
    Column("score_moyen",       Float),
    Column("pct_articles",      Float),
    Column("pct_commentaires",  Float),
)

narratifs_table = Table("narratifs", metadata,
    Column("id",            Integer, primary_key=True),
    Column("categorie",     String(40), unique=True),
    Column("n_documents",   Integer),
    Column("pct_articles",  Float),
    Column("mots_moyens",   Float),
    Column("score_moyen",   Float),
)


# ─── Initialisation ───────────────────────────────────────────────────────────

def init_db():
    print(f"Initialisation de la base : {DB_PATH}")
    metadata.drop_all(engine)
    metadata.create_all(engine)

    with engine.begin() as conn:

        # ── Table documents ──
        if not CSV_RESULTATS.exists():
            print(f"  ⚠ CSV introuvable : {CSV_RESULTATS}")
        else:
            df = pd.read_csv(CSV_RESULTATS, encoding='utf-8-sig')
            df = df.where(pd.notna(df), None)

            # Vide la table
            conn.execute(documents_table.delete())

            # Construit les lignes
            rows = []
            seen_urls = set()

            for _, row in df.iterrows():
                url = str(row.get("url", ""))[:500]

                # Ignore les doublons d'URL
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                r = {
                    "url":          url,
                    "titre":        str(row["titre"])[:300] if row.get("titre") else None,
                    "date":         str(row["date"])[:20]   if row.get("date")  else None,
                    "sitename":     str(row["sitename"])[:100] if row.get("sitename") else None,
                    "type_doc":     str(row["type_doc"])[:20]  if row.get("type_doc") else None,
                    "type_source":  str(row["type_source"])[:30] if row.get("type_source") else None,
                    "word_count":   int(row["word_count"]) if row.get("word_count") is not None else None,
                    "categorie_dominante": str(row.get("categorie_dominante", ""))[:40],
                    "score_total":  float(row["score_total"]) if row.get("score_total") is not None else 0,
                    "cluster":      int(row["cluster"])   if pd.notna(row.get("cluster")) else None,
                    "cluster_mots_cles": str(row["cluster_mots_cles"]) if row.get("cluster_mots_cles") else None,
                }
                for cat in CATEGORIES:
                    col = f"score_{cat}"
                    r[col] = float(row[col]) if row.get(col) is not None else 0.0

                rows.append(r)

            if rows:
                conn.execute(documents_table.insert(), rows)
                print(f"  ✓ {len(rows)} documents insérés")

        # ── Table clusters ──
        if not CSV_CLUSTERS.exists():
            print(f"  ⚠ CSV introuvable : {CSV_CLUSTERS}")
        else:
            df_c = pd.read_csv(CSV_CLUSTERS, encoding='utf-8-sig')
            df_c = df_c.where(pd.notna(df_c), None)
            conn.execute(clusters_table.delete())

            rows_c = []
            for _, row in df_c.iterrows():
                rows_c.append({
                    "cluster":           int(row["cluster"]),
                    "n_documents":       int(row["n_documents"])   if row.get("n_documents")   is not None else 0,
                    "mots_cles":         str(row["mots_cles"])     if row.get("mots_cles")     else None,
                    "narratif_dominant": str(row["narratif_dominant"])[:40] if row.get("narratif_dominant") else None,
                    "score_moyen":       float(row["score_moyen"]) if row.get("score_moyen")   is not None else 0,
                    "pct_articles":      float(row["pct_articles"]) if row.get("pct_articles") is not None else 0,
                    "pct_commentaires":  float(row["pct_commentaires"]) if row.get("pct_commentaires") is not None else 0,
                })

            if rows_c:
                conn.execute(clusters_table.insert(), rows_c)
                print(f"  ✓ {len(rows_c)} clusters insérés")

        # ── Table narratifs ──
        if not CSV_NARRATIFS.exists():
            print(f"  ⚠ CSV introuvable : {CSV_NARRATIFS}")
        else:
            df_n = pd.read_csv(CSV_NARRATIFS, encoding='utf-8-sig')
            df_n = df_n.where(pd.notna(df_n), None)
            conn.execute(narratifs_table.delete())

            rows_n = []
            for _, row in df_n.iterrows():
                rows_n.append({
                    "categorie":    str(row.get("categorie_dominante", ""))[:40],
                    "n_documents":  int(row["n_documents"])  if row.get("n_documents")  is not None else 0,
                    "pct_articles": float(row["pct_articles"]) if row.get("pct_articles") is not None else 0,
                    "mots_moyens":  float(row["mots_moyens"]) if row.get("mots_moyens")  is not None else 0,
                    "score_moyen":  float(row["score_moyen"]) if row.get("score_moyen")  is not None else 0,
                })

            if rows_n:
                conn.execute(narratifs_table.insert(), rows_n)
                print(f"  ✓ {len(rows_n)} narratifs insérés")

        # ── Scores LLM ──
        if not CORPUS_LLM_CLASSE.exists():
            print(f"  ⚠ corpus LLM introuvable : {CORPUS_LLM_CLASSE}")
        else:
            with open(CORPUS_LLM_CLASSE, encoding="utf-8") as f:
                corpus_llm = json.load(f)

            llm_par_url = {
                d["url"]: d for d in corpus_llm
                if d.get("url") and d.get("categorie_dominante_llm") is not None
            }

            nb_maj = 0
            for url, d in llm_par_url.items():
                conn.execute(text("""
                    UPDATE documents SET
                        categorie_dominante_llm         = :cat_llm,
                        score_soutien_victime_llm       = :sv,
                        score_remise_en_question_llm    = :rq,
                        score_legitime_defense_llm      = :ld,
                        score_discours_feministe_llm    = :df,
                        score_emprise_psychologique_llm = :ep,
                        score_silence_collectif_llm     = :sc,
                        score_sensationnalisme_llm      = :ss,
                        score_jugement_moral_llm        = :jm,
                        score_total_llm                 = :total
                    WHERE url = :url
                """), {
                    "cat_llm": d.get("categorie_dominante_llm"),
                    "sv":    d.get("score_soutien_victime_llm"),
                    "rq":    d.get("score_remise_en_question_llm"),
                    "ld":    d.get("score_legitime_defense_llm"),
                    "df":    d.get("score_discours_feministe_llm"),
                    "ep":    d.get("score_emprise_psychologique_llm"),
                    "sc":    d.get("score_silence_collectif_llm"),
                    "ss":    d.get("score_sensationnalisme_llm"),
                    "jm":    d.get("score_jugement_moral_llm"),
                    "total": d.get("score_total_llm"),
                    "url":   url,
                })
                nb_maj += 1

            print(f"  ✓ {nb_maj} documents mis à jour avec scores LLM")

    print(f"\n✓ Base de données prête : {DB_PATH}")
    print("  Lance maintenant : python -m uvicorn main:app --reload")


if __name__ == "__main__":
    init_db()
