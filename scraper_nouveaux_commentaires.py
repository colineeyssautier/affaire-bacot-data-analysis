"""
scraper_commentaires_bacot.py
==============================
Scrape les commentaires YouTube (avec pagination complète)
pour les vidéos découvertes dans nouvelles_videos_bacot.json.

Fonctionnalités :
- Pagination complète via nextPageToken (tous les commentaires, pas juste 100)
- Collecte des réponses aux commentaires (replies)
- Seuil de pertinence configurable pour filtrer les vidéos
- Reprise automatique si le script est interrompu (checkpoint)
- Gestion du quota YouTube (pause si proche de la limite)
- Export JSON + CSV

Quota YouTube Data v3 :
- commentThreads.list : 1 unité / appel (100 commentaires max par appel)
- comments.list (replies) : 1 unité / appel
- Pour 83 000 commentaires estimés : ~830 unités minimum
"""

import os
import json
import time
import csv
from datetime import datetime
from collections import defaultdict
import requests

# ─────────────────────────────────────────────
# CONFIGURATION — à modifier selon tes besoins
# ─────────────────────────────────────────────

API_KEY = "AIzaSyD_r8xosGQ8AeX_CNaMRkgXxrn4wW6_cfI"  # Ta clé YouTube Data v3

INPUT_FILE = "nouvelles_videos_bacot.json"   # Fichier de vidéos découvertes
OUTPUT_JSON = "commentaires_nouvelles_videos.json"
OUTPUT_CSV  = "commentaires_nouvelles_videos.csv"
CHECKPOINT_FILE = "checkpoint_commentaires.json"  # Pour reprendre si interruption
LOG_FILE = "scraping_commentaires.log"

# Seuil de score de pertinence minimum pour scraper une vidéo
# 1 = tout scraper | 4 = vidéos clairement liées | 6 = très ciblé
SCORE_MIN_PERTINENCE = 4

# Scraper les réponses aux commentaires (plus exhaustif mais +quota)
SCRAPER_REPLIES = True

# Pause entre chaque vidéo (secondes) — pour ménager le quota
PAUSE_ENTRE_VIDEOS = 1.5

# Quota max à utiliser (sur 10 000/jour). Laisser 2000 de marge.
QUOTA_MAX = 8000

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

def log(message, niveau="INFO"):
    horodatage = datetime.now().strftime("%H:%M:%S")
    ligne = f"[{horodatage}] [{niveau}] {message}"
    print(ligne)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


# ─────────────────────────────────────────────
# CHECKPOINT — reprise après interruption
# ─────────────────────────────────────────────

def charger_checkpoint():
    """Charge la liste des video_id déjà scrapés."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def sauvegarder_checkpoint(ids_traites):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids_traites), f)


# ─────────────────────────────────────────────
# APPELS API YOUTUBE (via requests, sans ADC)
# ─────────────────────────────────────────────

BASE_URL = "https://www.googleapis.com/youtube/v3"

def appel_api(endpoint, params, quota_compteur):
    """
    Appel générique à l'API YouTube.
    Retourne (données, quota_utilisé) ou (None, quota_utilisé) si erreur.
    """
    params["key"] = API_KEY
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)

        if r.status_code == 200:
            quota_compteur[0] += 1
            return r.json(), quota_compteur

        elif r.status_code == 403:
            erreur = r.json().get("error", {})
            raison = erreur.get("errors", [{}])[0].get("reason", "")
            if raison in ("quotaExceeded", "rateLimitExceeded"):
                log("⛔ QUOTA YOUTUBE ÉPUISÉ — arrêt du scraping", "ERREUR")
                raise SystemExit("Quota épuisé")
            elif raison == "commentsDisabled":
                return {"items": [], "commentsDisabled": True}, quota_compteur
            else:
                log(f"403 interdit : {erreur.get('message', '')}", "WARN")
                return None, quota_compteur

        elif r.status_code == 404:
            log("404 vidéo introuvable", "WARN")
            return None, quota_compteur

        else:
            log(f"Erreur HTTP {r.status_code}", "WARN")
            return None, quota_compteur

    except requests.exceptions.Timeout:
        log("Timeout — on passe", "WARN")
        return None, quota_compteur
    except requests.exceptions.RequestException as e:
        log(f"Erreur réseau : {e}", "WARN")
        return None, quota_compteur


def scraper_commentaires_video(video_id, video_meta, quota_compteur):
    """
    Scrape TOUS les commentaires d'une vidéo avec pagination complète.
    Retourne une liste de dicts commentaires.
    """
    commentaires = []
    page_token = None
    page_num = 0

    while True:
        # Vérification quota avant chaque appel
        if quota_compteur[0] >= QUOTA_MAX:
            log(f"⚠ Quota max atteint ({QUOTA_MAX}), arrêt propre", "WARN")
            raise SystemExit("Quota max atteint")

        params = {
            "part": "snippet,replies",
            "videoId": video_id,
            "maxResults": 100,  # maximum autorisé par appel
            "order": "relevance",
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        data, quota_compteur = appel_api("commentThreads", params, quota_compteur)

        if data is None:
            break
        if data.get("commentsDisabled"):
            log(f"  Commentaires désactivés", "INFO")
            break

        items = data.get("items", [])
        page_num += 1

        for item in items:
            snippet_thread = item.get("snippet", {})
            snippet_top = snippet_thread.get("topLevelComment", {}).get("snippet", {})

            commentaire = {
                # Identifiants
                "commentaire_id": item.get("id"),
                "video_id": video_id,
                "parent_id": None,  # commentaire racine
                "type": "commentaire",

                # Contenu
                "texte": snippet_top.get("textDisplay", ""),
                "auteur": snippet_top.get("authorDisplayName", ""),
                "auteur_id": snippet_top.get("authorChannelId", {}).get("value", ""),
                "date": snippet_top.get("publishedAt", ""),
                "date_modif": snippet_top.get("updatedAt", ""),

                # Engagement
                "likes": snippet_top.get("likeCount", 0),
                "nb_replies": snippet_thread.get("totalReplyCount", 0),

                # Métadonnées vidéo (dénormalisées pour faciliter l'analyse)
                "video_titre": video_meta.get("titre", ""),
                "video_chaine": video_meta.get("chaine", ""),
                "video_score_pertinence": video_meta.get("score_pertinence", 0),
                "video_label": video_meta.get("label_requete", ""),
            }
            commentaires.append(commentaire)

            # Réponses incluses dans la réponse (jusqu'à 5 par défaut)
            if SCRAPER_REPLIES:
                replies_incluses = item.get("replies", {}).get("comments", [])
                for reply in replies_incluses:
                    s = reply.get("snippet", {})
                    rep = {
                        "commentaire_id": reply.get("id"),
                        "video_id": video_id,
                        "parent_id": item.get("id"),
                        "type": "reply",
                        "texte": s.get("textDisplay", ""),
                        "auteur": s.get("authorDisplayName", ""),
                        "auteur_id": s.get("authorChannelId", {}).get("value", ""),
                        "date": s.get("publishedAt", ""),
                        "date_modif": s.get("updatedAt", ""),
                        "likes": s.get("likeCount", 0),
                        "nb_replies": 0,
                        "video_titre": video_meta.get("titre", ""),
                        "video_chaine": video_meta.get("chaine", ""),
                        "video_score_pertinence": video_meta.get("score_pertinence", 0),
                        "video_label": video_meta.get("label_requete", ""),
                    }
                    commentaires.append(rep)

                # Si un thread a plus de 5 réponses, les récupérer explicitement
                if snippet_thread.get("totalReplyCount", 0) > len(replies_incluses):
                    replies_sup = scraper_replies_thread(
                        item.get("id"), video_id, video_meta, quota_compteur
                    )
                    commentaires.extend(replies_sup)

        # Pagination
        page_token = data.get("nextPageToken")
        if not page_token:
            break

        time.sleep(0.3)  # petite pause entre pages

    return commentaires


def scraper_replies_thread(thread_id, video_id, video_meta, quota_compteur):
    """
    Récupère toutes les réponses d'un thread spécifique
    quand il y en a plus de 5 (non incluses automatiquement).
    """
    replies = []
    page_token = None

    while True:
        params = {
            "part": "snippet",
            "parentId": thread_id,
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        data, quota_compteur = appel_api("comments", params, quota_compteur)
        if data is None:
            break

        for item in data.get("items", []):
            s = item.get("snippet", {})
            replies.append({
                "commentaire_id": item.get("id"),
                "video_id": video_id,
                "parent_id": thread_id,
                "type": "reply",
                "texte": s.get("textDisplay", ""),
                "auteur": s.get("authorDisplayName", ""),
                "auteur_id": s.get("authorChannelId", {}).get("value", ""),
                "date": s.get("publishedAt", ""),
                "date_modif": s.get("updatedAt", ""),
                "likes": s.get("likeCount", 0),
                "nb_replies": 0,
                "video_titre": video_meta.get("titre", ""),
                "video_chaine": video_meta.get("chaine", ""),
                "video_score_pertinence": video_meta.get("score_pertinence", 0),
                "video_label": video_meta.get("label_requete", ""),
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return replies


# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────

COLONNES_CSV = [
    "commentaire_id", "video_id", "parent_id", "type",
    "texte", "auteur", "auteur_id", "date", "date_modif",
    "likes", "nb_replies",
    "video_titre", "video_chaine", "video_score_pertinence", "video_label"
]

def sauvegarder(tous_commentaires):
    """Sauvegarde JSON + CSV (écrasement à chaque fois)."""
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tous_commentaires, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES_CSV, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tous_commentaires)


# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────

def main():
    log("=" * 60)
    log("DÉMARRAGE — Scraping commentaires nouvelles vidéos Bacot")
    log("=" * 60)

    # Chargement des vidéos
    with open(INPUT_FILE, encoding="utf-8") as f:
        toutes_videos = json.load(f)

    # Filtrage par score de pertinence
    videos_cibles = [
        v for v in toutes_videos
        if v.get("score_pertinence", 0) >= SCORE_MIN_PERTINENCE
        and v.get("nb_commentaires", 0) > 0  # ignorer commentaires désactivés
    ]
    videos_cibles.sort(key=lambda v: v.get("score_pertinence", 0), reverse=True)

    log(f"Vidéos dans le fichier source    : {len(toutes_videos)}")
    log(f"Vidéos après filtre score ≥ {SCORE_MIN_PERTINENCE}   : {len(videos_cibles)}")
    log(f"Commentaires estimés total       : {sum(v.get('nb_commentaires', 0) for v in videos_cibles):,}")

    # Chargement checkpoint (vidéos déjà traitées)
    deja_traites = charger_checkpoint()
    a_traiter = [v for v in videos_cibles if v["video_id"] not in deja_traites]
    log(f"Déjà scrapées (checkpoint)       : {len(deja_traites)}")
    log(f"Vidéos à scraper                 : {len(a_traiter)}")
    log(f"Quota max configuré              : {QUOTA_MAX} unités\n")

    if not a_traiter:
        log("Rien à faire — toutes les vidéos ont déjà été scrapées.")
        return

    # Initialisation
    quota_compteur = [0]  # liste pour passage par référence
    tous_commentaires = []
    ids_traites = set(deja_traites)

    # Chargement des commentaires déjà collectés si fichier existe
    if os.path.exists(OUTPUT_JSON) and deja_traites:
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            tous_commentaires = json.load(f)
        log(f"Commentaires déjà collectés chargés : {len(tous_commentaires)}\n")

    # ── Boucle principale ──
    for i, video in enumerate(a_traiter, 1):
        vid_id = video["video_id"]
        titre = video.get("titre", "")[:60]
        chaine = video.get("chaine", "")
        score = video.get("score_pertinence", 0)
        nb_comms_estime = video.get("nb_commentaires", 0)

        log(f"[{i}/{len(a_traiter)}] [{score}pts] {titre}")
        log(f"  Chaîne : {chaine} | ~{nb_comms_estime} commentaires | quota utilisé : {quota_compteur[0]}")

        try:
            commentaires_video = scraper_commentaires_video(vid_id, video, quota_compteur)
            nb_recoltes = len(commentaires_video)
            tous_commentaires.extend(commentaires_video)
            ids_traites.add(vid_id)

            log(f"  ✓ {nb_recoltes} commentaires récoltés")

            # Sauvegarde intermédiaire toutes les 10 vidéos
            if i % 10 == 0:
                sauvegarder(tous_commentaires)
                sauvegarder_checkpoint(ids_traites)
                log(f"  💾 Sauvegarde intermédiaire ({len(tous_commentaires)} commentaires total)")

        except SystemExit:
            # Quota atteint — sauvegarde d'urgence et arrêt propre
            log("Sauvegarde d'urgence avant arrêt...", "WARN")
            sauvegarder(tous_commentaires)
            sauvegarder_checkpoint(ids_traites)
            log(f"Arrêt propre. {len(tous_commentaires)} commentaires sauvegardés.")
            log(f"Relance le script demain pour continuer (checkpoint actif).")
            return

        except Exception as e:
            log(f"  ✗ Erreur inattendue : {e}", "ERREUR")
            ids_traites.add(vid_id)  # on marque quand même pour ne pas reboucler

        time.sleep(PAUSE_ENTRE_VIDEOS)

    # Sauvegarde finale
    sauvegarder(tous_commentaires)
    sauvegarder_checkpoint(ids_traites)

    # ── Rapport final ──
    log("\n" + "=" * 60)
    log("RÉSULTATS FINAUX")
    log("=" * 60)
    log(f"Vidéos scrapées                  : {len(ids_traites)}")
    log(f"Commentaires récoltés total      : {len(tous_commentaires):,}")
    log(f"  dont commentaires racines      : {sum(1 for c in tous_commentaires if c['type'] == 'commentaire'):,}")
    log(f"  dont réponses (replies)        : {sum(1 for c in tous_commentaires if c['type'] == 'reply'):,}")
    log(f"Quota YouTube utilisé            : ~{quota_compteur[0]} unités")
    log(f"Fichiers de sortie               : {OUTPUT_JSON} | {OUTPUT_CSV}")

    # Répartition par chaîne
    from collections import Counter
    chaines = Counter(c["video_chaine"] for c in tous_commentaires)
    log("\nTop 10 chaînes par volume de commentaires :")
    for chaine, nb in chaines.most_common(10):
        log(f"  {nb:5,}  {chaine}")


if __name__ == "__main__":
    main()