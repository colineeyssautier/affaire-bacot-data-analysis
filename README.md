# Affaire Bacot — Media Corpus & Analysis API

A Python data pipeline that collects, cleans, classifies, and serves a corpus of 953 media documents (press articles + YouTube comments) related to the *Valérie Bacot* criminal case (France, 2021). Built as a full backend project: multi-source scraping → SQLite storage → async REST API → interactive dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API** | FastAPI 0.115, Uvicorn |
| **ORM / DB** | SQLAlchemy 2.0 (async), aiosqlite 0.20, SQLite |
| **Scraping** | trafilatura, feedparser, gnews, googlenewsdecoder, yt-dlp |
| **Data processing** | pandas 2.2 |
| **Dashboard** | Streamlit, Plotly |
| **Language** | Python 3.14 |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  DATA COLLECTION                    │
│                                                     │
│  Google News RSS ──┐                                │
│  GNews API ────────┤                                │
│  Bing Search ──────┼──► URL deduplication           │
│  DuckDuckGo ───────┤    & resolution                │
│  Newspaper sources ┘                                │
│                                                     │
│  YouTube API ──────────► comment scraping           │
└─────────────────────────────────┬───────────────────┘
                                  │ raw JSON
                                  ▼
┌─────────────────────────────────────────────────────┐
│                DATA PROCESSING                      │
│                                                     │
│  trafilatura extraction  →  text cleaning           │
│  semi-auto curation (CSV review)                    │
│  lexical classification  →  8 narrative categories  │
│  K-Means clustering      →  6 groups                │
└─────────────────────────────────┬───────────────────┘
                                  │ CSVs
                                  ▼
┌─────────────────────────────────────────────────────┐
│                    STORAGE                          │
│                                                     │
│  SQLite (bacot.db)                                  │
│  ├── documents   (953 rows — metadata + scores)     │
│  ├── clusters    (6 rows — K-Means summary)         │
│  └── narratifs   (8 rows — category breakdown)      │
└─────────────────────────────────┬───────────────────┘
                                  │ SQLAlchemy
                                  ▼
┌─────────────────────────────────────────────────────┐
│                   FASTAPI                           │
│                                                     │
│  GET  /documents        paginated, multi-filter     │
│  GET  /documents/{id}   single document             │
│  GET  /search           full-text search on title   │
│  GET  /stats/*          aggregate statistics        │
│  POST /classify         score any free text         │
│  GET  /lexique          expose the keyword lexicon  │
│  GET  /health           DB liveness check           │
└─────────────────────────────────────────────────────┘
```

---

## Data Pipeline

### 1. Multi-source URL collection

Five independent scrapers collect article URLs:

- `scraper_rss_bacot.py` — Google News RSS feed via `feedparser` + `googlenewsdecoder` to resolve encoded redirect URLs
- `scraper_bacot.py` — Google News via `gnews` library
- `scraper_bing_bacot.py` — Bing News search results
- `scraper_journaux_bacot.py` — targeted scraping of major French newspaper sites
- `scraper_url_manuelles.py` — manually curated URL list

Each source outputs a deduplicated JSON file in `corpus_bacot/`.

### 2. Content extraction

`trafilatura` handles HTML-to-text extraction with boilerplate removal. Each article is saved with structured metadata: `url`, `title`, `date`, `sitename`, `word_count`, `text`.

### 3. YouTube comments

`scraper_youtube_bacot.py` collects comments from relevant videos using `yt-dlp`. Comments are treated as a separate document type (`type_doc: commentaire`) throughout the pipeline.

### 4. Semi-automated curation

`trier_corpus.py` runs in two modes:

```bash
# Mode 1 — generate a CSV review file
python trier_corpus.py --mode generer
# → opens corpus_bacot/a_reviewer.csv in Excel, manually flag each doc (1=keep / 0=discard)

# Mode 2 — apply decisions, produce clean corpus
python trier_corpus.py --mode appliquer
# → outputs corpus_bacot/corpus_final.json
```

### 5. Lexical classification

`classifier_bacot.py` scores every document against 8 manually built keyword lexicons:

| Category | Description |
|---|---|
| `soutien_victime` | Support for the defendant |
| `remise_en_question` | Questioning her choices |
| `legitime_defense` | Self-defense legal discourse |
| `discours_feministe` | Feminist framing |
| `emprise_psychologique` | Psychological coercion |
| `silence_collectif` | Collective silence / bystanders |
| `sensationnalisme` | True crime / sensationalist coverage |
| `jugement_moral` | Moral judgment framing |

Each document receives a score per category. The dominant category is stored in `categorie_dominante`.

K-Means clustering (k=6) groups documents by lexical similarity, independent of the supervised classification.

### 6. Database initialization

```bash
cd API_bacot/
python database.py
```

Reads the classification CSVs and populates `bacot.db` via SQLAlchemy bulk inserts.

---

## API Reference

Start the server:

```bash
cd API_bacot/
uvicorn main:app --reload
# Interactive docs at http://localhost:8000/docs
```

### Endpoints

#### `GET /documents`

Paginated document list with multiple optional filters.

| Parameter | Type | Description |
|---|---|---|
| `narratif` | string | Filter by dominant narrative category |
| `type_doc` | string | `article` or `commentaire` |
| `type_source` | string | Source type (e.g. `presse_nationale`) |
| `cluster` | int | K-Means cluster number (0–5) |
| `min_mots` | int | Minimum word count |
| `max_mots` | int | Maximum word count |
| `limit` | int | Results per page (max 100, default 20) |
| `offset` | int | Pagination offset |
| `tri` | string | Sort column |
| `ordre` | string | `asc` or `desc` |

```bash
# Example: feminist articles, sorted by score
curl "http://localhost:8000/documents?narratif=discours_feministe&type_doc=article&limit=10"
```

#### `GET /documents/{id}`

Single document by ID. Returns all metadata, narrative scores, and cluster assignment.

#### `GET /search`

Full-text search on document titles.

```bash
curl "http://localhost:8000/search?q=emprise&type_doc=article"
```

#### `GET /stats/narratifs`

Distribution of the 8 narrative categories across the corpus, with article/comment breakdown per category.

#### `GET /stats/clusters`

Summary of the 6 K-Means clusters with interpreted profiles.

#### `GET /stats/sources`

Document count, average word count, and average narrative score per source type and per site (top 20).

#### `GET /stats/temporal`

Monthly document distribution by narrative category — tracks how coverage evolved over time (2017–2023).

#### `POST /classify`

Score any free text against the 8 narrative lexicons. Useful for testing new content.

```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"texte": "Valérie Bacot était sous emprise totale, elle se défendait"}'
```

Response:
```json
{
  "scores": {
    "soutien_victime": 3,
    "emprise_psychologique": 2,
    "legitime_defense": 1,
    ...
  },
  "score_total": 8,
  "categorie_dominante": "soutien_victime",
  "label_fr": "Soutien à la victime",
  "nb_mots": 9,
  "nb_caracteres": 55
}
```

#### `GET /lexique`

Returns the full keyword lexicon for all 8 categories.

#### `GET /health`

Liveness check — verifies the API and database are reachable.

```json
{ "status": "ok", "documents_en_base": 953 }
```

---

## Database Schema

```sql
-- Main documents table
CREATE TABLE documents (
    id                          INTEGER PRIMARY KEY,
    url                         TEXT,
    titre                       TEXT,
    date                        TEXT,
    sitename                    TEXT,
    type_doc                    TEXT,   -- 'article' | 'commentaire'
    type_source                 TEXT,
    word_count                  INTEGER,
    categorie_dominante         TEXT,
    score_total                 INTEGER,
    cluster                     INTEGER,
    -- narrative scores (one column per category)
    score_soutien_victime       INTEGER,
    score_remise_en_question    INTEGER,
    score_legitime_defense      INTEGER,
    score_discours_feministe    INTEGER,
    score_emprise_psychologique INTEGER,
    score_silence_collectif     INTEGER,
    score_sensationnalisme      INTEGER,
    score_jugement_moral        INTEGER
);

-- K-Means cluster profiles
CREATE TABLE clusters (
    cluster              INTEGER PRIMARY KEY,
    n_documents          INTEGER,
    narratif_dominant    TEXT,
    mots_moyens          REAL
);

-- Narrative category summary
CREATE TABLE narratifs (
    categorie       TEXT PRIMARY KEY,
    n_documents     INTEGER,
    n_articles      INTEGER,
    n_commentaires  INTEGER,
    score_moyen     REAL
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
pip install -r API_bacot/requirements.txt
```

### Run the API

```bash
cd API_bacot/
python database.py   # initialize SQLite from the open dataset CSVs (run once)
uvicorn main:app --reload
```

API available at `http://localhost:8000` — interactive Swagger docs at `http://localhost:8000/docs`.

### Run the dashboard

```bash
pip install streamlit plotly
streamlit run dashboard_bacot.py
```

Opens at `http://localhost:8501`.

---

## Project Structure

```
Affaire-bacot-data-analysis/
│
├── API_bacot/                      FastAPI application
│   ├── main.py                     Routes, classification logic, CORS
│   ├── database.py                 SQLAlchemy schema + CSV ingestion
│   ├── requirements.txt
│   └── bacot.db                    SQLite database (generated on first run)
│
├── data/                           Open dataset (CC BY 4.0)
│   ├── corpus_bacot_metadata.csv   Metadata for all 953 documents
│   ├── corpus_youtube_commentaires.csv
│   ├── citations.json              Representative quotes per narrative
│   ├── lexique_narratifs.json      8-category keyword lexicon
│   └── rhetorique.json
│
├── scraper_rss_bacot.py            Google News RSS scraper
├── scraper_bacot.py                GNews API scraper
├── scraper_bing_bacot.py           Bing News scraper
├── scraper_journaux_bacot.py       Newspaper-targeted scraper
├── scraper_url_manuelles.py        Manual URL list scraper
├── scraper_youtube_bacot.py        YouTube comment scraper
│
├── trier_corpus.py                 Semi-automated curation (2-mode CLI)
├── extraire_citations.py           Qualitative quote extraction to Excel
├── generer_citations_json.py       Export representative quotes to JSON
├── generer_dataset_open.py         Build the publishable open dataset
├── debug_citations.py
│
└── dashboard_bacot.py              Streamlit interactive dashboard
```

---

## Open Dataset

The `data/` directory contains files that can be used without running any code:

| File | Content |
|---|---|
| `corpus_bacot_metadata.csv` | Metadata for 953 documents (URL, title, date, source, narrative scores) |
| `corpus_youtube_commentaires.csv` | Full text of 739 YouTube comments |
| `lexique_narratifs.json` | 8 narrative categories with their characteristic keywords |
| `citations.json` | Representative quotes per narrative category |

> Press article **texts are not included** for copyright reasons — only URLs and metadata are published.

License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

---

## Corpus — Background

Valérie Bacot killed her husband in 2012 after 25 years of rape, abuse, and forced prostitution. Her 2021 trial sparked a major public debate in France on self-defense law, domestic violence, and institutional silence. A petition in her support gathered over 600,000 signatures.

This project documents the media narratives that emerged around the case: how did press articles and YouTube comments frame her story? The lexical classification identifies 8 recurring narrative patterns in the corpus (2017–2023).

---

## License

- **Data** (`data/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Code**: [MIT](https://opensource.org/licenses/MIT)
