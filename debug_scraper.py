#!/usr/bin/env python3
"""
debug_scraper.py
Outil de diagnostic pour scraper_rss_etendu_bacot.py.

Usage :
    python debug_scraper.py url <URL>          # teste l'extraction d'une URL
    python debug_scraper.py score <URL>        # détail du score de pertinence
    python debug_scraper.py add-url <URL>      # extrait et ajoute directement à rss_articles.json
    python debug_scraper.py analyse            # rejoue les URLs non-corpus avec score détaillé
    python debug_scraper.py rss                # vérifie tous les flux RSS directs
    python debug_scraper.py csv                # teste l'écriture du log CSV
    python debug_scraper.py timeout <URL>      # mesure le temps d'extraction
"""

import json
import sys
import time
import concurrent.futures
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

FLUX_RSS = [
    ("https://www.lejsl.com/rss",                                           "JSL"),
    ("https://france3-regions.francetvinfo.fr/bourgogne-franche-comte/rss", "France 3 BFC"),
    ("https://www.bienpublic.com/rss",                                      "Le Bien Public"),
    ("https://www.estrepublicain.fr/rss",                                   "Est Républicain"),
    ("https://www.leprogres.fr/rss",                                        "Le Progrès"),
    ("https://www.lyoncapitale.fr/feed/",                                   "Lyon Capitale"),
    ("https://www.bfmtv.com/rss/news-24-7/",                               "BFMTV"),
    ("https://www.20minutes.fr/feeds/rss-une.xml",                         "20 Minutes"),
    ("https://feeds.leparisien.fr/leparisien/rss",                         "Le Parisien"),
    ("https://www.francetvinfo.fr/titres.rss",                             "France Info"),
    ("https://www.huffingtonpost.fr/feeds/index.xml",                      "HuffPost"),
    ("https://www.madmoizelle.com/feed",                                   "Madmoizelle"),
    ("https://www.senat.fr/rss/presse.rss",                               "Sénat"),
]


# ── Commande : url ────────────────────────────────────────────────────────────

def cmd_url(url: str):
    try:
        import trafilatura
    except ImportError:
        print("ERREUR : trafilatura non installé")
        return

    print(f"\n{'─'*60}")
    print(f"URL : {url}")
    print(f"{'─'*60}")

    # Requête
    t0 = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
        t_req = time.time() - t0
        print(f"[OK] HTTP {resp.status_code} — {len(resp.content)//1024} Ko — {t_req:.1f}s")
        html = resp.text
    except Exception as e:
        print(f"[ECHEC] Requête : {e}")
        return

    # Extraction trafilatura
    t1 = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(trafilatura.extract, html,
                               include_comments=False, include_tables=False,
                               output_format="json", with_metadata=True,
                               favor_precision=True)
            try:
                raw = future.result(timeout=30)
                t_traf = time.time() - t1
            except concurrent.futures.TimeoutError:
                print("[TIMEOUT] trafilatura a dépassé 30s")
                return
    except Exception as e:
        print(f"[ERREUR] trafilatura : {e}")
        return

    if not raw:
        print("[VIDE] trafilatura n'a rien extrait")
        return

    data = json.loads(raw)
    texte = data.get("text", "")
    nb_mots = len(texte.split())

    print(f"[OK] trafilatura — {nb_mots} mots — {t_traf:.1f}s")
    print(f"     Titre   : {data.get('title','—')[:80]}")
    print(f"     Date    : {data.get('date','—')}")
    print(f"     Auteur  : {data.get('author','—')}")
    print(f"     Site    : {data.get('sitename','—')}")
    print(f"\n--- Extrait (200 premiers mots) ---")
    print(" ".join(texte.split()[:200]))
    print(f"\nTemps total : {time.time()-t0:.1f}s")


# ── Commande : rss ────────────────────────────────────────────────────────────

def cmd_rss():
    import xml.etree.ElementTree as ET

    print(f"\n{'─'*60}")
    print("Vérification des flux RSS directs")
    print(f"{'─'*60}\n")

    ok, ko = [], []
    for url, nom in FLUX_RSS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            print(f"  [OK]  {nom:<25} {len(items):>3} items  {url}")
            ok.append(nom)
        except Exception as e:
            err = str(e)[:60]
            print(f"  [KO]  {nom:<25} {err}")
            ko.append((nom, url, err))

    print(f"\n{'─'*60}")
    print(f"OK : {len(ok)}   KO : {len(ko)}")
    if ko:
        print("\nFlux à corriger :")
        for nom, url, err in ko:
            print(f"  • {nom} : {url}")
            print(f"    → {err}")


# ── Commande : csv ────────────────────────────────────────────────────────────

def cmd_csv():
    import csv
    test_path = Path("corpus_bacot") / "rss_log.csv"
    print(f"\nTest écriture CSV → {test_path}")

    for i in range(3):
        try:
            existe = test_path.exists()
            with open(test_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["url","source","statut","nb_mots","score_pertinence","date"])
                if not existe:
                    writer.writeheader()
                writer.writerow({"url": f"test_{i}", "source": "debug", "statut": "test",
                                 "nb_mots": 0, "score_pertinence": 0, "date": ""})
            print(f"  [OK] écriture {i+1}/3")
        except PermissionError as e:
            print(f"  [KO] PermissionError : {e}")
            print("  → Le fichier est probablement ouvert dans Excel ou un autre programme.")
        except Exception as e:
            print(f"  [KO] {e}")


# ── Commande : timeout ────────────────────────────────────────────────────────

def cmd_timeout(url: str):
    try:
        import trafilatura
    except ImportError:
        print("ERREUR : trafilatura non installé")
        return

    print(f"\nTest timeout sur : {url[:80]}")
    t0 = time.time()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
        t_req = time.time() - t0
        print(f"Requête : {t_req:.1f}s — {len(resp.content)//1024} Ko")
        html = resp.text
    except Exception as e:
        print(f"Requête échouée : {e} ({time.time()-t0:.1f}s)")
        return

    print("trafilatura en cours (timeout 30s)…")
    t1 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(trafilatura.extract, html,
                           include_comments=False, output_format="json",
                           with_metadata=True, favor_precision=True)
        try:
            raw = future.result(timeout=30)
            t_traf = time.time() - t1
            nb_mots = len(json.loads(raw).get("text","").split()) if raw else 0
            print(f"trafilatura : {t_traf:.1f}s — {nb_mots} mots")
        except concurrent.futures.TimeoutError:
            print(f"trafilatura : TIMEOUT après 30s")

    print(f"Temps total : {time.time()-t0:.1f}s")


# ── Score de pertinence (réplique exacte du scraper) ─────────────────────────

TERMES_PERTINENCE = [
    "valérie bacot", "valerie bacot", "bacot", "polette",
    "clayette", "tout le monde savait",
]
SCORE_MIN = 3
MIN_MOTS  = 100


def _score_detail(texte: str) -> tuple[int, list[str]]:
    """Retourne (score, liste des signaux trouvés)."""
    t = texte.lower()
    score = 0
    signaux = []

    if "valérie bacot" in t or "valerie bacot" in t:
        score += 4
        signaux.append("+4 nom complet")
    elif "bacot" in t:
        score += 2
        signaux.append("+2 nom de famille")
    else:
        return 0, ["0 — 'bacot' absent du texte extrait"]

    if "daniel polette" in t or "polette" in t:
        score += 2
        signaux.append("+2 polette")
    if "tout le monde savait" in t:
        score += 2
        signaux.append("+2 tout le monde savait")
    if "clayette" in t:
        score += 2
        signaux.append("+2 clayette")
    if "tomasini" in t:
        score += 1
        signaux.append("+1 tomasini")
    if "saône-et-loire" in t or "saone-et-loire" in t:
        score += 1
        signaux.append("+1 saône-et-loire")
    for terme in ["proxénète", "proxenete", "emprise",
                  "légitime défense", "legitime defense",
                  "violences conjugales", "féminicide", "feminicide"]:
        if terme in t:
            score += 1
            signaux.append(f"+1 {terme}")
            break

    return score, signaux


def _decode_response(resp) -> str:
    """Décode la réponse en évitant le défaut ISO-8859-1 de requests."""
    if resp.encoding and resp.encoding.lower().replace("-", "") in ("iso88591", "latin1"):
        apparent = (resp.apparent_encoding or "").lower()
        if apparent.startswith("utf") or apparent.startswith("ascii"):
            resp.encoding = resp.apparent_encoding
    return resp.text


def _extraire_texte(url: str):
    """Télécharge et extrait via trafilatura. Retourne (texte, meta, erreur)."""
    import trafilatura

    try:
        resp = requests.get(url, headers=HEADERS, timeout=(10, 25))
        resp.raise_for_status()
        html = _decode_response(resp)
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        return None, {}, f"HTTP {code}"
    except Exception as e:
        return None, {}, str(e)

    import concurrent.futures
    for mode in [{"favor_precision": True}, {"favor_recall": True}]:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(trafilatura.extract, html,
                                   include_comments=False, include_tables=False,
                                   output_format="json", with_metadata=True,
                                   **mode)
                raw = future.result(timeout=30)
            if raw:
                data = json.loads(raw)
                if data.get("text"):
                    return data["text"].strip(), data, None
        except Exception:
            pass

    return None, {}, "trafilatura n'a rien extrait"


def cmd_score(url: str):
    print(f"\n{'─'*70}")
    print(f"URL : {url}")
    print(f"{'─'*70}")

    texte, meta, erreur = _extraire_texte(url)

    if erreur:
        print(f"[ECHEC] {erreur}")
        return

    nb_mots = len(texte.split())
    score, signaux = _score_detail(texte)

    print(f"Titre  : {meta.get('title','—')[:80]}")
    print(f"Date   : {meta.get('date','—')}   Site : {meta.get('sitename','—')}")
    print(f"Mots   : {nb_mots}  (seuil={MIN_MOTS})")
    print(f"Score  : {score}  (seuil={SCORE_MIN})")
    print(f"Signaux: {', '.join(signaux) if signaux else '—'}")

    verdict = "RETENU" if (nb_mots >= MIN_MOTS and score >= SCORE_MIN) else "REJETÉ"
    if nb_mots < MIN_MOTS:
        verdict += f" (trop court : {nb_mots} mots)"
    elif score < SCORE_MIN:
        verdict += f" (hors sujet : score={score})"
    print(f"→ {verdict}")

    print(f"\n--- Extrait (200 premiers mots) ---")
    print(" ".join(texte.split()[:200]))


# ── Analyse batch des URLs non-corpus ─────────────────────────────────────────

def cmd_analyse():
    corpus_dir = Path("corpus_bacot")
    urls_file  = corpus_dir / "rss_urls_collectees.json"

    if not urls_file.exists():
        print(f"Fichier introuvable : {urls_file}")
        print("Lancez d'abord scraper_rss_etendu_bacot.py pour générer rss_urls_collectees.json")
        return

    # Charger les URLs collectées
    with open(urls_file, encoding="utf-8") as f:
        collectees = json.load(f)
    print(f"\n{len(collectees)} URLs collectées dans {urls_file.name}")

    # Charger toutes les URLs du corpus existant
    urls_corpus: set[str] = set()
    for path in corpus_dir.glob("*.json"):
        if path.name in ("rss_checkpoint.json", "rss_urls_collectees.json",
                         "rss_echecs.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("url"):
                    urls_corpus.add(item["url"].strip())
        except Exception:
            pass
    print(f"{len(urls_corpus)} URLs déjà dans le corpus")

    # Dédupliquer + filtrer
    seen: set[str] = set()
    a_tester = []
    for m in collectees:
        u = m["url"].strip()
        if u not in seen:
            seen.add(u)
            if u not in urls_corpus:
                a_tester.append(m)

    print(f"{len(collectees) - len(seen)} doublons internes retirés")
    print(f"{len(a_tester)} URLs à tester (non encore dans le corpus)\n")

    if not a_tester:
        print("Rien à tester.")
        return

    stats = {"retenu": 0, "trop_court": 0, "hors_sujet": 0, "erreur": 0}

    for i, meta in enumerate(a_tester, 1):
        url = meta["url"].strip()
        label = meta.get("label", "")
        print(f"[{i:02d}/{len(a_tester):02d}] [{label}] {url[:80]}")

        texte, _, erreur = _extraire_texte(url)

        if erreur:
            print(f"         → ECHEC : {erreur}")
            stats["erreur"] += 1
            time.sleep(1)
            continue

        nb_mots = len(texte.split())
        score, signaux = _score_detail(texte)

        if nb_mots < MIN_MOTS:
            print(f"         → trop court : {nb_mots} mots")
            stats["trop_court"] += 1
        elif score < SCORE_MIN:
            print(f"         → hors sujet : score={score} ({', '.join(signaux)})")
            print(f"            extrait : {' '.join(texte.split()[:30])}…")
            stats["hors_sujet"] += 1
        else:
            print(f"         → RETENU score={score} ({', '.join(signaux)}) {nb_mots} mots")
            stats["retenu"] += 1

        time.sleep(1)

    print(f"\n{'─'*50}")
    print(f"Retenus    : {stats['retenu']}")
    print(f"Trop courts: {stats['trop_court']}")
    print(f"Hors sujet : {stats['hors_sujet']}")
    print(f"Erreurs    : {stats['erreur']}")


# ── Ajout direct d'une URL dans rss_articles.json ────────────────────────────

def cmd_add_url(url: str):
    articles_path = Path("corpus_bacot") / "rss_articles.json"

    # Vérifier si l'URL est déjà dans le fichier
    existants = json.loads(articles_path.read_text(encoding="utf-8")) if articles_path.exists() else []
    if any(a.get("url") == url for a in existants if isinstance(a, dict)):
        print(f"URL déjà présente dans {articles_path.name}")
        return

    print(f"\nExtraction de : {url[:80]}")
    texte, meta, erreur = _extraire_texte(url)

    if erreur:
        print(f"[ECHEC] {erreur}")
        return

    nb_mots = len(texte.split())
    score, signaux = _score_detail(texte)

    print(f"Titre  : {meta.get('title','—')[:80]}")
    print(f"Mots   : {nb_mots}   Score : {score} ({', '.join(signaux)})")

    if nb_mots < MIN_MOTS:
        print(f"⚠ Article trop court ({nb_mots} mots < {MIN_MOTS}). Ajout forcé quand même ? [o/N] ", end="")
        if input().strip().lower() != "o":
            return
    if score < SCORE_MIN:
        print(f"⚠ Score faible ({score} < {SCORE_MIN}). Ajout forcé quand même ? [o/N] ", end="")
        if input().strip().lower() != "o":
            return

    from datetime import datetime, timezone
    article = {
        "url":              url,
        "titre":            (meta.get("title") or "").strip(),
        "texte":            texte,
        "auteur":           (meta.get("author") or "").strip(),
        "date":             (meta.get("date") or "")[:10],
        "sitename":         (meta.get("sitename") or "").strip(),
        "description":      (meta.get("description") or "").strip(),
        "nb_mots":          nb_mots,
        "score_pertinence": score,
        "source_rss":       "debug_add_url",
        "type_doc":         "article",
        "scraped_at":       datetime.now(timezone.utc).isoformat(),
    }

    existants.append(article)
    articles_path.write_text(json.dumps(existants, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Article ajouté à {articles_path.name} ({len(existants)} articles au total)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "url" and len(sys.argv) >= 3:
        cmd_url(sys.argv[2])
    elif cmd == "score" and len(sys.argv) >= 3:
        cmd_score(sys.argv[2])
    elif cmd in ("add-url", "add_url") and len(sys.argv) >= 3:
        cmd_add_url(sys.argv[2])
    elif cmd == "analyse":
        cmd_analyse()
    elif cmd == "rss":
        cmd_rss()
    elif cmd == "csv":
        cmd_csv()
    elif cmd == "timeout" and len(sys.argv) >= 3:
        cmd_timeout(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
