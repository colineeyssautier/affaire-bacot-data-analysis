# Affaire Bacot — Media Corpus & Analysis API

A Python data pipeline that collects, cleans, classifies, and serves a corpus of **21,087 media documents** (390 press articles + 17,797 YouTube comments + 2,900 tweets) related to the *Valérie Bacot* criminal case (France, 2021). Built as a complete backend project: multi-source scraping → semi-automated curation → dual-track classification (lexical + LLM) → SQLite storage → async REST API → interactive dashboard.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture](#architecture)
3. [Data Pipeline](#data-pipeline)
   - [Multi-source URL collection](#1-multi-source-url-collection)
   - [Content extraction](#2-content-extraction)
   - [YouTube comments](#3-youtube-comments)
   - [Semi-automated curation](#4-semi-automated-curation)
   - [Lexical classification & clustering](#5-lexical-classification--clustering)
   - [LLM classification](#6-llm-classification)
   - [Rhetorical analysis](#7-rhetorical-analysis)
   - [YouTube comment analysis](#8-youtube-comment-analysis)
   - [Database initialization](#9-database-initialization)
4. [Narrative Lexicon](#narrative-lexicon)
5. [API Reference](#api-reference)
6. [Database Schema](#database-schema)
7. [Getting Started](#getting-started)
8. [Environment Variables](#environment-variables)
9. [Project Structure](#project-structure)
10. [Open Dataset](#open-dataset)
11. [Corpus — Background](#corpus--background)
12. [License](#license)

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.115, Uvicorn 0.30 |
| **ORM / DB** | SQLAlchemy 2.0 (async), aiosqlite 0.20, SQLite |
| **Scraping** | trafilatura 2.0, feedparser 6.0, gnews 0.4, googlenewsdecoder, yt-dlp, playwright 1.58 |
| **Data processing** | pandas 2.2, scikit-learn 1.8, scipy 1.17, numpy 2.4, nltk 3.9 |
| **Visualization** | Streamlit 1.58, Plotly 6.0, matplotlib 3.10, seaborn 0.13, wordcloud 1.9 |
| **LLM classification** | Groq API (via `groq` SDK) |
| **Export** | openpyxl 3.1 |
| **Language** | Python 3.10+ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA COLLECTION                        │
│                                                             │
│  Google News RSS ──┐                                        │
│  GNews API ────────┤                                        │
│  Bing Search ──────┼──► URL deduplication & resolution      │
│  Newspaper sources ┘                                        │
│  Manual curation ──────────────────────────────────────     │
│                                                             │
│  YouTube Data API ──────────► comment scraping (yt-dlp)    │
│  Wayback Machine ───────────► historical URL recovery       │
└─────────────────────────────────┬───────────────────────────┘
                                  │ raw JSON (corpus_bacot/)
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA PROCESSING                         │
│                                                             │
│  trafilatura extraction  →  text cleaning                   │
│  semi-auto curation (CSV review) → corpus_final.json        │
│                                                             │
│  ┌─────────────────────────┐  ┌──────────────────────────┐ │
│  │   LEXICAL TRACK         │  │   LLM TRACK              │ │
│  │  8-category keyword     │  │  Groq API classification  │ │
│  │  scoring + K-Means      │  │  on 400-doc subset        │ │
│  │  clustering (k=6)       │  │  → concordance analysis   │ │
│  └─────────────────────────┘  └──────────────────────────┘ │
│                                                             │
│  Rhetorical analysis → KWIC extraction → LLM annotation    │
│  YouTube comment analysis (temporal, sentiment, clusters)   │
└─────────────────────────────────┬───────────────────────────┘
                                  │ CSVs / JSONs (data/, analyse_bacot/)
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                       STORAGE                               │
│                                                             │
│  SQLite (bacot.db)                                          │
│  ├── documents   (21 087 rows — metadata + lexical + LLM)   │
│  ├── clusters    (6 rows — K-Means summary)                 │
│  └── narratifs   (8 rows — category breakdown)              │
└─────────────────────────────────┬───────────────────────────┘
                                  │ SQLAlchemy (async)
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                       FASTAPI                               │
│                                                             │
│  GET  /                    HTML interactive dashboard        │
│  GET  /info                API metadata & corpus stats       │
│  GET  /documents           paginated, 9 filters              │
│  GET  /documents/{id}      single document, all scores       │
│  GET  /search              full-text search on title         │
│  GET  /stats/narratifs     lexical category distribution     │
│  GET  /stats/narratifs_llm LLM distribution + concordance    │
│  GET  /stats/clusters      K-Means cluster profiles          │
│  GET  /stats/sources       source type & site statistics     │
│  GET  /stats/temporal      monthly evolution by narrative    │
│  POST /classify            score any free text live          │
│  GET  /lexique             full 8-category keyword lexicon   │
│  GET  /health              DB liveness check                 │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                                  ▼
                    Streamlit dashboard (dashboard_bacot.py)
                    http://localhost:8501
```

---

## Data Pipeline

### 1. Multi-source URL collection

Eight independent scrapers collect article URLs from different sources:

| Script | Source | Method |
|---|---|---|
| `scraper_rss_bacot.py` | Google News RSS | `feedparser` + `googlenewsdecoder` to resolve redirect URLs |
| `scraper_rss_etendu_bacot.py` | Extended RSS feeds | Broader coverage of French news sites |
| `scraper_bacot.py` | Google News | `gnews` Python library |
| `scraper_bing_bacot.py` | Bing News | Scraping of Bing search results |
| `scraper_journaux_bacot.py` | Major French newspapers | Direct site scraping (Le Monde, Libération, etc.) |
| `scraper_url_manuelles.py` | Curated list | Manually selected URLs from editorial review |
| `scraper_wayback_bacot.py` | Wayback Machine | Historical URL recovery via Internet Archive API |
| `scraper_nouvelles_urls.py` | Incremental updates | Batch-adds new URLs to existing corpus |

Each scraper outputs a deduplicated JSON file in `corpus_bacot/`. A common URL normalization step resolves redirects before final deduplication.

### 2. Content extraction

`trafilatura` handles HTML-to-text extraction with boilerplate removal (navigation, ads, sidebars). Each article is saved with structured metadata:

```json
{
  "url": "https://...",
  "titre": "Article title",
  "date": "2021-06-25",
  "sitename": "lemonde.fr",
  "type_source": "presse_nationale",
  "word_count": 847,
  "texte": "Full article text..."
}
```

Source types (`type_source`) assigned during extraction:

| Value | Description |
|---|---|
| `presse_nationale` | Major French national press |
| `presse_locale` | Regional press |
| `presse_militante` | Advocacy / feminist media |
| `institutionnel` | Institutional / governmental sources |
| `youtube_commentaire` | YouTube comment |
| `youtube_video` | YouTube video metadata |
| `autre` | Miscellaneous |

### 3. YouTube comments

`scraper_youtube_bacot.py` uses `yt-dlp` to collect comments from relevant videos. Three complementary scripts handle the full YouTube collection:

- `scraper_youtube_bacot.py` — initial comment scraping via YouTube Data API v3 (requires `YOUTUBE_API_KEY`)
- `scraper_decouverte_videos_bacot.py` — discovers relevant video URLs
- `scraper_nouveaux_commentaires.py` — incremental updates for new comments
- `integrer_nouveaux_commentaires.py` — merges new comments into the existing corpus

Comments are stored as `type_doc: commentaire` throughout the pipeline. The corpus contains **17,797 YouTube comments** from relevant videos.

### 4. Semi-automated curation

`trier_corpus.py` implements a two-mode CLI curation workflow:

```bash
# Mode 1 — generate a review spreadsheet
python trier_corpus.py --mode generer
# → writes corpus_bacot/a_reviewer.csv
# Open in Excel, set column D to 1 (keep) or 0 (discard) for each document

# Mode 2 — apply decisions, output clean corpus
python trier_corpus.py --mode appliquer
# → writes corpus_bacot/corpus_final.json
```

**Automatic pre-filters applied in Mode 1:**
- Minimum word count: 150 words for articles, 20 words for comments
- Domain blocklist (irrelevant aggregators, paywalled sites without content)
- Keyword relevance check (must mention Bacot or related terms)

**Output:** `corpus_bacot/corpus_final.json` — the clean, deduplicated, curated corpus used for all downstream analysis.

### 5. Lexical classification & clustering

`Classifier_bacot.py` is the core classification pipeline (650+ lines):

**Step 1 — Keyword scoring:** Each document is scored against 8 manually built keyword lexicons. Score = number of keyword matches per category. The category with the highest score becomes `categorie_dominante`.

**Step 2 — TF-IDF vectorization:** All document texts are vectorized using `TfidfVectorizer` with French stopwords removal.

**Step 3 — K-Means clustering (k=6):** Documents are grouped by lexical similarity, independent of the supervised classification. Each cluster gets a top-5 TF-IDF terms fingerprint.

**Step 4 — Outputs:**
- `analyse_bacot/resultats_classification.csv` — full classification results
- `analyse_bacot/resume_clusters.csv` — K-Means cluster summary
- `analyse_bacot/resume_narratifs.csv` — per-category narrative summary
- `analyse_bacot/*.png` — 5 analysis charts (distribution, source heatmap, PCA, temporal evolution)
- `analyse_bacot/wordclouds/` — word clouds per narrative category

**K-Means cluster interpretations:**

| Cluster | Profile |
|---|---|
| 0 | Dense press — long articles about the trial. In-depth journalism. |
| 1 | Direct support comments — short, emotional. |
| 2 | Factual articles — standard trial coverage. |
| 3 | Engaged comments — mix support + reflection on justice. |
| 4 | Petition/mobilization cluster — support campaign content. |
| 5 | Short encouragements — addressed directly to Valérie. |

### 6. LLM classification

`classifier_rhetorique_llm.py` sends a subset (~400 documents) to the **Groq API** for independent classification. This second classification track is used to validate and compare against the lexical approach.

**Workflow:**
- Requires `GROQ_API_KEY` in environment
- Checkpointed processing (resumes from `data/checkpoint_llm.json` if interrupted)
- Outputs `data/corpus_llm_classe.json` and `data/corpus_llm_resultats.json`
- Results are merged back into the main corpus via `fusionner_corpus_llm.py`
- Concordance rate between lexical and LLM classifications is exposed via `GET /stats/narratifs_llm`

The API stores LLM scores alongside lexical scores in the `documents` table (see [Database Schema](#database-schema)).

### 7. Rhetorical analysis

A specialized sub-pipeline analyzes primary source documents (trial transcripts, Senate hearings):

1. **`analyser_rhetorique.py`** — segments documents into rhetorical units (argument, rebuttal, testimony, etc.)
2. **`classifier_rhetorique_llm.py`** — annotates each unit with the Groq API for fine-grained rhetorical classification
3. **KWIC extraction** — generates `data/kwic_mots_pivots.json` with keyword-in-context (KWIC) extractions for pivot terms

**Outputs:**
- `data/rhetorique.json` — raw rhetorical segments
- `data/rhetorique_classifiee.json` — LLM-annotated segments
- `data/kwic_mots_pivots.json` — keyword-in-context data

### 8. YouTube comment analysis

`analyser_commentaires_youtube.py` (400+ lines) performs a 5-axis dedicated analysis of the comment corpus:

1. **Narrative classification** — applies the 8-category lexicon to comments specifically
2. **Temporal analysis** — tracks comment volume spikes around trial dates and anniversaries
3. **Sentiment/affect scoring** — lexical affect detection
4. **K-Means clustering** — separate clustering of the comment sub-corpus
5. **Engagement sociology** — correlates likes, channel types, and comment length patterns

**Outputs:** `analyse_bacot/commentaires/` + `data/resultats_commentaires_youtube.csv`

### 9. Database initialization

```bash
cd API_bacot/
python database.py
```

Reads `data/corpus_bacot_metadata.csv`, `data/corpus_youtube_commentaires.csv`, `analyse_bacot/resume_clusters.csv`, and `analyse_bacot/resume_narratifs.csv`, then populates `bacot.db` via SQLAlchemy bulk inserts. Run once — or re-run to reset the database from CSVs.

---

## Narrative Lexicon

Eight categories, each built from manually curated keyword lists. A document's score for a category = count of keyword occurrences in the text. The highest-scoring category becomes `categorie_dominante`.

| Category | Label (FR) | Intent |
|---|---|---|
| `soutien_victime` | Soutien à la victime | Compassion, validation of self-defense as survival |
| `remise_en_question` | Remise en question | Moral doubt, exploration of alternatives, possible condemnation |
| `legitime_defense` | Légitime défense | Legal discourse, precedent law, reform advocacy |
| `discours_feministe` | Discours féministe | Systemic analysis of gender-based violence |
| `emprise_psychologique` | Emprise psychologique | Mechanisms of coercion and psychological control |
| `silence_collectif` | Silence collectif | Institutional and social complicity |
| `sensationnalisme` | Sensationnalisme | Spectacle-driven coverage without critical lens |
| `jugement_moral` | Jugement moral | Moral evaluation, verdict framing, legality judgment |

**Sample keywords per category:**

| Category | Characteristic terms |
|---|---|
| `soutien_victime` | victime, survie, courage, innocente, soutien, solidarité, libération, pétition |
| `remise_en_question` | partir, quitter, fuir, police, gendarmerie, signaler, meurtre, autre solution |
| `legitime_defense` | légitime défense, défense différée, code pénal, jacqueline sauvage, réforme |
| `discours_feministe` | féminicide, féminisme, patriarcat, violences conjugales, contrôle coercitif, nous toutes |
| `emprise_psychologique` | emprise, manipulation, isolement, terreur, traumatisme, proxénétisme, menace |
| `silence_collectif` | savaient, silence, complice, voisin, institution, médecin, fermé les yeux |
| `sensationnalisme` | choquant, atroce, true crime, fait divers, documentaire, like, partager |
| `jugement_moral` | mérite, punir, condamner, coupable, responsable, pardon, juste, injuste |

Full lexicon exposed at `GET /lexique` and stored in `data/lexique_narratifs.json`.

---

## API Reference

Start the server:

```bash
cd API_bacot/
python database.py          # initialize SQLite (run once)
uvicorn main:app --reload
```

Base URL: `http://localhost:8000`  
Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

### `GET /`

Serves the embedded HTML interactive dashboard (`API_bacot/index.html`).

---

### `GET /info`

Returns API metadata and corpus statistics.

**Response:**
```json
{
  "projet": "Mythodologie — Corpus narratifs Valérie Bacot",
  "version": "1.0.0",
  "corpus": {
    "total_documents": 21087,
    "articles_presse": 390,
    "commentaires_youtube": 17797,
    "tweets": 2900,
    "periode": "2017–2023"
  },
  "endpoints": { "...": "..." },
  "licence": "CC BY 4.0 (données) / MIT (code)"
}
```

---

### `GET /documents`

Paginated document list with up to 9 simultaneous filters.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `narratif` | string | — | Filter by lexical dominant category (e.g. `discours_feministe`) |
| `narratif_llm` | string | — | Filter by LLM dominant category |
| `type_doc` | string | — | `article` or `commentaire` |
| `type_source` | string | — | `presse_nationale`, `presse_locale`, `presse_militante`, `institutionnel`, `autre` |
| `cluster` | int | — | K-Means cluster number (0–5) |
| `min_mots` | int | — | Minimum word count |
| `max_mots` | int | — | Maximum word count |
| `limit` | int | 20 | Results per page (max 100) |
| `offset` | int | 0 | Pagination offset |
| `tri` | string | `score_total` | Sort column: `score_total`, `word_count`, `date`, or any score column |
| `ordre` | string | `desc` | Sort direction: `asc` or `desc` |

**Response:**
```json
{
  "total": 21087,
  "limit": 20,
  "offset": 0,
  "resultats": [
    {
      "id": 1,
      "url": "https://...",
      "titre": "Article title",
      "date": "2021-06-25",
      "sitename": "lemonde.fr",
      "type_doc": "article",
      "type_source": "presse_nationale",
      "word_count": 847,
      "categorie_dominante": "discours_feministe",
      "score_total": 12.0,
      "label_narratif": "Discours féministe",
      "cluster": 0,
      "score_soutien_victime": 3.0,
      "score_remise_en_question": 0.0,
      "score_legitime_defense": 1.0,
      "score_discours_feministe": 5.0,
      "score_emprise_psychologique": 2.0,
      "score_silence_collectif": 1.0,
      "score_sensationnalisme": 0.0,
      "score_jugement_moral": 0.0,
      "categorie_dominante_llm": "discours_feministe",
      "score_soutien_victime_llm": 2.0,
      "score_remise_en_question_llm": 0.0,
      "score_legitime_defense_llm": 1.0,
      "score_discours_feministe_llm": 6.0,
      "score_emprise_psychologique_llm": 2.0,
      "score_silence_collectif_llm": 1.0,
      "score_sensationnalisme_llm": 0.0,
      "score_jugement_moral_llm": 0.0,
      "score_total_llm": 12.0
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/documents?narratif=discours_feministe&type_doc=article&tri=score_total&ordre=desc&limit=10"
```

---

### `GET /documents/{doc_id}`

Single document by ID. Returns all metadata, all narrative scores (lexical and LLM), and cluster assignment.

**Path parameter:** `doc_id` (integer, required)

**Response:** Same schema as a single object from `GET /documents`.

**Example:**
```bash
curl "http://localhost:8000/documents/42"
```

---

### `GET /search`

Full-text search on document titles.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | required | Search term (minimum 2 characters) |
| `type_doc` | string | — | Filter by `article` or `commentaire` |
| `limit` | int | 20 | Max results (up to 100) |

**Response:**
```json
{
  "query": "emprise",
  "total": 47,
  "resultats": [
    {
      "id": 12,
      "url": "https://...",
      "titre": "Valérie Bacot, sous emprise depuis l'enfance",
      "date": "2021-06-22",
      "sitename": "liberation.fr",
      "type_doc": "article",
      "categorie_dominante": "emprise_psychologique",
      "score_total": 9.0,
      "word_count": 1203,
      "label_narratif": "Emprise psychologique"
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/search?q=emprise&type_doc=article"
```

---

### `GET /stats/narratifs`

Distribution of the 8 lexical narrative categories across the full corpus.

**Response:**
```json
{
  "total_categories": 8,
  "narratifs": [
    {
      "categorie": "soutien_victime",
      "label_fr": "Soutien à la victime",
      "n_documents": 312,
      "pct_articles": 68.5,
      "mots_moyens": 423.7,
      "score_moyen": 4.2
    }
  ]
}
```

---

### `GET /stats/narratifs_llm`

Distribution of LLM classifications + concordance analysis between lexical and LLM tracks.

**Response:**
```json
{
  "n_classes_llm": 412,
  "taux_concordance": 73.8,
  "nb_concordants": 304,
  "distribution": [
    {
      "categorie": "soutien_victime",
      "label_fr": "Soutien à la victime",
      "n_documents": 148,
      "pct": 35.9,
      "score_moyen_llm": 3.9,
      "n_commentaires": 89,
      "n_tweets": 0
    }
  ]
}
```

---

### `GET /stats/clusters`

Summary of the 6 K-Means clusters with their lexical fingerprints and interpreted profiles.

**Response:**
```json
{
  "n_clusters": 6,
  "clusters": [
    {
      "cluster": 0,
      "n_documents": 187,
      "mots_cles": "procès, tribunal, avocat, défense, verdict",
      "narratif_dominant": "legitime_defense",
      "score_moyen": 6.3,
      "pct_articles": 91.4,
      "pct_commentaires": 8.6,
      "interpretation": "Presse dense — articles longs sur le procès. Journalisme de fond."
    }
  ]
}
```

---

### `GET /stats/sources`

Document count, average word count, and average narrative score per source type and per site.

**Response:**
```json
{
  "par_type_source": [
    {
      "type_source": "presse_nationale",
      "n_documents": 124,
      "mots_moyens": 912.4,
      "score_moyen": 5.7
    }
  ],
  "top_20_sites": [
    {
      "sitename": "lemonde.fr",
      "n_documents": 34,
      "score_moyen": 6.1
    }
  ],
  "narratifs_par_source": [
    {
      "type_source": "presse_nationale",
      "categorie_dominante": "discours_feministe",
      "n": 41
    }
  ]
}
```

---

### `GET /stats/temporal`

Monthly document distribution by narrative category — tracks how coverage evolved over time (2017–2023).

**Response:**
```json
{
  "distribution_temporelle": [
    {
      "annee_mois": "2021-06",
      "categorie_dominante": "soutien_victime",
      "n_documents": 87
    }
  ]
}
```

---

### `POST /classify`

Score any free text against the 8 lexical narrative lexicons in real time.

**Request body:**
```json
{
  "texte": "Valérie Bacot était sous emprise totale, elle se défendait"
}
```

Constraints: minimum 10 characters, maximum 50,000 characters.

**Response:**
```json
{
  "scores": {
    "soutien_victime": 3,
    "remise_en_question": 0,
    "legitime_defense": 1,
    "discours_feministe": 0,
    "emprise_psychologique": 2,
    "silence_collectif": 0,
    "sensationnalisme": 0,
    "jugement_moral": 0
  },
  "score_total": 6,
  "categorie_dominante": "soutien_victime",
  "label_fr": "Soutien à la victime",
  "nb_mots": 9,
  "nb_caracteres": 55
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"texte": "Valérie Bacot était sous emprise totale, elle se défendait"}'
```

---

### `GET /lexique`

Returns the full keyword lexicon for all 8 categories, including term lists and metadata.

**Response:**
```json
{
  "description": "Lexique narratif — 8 catégories de cadrage médiatique",
  "n_categories": 8,
  "categories": {
    "soutien_victime": {
      "label_fr": "Soutien à la victime",
      "n_termes": 20,
      "termes": ["victime", "survie", "courage", "..."]
    }
  }
}
```

---

### `GET /health`

Liveness check — verifies the API and database are reachable.

**Response:**
```json
{ "status": "ok", "documents_en_base": 21087 }
```

---

## Database Schema

```sql
-- Main documents table (21 087 rows)
CREATE TABLE documents (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    url                             TEXT UNIQUE NOT NULL,
    titre                           TEXT,
    date                            STRING(20),
    sitename                        STRING(100),
    type_doc                        STRING(20),    -- 'article' | 'commentaire' | 'tweet'
    type_source                     STRING(30),    -- 'presse_nationale' | 'presse_locale' | ...
    word_count                      INTEGER,
    categorie_dominante             STRING(40),    -- dominant lexical category
    score_total                     FLOAT,
    cluster                         INTEGER,       -- K-Means assignment (0–5)
    cluster_mots_cles               TEXT,          -- top TF-IDF terms for this cluster
    -- Lexical scores (one per category)
    score_soutien_victime           FLOAT DEFAULT 0,
    score_remise_en_question        FLOAT DEFAULT 0,
    score_legitime_defense          FLOAT DEFAULT 0,
    score_discours_feministe        FLOAT DEFAULT 0,
    score_emprise_psychologique     FLOAT DEFAULT 0,
    score_silence_collectif         FLOAT DEFAULT 0,
    score_sensationnalisme          FLOAT DEFAULT 0,
    score_jugement_moral            FLOAT DEFAULT 0,
    -- LLM scores (nullable — only set for the ~400-doc classified subset)
    categorie_dominante_llm         STRING(40),
    score_total_llm                 FLOAT,
    score_soutien_victime_llm       FLOAT,
    score_remise_en_question_llm    FLOAT,
    score_legitime_defense_llm      FLOAT,
    score_discours_feministe_llm    FLOAT,
    score_emprise_psychologique_llm FLOAT,
    score_silence_collectif_llm     FLOAT,
    score_sensationnalisme_llm      FLOAT,
    score_jugement_moral_llm        FLOAT
);

-- K-Means cluster profiles (6 rows)
CREATE TABLE clusters (
    id                INTEGER PRIMARY KEY,
    cluster           INTEGER UNIQUE,    -- 0–5
    n_documents       INTEGER,
    mots_cles         TEXT,              -- comma-separated top 5 TF-IDF terms
    narratif_dominant STRING(40),
    score_moyen       FLOAT,
    pct_articles      FLOAT,
    pct_commentaires  FLOAT
);

-- Narrative category summary (8 rows)
CREATE TABLE narratifs (
    id            INTEGER PRIMARY KEY,
    categorie     STRING(40) UNIQUE,
    n_documents   INTEGER,
    pct_articles  FLOAT,
    mots_moyens   FLOAT,
    score_moyen   FLOAT
);
```

---

## Getting Started

### Requirements

- Python 3.10+
- pip

### Installation

```bash
git clone https://github.com/colineeyssautier/Affaire-bacot-data-analysis.git
cd Affaire-bacot-data-analysis
```

Install API dependencies only (to run the API and dashboard):

```bash
pip install -r API_bacot/requirements.txt
pip install streamlit plotly
```

Install the full pipeline dependencies (to run scrapers, classifiers, analysis):

```bash
pip install -r requirements.txt
```

### Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys (see Environment Variables section)
```

### Run the API

```bash
cd API_bacot/
python database.py       # initialize SQLite from open dataset CSVs (run once)
uvicorn main:app --reload
```

API available at `http://localhost:8000`  
Swagger UI at `http://localhost:8000/docs`

### Run the dashboard

```bash
streamlit run dashboard_bacot.py
```

Opens at `http://localhost:8501`. No API key required.

### Run the full classification pipeline

```bash
python Classifier_bacot.py
# → reads corpus_bacot/corpus_final.json
# → writes analyse_bacot/ outputs (CSVs, PNGs, wordclouds)
# → run database.py afterward to reload the DB
```

### Run the LLM classification (requires Groq API key)

```bash
python classifier_rhetorique_llm.py
# → reads corpus_bacot/corpus_final.json
# → writes data/corpus_llm_classe.json (checkpointed — safe to interrupt)
python fusionner_corpus_llm.py
# → merges LLM results back into the corpus
```

### Run a scraper

```bash
# Google News RSS (no API key required)
python scraper_rss_bacot.py

# YouTube comments (requires YOUTUBE_API_KEY)
python scraper_youtube_bacot.py

# After scraping, merge and curate:
python fusionner_corpus.py
python trier_corpus.py --mode generer
# → review corpus_bacot/a_reviewer.csv manually
python trier_corpus.py --mode appliquer
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```dotenv
YOUTUBE_API_KEY=your_youtube_data_v3_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

| Variable | Required for | Where to obtain |
|---|---|---|
| `YOUTUBE_API_KEY` | `scraper_youtube_bacot.py`, `scraper_decouverte_videos_bacot.py` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) — enable "YouTube Data API v3" |
| `GROQ_API_KEY` | `classifier_rhetorique_llm.py` | [Groq Console](https://console.groq.com/keys) |

The API server (`main.py`) and the Streamlit dashboard do **not** require any API keys.

---

## Project Structure

```
Affaire-bacot-data-analysis/
│
├── API_bacot/                              FastAPI application
│   ├── main.py                             Routes, live classification logic, CORS
│   ├── database.py                         SQLAlchemy schema + CSV ingestion
│   ├── requirements.txt                    API-only dependencies
│   └── bacot.db                            SQLite database (generated on first run)
│
├── data/                                   Open dataset + analysis outputs (CC BY 4.0)
│   ├── corpus_bacot_metadata.csv           Metadata for 21 087 documents (no article text)
│   ├── corpus_youtube_commentaires.csv     Full text of 17 797 YouTube comments
│   ├── resultats_classification.csv        Full classification results (all 21 087 docs)
│   ├── lexique_narratifs.json              8-category keyword lexicon
│   ├── citations.json                      Representative quotes per narrative category
│   ├── rhetorique.json                     Rhetorical segments from primary sources
│   ├── rhetorique_classifiee.json          LLM-annotated rhetorical segments
│   ├── kwic_mots_pivots.json               Keyword-in-context (KWIC) extractions
│   ├── corpus_llm_classe.json              LLM classification results (~400 docs)
│   ├── corpus_llm_resultats.json           Final merged LLM results
│   ├── checkpoint_llm.json                 LLM processing checkpoint (resumable)
│   ├── articles_interface.json             Formatted data for API/dashboard
│   └── classification_llm.log             LLM processing log
│
├── corpus_bacot/                           Raw corpus data (not in open dataset)
│   ├── corpus_final.json                   Curated clean corpus (~21 087 docs)
│   ├── corpus_bacot.json                   Raw merged corpus before curation
│   └── a_reviewer.csv                      Manual curation spreadsheet
│
├── analyse_bacot/                          Analysis outputs
│   ├── resultats_classification.csv
│   ├── resume_clusters.csv
│   ├── resume_narratifs.csv
│   ├── 01_distribution_narratifs.png
│   ├── 02_narratifs_par_source.png
│   ├── 03_heatmap_narratifs_sources.png
│   ├── 04_clusters_pca.png
│   ├── 05_evolution_temporelle.png
│   ├── wordclouds/                         One word cloud PNG per narrative category
│   └── commentaires/                       YouTube comment-specific analysis outputs
│
├── Scrapers
│   ├── scraper_rss_bacot.py                Google News RSS + googlenewsdecoder
│   ├── scraper_rss_etendu_bacot.py         Extended RSS feeds
│   ├── scraper_bacot.py                    GNews Python library
│   ├── scraper_bing_bacot.py               Bing News search results
│   ├── scraper_journaux_bacot.py           Direct French newspaper scraping
│   ├── scraper_url_manuelles.py            Manually curated URL list
│   ├── scraper_wayback_bacot.py            Wayback Machine / Internet Archive
│   ├── scraper_youtube_bacot.py            YouTube comments via yt-dlp + API
│   ├── scraper_decouverte_videos_bacot.py  YouTube video discovery
│   ├── scraper_nouveaux_commentaires.py    Incremental comment updates
│   └── scraper_nouvelles_urls.py           Incremental URL updates
│
├── Classification & Analysis
│   ├── Classifier_bacot.py                 Lexical classification + K-Means clustering
│   ├── classifier_rhetorique_llm.py        Groq API LLM classification (checkpointed)
│   ├── analyser_commentaires_youtube.py    5-axis YouTube comment analysis
│   ├── analyser_rhetorique.py              Rhetorical unit segmentation
│   └── collecteur_urls_presse.py           URL aggregation utility
│
├── Corpus Management
│   ├── trier_corpus.py                     Semi-automated curation (2-mode CLI)
│   ├── fusionner_corpus.py                 Merge scraped JSON files
│   ├── fusionner_corpus_llm.py             Integrate LLM results into main corpus
│   ├── integrer_nouveaux_commentaires.py   Update corpus with new comments
│   └── preparer_corpus_interface.py        Format corpus for API/dashboard
│
├── Export & Visualization
│   ├── dashboard_bacot.py                  Streamlit interactive dashboard
│   ├── generer_dataset_open.py             Build publishable open dataset (CC BY 4.0)
│   ├── generer_graphiques.py               Generate analysis charts (matplotlib/seaborn)
│   ├── generer_graphiques_tweets.py        Twitter-specific visualizations
│   ├── extraire_citations.py               Extract representative quotes to Excel
│   └── generer_citations_json.py           Export quotes to data/citations.json
│
├── Utilities
│   ├── debug_scraper.py                    Scraper debugging
│   └── debug_citations.py                  Citation extraction debugging
│
├── .env.example                            API key template
├── requirements.txt                        Full pipeline dependencies
└── README.md
```

---

## Open Dataset

The `data/` directory contains all files usable without running any code. License: **CC BY 4.0**.

| File | Description | Rows |
|---|---|---|
| `corpus_bacot_metadata.csv` | Metadata for all 21,087 documents: URL, title, date, sitename, type, source type, word count, cluster, all 8 narrative scores, dominant category | 21 087 |
| `corpus_youtube_commentaires.csv` | Full text of YouTube comments | 17 797 |
| `resultats_classification.csv` | Complete classification output from `Classifier_bacot.py` | 21 087 |
| `lexique_narratifs.json` | 8-category keyword lexicon with descriptions and term lists | 8 categories |
| `citations.json` | Representative quotes per narrative category | — |
| `rhetorique.json` | Segmented rhetorical units from primary sources | — |
| `kwic_mots_pivots.json` | KWIC extractions for pivot terms across the corpus | — |

> Press article **texts are not included** for copyright reasons — only URLs and metadata are published. Comment texts are included, as they are user-generated content.

---

## Corpus — Background

Valérie Bacot was tried in June 2021 for the 2012 killing of her husband Daniel Polette, who had sexually abused her since she was 12, and later forced her into prostitution. After 25 years under his control, she shot him and buried his body in the woods. Her trial became a national event in France, prompting a petition with over **600,000 signatures** and intense media debate on:

- The limits of self-defense law in France (*légitime défense différée*)
- Psychological coercion (*emprise*) as a mitigating factor
- Institutional silence — neighbors, schools, doctors who knew and did nothing
- The feminist framing of femicide and gender-based violence

The corpus (2017–2023) tracks how press articles, YouTube comments, and tweets framed the case across these axes. The 8 narrative categories identify recurring rhetorical patterns: from feminist analysis and legal commentary to moral condemnation and true-crime sensationalism.

Valérie Bacot received a suspended sentence in June 2021. She published a memoir (*Tout le monde savait*, 2021) and became an advocate for victims of domestic violence.

---

## License

- **Data** (`data/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — free to use with attribution
- **Code**: [MIT](https://opensource.org/licenses/MIT)
