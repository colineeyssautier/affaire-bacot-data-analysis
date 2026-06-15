#!/usr/bin/env python3
"""
scraper_rss_etendu_bacot.py
Enrichissement du corpus Bacot via Google News RSS + flux RSS directs.
"""

import concurrent.futures
import csv
import json
import logging
import os
import random
import re
import signal
import sys
import time
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

try:
    import trafilatura
except ImportError:
    print("ERREUR : trafilatura n'est pas installé. Lancez : pip install trafilatura")
    sys.exit(1)

try:
    import urllib3
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

try:
    from googlenewsdecoder import new_decoderv1 as gnews_decode
    GNEWS_DECODER_AVAILABLE = True
except ImportError:
    GNEWS_DECODER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
CORPUS_DIR = Path("corpus_bacot")
CORPUS_DIR.mkdir(exist_ok=True)

OUT_ARTICLES   = CORPUS_DIR / "rss_articles.json"
OUT_URLS       = CORPUS_DIR / "rss_urls_collectees.json"
OUT_ECHECS     = CORPUS_DIR / "rss_echecs.json"
OUT_LOG_CSV    = CORPUS_DIR / "rss_log.csv"
OUT_CHECKPOINT = CORPUS_DIR / "rss_checkpoint.json"
LOG_FILE       = "scraper_rss_etendu.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TERMES_PERTINENCE = [
    "valérie bacot", "valerie bacot", "bacot", "polette",
    "clayette", "tout le monde savait",
]
TERMES_FILTRE_RSS = ["bacot", "valérie bacot", "valerie bacot", "polette", "tout le monde savait"]

MIN_MOTS = 100
CHECKPOINT_INTERVAL = 25

SCORE_MIN = 3

# ---------------------------------------------------------------------------
# PARTIE A — Requêtes Google News RSS
# ---------------------------------------------------------------------------
REQUETES_GNEWS = [
    # Pré-procès
    ('"Valérie Bacot" after:2020-01-01 before:2021-01-01',         "preprocès_2020"),
    ('"Valérie Bacot" pétition after:2021-01-01 before:2021-04-01',"petition_2021"),
    ('"Valérie Bacot" after:2021-04-01 before:2021-06-21',         "preprocès_avril_juin21"),
    ('Bacot Polette after:2020-01-01 before:2021-06-21',           "bacot_polette"),
    ('Bacot "légitime défense" after:2020-01-01 before:2021-06-21',"légitime_défense"),
    # Semaine du procès
    ('"Valérie Bacot" procès after:2021-06-21 before:2021-06-22',  "procès_j1"),
    ('"Valérie Bacot" procès after:2021-06-22 before:2021-06-23',  "procès_j2"),
    ('"Valérie Bacot" procès after:2021-06-23 before:2021-06-24',  "procès_j3"),
    ('"Valérie Bacot" verdict after:2021-06-24 before:2021-06-27', "verdict"),
    ('Bacot assises after:2021-06-21 before:2021-06-27',           "bacot_assises"),
    ('Bacot acquittement after:2021-06-21 before:2021-06-30',      "acquittement"),
    ('Bacot sursis after:2021-06-21 before:2021-06-30',            "sursis"),
    # Post-verdict
    ('"Valérie Bacot" after:2021-06-27 before:2021-08-01',         "post_verdict_juil21"),
    ('Bacot emprise after:2021-06-21 before:2021-09-01',           "emprise"),
    ('Bacot féminisme after:2021-06-21 before:2021-09-01',         "féminisme"),
    ('Bacot "Jacqueline Sauvage" after:2021-06-21 before:2021-09-01', "bacot_sauvage"),
    # Livre
    ('"Valérie Bacot" livre after:2021-09-01 before:2021-10-01',   "livre_sept21"),
    ('"tout le monde savait" Bacot after:2021-09-01 before:2021-12-01', "tmls_automne21"),
    ('"Valérie Bacot" after:2021-09-01 before:2021-10-01',         "bacot_sept21"),
    ('"Valérie Bacot" after:2021-10-01 before:2021-11-01',         "bacot_oct21"),
    # Sénat
    ('Bacot sénat after:2021-10-01 before:2021-12-01',             "sénat"),
    ('"Valérie Bacot" after:2021-11-01 before:2021-12-01',         "bacot_nov21"),
    ('"Valérie Bacot" after:2021-12-01 before:2022-01-01',         "bacot_déc21"),
    # 2022
    ('"Valérie Bacot" after:2022-01-01 before:2022-04-01',         "bacot_t1_2022"),
    ('"Valérie Bacot" after:2022-04-01 before:2022-07-01',         "bacot_t2_2022"),
    ('"Valérie Bacot" after:2022-07-01 before:2023-01-01',         "bacot_s2_2022"),
    ('Bacot anniversaire verdict after:2022-06-01 before:2022-07-01', "anniversaire_verdict"),
    # 2023-2026
    ('"Valérie Bacot" after:2023-01-01 before:2023-07-01',         "bacot_s1_2023"),
    ('"Valérie Bacot" after:2023-07-01 before:2024-01-01',         "bacot_s2_2023"),
    ('"Valérie Bacot" after:2024-01-01 before:2024-07-01',         "bacot_s1_2024"),
    ('"Valérie Bacot" after:2024-07-01 before:2025-01-01',         "bacot_s2_2024"),
    ('"Valérie Bacot" after:2025-01-01 before:2025-07-01',         "bacot_s1_2025"),
    ('"Valérie Bacot" after:2025-07-01 before:2026-06-11',         "bacot_s2_2025_2026"),
    # Thématiques
    ('Bacot "violences conjugales" after:2021-01-01 before:2026-06-11', "violences_conjugales"),
    ('Bacot féminicide after:2021-01-01 before:2026-06-11',         "féminicide"),
    ('Bacot Tomasini after:2021-01-01 before:2026-06-11',           "tomasini"),
    ('Bacot "Daniel Polette" after:2021-01-01 before:2026-06-11',   "daniel_polette"),
    ('Bacot proxénète after:2021-01-01 before:2026-06-11',          "proxénète"),
    ('"tout le monde savait" Bacot after:2021-01-01 before:2026-06-11', "tmls_all"),
]

FLUX_RSS_DIRECTS = [
    # JSL — jsl.fr timeout, domaine migré vers lejsl.com
    {"url": "https://www.lejsl.com/rss",                                           "source": "JSL"},
    {"url": "https://france3-regions.francetvinfo.fr/bourgogne-franche-comte/rss", "source": "France 3 BFC"},
    # Groupe Ebra — anciennes URLs en /rss/une.rss → 404, essai sans suffixe
    {"url": "https://www.bienpublic.com/rss",                                      "source": "Le Bien Public"},
    {"url": "https://www.estrepublicain.fr/rss",                                   "source": "Est Républicain"},
    {"url": "https://www.leprogres.fr/rss",                                        "source": "Le Progrès"},
    {"url": "https://www.lyoncapitale.fr/feed/",                                   "source": "Lyon Capitale"},
    # BFMTV — nouvelle URL (ancienne /rss/news-0/ → 404)
    {"url": "https://www.bfmtv.com/rss/news-24-7/",                               "source": "BFMTV"},
    # RTL — aucun flux RSS public news disponible, supprimé
    # 20 Minutes — nouvelle URL (ancienne /feeds/rss/une → 404)
    {"url": "https://www.20minutes.fr/feeds/rss-une.xml",                         "source": "20 Minutes"},
    {"url": "https://feeds.leparisien.fr/leparisien/rss",                         "source": "Le Parisien"},
    {"url": "https://www.francetvinfo.fr/titres.rss",                             "source": "France Info"},
    {"url": "https://www.huffingtonpost.fr/feeds/index.xml",                      "source": "HuffPost"},
    # Causette — domaine défunt (DNS failure), supprimé
    {"url": "https://www.madmoizelle.com/feed",                                   "source": "Madmoizelle"},
    # Néon — site inactif depuis oct 2023, supprimé
    # Sénat — nouvelle URL (ancienne /rss/senat.rss → 404)
    {"url": "https://www.senat.fr/rss/presse.rss",                               "source": "Sénat"},
]

# ---------------------------------------------------------------------------
# État global (pour sauvegarde Ctrl+C)
# ---------------------------------------------------------------------------
_etat = {
    "articles":   [],
    "echecs":     [],
    "log_rows":   [],
    "checkpoint": set(),
}
_shutdown = False


def _handler_sigint(sig, frame):
    global _shutdown
    log.warning("Interruption reçue — sauvegarde en cours…")
    _shutdown = True


signal.signal(signal.SIGINT, _handler_sigint)

# ---------------------------------------------------------------------------
# Utilitaires — chargement / sauvegarde
# ---------------------------------------------------------------------------

def charger_json(path: Path, defaut):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Impossible de lire %s : %s", path, e)
    return defaut


def sauvegarder_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sauvegarder_checkpoint():
    _flush_log_csv()
    data = {
        "articles":   _etat["articles"],
        "echecs":     _etat["echecs"],
        "done_urls":  list(_etat["checkpoint"]),
    }
    sauvegarder_json(OUT_CHECKPOINT, data)
    # Écriture progressive dans rss_articles.json (évite toute perte en cas de crash)
    existants = charger_json(OUT_ARTICLES, [])
    urls_existantes = {a["url"] for a in existants if isinstance(a, dict) and a.get("url")}
    a_ajouter = [a for a in _etat["articles"] if a["url"] not in urls_existantes]
    sauvegarder_json(OUT_ARTICLES, existants + a_ajouter)
    log.info("Checkpoint sauvegardé (%d articles, %d URLs traitées)",
             len(_etat["articles"]), len(_etat["checkpoint"]))


def charger_urls_corpus() -> set:
    """
    Charge uniquement les URLs des articles de presse déjà scrapés.
    Exclut explicitement les fichiers de tweets et tous les fichiers
    de travail internes au scraper.
    """
    urls = set()

    # Fichiers à exclure — tweets, fichiers de travail, checkpoints
    FICHIERS_EXCLUS = {
        # Fichiers de travail du scraper RSS
        "rss_checkpoint.json",
        "rss_urls_collectees.json",
        "rss_echecs.json",

        # Tweets — ne pas confondre avec des articles
        "tweets_bacot.json",
        "tweets_bacot_preproc.json",

        # Wayback (géré séparément)
        "wayback_articles.json",
        "wayback_failed.json",
        "urls_wayback_cdx.json",
        "wayback_checkpoint.json",

        # Listes d'URLs à scraper (pas encore traitées)
        "urls_gdelt.json",
        "urls_raw.json",
        "urls_bing.json",
        "urls_ddg.json",
        "urls_journaux.json",
        "urls_rss.json",

        # Échecs de scrape — l'URL n'a jamais été extraite avec succès
        "failed_urls.json",
        "failed_manuelles.json",
        "failed_journaux.json",
        "failed_rss.json",
        "failed_incremental.json",

        # Vidéos YouTube — pas des articles de presse
        "videos_youtube.json",

        # Autres fichiers de travail éventuels
        "articles_existants.json",
    }

    for path in CORPUS_DIR.glob("*.json"):
        if path.name in FICHIERS_EXCLUS:
            continue
        try:
            data = charger_json(path, [])
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("url"):
                        urls.add(item["url"].strip())
            elif isinstance(data, dict):
                if data.get("url"):
                    urls.add(data["url"].strip())
        except Exception as e:
            log.debug("Lecture %s ignorée : %s", path.name, e)

    log.info("Articles déjà dans le corpus : %d URLs chargées", len(urls))
    return urls


def charger_checkpoint() -> set:
    if not OUT_CHECKPOINT.exists():
        return set()
    data = charger_json(OUT_CHECKPOINT, {})
    _etat["articles"] = data.get("articles", [])
    _etat["echecs"]   = data.get("echecs", [])
    done = set(data.get("done_urls", []))
    log.info("Checkpoint chargé : %d articles, %d URLs déjà traitées",
             len(_etat["articles"]), len(done))
    return done

# ---------------------------------------------------------------------------
# PARTIE A — Google News RSS
# ---------------------------------------------------------------------------

def _decoder_url_gnews(url_gnews: str) -> str | None:
    """Décode une URL Google News vers l'URL réelle. Retourne None si échec."""
    if not GNEWS_DECODER_AVAILABLE:
        return None
    try:
        result = gnews_decode(url_gnews)
        if isinstance(result, dict):
            decoded = result.get("decoded_url") or result.get("url") or ""
        else:
            decoded = str(result) if result else ""

        if not decoded:
            return None
        if not decoded.startswith("http"):
            return None
        if "news.google.com" in decoded:
            return None
        if "google.com/search" in decoded:
            return None

        return decoded
    except Exception as e:
        log.debug("Décodage Google News échoué : %s", e)
        return None


def collecter_gnews_rss() -> tuple[list[dict], int]:
    """Retourne (liste de dicts {url, titre_rss, date_rss, source_rss, label}, nb_decode_echecs)."""
    if not GNEWS_DECODER_AVAILABLE:
        log.error(
            "googlenewsdecoder n'est pas installé.\n"
            "Installez-le avec : pip install googlenewsdecoder\n"
            "puis relancez le script."
        )
        sys.exit(1)

    collectes = []
    total = len(REQUETES_GNEWS)
    nb_decode_echecs = 0
    nb_items_total = 0

    for idx, (requete, label) in enumerate(REQUETES_GNEWS, 1):
        if _shutdown:
            break
        rss_url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(requete)
            + "&hl=fr&gl=FR&ceid=FR:fr"
        )
        log.info("[GNews %d/%d] %s", idx, total, label)
        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            log.warning("Flux GNews inaccessible (%s) : %s", label, e)
            time.sleep(1)
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            log.warning("XML invalide pour %s : %s", label, e)
            time.sleep(1)
            continue

        items = root.findall(".//item")
        log.info("  → %d items trouvés", len(items))
        nb_items_total += len(items)

        for item in items:
            titre  = (item.findtext("title") or "").strip()
            lien   = (item.findtext("link")  or "").strip()
            date   = (item.findtext("pubDate") or "").strip()
            source = ""
            src_el = item.find("source")
            if src_el is not None:
                source = (src_el.text or "").strip()

            if not lien:
                continue

            url_reelle = _decoder_url_gnews(lien)
            if url_reelle is None:
                log.info("  ⚠ Décodage échoué pour : %s", titre[:60])
                nb_decode_echecs += 1
                continue
            collectes.append({
                "url":        url_reelle,
                "url_gnews":  lien,
                "titre_rss":  titre,
                "date_rss":   date,
                "source_rss": source or label,
                "label":      label,
            })

        time.sleep(1)

    log.info("Décodages échoués : %d/%d items Google News", nb_decode_echecs, nb_items_total)
    log.info("Partie A — %d URLs collectées via Google News RSS", len(collectes))
    return collectes, nb_decode_echecs

# ---------------------------------------------------------------------------
# PARTIE B — Flux RSS directs
# ---------------------------------------------------------------------------

def _contient_terme(texte: str) -> bool:
    t = texte.lower()
    return any(terme in t for terme in TERMES_FILTRE_RSS)


def collecter_flux_directs() -> list[dict]:
    collectes = []
    total = len(FLUX_RSS_DIRECTS)

    for idx, flux in enumerate(FLUX_RSS_DIRECTS, 1):
        if _shutdown:
            break
        log.info("[RSS direct %d/%d] %s", idx, total, flux["source"])
        try:
            resp = requests.get(flux["url"], headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            log.warning("  Flux inaccessible : %s", e)
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            log.warning("  XML invalide : %s", e)
            continue

        items = root.findall(".//item")
        retenus = 0
        for item in items:
            titre = (item.findtext("title") or "").strip()
            lien  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            date  = (item.findtext("pubDate") or "").strip()

            if not lien:
                continue
            if not (_contient_terme(titre) or _contient_terme(desc)):
                continue

            collectes.append({
                "url":        lien,
                "titre_rss":  titre,
                "date_rss":   date,
                "source_rss": flux["source"],
                "label":      f"direct_{flux['source']}",
            })
            retenus += 1

        log.info("  → %d items retenus sur %d", retenus, len(items))

    log.info("Partie B — %d URLs collectées via flux RSS directs", len(collectes))
    return collectes

# ---------------------------------------------------------------------------
# PARTIE C — Téléchargement et extraction
# ---------------------------------------------------------------------------

def _score_pertinence(texte: str) -> int:
    t = texte.lower()
    score = 0

    # Signal fort — nom complet présent (les deux mots ensemble)
    if "valérie bacot" in t or "valerie bacot" in t:
        score += 4

    # Signal moyen — nom de famille seul
    elif "bacot" in t:
        score += 2

    # Sans "bacot" dans le texte, l'article n'est pas pertinent
    else:
        return 0

    # Signaux contextuels — renforcent la pertinence
    if "daniel polette" in t or "polette" in t:
        score += 2
    if "tout le monde savait" in t:
        score += 2
    if "clayette" in t:
        score += 2
    if "tomasini" in t:
        score += 1
    if "saône-et-loire" in t or "saone-et-loire" in t:
        score += 1
    for terme in ["proxénète", "proxenete", "emprise",
                  "légitime défense", "legitime defense",
                  "violences conjugales", "féminicide", "feminicide"]:
        if terme in t:
            score += 1
            break  # un seul point même si plusieurs termes présents

    return score


_TRAFILATURA_TIMEOUT = 30  # secondes max pour l'extraction


def _run_trafilatura(html: str, mode: dict):
    return trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        output_format="json",
        with_metadata=True,
        **mode,
    )


def _decode_response(resp) -> str:
    """Décode la réponse en évitant le défaut ISO-8859-1 de requests."""
    if resp.encoding and resp.encoding.lower().replace("-", "") in ("iso88591", "latin1"):
        apparent = (resp.apparent_encoding or "").lower()
        if apparent.startswith("utf") or apparent.startswith("ascii"):
            resp.encoding = resp.apparent_encoding
    return resp.text


def _extraire_article(url: str) -> dict | None:
    """Télécharge une URL et extrait le texte via trafilatura. Retourne None si échec."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
        resp.raise_for_status()
        html = _decode_response(resp)
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=(10, 25), verify=False)
            resp.raise_for_status()
            html = _decode_response(resp)
        except Exception as e:
            return {"erreur": f"SSL + retry échoué : {e}"}
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code in (404, 403, 410):
            return {"erreur": f"HTTP {code}"}
        if code == 429:
            log.warning("  429 reçu, attente 30s…")
            time.sleep(30)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
                resp.raise_for_status()
                html = resp.text
            except Exception as e2:
                return {"erreur": f"429 retry échoué : {e2}"}
        else:
            return {"erreur": str(e)}
    except Exception as e:
        return {"erreur": str(e)}

    # Extraction trafilatura — avec timeout thread pour éviter les blocages
    resultat = None
    for mode in [{"favor_precision": True}, {"favor_recall": True}]:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_run_trafilatura, html, mode)
                try:
                    raw = future.result(timeout=_TRAFILATURA_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    log.warning("  trafilatura timeout (%ds)", _TRAFILATURA_TIMEOUT)
                    return {"erreur": "trafilatura timeout"}
            if raw:
                resultat = json.loads(raw)
                if resultat.get("text"):
                    break
        except Exception:
            pass

    if not resultat or not resultat.get("text"):
        return {"erreur": "trafilatura n'a rien extrait"}

    texte = resultat["text"].strip()
    nb_mots = len(texte.split())

    return {
        "texte":       texte,
        "nb_mots":     nb_mots,
        "titre":       (resultat.get("title") or "").strip(),
        "auteur":      (resultat.get("author") or "").strip(),
        "date":        (resultat.get("date") or "")[:10],
        "sitename":    (resultat.get("sitename") or "").strip(),
        "description": (resultat.get("description") or "").strip(),
    }


def _ecrire_log_csv(row: dict):
    """Bufferise la ligne — écriture groupée via _flush_log_csv."""
    _etat["log_rows"].append(row)


def _flush_log_csv():
    """Écrit toutes les lignes bufferisées dans le CSV, puis vide le buffer."""
    if not _etat["log_rows"]:
        return
    try:
        existe = OUT_LOG_CSV.exists()
        with open(OUT_LOG_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["url", "source", "statut", "nb_mots", "score_pertinence", "date"])
            if not existe:
                writer.writeheader()
            writer.writerows(_etat["log_rows"])
        _etat["log_rows"].clear()
    except Exception as e:
        log.warning("Impossible d'écrire le log CSV : %s", e)


def telecharger_articles(urls_meta: list[dict], urls_corpus: set, done_urls: set):
    """Télécharge et extrait chaque URL non encore traitée."""
    stats = {
        "retenus": 0, "trop_courts": 0, "hors_sujet": 0,
        "erreurs": 0, "doublons": 0,
    }

    # Dédupliquer la liste d'entrée elle-même (même URL peut venir de plusieurs requêtes)
    seen_input: set[str] = set()
    urls_uniques = []
    for m in urls_meta:
        u = m["url"].strip()
        if u not in seen_input:
            seen_input.add(u)
            urls_uniques.append(m)

    a_telecharger = [
        m for m in urls_uniques
        if m["url"].strip() not in urls_corpus and m["url"].strip() not in done_urls
    ]

    sautes = len(urls_uniques) - len(a_telecharger)
    log.info("%d URLs à télécharger (%d déjà dans le corpus, skippées)",
             len(a_telecharger), sautes)

    total = len(a_telecharger)
    for idx, meta in enumerate(a_telecharger, 1):
        if _shutdown:
            break

        url = meta["url"].strip()
        log.info("[%d/%d] %s", idx, total, url[:90])

        resultat = _extraire_article(url)

        if resultat is None or "erreur" in resultat:
            raison = (resultat or {}).get("erreur", "inconnu")
            log.warning("  ECHEC : %s", raison)
            _etat["echecs"].append({"url": url, "raison": raison,
                                    "source": meta.get("source_rss","")})
            _ecrire_log_csv({"url": url, "source": meta.get("source_rss",""),
                             "statut": "erreur", "nb_mots": 0,
                             "score_pertinence": 0, "date": ""})
            stats["erreurs"] += 1
            done_urls.add(url)
            _etat["checkpoint"].add(url)
            time.sleep(random.uniform(1.0, 2.5))
            continue

        texte   = resultat["texte"]
        nb_mots = resultat["nb_mots"]

        if nb_mots < MIN_MOTS:
            log.info("  trop court (%d mots)", nb_mots)
            _ecrire_log_csv({"url": url, "source": meta.get("source_rss",""),
                             "statut": "trop_court", "nb_mots": nb_mots,
                             "score_pertinence": 0, "date": resultat["date"]})
            stats["trop_courts"] += 1
            done_urls.add(url)
            _etat["checkpoint"].add(url)
            time.sleep(random.uniform(1.0, 2.5))
            continue

        score = _score_pertinence(texte)
        if score < SCORE_MIN:
            log.info("  hors sujet (score=%d)", score)
            _ecrire_log_csv({"url": url, "source": meta.get("source_rss",""),
                             "statut": "hors_sujet", "nb_mots": nb_mots,
                             "score_pertinence": score, "date": resultat["date"]})
            stats["hors_sujet"] += 1
            done_urls.add(url)
            _etat["checkpoint"].add(url)
            time.sleep(random.uniform(1.0, 2.5))
            continue

        article = {
            "url":               url,
            "titre":             resultat["titre"] or meta.get("titre_rss", ""),
            "texte":             texte,
            "auteur":            resultat["auteur"],
            "date":              resultat["date"] or meta.get("date_rss", "")[:10],
            "sitename":          resultat["sitename"],
            "description":       resultat["description"],
            "nb_mots":           nb_mots,
            "score_pertinence":  score,
            "source_rss":        meta.get("source_rss", meta.get("label", "")),
            "type_doc":          "article",
            "scraped_at":        datetime.now(timezone.utc).isoformat(),
        }
        _etat["articles"].append(article)
        urls_corpus.add(url)  # évite les doublons intra-run
        done_urls.add(url)
        _etat["checkpoint"].add(url)
        stats["retenus"] += 1
        log.info("  RETENU score=%d, %d mots", score, nb_mots)
        _ecrire_log_csv({"url": url, "source": meta.get("source_rss",""),
                         "statut": "retenu", "nb_mots": nb_mots,
                         "score_pertinence": score, "date": resultat["date"]})

        if idx % CHECKPOINT_INTERVAL == 0:
            sauvegarder_checkpoint()

        time.sleep(random.uniform(1.0, 2.5))

    return stats, sautes

# ---------------------------------------------------------------------------
# Fusion avec rss_articles.json existant
# ---------------------------------------------------------------------------

def fusionner_et_sauvegarder(nouveaux: list[dict]) -> int:
    existants = charger_json(OUT_ARTICLES, [])
    urls_existantes = {a["url"] for a in existants if isinstance(a, dict) and a.get("url")}
    a_ajouter = [a for a in nouveaux if a["url"] not in urls_existantes]
    fusionnes = existants + a_ajouter
    sauvegarder_json(OUT_ARTICLES, fusionnes)
    return len(a_ajouter)

# ---------------------------------------------------------------------------
# Résumé final
# ---------------------------------------------------------------------------

def afficher_resume(nb_collectees, nb_decode_echecs, nb_sautes, stats):
    retenus     = stats["retenus"]
    trop_courts = stats["trop_courts"]
    hors_sujet  = stats["hors_sujet"]
    erreurs     = stats["erreurs"]
    telecharges = retenus + trop_courts + hors_sujet + erreurs

    print("\n")
    print("╔══════════════════════════════════════════════════╗")
    print("║         RSS ÉTENDU — RÉSULTATS FINAUX            ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  URLs collectées via RSS        : {nb_collectees:<15d}║")
    print(f"║  Décodages Google News échoués  : {nb_decode_echecs:<4d} (skippées)  ║")
    print(f"║  Déjà dans le corpus            : {nb_sautes:<4d} (skippées)  ║")
    print(f"║  Téléchargées                   : {telecharges:<15d}║")
    print(f"║  Articles retenus               : {retenus:<15d}║")
    print(f"║  Trop courts (< 100 mots)       : {trop_courts:<15d}║")
    print(f"║  Hors sujet                     : {hors_sujet:<15d}║")
    print(f"║  Erreurs réseau                 : {erreurs:<15d}║")
    print("╚══════════════════════════════════════════════════╝")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=== scraper_rss_etendu_bacot.py démarré ===")

    # Vérification googlenewsdecoder
    if not GNEWS_DECODER_AVAILABLE:
        print(
            "\nERREUR : la librairie 'googlenewsdecoder' est requise.\n"
            "Installez-la avec :\n\n"
            "    pip install googlenewsdecoder\n\n"
            "puis relancez le script."
        )
        sys.exit(1)

    # Charger checkpoint
    done_urls = charger_checkpoint()
    _etat["checkpoint"] = set(done_urls)

    # Charger URLs corpus existant
    urls_corpus = charger_urls_corpus()

    # Ajouter les URLs déjà dans rss_articles.json (fusions précédentes)
    for a in charger_json(OUT_ARTICLES, []) + _etat["articles"]:
        if isinstance(a, dict) and a.get("url"):
            urls_corpus.add(a["url"])

    # --- Partie A ---
    log.info("--- PARTIE A : Google News RSS ---")
    urls_gnews, nb_decode_echecs = collecter_gnews_rss()

    # --- Partie B ---
    if _shutdown:
        sauvegarder_checkpoint()
        log.info("Arrêt demandé — script interrompu après Partie A.")
        return

    log.info("--- PARTIE B : Flux RSS directs ---")
    urls_directs = collecter_flux_directs()

    # Fusion des listes
    toutes_urls = urls_gnews + urls_directs
    nb_collectees = len(toutes_urls)

    # Sauvegarder la liste brute pour debug
    sauvegarder_json(OUT_URLS, toutes_urls)
    log.info("URLs brutes sauvegardées → %s", OUT_URLS)

    # --- Partie C ---
    if _shutdown:
        sauvegarder_checkpoint()
        log.info("Arrêt demandé — script interrompu après Partie B.")
        return

    log.info("--- PARTIE C : Téléchargement et extraction ---")
    stats, nb_sautes = telecharger_articles(toutes_urls, urls_corpus, done_urls)

    # Sauvegarde finale
    _flush_log_csv()
    nb_ajoutes = fusionner_et_sauvegarder(_etat["articles"])
    sauvegarder_json(OUT_ECHECS, _etat["echecs"])

    # Nettoyer le checkpoint si tout s'est bien passé
    if not _shutdown and OUT_CHECKPOINT.exists():
        OUT_CHECKPOINT.unlink()
        log.info("Checkpoint supprimé (run complet).")
    else:
        sauvegarder_checkpoint()

    log.info("%d nouveaux articles ajoutés à %s", nb_ajoutes, OUT_ARTICLES)
    afficher_resume(nb_collectees, nb_decode_echecs, nb_sautes, stats)


if __name__ == "__main__":
    main()
