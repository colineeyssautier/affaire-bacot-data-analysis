"""
scraper_decouverte_videos_bacot.py
===================================
Découverte de nouvelles vidéos YouTube sur l'affaire Valérie Bacot.
Exclut les 38 vidéos déjà scrapées.
Cible : grands médias, chaînes féministes, juridiques, true crime.

Quota YouTube Data v3 estimé : ~200-400 unités pour ce script
(chaque appel search.list = 100 unités, videoDetails = 1 unité/vidéo)
"""

import os
import json
import time
import googleapiclient.discovery
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

API_KEY = "AIzaSyD_r8xosGQ8AeX_CNaMRkgXxrn4wW6_cfI"

OUTPUT_FILE = "nouvelles_videos_bacot.json"
LOG_FILE = "decouverte_videos.log"

# IDs déjà scrapés — à exclure
VIDEOS_DEJA_SCRAPEES = {
    '1DrcFK5gk9k', 'QlqtSNKF3f8', 'rFArRZ-5J4U', '6Uz0O5OX63o', 'nwax-EdNYMA',
    'cQriCTmDNYE', '23HDisPUTVs', 'j6w28IhZq-0', 'gd-ScjW1rpM', 'rOyfiYptsEQ',
    'zA3etFUNYLA', 'DbX2rpzjbGo', '5pQKk4LZzws', '_phXzaYXD-0', 'wP0a9xU972c',
    'MiYmZ-WSfAY', 'JtTI2zymh88', 'yYDGDvIMWIQ', 'QnFo5I7tHzM', '8quOTcR0mZc',
    'tDji4J1rlIg', 'WnNAhXzUZ4Y', 'lsrnV4UlZ6M', 'rezprI9xze0', 'l4EYSK6xKZc',
    '7xOsdJh-140', 'JdRgR-v1FU8', 'wvM1BFu2-LI', 'WPJs7M8DKVs', 'oM1HHZaPPkc',
    'MF9A6V_TWmc', 'ukVYcxr1P-c', 'Gxb3u0D2nNQ', 'TF_7APBRN1s', 'jTeAPlI4xUU',
    'Fa2xGED0ceE', 'YO-C924RxN4', 'A3Vsg0gFNhU'
}

# Seuil de pertinence : score minimum pour retenir une vidéo
SCORE_MIN = 1

# ─────────────────────────────────────────────
# REQUÊTES DE RECHERCHE
# Organisées par angle narratif pour maximiser
# la diversité du corpus
# ─────────────────────────────────────────────

REQUETES = [
    # — Requêtes directes sur l'affaire —
    {"q": "Valérie Bacot", "label": "affaire_directe"},
    {"q": "Valérie Bacot procès", "label": "affaire_directe"},
    {"q": "Valérie Bacot verdict", "label": "affaire_directe"},
    {"q": "Valérie Bacot acquittement", "label": "affaire_directe"},
    {"q": "Valérie Bacot livre", "label": "affaire_directe"},
    {"q": "Daniel Polette", "label": "affaire_directe"},

    # — Angle juridique —
    {"q": "Valérie Bacot légitime défense", "label": "juridique"},
    {"q": "femme tue mari violent procès France", "label": "juridique"},
    {"q": "féminicide inversé jugement", "label": "juridique"},
    {"q": "violences conjugales meurtre acquittement", "label": "juridique"},
    {"q": "légitime défense différée jurisprudence", "label": "juridique"},

    # — Angle féministe / militant —
    {"q": "Valérie Bacot féminisme", "label": "feministe"},
    {"q": "violences conjugales survivante jugée", "label": "feministe"},
    {"q": "femmes victimes jugées France", "label": "feministe"},
    {"q": "patriarcat justice féminicide", "label": "feministe"},
    {"q": "Valérie Bacot soutien pétition", "label": "feministe"},

    # — Angle médias / débat public —
    {"q": "Valérie Bacot débat télévision", "label": "media"},
    {"q": "Valérie Bacot interview", "label": "media"},
    {"q": "affaire Bacot opinion", "label": "media"},
    {"q": "Valérie Bacot documentaire", "label": "media"},

    # — Angle true crime / fait divers —
    {"q": "Valérie Bacot crime vrai", "label": "true_crime"},
    {"q": "affaire Bacot Polette fait divers", "label": "true_crime"},
    {"q": "femme condamnée mari abusif France", "label": "true_crime"},
    {"q": "affaire criminelle violences conjugales 2021", "label": "true_crime"},

    # — Contexte / comparaisons —
    {"q": "Jacqueline Sauvage Valérie Bacot comparaison", "label": "contexte"},
    {"q": "femmes violences conjugales justice France", "label": "contexte"},
    {"q": "Valérie Bacot Chalon-sur-Saône", "label": "contexte"},
]

# ─────────────────────────────────────────────
# MOTS-CLÉS DE PERTINENCE
# Une vidéo gagne 1 point par mot-clé trouvé
# dans son titre ou sa description
# ─────────────────────────────────────────────

MOTS_CLES_PERTINENCE = [
    "bacot", "polette", "valérie", "valerie",
    "féminicide", "feminicide", "conjugal", "conjugales",
    "victime", "meurtre", "procès", "proces",
    "acquittement", "légitime défense", "legitime defense",
    "violences", "mari", "bourreau", "survivante",
    "chalon", "saône", "tribunal", "cour d'assises",
    "jacqueline sauvage",  # comparaison fréquente
]

# ─────────────────────────────────────────────
# FONCTIONS
# ─────────────────────────────────────────────

def log(message):
    horodatage = datetime.now().strftime("%H:%M:%S")
    ligne = f"[{horodatage}] {message}"
    print(ligne)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def calculer_score_pertinence(titre, description):
    """
    Score de pertinence basé sur la présence de mots-clés
    dans le titre (poids x2) et la description (poids x1).
    """
    texte_titre = titre.lower()
    texte_desc = (description or "").lower()
    score = 0
    for mot in MOTS_CLES_PERTINENCE:
        if mot in texte_titre:
            score += 2  # titre = signal fort
        elif mot in texte_desc:
            score += 1
    return score


def rechercher_videos(youtube, requete, label, max_resultats=50):
    """
    Lance une recherche YouTube et retourne les vidéos trouvées.
    max_resultats : YouTube permet jusqu'à 50 par appel (1 page).
    Chaque appel search.list coûte 100 unités de quota.
    """
    videos = []
    try:
        reponse = youtube.search().list(
            part="snippet",
            q=requete["q"],
            type="video",
            relevanceLanguage="fr",
            regionCode="FR",
            maxResults=max_resultats,
            order="relevance",
        ).execute()

        for item in reponse.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            titre = snippet.get("title", "")
            description = snippet.get("description", "")
            score = calculer_score_pertinence(titre, description)

            videos.append({
                "video_id": video_id,
                "titre": titre,
                "chaine": snippet.get("channelTitle", ""),
                "chaine_id": snippet.get("channelId", ""),
                "date_publication": snippet.get("publishedAt", ""),
                "description_courte": description[:300],
                "score_pertinence": score,
                "label_requete": label,
                "requete_source": requete["q"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })

    except HttpError as e:
        log(f"  ⚠ Erreur HTTP sur '{requete['q']}' : {e}")

    return videos


def enrichir_avec_stats(youtube, videos):
    """
    Récupère les statistiques (vues, likes, nb commentaires)
    pour chaque vidéo via videos.list.
    Traitement par lots de 50 (limite API).
    Coût : 1 unité par vidéo.
    """
    ids = [v["video_id"] for v in videos]
    stats_par_id = {}

    for i in range(0, len(ids), 50):
        lot = ids[i:i+50]
        try:
            reponse = youtube.videos().list(
                part="statistics,contentDetails",
                id=",".join(lot)
            ).execute()

            for item in reponse.get("items", []):
                vid_id = item["id"]
                stats = item.get("statistics", {})
                details = item.get("contentDetails", {})
                stats_par_id[vid_id] = {
                    "vues": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "nb_commentaires": int(stats.get("commentCount", 0)),
                    "duree": details.get("duration", ""),
                }
            time.sleep(0.5)
        except HttpError as e:
            log(f"  ⚠ Erreur stats lot {i//50 + 1} : {e}")

    for v in videos:
        stats = stats_par_id.get(v["video_id"], {})
        v.update(stats)

    return videos


# ─────────────────────────────────────────────
# PROGRAMME PRINCIPAL
# ─────────────────────────────────────────────

def main():
    log("=" * 55)
    log("DÉMARRAGE — Découverte de vidéos Valérie Bacot")
    log("=" * 55)
    log(f"Vidéos déjà scrapées à exclure : {len(VIDEOS_DEJA_SCRAPEES)}")
    log(f"Requêtes planifiées : {len(REQUETES)}")
    log(f"Quota estimé : ~{len(REQUETES) * 100 + 500} unités\n")

    print(f"Clé chargée : {API_KEY[:10]}...")

    youtube = build(
        "youtube", "v3",
        developerKey=API_KEY,
        cache_discovery=False  # évite les conflits de cache d'authentification
    )
    # Collecte toutes les vidéos candidates
    toutes_videos = {}  # video_id → données (dédupliqué)
    quota_utilise = 0

    for i, requete in enumerate(REQUETES, 1):
        log(f"[{i}/{len(REQUETES)}] Recherche : \"{requete['q']}\"")
        videos = rechercher_videos(youtube, requete, requete["label"])
        quota_utilise += 100

        nouvelles = 0
        exclues = 0
        non_pertinentes = 0

        for v in videos:
            vid_id = v["video_id"]

            if vid_id in VIDEOS_DEJA_SCRAPEES:
                exclues += 1
                continue

            if v["score_pertinence"] < SCORE_MIN:
                non_pertinentes += 1
                continue

            if vid_id not in toutes_videos:
                toutes_videos[vid_id] = v
                nouvelles += 1
            else:
                # Garder le score le plus élevé si la vidéo
                # apparaît dans plusieurs requêtes
                if v["score_pertinence"] > toutes_videos[vid_id]["score_pertinence"]:
                    toutes_videos[vid_id]["score_pertinence"] = v["score_pertinence"]
                toutes_videos[vid_id]["label_requete"] += f", {v['label_requete']}"

        log(f"   → {nouvelles} nouvelles | {exclues} déjà scrapées | {non_pertinentes} non pertinentes")
        time.sleep(1)  # pause courtoise entre requêtes

    # Enrichissement avec les statistiques
    log(f"\nEnrichissement des statistiques pour {len(toutes_videos)} vidéos...")
    liste_videos = list(toutes_videos.values())
    liste_videos = enrichir_avec_stats(youtube, liste_videos)
    quota_utilise += len(liste_videos)

    # Tri par score de pertinence puis par nombre de vues
    liste_videos.sort(
        key=lambda v: (v["score_pertinence"], v.get("vues", 0)),
        reverse=True
    )

    # Sauvegarde
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(liste_videos, f, ensure_ascii=False, indent=2)

    # Rapport final
    log("\n" + "=" * 55)
    log("RÉSULTATS")
    log("=" * 55)
    log(f"Vidéos découvertes (nouvelles, pertinentes) : {len(liste_videos)}")
    log(f"Quota YouTube estimé utilisé : ~{quota_utilise} unités")
    log(f"Fichier de sortie : {OUTPUT_FILE}")

    # Aperçu des 10 meilleures
    log("\nTop 10 vidéos par pertinence :")
    for v in liste_videos[:10]:
        vues = v.get('vues', 0)
        log(f"  [{v['score_pertinence']}pts | {vues:,} vues] {v['titre'][:60]} — {v['chaine']}")

    # Répartition par label
    log("\nRépartition par angle thématique :")
    from collections import Counter
    labels = []
    for v in liste_videos:
        for label in v["label_requete"].split(", "):
            labels.append(label.strip())
    for label, count in Counter(labels).most_common():
        log(f"  {label:<20} : {count} vidéos")

    log("\nTerminé. Vérifie nouvelles_videos_bacot.json avant de lancer le scraper de commentaires.")


if __name__ == "__main__":
    main()
