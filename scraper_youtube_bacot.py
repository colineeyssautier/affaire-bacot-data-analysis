"""
Scraper YouTube commentaires — Affaire Valérie Bacot
=====================================================
Utilise l'API YouTube Data v3 pour :
  1. Rechercher les vidéos sur l'affaire Bacot
  2. Récupérer les commentaires de chaque vidéo
  3. Filtrer et sauvegarder comme documents du corpus

Installation :
    pip install google-api-python-client pandas

Usage :
    1. Crée une clé API YouTube sur console.cloud.google.com
    2. Colle ta clé dans YOUTUBE_API_KEY ci-dessous
    3. python scraper_youtube_bacot.py
"""

import os
import json
import time
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ─── Requêtes de recherche ────────────────────────────────────────────────────

QUERIES_VIDEO = [
    "Valérie Bacot procès",
    "Valérie Bacot reportage",
    "Valérie Bacot interview",
    "Valérie Bacot Daniel Polette",
    "Valérie Bacot Sept à Huit",
    "affaire Bacot féminicide",
    "Valérie Bacot livre",
]

# ─── Configuration ────────────────────────────────────────────────────────────

MAX_VIDEOS_PAR_REQUETE = 10    # vidéos récupérées par requête
MAX_COMMENTAIRES_PAR_VIDEO = 500  # commentaires max par vidéo
MIN_CHARS_COMMENTAIRE = 100    # longueur minimale d'un commentaire à garder
MIN_LIKES_COMMENTAIRE = 0      # likes minimum (0 = tous)
OUTPUT_DIR = Path("corpus_bacot")
DELAY = 1.0

# Mots-clés pour filtrer les commentaires pertinents
# (si vide, tous les commentaires suffisamment longs sont gardés)
MOTS_CLES_FILTRE = [
    "bacot", "valerie", "valérie", "polette",
    "violence", "conjugale", "feminicide", "féminicide",
    "victime", "assassin", "mari", "procès", "proces",
    "condamn", "acquitt", "légitim", "legitim", "défense",
    "emprise", "pétition",
]

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_youtube.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)


# ─── Initialisation API ───────────────────────────────────────────────────────

def init_youtube():
    if not YOUTUBE_API_KEY:
        log.error("⚠ Variable d'environnement YOUTUBE_API_KEY manquante.")
        log.error("Copie .env.example en .env et renseigne ta clé YouTube Data v3.")
        return None
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


# ─── Étape 1 : recherche de vidéos ───────────────────────────────────────────

def rechercher_videos(youtube, query: str) -> list[dict]:
    """
    Recherche des vidéos YouTube sur une requête et retourne
    leurs métadonnées (id, titre, chaîne, date, vues, likes).
    """
    try:
        response = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=MAX_VIDEOS_PAR_REQUETE,
            relevanceLanguage="fr",
            regionCode="FR",
            order="relevance",
        ).execute()

        videos = []
        for item in response.get("items", []):
            video_id = item["id"].get("videoId", "")
            if not video_id:
                continue

            snippet = item.get("snippet", {})
            videos.append({
                "video_id":    video_id,
                "url":         f"https://www.youtube.com/watch?v={video_id}",
                "titre":       snippet.get("title", ""),
                "chaine":      snippet.get("channelTitle", ""),
                "date":        snippet.get("publishedAt", ""),
                "description": snippet.get("description", "")[:300],
                "query":       query,
            })

        return videos

    except HttpError as e:
        log.warning(f"  Erreur API recherche '{query}' : {e}")
        return []


def collecter_videos(youtube, queries: list[str]) -> list[dict]:
    """Collecte toutes les vidéos pour toutes les requêtes, sans doublons."""
    toutes = {}

    for query in queries:
        log.info(f"Recherche vidéos : '{query}'")
        videos = rechercher_videos(youtube, query)
        nouvelles = 0

        for v in videos:
            if v["video_id"] not in toutes:
                toutes[v["video_id"]] = v
                nouvelles += 1

        log.info(f"  → {len(videos)} vidéos trouvées, {nouvelles} nouvelles")
        time.sleep(DELAY)

    log.info(f"Total vidéos uniques : {len(toutes)}")
    return list(toutes.values())


# ─── Étape 2 : récupération des commentaires ─────────────────────────────────

def est_pertinent(texte: str) -> bool:
    """
    Vérifie si un commentaire est pertinent pour l'affaire Bacot.
    Si aucun mot-clé n'est défini, garde tous les commentaires assez longs.
    """
    if not MOTS_CLES_FILTRE:
        return True
    texte_lower = texte.lower()
    return any(mot in texte_lower for mot in MOTS_CLES_FILTRE)


def recuperer_commentaires(youtube, video: dict) -> list[dict]:
    """
    Récupère les commentaires d'une vidéo YouTube.
    Retourne une liste de commentaires filtrés et enrichis.
    """
    video_id = video["video_id"]
    commentaires = []
    next_page_token = None
    total_recuperes = 0

    try:
        while total_recuperes < MAX_COMMENTAIRES_PAR_VIDEO:
            params = {
                "videoId":    video_id,
                "part":       "snippet",
                "maxResults": min(100, MAX_COMMENTAIRES_PAR_VIDEO - total_recuperes),
                "order":      "relevance",
                "textFormat": "plainText",
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            response = youtube.commentThreads().list(**params).execute()

            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                texte  = top.get("textDisplay", "").strip()
                likes  = top.get("likeCount", 0)

                # Filtres
                if len(texte) < MIN_CHARS_COMMENTAIRE:
                    continue
                if likes < MIN_LIKES_COMMENTAIRE:
                    pass  # on garde quand même si texte long
                if not est_pertinent(texte):
                    continue

                commentaires.append({
                    "texte":       texte,
                    "likes":       likes,
                    "date":        top.get("publishedAt", ""),
                    "auteur":      top.get("authorDisplayName", ""),
                    "video_id":    video_id,
                    "video_titre": video["titre"],
                    "video_url":   video["url"],
                    "chaine":      video["chaine"],
                })

            total_recuperes += len(response.get("items", []))
            next_page_token = response.get("nextPageToken")

            if not next_page_token:
                break

            time.sleep(0.5)

    except HttpError as e:
        # Commentaires désactivés sur cette vidéo — normal
        if "commentsDisabled" in str(e) or "403" in str(e):
            log.info(f"  Commentaires désactivés sur cette vidéo")
        else:
            log.warning(f"  Erreur API commentaires {video_id} : {e}")

    return commentaires


# ─── Étape 3 : formatage pour le corpus ──────────────────────────────────────

def formater_comme_document(commentaire: dict) -> dict:
    """
    Formate un commentaire YouTube comme un document du corpus,
    compatible avec le format des articles de presse.
    """
    return {
        "url":         commentaire["video_url"] + f"#comment_{commentaire['auteur']}",
        "text":        commentaire["texte"],
        "title":       f"Commentaire sur : {commentaire['video_titre'][:80]}",
        "author":      commentaire["auteur"],
        "date":        commentaire["date"][:10] if commentaire["date"] else "",
        "sitename":    f"YouTube — {commentaire['chaine']}",
        "description": "",
        "source":      "youtube_commentaire",
        "video_url":   commentaire["video_url"],
        "video_titre": commentaire["video_titre"],
        "likes":       commentaire["likes"],
        "word_count":  len(commentaire["texte"].split()),
        "scraped_at":  datetime.utcnow().isoformat(),
    }


# ─── Étape 4 : sauvegarde ─────────────────────────────────────────────────────

def sauvegarder(documents: list[dict], videos: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Sauvegarde des métadonnées vidéos
    with open(OUTPUT_DIR / "videos_youtube.json", "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

    # Fusion avec corpus existant
    json_path = OUTPUT_DIR / "corpus_bacot.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            corpus_existant = json.load(f)
        urls_existantes = {a.get("url", "") for a in corpus_existant}
        nouveaux = [d for d in documents if d["url"] not in urls_existantes]
        corpus_final = corpus_existant + nouveaux
        log.info(f"Fusion : {len(corpus_existant)} existants + {len(nouveaux)} nouveaux = {len(corpus_final)} total")
    else:
        corpus_final = documents

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(corpus_final, f, ensure_ascii=False, indent=2)

    # CSV des commentaires seuls
    df = pd.DataFrame(documents)
    if not df.empty:
        df.to_csv(
            OUTPUT_DIR / "corpus_youtube_commentaires.csv",
            index=False,
            encoding="utf-8-sig"
        )

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         RÉSUMÉ — SCRAPER YOUTUBE                 ║
╠══════════════════════════════════════════════════╣
║  Vidéos scrapées    : {len(videos):>5}                   ║
║  Commentaires gardés: {len(documents):>5}                   ║
║  Corpus total       : {len(corpus_final):>5} documents         ║
╚══════════════════════════════════════════════════╝
→ Corpus    : {OUTPUT_DIR}/corpus_bacot.json
→ YouTube   : {OUTPUT_DIR}/corpus_youtube_commentaires.csv
→ Vidéos    : {OUTPUT_DIR}/videos_youtube.json
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():

    youtube = init_youtube()
    if not youtube:
        return

    # ── Étape 1 : recherche des vidéos ──
    log.info("=" * 60)
    log.info("ÉTAPE 1 — Recherche des vidéos YouTube")
    log.info("=" * 60)

    videos = collecter_videos(youtube, QUERIES_VIDEO)

    if not videos:
        log.error("Aucune vidéo trouvée.")
        return

    log.info(f"\nVidéos trouvées :")
    for v in videos:
        log.info(f"  - [{v['chaine']}] {v['titre'][:60]}")

    # ── Étape 2 : commentaires ──
    log.info("\n" + "=" * 60)
    log.info("ÉTAPE 2 — Récupération des commentaires")
    log.info("=" * 60)

    tous_commentaires = []

    for i, video in enumerate(videos, 1):
        log.info(f"\n[{i}/{len(videos)}] {video['titre'][:60]}")
        log.info(f"  Chaîne : {video['chaine']}")
        log.info(f"  URL    : {video['url']}")

        commentaires = recuperer_commentaires(youtube, video)
        log.info(f"  → {len(commentaires)} commentaires pertinents récupérés")

        tous_commentaires.extend(commentaires)
        time.sleep(DELAY)

    # ── Étape 3 : formatage + sauvegarde ──
    log.info("\n" + "=" * 60)
    log.info("ÉTAPE 3 — Formatage et sauvegarde")
    log.info("=" * 60)

    documents = [formater_comme_document(c) for c in tous_commentaires]

    # Trie par nombre de likes décroissant (commentaires les plus engagés en premier)
    documents.sort(key=lambda x: x.get("likes", 0), reverse=True)

    sauvegarder(documents, videos)


if __name__ == "__main__":
    run()
