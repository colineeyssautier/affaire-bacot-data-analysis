"""
scraper_wayback_bacot.py — Articles archivés via Wayback Machine CDX API
=========================================================================
Pipeline :
  1. Interroge l'API CDX (Internet Archive) pour récupérer les URLs archivées
     liées à l'affaire Valérie Bacot, sur 21 domaines de presse + 5 patterns larges
  2. Télécharge chaque page archivée depuis web.archive.org
  3. Extrait le texte éditorial avec trafilatura
  4. Sauvegarde le corpus en JSON (compatible avec corpus_bacot.json existant)

Installation :
    pip install requests trafilatura urllib3

Usage :
    python scraper_wayback_bacot.py

Produit :
    corpus_bacot/wayback_articles.json    — articles extraits
    corpus_bacot/urls_wayback_cdx.json    — URLs collectées par CDX
    corpus_bacot/wayback_failed.json      — URLs en échec
    corpus_bacot/wayback_checkpoint.json  — checkpoint (supprimé en fin de run)
"""

import json
import logging
import random
import time
from datetime import datetime
from pathlib import Path

import requests
import trafilatura
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ─── Configuration ────────────────────────────────────────────────────────────

CDX_BASE     = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "https://web.archive.org/web"

DATE_FROM = "20190101"
DATE_TO   = "20260601"
CDX_LIMIT = 500

MIN_WORDS = 150
PAUSE_MIN = 1.5
PAUSE_MAX = 3.5

OUTPUT_DIR      = Path("corpus_bacot")
OUTPUT_JSON     = OUTPUT_DIR / "wayback_articles.json"
OUTPUT_FAILED   = OUTPUT_DIR / "wayback_failed.json"
CHECKPOINT_FILE = OUTPUT_DIR / "wayback_checkpoint.json"

# Mots-clés pour filtrer la pertinence (URL et texte)
MOTS_CLES = ["bacot", "polette"]

# Approche correcte pour CDX :
# - matchType=domain → toutes les URLs d'un domaine et ses sous-domaines
# - filter=original:.*keyword.* → filtre regex côté serveur sur l'URL originale
# Les patterns *.domain/*keyword* NE fonctionnent PAS : CDX ignore la sous-chaîne
# après le premier wildcard et retourne toutes les pages du domaine.

_DOMAINES_PRESSE = [
    # Nationale généraliste
    "lemonde.fr", "lefigaro.fr", "liberation.fr", "lepoint.fr",
    "lexpress.fr", "nouvelobs.com", "lobs.fr",
    # Télé/radio
    "francetvinfo.fr", "france24.com", "bfmtv.com", "rtl.fr", "europe1.fr",
    "rfi.fr", "tf1info.fr", "tf1.fr", "lci.fr",
    # Web/tabloïd
    "20minutes.fr", "leparisien.fr", "huffingtonpost.fr", "slate.fr",
    "cnews.fr", "capital.fr",
    # Régionale — Bourgogne/Saône-et-Loire (région d'origine de Valérie Bacot)
    "lejsl.com", "bienpublic.com", "estrepublicain.fr",
    # Autres régionales
    "lavoixdunord.fr", "letelegramme.fr", "sudouest.fr", "midilibre.fr",
    "nicematin.com", "laprovence.com",
    # Presse magazine / opinion
    "humanite.fr", "marianne.net", "politis.fr", "mediacites.fr",
    # International francophone
    "rtbf.be", "rts.ch", "lapresse.ca", "ledevoir.com",
]

# Mots-clés passés au filtre CDX filter=original:.*keyword.*
_KEYWORDS_CDX = ["bacot", "polette"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_wayback.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
logging.getLogger("trafilatura").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


# ─── Partie 1 : API CDX ───────────────────────────────────────────────────────

def requete_cdx(params: list[tuple], label: str = "") -> list[dict]:
    """
    Interroge l'API CDX avec 3 tentatives et backoff exponentiel.
    Retourne une liste de dicts {timestamp, original, statuscode, mimetype}.
    """
    session = requests.Session()

    for tentative in range(3):
        try:
            resp = session.get(
                CDX_BASE,
                params=params,
                headers={"User-Agent": HEADERS["User-Agent"]},
                timeout=90,
            )
            resp.raise_for_status()

            lignes = resp.json()
            if not lignes or len(lignes) <= 1:
                log.info(f"  CDX '{label}' : 0 résultat")
                return []

            champs = lignes[0]
            resultats = [
                dict(zip(champs, ligne))
                for ligne in lignes[1:]
                if len(ligne) >= len(champs)
            ]
            log.info(f"  CDX '{label}' : {len(resultats)} captures")
            return resultats

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 429:
                delai = (2 ** tentative) * 10
                log.warning(f"  Rate limit CDX — pause {delai}s (tentative {tentative+1}/3)")
                time.sleep(delai)
            elif code in (404, 400):
                log.debug(f"  CDX '{label}' : HTTP {code} — pas de résultat")
                return []
            else:
                log.warning(f"  HTTP {code} pour '{label}' (tentative {tentative+1}/3)")
                time.sleep(2 ** tentative * 2)

        except requests.exceptions.Timeout:
            log.warning(f"  Timeout CDX '{label}' (tentative {tentative+1}/3)")
            time.sleep(2 ** tentative * 3)

        except Exception as e:
            log.warning(f"  Erreur CDX '{label}' : {e} (tentative {tentative+1}/3)")
            time.sleep(2 ** tentative * 2)

    log.error(f"  CDX échoué après 3 tentatives pour '{label}'")
    return []


def url_est_pertinente(url: str) -> bool:
    """Vérifie que l'URL contient au moins un mot-clé lié à l'affaire Bacot."""
    url_lower = url.lower()
    return any(kw in url_lower for kw in MOTS_CLES)


def est_pertinent(article: dict) -> bool:
    """Vérifie que le texte ou le titre mentionne l'affaire Bacot.
    "polette" seul ne suffit pas — il doit co-occurrer avec "bacot" ou "valérie"."""
    texte = (article.get("text", "") + " " + article.get("title", "")).lower()
    if "bacot" in texte:
        return True
    if "polette" in texte and "valérie" in texte:
        return True
    return False


def _params_domaine(domain: str, keyword: str) -> list[tuple]:
    """
    Requête CDX par domaine avec filtre regex sur l'URL originale.
    matchType=domain couvre le domaine et tous ses sous-domaines.
    filter=original:.*keyword.* garantit que "keyword" est dans l'URL retournée.
    """
    return [
        ("url",       domain),
        ("matchType", "domain"),
        ("output",    "json"),
        ("fl",        "timestamp,original,statuscode,mimetype"),
        ("filter",    "statuscode:200"),
        ("filter",    "mimetype:text/html"),
        ("filter",    f"original:.*{keyword}.*"),
        ("collapse",  "urlkey"),
        ("collapse",  "timestamp:8"),
        ("limit",     str(CDX_LIMIT)),
        ("from",      DATE_FROM),
        ("to",        DATE_TO),
    ]


def collecter_urls_depuis_rss() -> dict[str, str]:
    """
    Lit urls_rss.json et interroge CDX avec matchType=exact pour chaque URL résolue.
    Retourne {url_originale: timestamp_le_plus_recent} pour les URLs archivées.
    """
    fichier_rss = OUTPUT_DIR / "urls_rss.json"
    if not fichier_rss.exists():
        log.info("urls_rss.json introuvable — étape RSS ignorée")
        return {}

    with open(fichier_rss, encoding="utf-8") as f:
        entrees = json.load(f)

    urls = [e["url"] for e in entrees if "url" in e and e["url"]]
    log.info(f"URLs RSS à vérifier dans CDX : {len(urls)}")

    captures: dict[str, str] = {}
    for i, url in enumerate(urls, 1):
        params = [
            ("url",       url),
            ("matchType", "exact"),
            ("output",    "json"),
            ("fl",        "timestamp,original,statuscode,mimetype"),
            ("filter",    "statuscode:200"),
            ("filter",    "mimetype:text/html"),
            ("collapse",  "timestamp:8"),
            ("limit",     "5"),
            ("from",      DATE_FROM),
            ("to",        DATE_TO),
        ]
        resultats = requete_cdx(params, label=f"rss {i}/{len(urls)}")
        if resultats:
            meilleur = max(resultats, key=lambda r: r.get("timestamp", ""))
            ts      = meilleur.get("timestamp", "")
            url_cap = meilleur.get("original", url)
            if ts:
                captures[url_cap] = ts
        time.sleep(0.5)

    log.info(f"URLs RSS archivées dans Wayback : {len(captures)}/{len(urls)}")
    return captures


def collecter_urls_wayback() -> dict[str, str]:
    """
    Interroge l'API CDX avec matchType=domain + filter=original pour chaque
    domaine × mot-clé. Retourne {url_originale: timestamp_le_plus_recent}.
    """
    captures: dict[str, str] = {}
    domaines_echec: set[str] = set()
    nb_requetes = len(_DOMAINES_PRESSE) * len(_KEYWORDS_CDX)

    log.info("=" * 60)
    log.info("PARTIE 1 — Collecte des URLs via CDX Wayback Machine")
    log.info("=" * 60)
    log.info(f"\n{nb_requetes} requêtes CDX ({len(_DOMAINES_PRESSE)} domaines × {len(_KEYWORDS_CDX)} mots-clés)")

    for domain in _DOMAINES_PRESSE:
        domaine_ok = False
        for keyword in _KEYWORDS_CDX:
            if domain in domaines_echec:
                log.info(f"  Domaine '{domain}' ignoré (tous les mots-clés précédents ont échoué)")
                continue
            label = f"{domain} / {keyword}"
            resultats = requete_cdx(_params_domaine(domain, keyword), label=label)
            if resultats:
                domaine_ok = True
                for cap in resultats:
                    url = cap.get("original", "")
                    ts  = cap.get("timestamp", "")
                    if url and ts:
                        if url not in captures or ts > captures[url]:
                            captures[url] = ts
            elif not domaine_ok:
                # Aucun résultat sur le premier mot-clé → on ne perd pas de temps sur les suivants
                domaines_echec.add(domain)
            time.sleep(1.0)

    if domaines_echec:
        log.warning(f"Domaines sans résultat CDX ({len(domaines_echec)}) : {', '.join(sorted(domaines_echec))}")
    log.info(f"\nURLs collectées : {len(captures)}")
    return captures


# ─── Partie 2 : Téléchargement et extraction ─────────────────────────────────

def charger_urls_corpus_existant() -> set[str]:
    """
    Charge les URLs déjà présentes dans le corpus pour éviter les doublons.
    Cherche d'abord articles_existants.json, sinon parcourt tous les JSON du corpus.
    """
    urls: set[str] = set()

    fichier_index = OUTPUT_DIR / "articles_existants.json"
    if fichier_index.exists():
        with open(fichier_index, encoding="utf-8") as f:
            data = json.load(f)
        urls = set(data) if isinstance(data, list) else set(data.keys())
        log.info(f"Index corpus : {len(urls)} URLs chargées depuis articles_existants.json")
        return urls

    # Parcourt tous les fichiers JSON du corpus (hors listes d'URLs brutes et échecs)
    prefixes_exclus = ("failed_", "urls_", "wayback_checkpoint")
    for fichier in OUTPUT_DIR.glob("*.json"):
        if any(fichier.name.startswith(p) for p in prefixes_exclus):
            continue
        try:
            with open(fichier, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "url" in item:
                        urls.add(item["url"])
        except Exception as e:
            log.debug(f"  Lecture {fichier.name} ignorée : {e}")

    log.info(f"Index corpus : {len(urls)} URLs chargées depuis le corpus existant")
    return urls


def telecharger_page_wayback(timestamp: str, url_originale: str) -> str | None:
    """
    Télécharge une page archivée depuis Wayback Machine.
    Retente 3 fois avec backoff ; bascule sur verify=False en cas d'erreur SSL.
    """
    url_wayback = f"{WAYBACK_BASE}/{timestamp}/{url_originale}"

    for tentative in range(3):
        try:
            resp = requests.get(url_wayback, headers=HEADERS, timeout=20, verify=True)
            resp.raise_for_status()
            return resp.text

        except requests.exceptions.SSLError:
            try:
                resp = requests.get(url_wayback, headers=HEADERS, timeout=20, verify=False)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                log.debug(f"  SSL + fallback échoué : {e}")
                return None

        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code in (404, 403, 410):
                return None  # pas la peine de réessayer
            log.debug(f"  HTTP {code} (tentative {tentative+1}/3)")
            time.sleep(2 ** tentative)

        except requests.exceptions.Timeout:
            log.debug(f"  Timeout (tentative {tentative+1}/3)")
            time.sleep(2 ** tentative)

        except Exception as e:
            log.debug(f"  Erreur téléchargement (tentative {tentative+1}/3) : {e}")
            time.sleep(2 ** tentative)

    return None


def extraire_texte(html: str, url: str) -> dict | None:
    """
    Extrait le texte éditorial via trafilatura.
    Essaie favor_precision d'abord, puis favor_recall si résultat None.
    Retourne None si le texte fait moins de MIN_WORDS mots.
    """
    kwargs = dict(
        include_comments=False,
        include_tables=False,
        no_fallback=False,
        output_format="json",
        with_metadata=True,
        url=url,
    )

    result = trafilatura.extract(html, favor_precision=True, **kwargs)
    if result is None:
        result = trafilatura.extract(html, favor_recall=True, **kwargs)
    if result is None:
        return None

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return None

    text     = data.get("text", "") or ""
    nb_mots  = len(text.split())

    if nb_mots < MIN_WORDS:
        return None

    return {
        "text":        text,
        "title":       data.get("title", ""),
        "author":      data.get("author", ""),
        "date":        data.get("date", ""),
        "description": data.get("description", ""),
        "sitename":    data.get("sitename", ""),
        "word_count":  nb_mots,
    }


def _sauvegarder_checkpoint(articles: list[dict], urls_traitees: list[str]) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"articles": articles, "urls_traitees": urls_traitees},
            f, ensure_ascii=False,
        )


def _ecriture_incrementale(articles_base: list[dict], articles_run: list[dict]) -> int:
    """Écrit articles_base + articles_run dans OUTPUT_JSON sans doublons."""
    urls_base = {a["url"] for a in articles_base}
    nouveaux  = [a for a in articles_run if a["url"] not in urls_base]
    tous      = articles_base + nouveaux
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tous, f, ensure_ascii=False, indent=2)
    return len(tous)


def scraper_articles_wayback(
    captures: dict[str, str],
    urls_existantes: set[str],
) -> tuple[list[dict], list[dict]]:
    """
    Télécharge et extrait chaque article archivé.
    Reprend depuis le checkpoint si disponible.
    Retourne (articles_ok, articles_echec).
    """
    articles: list[dict] = []
    echecs:   list[dict] = []
    urls_traitees: set[str] = set()

    # Articles déjà dans le fichier de sortie (runs précédents) — base pour l'écriture incrémentale
    articles_base: list[dict] = []
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, encoding="utf-8") as f:
                articles_base = json.load(f)
        except Exception:
            articles_base = []

    # Reprise depuis checkpoint
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            checkpoint = json.load(f)
        articles_cp   = checkpoint.get("articles", [])
        urls_traitees = set(checkpoint.get("urls_traitees", []))
        # Filtre : ne garder que les articles pertinents du checkpoint
        articles = [a for a in articles_cp if est_pertinent(a)]
        ignores  = len(articles_cp) - len(articles)
        log.info(
            f"Reprise checkpoint : {len(articles)} articles pertinents "
            f"({ignores} non-pertinents écartés), "
            f"{len(urls_traitees)} URLs déjà traitées"
        )

    a_traiter = [
        (url, ts)
        for url, ts in captures.items()
        if url not in urls_existantes and url not in urls_traitees
    ]
    total   = len(a_traiter)
    skipped = len(captures) - total
    log.info(f"{total} URLs à scraper  ({skipped} déjà dans le corpus ou traitées)")

    for i, (url_originale, timestamp) in enumerate(a_traiter, 1):
        log.info(f"[{i}/{total}] {url_originale[:90]}")

        html = telecharger_page_wayback(timestamp, url_originale)

        if html is None:
            log.info("  → Téléchargement échoué")
            echecs.append({
                "url":       url_originale,
                "timestamp": timestamp,
                "raison":    "téléchargement échoué",
            })
        else:
            extrait = extraire_texte(html, url_originale)
            if extrait is None:
                log.info("  → Extraction échouée ou texte < 150 mots")
                echecs.append({
                    "url":       url_originale,
                    "timestamp": timestamp,
                    "raison":    "extraction échouée / texte trop court",
                })
            elif not est_pertinent({"text": extrait["text"], "title": extrait["title"]}):
                log.info(f"  → Non pertinent (aucune mention de {MOTS_CLES})")
                echecs.append({
                    "url":       url_originale,
                    "timestamp": timestamp,
                    "raison":    "texte non pertinent (pas de mention affaire Bacot)",
                })
            else:
                article = {
                    "url":               url_originale,
                    "url_wayback":       f"{WAYBACK_BASE}/{timestamp}/{url_originale}",
                    "timestamp_wayback": timestamp,
                    "text":              extrait["text"],
                    "title":             extrait["title"],
                    "author":            extrait["author"],
                    "date":              extrait["date"],
                    "description":       extrait["description"],
                    "sitename":          extrait["sitename"],
                    "source":            "wayback_machine",
                    "scraped_at":        datetime.now().isoformat(),
                    "word_count":        extrait["word_count"],
                }
                articles.append(article)
                log.info(
                    f"  → OK — {extrait['word_count']} mots | "
                    f"{extrait['title'][:60]}"
                )

        urls_traitees.add(url_originale)

        # Sauvegarde toutes les 20 URLs : checkpoint + écriture dans le JSON de sortie
        if i % 20 == 0:
            _sauvegarder_checkpoint(articles, list(urls_traitees))
            n = _ecriture_incrementale(articles_base, articles)
            log.info(f"  [checkpoint] {n} articles dans {OUTPUT_JSON.name}")

        if i < total:
            time.sleep(random.uniform(PAUSE_MIN, PAUSE_MAX))

    return articles, echecs


# ─── Sauvegarde finale ────────────────────────────────────────────────────────

def sauvegarder(articles: list[dict], echecs: list[dict]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Fusionne avec les articles wayback déjà sauvegardés (runs précédents)
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existants = json.load(f)
        urls_existantes_wb = {a["url"] for a in existants}
        nouveaux = [a for a in articles if a["url"] not in urls_existantes_wb]
        articles = existants + nouveaux
        log.info(f"Fusion : {len(existants)} existants + {len(nouveaux)} nouveaux = {len(articles)} total")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_FAILED, "w", encoding="utf-8") as f:
        json.dump(echecs, f, ensure_ascii=False, indent=2)

    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()

    log.info(f"""
╔══════════════════════════════════════════════════╗
║       WAYBACK MACHINE — RÉSULTATS FINAUX         ║
╠══════════════════════════════════════════════════╣
║  Articles extraits  : {len(articles):>5}                   ║
║  Échecs             : {len(echecs):>5}                   ║
╚══════════════════════════════════════════════════╝
→ Articles : {OUTPUT_JSON}
→ Échecs   : {OUTPUT_FAILED}
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run() -> None:
    log.info("Scraper Wayback Machine — Affaire Valérie Bacot")
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Avertissement si wayback_articles.json contient des données du run corrompu
    # (9001 faux positifs collectés avec les requêtes par domaine désormais supprimées)
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, encoding="utf-8") as f:
                existants = json.load(f)
            non_pertinents = [a for a in existants if not est_pertinent(a)]
            if non_pertinents:
                log.warning(
                    f"{len(non_pertinents)} articles non pertinents détectés dans "
                    f"{OUTPUT_JSON.name}. Suppression automatique avant le run."
                )
                pertinents = [a for a in existants if est_pertinent(a)]
                with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                    json.dump(pertinents, f, ensure_ascii=False, indent=2)
                log.info(f"  → {len(pertinents)} articles pertinents conservés.")
        except Exception:
            pass

    # Partie 1 : CDX API → URLs archivées (scan domain + injection RSS)
    captures = collecter_urls_wayback()

    log.info("=" * 60)
    log.info("PARTIE 1b — Injection des URLs RSS dans CDX")
    log.info("=" * 60)
    captures_rss = collecter_urls_depuis_rss()
    avant = len(captures)
    for url, ts in captures_rss.items():
        if url not in captures or ts > captures[url]:
            captures[url] = ts
    log.info(f"Après fusion RSS : {len(captures)} URLs ({len(captures) - avant} nouvelles)")

    if not captures:
        log.error("Aucune URL collectée via CDX. Arrêt.")
        return

    urls_cdx_path = OUTPUT_DIR / "urls_wayback_cdx.json"
    with open(urls_cdx_path, "w", encoding="utf-8") as f:
        json.dump(captures, f, ensure_ascii=False, indent=2)
    log.info(f"URLs CDX sauvegardées : {urls_cdx_path}")

    # Partie 2 : téléchargement + extraction
    log.info("=" * 60)
    log.info("PARTIE 2 — Téléchargement et extraction")
    log.info("=" * 60)

    urls_existantes = charger_urls_corpus_existant()
    articles, echecs = scraper_articles_wayback(captures, urls_existantes)

    sauvegarder(articles, echecs)


if __name__ == "__main__":
    run()
