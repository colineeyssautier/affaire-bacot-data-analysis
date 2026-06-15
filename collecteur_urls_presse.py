#!/usr/bin/env python3
"""
collecteur_urls_presse.py
Collecte maximale d'URLs d'articles de presse — Affaire Valérie Bacot.

Sources :
  A. urls_raw.json — 140 URLs Google News déjà collectées, non encore décodées
  B. GDELT DOC API (avec backoff correct) — couverture internationale

Exclut strictement tout ce qui n'est pas de la presse (YouTube, Twitter…).

Produit :
  corpus_bacot/presse_nouveaux.json  — nouveaux articles extraits
  corpus_bacot/presse_urls.json      — toutes les URLs collectées (debug)
  corpus_bacot/presse_echecs.json    — URLs en échec

Usage :
    python collecteur_urls_presse.py
"""

import concurrent.futures
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    import trafilatura
except ImportError:
    print("ERREUR : pip install trafilatura")
    sys.exit(1)

try:
    import urllib3
    import warnings
    warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

try:
    from googlenewsdecoder import new_decoderv1 as gnews_decode
    GNEWS_OK = True
except ImportError:
    GNEWS_OK = False
    print("AVERTISSEMENT : googlenewsdecoder non installé — Partie A ignorée.")

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_DIR     = Path("corpus_bacot")
OUT_NOUVEAUX   = CORPUS_DIR / "presse_nouveaux.json"
OUT_URLS       = CORPUS_DIR / "presse_urls.json"
OUT_ECHECS     = CORPUS_DIR / "presse_echecs.json"
OUT_CHECKPOINT = CORPUS_DIR / "presse_checkpoint.json"
URLS_RAW       = CORPUS_DIR / "urls_raw.json"

SOURCES_PRESSE_EXISTANTES = [
    CORPUS_DIR / "corpus_bacot.json",
    CORPUS_DIR / "rss_articles.json",
    CORPUS_DIR / "wayback_articles.json",
    CORPUS_DIR / "presse_nouveaux.json",
]

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("collecteur_presse.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MIN_MOTS          = 100
CHECKPOINT_INTV   = 25
TRAFILATURA_TO    = 30

DOMAINES_EXCLUS = frozenset({
    "youtube.com", "youtu.be",
    "twitter.com", "x.com", "t.co",
    "facebook.com", "fb.com", "instagram.com",
    "tiktok.com", "linkedin.com", "pinterest.com",
    "reddit.com", "discord.com",
    "wikipedia.org", "wikimedia.org", "wikidata.org",
    "google.com", "google.fr", "news.google.com",
    "amazon.fr", "amazon.com", "fnac.com", "decitre.fr",
    "babelio.com", "goodreads.com", "senscritique.com",
    "allocine.fr", "imdb.com",
    "change.org", "avaaz.org", "mesopinions.com",
    "paypal.com", "leetchi.com", "gofundme.com",
})

# ─── PARTIE A — urls_raw.json ─────────────────────────────────────────────────

def _decoder_gnews(url_gnews: str) -> str | None:
    if not GNEWS_OK:
        return None
    try:
        result = gnews_decode(url_gnews)
        decoded = (
            result.get("decoded_url") or result.get("url") or ""
        ) if isinstance(result, dict) else str(result or "")
        if not decoded or not decoded.startswith("http"):
            return None
        if "news.google.com" in decoded or "google.com/search" in decoded:
            return None
        return decoded
    except Exception as e:
        log.debug("Décodage GNews échoué : %s", e)
        return None


def collecter_urls_raw() -> list[dict]:
    """Décode les 140 URLs Google News de urls_raw.json."""
    if not URLS_RAW.exists():
        log.info("urls_raw.json absent — Partie B ignorée.")
        return []
    if not GNEWS_OK:
        log.warning("googlenewsdecoder non installé — Partie B ignorée.")
        return []

    raw = charger_json(URLS_RAW, [])
    collectes: list[dict] = []
    nb_echecs = 0

    log.info("[URLs RAW] %d entrées à décoder", len(raw))
    for item in raw:
        url_gnews = (item.get("url_google") or item.get("url") or "").strip()
        if not url_gnews:
            continue
        url_reelle = _decoder_gnews(url_gnews)
        if url_reelle is None:
            nb_echecs += 1
            continue
        if _est_non_presse(url_reelle):
            continue
        collectes.append({
            "url":          url_reelle,
            "titre_gnews":  (item.get("titre") or item.get("title") or "").strip(),
            "date_gnews":   (item.get("date") or "")[:10],
            "source_gnews": _domaine(url_reelle),
            "label":        "urls_raw",
        })
        time.sleep(0.15)

    log.info("Partie A — %d URLs décodées (%d échecs)", len(collectes), nb_echecs)
    return collectes


# ─── PARTIE B — Bing News RSS ─────────────────────────────────────────────────
# Bing News a un index différent de Google News, donne des URLs directes (pas
# d'encodage), et ne rate-limite pas sur des requêtes espacées de 2-3 secondes.
# Chaque requête retourne jusqu'à ~15 articles en RSS.

BING_RSS_BASE = "https://www.bing.com/news/search?q={query}&format=RSS&setlang=fr&cc=FR"

REQUETES_BING = [
    # Nom seul / complet
    '"valérie bacot"',
    '"valerie bacot"',
    # Co-occurrences thématiques — capturent des articles qui ne citent que le nom de famille
    'bacot "daniel polette"',
    'bacot "légitime défense"',
    'bacot "legitime defense"',
    'bacot "violences conjugales"',
    'bacot "tout le monde savait"',
    'bacot proxénète',
    'bacot emprise',
    'bacot clayette',
    'bacot verdict',
    'bacot procès assises',
    'bacot sursis acquittement',
    'bacot livre',
    'bacot sénat',
    'bacot féminisme féminicide',
    'bacot "jacqueline sauvage"',
    'bacot tomasini',
    # Saône-et-Loire / région — capturent la presse locale
    'bacot "saône-et-loire"',
    'bacot chalon',
]


def collecter_bing_news() -> list[dict]:
    """
    Interroge Bing News RSS pour chaque requête thématique.
    Retourne des URLs directes d'articles de presse, sans décodage.
    """
    import xml.etree.ElementTree as ET

    collectes: list[dict] = []
    nb_requetes = len(REQUETES_BING)

    for idx, requete in enumerate(REQUETES_BING, 1):
        url_rss = BING_RSS_BASE.format(query=__import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(requete))
        log.info("[Bing %d/%d] %s", idx, nb_requetes, requete)

        try:
            resp = requests.get(url_rss, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:
            log.warning("  Bing inaccessible : %s", e)
            time.sleep(2)
            continue

        items = root.findall(".//item")
        retenus = 0
        for item in items:
            url   = (item.findtext("link") or "").strip()
            titre = (item.findtext("title") or "").strip()
            date  = (item.findtext("pubDate") or "").strip()

            if not url or not url.startswith("http"):
                continue
            if _est_non_presse(url):
                continue

            collectes.append({
                "url":          url,
                "titre_gnews":  titre,
                "date_gnews":   date,
                "source_gnews": _domaine(url),
                "label":        f"bing_{idx}",
            })
            retenus += 1

        log.info("  → %d articles", retenus)
        time.sleep(2.0)

    log.info("Partie B — %d URLs collectées via Bing News", len(collectes))
    return collectes


# ─── Utilitaires communs ──────────────────────────────────────────────────────

def _domaine(url: str) -> str:
    try:
        h = urlparse(url).hostname or ""
        return h.removeprefix("www.")
    except Exception:
        return ""


def _est_non_presse(url: str) -> bool:
    d = _domaine(url)
    return any(d == ex or d.endswith("." + ex) for ex in DOMAINES_EXCLUS)


def charger_json(path: Path, defaut):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Lecture %s : %s", path, e)
    return defaut


def sauvegarder_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── État global ──────────────────────────────────────────────────────────────

_state = {"articles": [], "echecs": [], "checkpoint": set()}


def sauvegarder_checkpoint():
    sauvegarder_json(OUT_CHECKPOINT, {
        "articles":  _state["articles"],
        "echecs":    _state["echecs"],
        "done_urls": list(_state["checkpoint"]),
    })
    existants = charger_json(OUT_NOUVEAUX, [])
    urls_ex = {a["url"] for a in existants if isinstance(a, dict) and a.get("url")}
    a_ajouter = [a for a in _state["articles"] if a["url"] not in urls_ex]
    sauvegarder_json(OUT_NOUVEAUX, existants + a_ajouter)
    log.info("Checkpoint : %d articles, %d URLs traitées",
             len(_state["articles"]), len(_state["checkpoint"]))


def charger_checkpoint() -> set:
    if not OUT_CHECKPOINT.exists():
        return set()
    data = charger_json(OUT_CHECKPOINT, {})
    _state["articles"] = data.get("articles", [])
    _state["echecs"]   = data.get("echecs", [])
    done = set(data.get("done_urls", []))
    log.info("Checkpoint chargé : %d articles, %d URLs déjà traitées",
             len(_state["articles"]), len(done))
    return done


def charger_urls_presse_existantes() -> set[str]:
    urls = set()
    for path in SOURCES_PRESSE_EXISTANTES:
        if not path.exists():
            continue
        data = charger_json(path, [])
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get("source") == "youtube_commentaire":
                continue
            url = (item.get("url") or "").strip()
            if url and not _est_non_presse(url):
                urls.add(url)
    log.info("Corpus presse existant : %d URLs", len(urls))
    return urls


# ─── Extraction du texte ──────────────────────────────────────────────────────

def _decode_response(resp) -> str:
    if resp.encoding and resp.encoding.lower().replace("-", "") in ("iso88591", "latin1"):
        apparent = (resp.apparent_encoding or "").lower()
        if apparent.startswith("utf") or apparent.startswith("ascii"):
            resp.encoding = resp.apparent_encoding
    return resp.text


def _run_trafilatura(html: str, mode: dict):
    return trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        output_format="json",
        with_metadata=True,
        **mode,
    )


def _extraire_article(url: str) -> dict | None:
    html = None
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
            return {"erreur": f"SSL : {e}"}
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code in (404, 403, 410, 451):
            return {"erreur": f"HTTP {code}"}
        if code == 429:
            log.warning("  429 — pause 30s")
            time.sleep(30)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
                resp.raise_for_status()
                html = _decode_response(resp)
            except Exception as e2:
                return {"erreur": f"429 retry : {e2}"}
        else:
            return {"erreur": str(e)}
    except Exception as e:
        return {"erreur": str(e)}

    for mode in [{"favor_precision": True}, {"favor_recall": True}]:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_run_trafilatura, html, mode)
                try:
                    raw = future.result(timeout=TRAFILATURA_TO)
                except concurrent.futures.TimeoutError:
                    return {"erreur": "trafilatura timeout"}
            if raw:
                d = json.loads(raw)
                if d.get("text"):
                    return d
        except Exception:
            pass

    return {"erreur": "trafilatura : rien extrait"}


def _est_pertinent(texte: str) -> bool:
    t = texte.lower()
    if "bacot" in t:
        return True
    if "polette" in t and ("valérie" in t or "valerie" in t):
        return True
    if "tout le monde savait" in t and "clayette" in t:
        return True
    return False


def telecharger_articles(urls_meta: list[dict], urls_existantes: set[str], done_urls: set[str]):
    stats = {"retenus": 0, "trop_courts": 0, "hors_sujet": 0, "erreurs": 0}

    seen: set[str] = set()
    urls_uniques = []
    for m in urls_meta:
        u = m["url"].strip()
        if u not in seen:
            seen.add(u)
            urls_uniques.append(m)

    a_telecharger = [
        m for m in urls_uniques
        if m["url"].strip() not in urls_existantes and m["url"].strip() not in done_urls
    ]
    sautes = len(urls_uniques) - len(a_telecharger)
    log.info("%d URLs à télécharger (%d déjà dans le corpus)", len(a_telecharger), sautes)

    total = len(a_telecharger)
    for idx, meta in enumerate(a_telecharger, 1):
        url = meta["url"].strip()
        log.info("[%d/%d] %s", idx, total, url[:90])

        resultat = _extraire_article(url)

        if resultat is None or "erreur" in resultat:
            raison = (resultat or {}).get("erreur", "inconnu")
            log.warning("  ECHEC : %s", raison)
            _state["echecs"].append({"url": url, "raison": raison,
                                     "source": meta.get("source_gnews", "")})
            stats["erreurs"] += 1
            done_urls.add(url)
            _state["checkpoint"].add(url)
            time.sleep(random.uniform(1.0, 2.5))
            continue

        texte   = (resultat.get("text") or "").strip()
        nb_mots = len(texte.split())

        if nb_mots < MIN_MOTS:
            log.info("  trop court (%d mots)", nb_mots)
            stats["trop_courts"] += 1
        elif not _est_pertinent(texte):
            log.info("  hors sujet")
            stats["hors_sujet"] += 1
        else:
            article = {
                "url":        url,
                "titre":      (resultat.get("title") or meta.get("titre_gnews") or "").strip(),
                "texte":      texte,
                "text":       texte,
                "auteur":     (resultat.get("author") or "").strip(),
                "date":       (resultat.get("date") or meta.get("date_gnews") or "")[:10],
                "sitename":   (resultat.get("sitename") or meta.get("source_gnews") or "").strip(),
                "description":(resultat.get("description") or "").strip(),
                "nb_mots":    nb_mots,
                "word_count": nb_mots,
                "source":     meta.get("label", "collecteur_presse"),
                "type_doc":   "article",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            _state["articles"].append(article)
            urls_existantes.add(url)
            stats["retenus"] += 1
            log.info("  RETENU — %d mots | %s", nb_mots,
                     article["sitename"] or _domaine(url))

        done_urls.add(url)
        _state["checkpoint"].add(url)

        if idx % CHECKPOINT_INTV == 0:
            sauvegarder_checkpoint()

        time.sleep(random.uniform(1.5, 3.0))

    return stats, sautes


def fusionner_et_sauvegarder(nouveaux: list[dict]) -> int:
    existants = charger_json(OUT_NOUVEAUX, [])
    urls_ex = {a["url"] for a in existants if isinstance(a, dict) and a.get("url")}
    a_ajouter = [a for a in nouveaux if a["url"] not in urls_ex]
    sauvegarder_json(OUT_NOUVEAUX, existants + a_ajouter)
    return len(a_ajouter)


# ─── Résumé d'une phase ───────────────────────────────────────────────────────

def _afficher_stats(label: str, stats: dict, nb_sautes: int, nb_ajoutes: int):
    t = stats["retenus"] + stats["trop_courts"] + stats["hors_sujet"] + stats["erreurs"]
    log.info(
        "%s — téléchargés: %d | retenus: %d | trop courts: %d | hors sujet: %d | erreurs: %d | sautes: %d | ajoutés: %d",
        label, t, stats["retenus"], stats["trop_courts"], stats["hors_sujet"],
        stats["erreurs"], nb_sautes, nb_ajoutes,
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=== collecteur_urls_presse.py démarré ===")

    done_urls = charger_checkpoint()
    _state["checkpoint"] = set(done_urls)
    urls_existantes = charger_urls_presse_existantes()
    for a in charger_json(OUT_NOUVEAUX, []) + _state["articles"]:
        if isinstance(a, dict) and a.get("url"):
            urls_existantes.add(a["url"])

    totaux = {"retenus": 0, "trop_courts": 0, "hors_sujet": 0, "erreurs": 0}
    nb_ajoutes_total = 0

    # ── Partie A : urls_raw.json — décoder et scraper immédiatement ──────────
    log.info("=== PARTIE A : urls_raw.json ===")
    urls_raw = collecter_urls_raw()
    if urls_raw:
        log.info("=== PARTIE A : téléchargement (%d URLs) ===", len(urls_raw))
        stats_a, sautes_a = telecharger_articles(urls_raw, urls_existantes, done_urls)
        nb_a = fusionner_et_sauvegarder(_state["articles"])
        _afficher_stats("Partie A", stats_a, sautes_a, nb_a)
        nb_ajoutes_total += nb_a
        for k in totaux:
            totaux[k] += stats_a[k]

    # ── Partie B : Bing News RSS — collecter et scraper immédiatement ────────
    log.info("=== PARTIE B : Bing News RSS ===")
    urls_bing = collecter_bing_news()
    if urls_bing:
        log.info("=== PARTIE B : téléchargement (%d URLs) ===", len(urls_bing))
        stats_b, sautes_b = telecharger_articles(urls_bing, urls_existantes, done_urls)
        nb_b = fusionner_et_sauvegarder(_state["articles"])
        _afficher_stats("Partie B", stats_b, sautes_b, nb_b)
        nb_ajoutes_total += nb_b
        for k in totaux:
            totaux[k] += stats_b[k]

    sauvegarder_json(OUT_ECHECS, _state["echecs"])
    if OUT_CHECKPOINT.exists():
        OUT_CHECKPOINT.unlink()

    t = sum(totaux.values())
    print("\n")
    print("╔══════════════════════════════════════════════════╗")
    print("║    COLLECTEUR PRESSE — RÉSULTATS FINAUX          ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Téléchargées (A+B)             : {t:<14d}║")
    print(f"║  Articles retenus               : {totaux['retenus']:<14d}║")
    print(f"║  Trop courts (< {MIN_MOTS} mots)      : {totaux['trop_courts']:<14d}║")
    print(f"║  Hors sujet                     : {totaux['hors_sujet']:<14d}║")
    print(f"║  Erreurs réseau                 : {totaux['erreurs']:<14d}║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  → corpus_bacot/presse_nouveaux.json ({nb_ajoutes_total} ajoutés)║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print("Étapes suivantes :")
    print("  python fusionner_corpus.py")
    print("  python Classifier_bacot.py")


if __name__ == "__main__":
    main()
