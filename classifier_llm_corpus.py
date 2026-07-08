"""
classifier_llm_corpus.py — Classification LLM du corpus complet (commentaires + tweets)
=========================================================================================
Envoie chaque document de data/corpus_llm.json à l'API Groq pour une classification
narrative indépendante (mêmes 8 catégories que la classification lexicale), avec
rotation automatique entre plusieurs clés API Groq et reprise sur interruption.

Conçu pour être relancé périodiquement (ex. toutes les 12h via le Planificateur de
tâches Windows) : chaque exécution reprend où la précédente s'est arrêtée et s'arrête
proprement (code retour 0) dès que toutes les clés API ont atteint leur quota du jour.

Prérequis :
    - data/corpus_llm.json (produit par fusionner_corpus_llm.py)
    - pip install groq python-dotenv
    - Un fichier .env à la racine du projet avec au moins GROQ_API_KEY_1
      (voir .env.example — GROQ_API_KEY_2, GROQ_API_KEY_3... pour la rotation)

Usage :
    python classifier_llm_corpus.py

Entrée  : data/corpus_llm.json
Sortie  : data/corpus_llm_classe.json (corpus complet + scores LLM, mis à jour en continu)
          data/checkpoint_llm.json (URLs déjà traitées + statistiques de la dernière session)
"""

import os
import sys
import json
import time
import re
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

try:
    from groq import (
        Groq, RateLimitError, AuthenticationError,
        APIConnectionError, APITimeoutError, InternalServerError,
        BadRequestError, UnprocessableEntityError,
    )
except ImportError:
    Groq = None

# Erreurs propres au document (le contenu pose problème) : on marque le
# document comme traité (résultat par défaut) et on passe au suivant.
ERREURS_PERMANENTES_DOC = (json.JSONDecodeError, BadRequestError, UnprocessableEntityError)

# Erreurs systémiques (réseau, panne API) : on arrête la session sans marquer
# le document courant comme traité, pour le retraiter au prochain lancement.
ERREURS_SESSION = (APIConnectionError, APITimeoutError, InternalServerError)

# Nombre d'erreurs systémiques consécutives tolérées avant d'arrêter la session
MAX_ERREURS_CONSECUTIVES = 3

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_LLM_JSON = Path("data/corpus_llm.json")
OUTPUT_CLASSE   = Path("data/corpus_llm_classe.json")
CHECKPOINT      = Path("data/checkpoint_llm.json")

MODELE = "llama-3.3-70b-versatile"

# Sauvegarde sur disque tous les N documents traités avec succès
SAUVEGARDE_TOUS_LES = 10

# Délai entre deux appels API (évite le rate limiting côté RPM)
DELAI_API = 1.3

# ─── Rotation des clés API Groq ───────────────────────────────────────────────
# Accepte GROQ_API_KEY_1, GROQ_API_KEY_2, ... et, à défaut, GROQ_API_KEY seule.

def charger_cles_api() -> list[str]:
    cles = []
    i = 1
    while True:
        cle = os.getenv(f"GROQ_API_KEY_{i}")
        if not cle:
            break
        cles.append(cle)
        i += 1
    if not cles:
        cle_unique = os.getenv("GROQ_API_KEY")
        if cle_unique:
            cles.append(cle_unique)
    return cles


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── Typologie (identique au lexique de Classifier_bacot.py) ─────────────────

CATEGORIES = [
    "soutien_victime", "remise_en_question", "legitime_defense",
    "discours_feministe", "emprise_psychologique", "silence_collectif",
    "sensationnalisme", "jugement_moral",
]

TYPOLOGIE_PROMPT = """
Tu analyses des commentaires YouTube et tweets postés au sujet de l'affaire
Valérie Bacot (elle a tué son mari après 25 ans de viols, violences et
proxénétisme ; procès en juin 2021, condamnée à 4 ans dont 3 avec sursis,
libérée le jour du verdict).

Note l'intensité (0 à 10) de chacun des 8 narratifs suivants dans le texte :

1. soutien_victime — soutien à Valérie, compréhension, admiration, "elle a bien fait"
2. remise_en_question — questionnement de ses choix, "elle aurait pu partir/appeler la police"
3. legitime_defense — arguments juridiques : légitime défense différée, Jacqueline Sauvage, réforme de la loi
4. discours_feministe — cadrage féministe : féminicide, patriarcat, violences systémiques, MeToo
5. emprise_psychologique — description du mécanisme d'emprise, manipulation, syndrome traumatique
6. silence_collectif — "tout le monde savait", complicité passive de l'entourage/institutions
7. sensationnalisme — registre choc/fait-divers, réaction émotive sans fond ("ouf", "incroyable")
8. jugement_moral — jugement de valeur sur culpabilité/innocence, mérite, pardon, sévérité du verdict

Réponds UNIQUEMENT en JSON strict, sans texte avant ni après :
{
  "categorie_dominante_llm": "NOM_CATEGORIE_LA_PLUS_FORTE_ou_non_classe",
  "score_soutien_victime_llm": 0,
  "score_remise_en_question_llm": 0,
  "score_legitime_defense_llm": 0,
  "score_discours_feministe_llm": 0,
  "score_emprise_psychologique_llm": 0,
  "score_silence_collectif_llm": 0,
  "score_sensationnalisme_llm": 0,
  "score_jugement_moral_llm": 0
}

Si aucun narratif n'est présent, mets tous les scores à 0 et
"categorie_dominante_llm": "non_classe".
"""


# ─── Appel API Groq avec rotation de clés ─────────────────────────────────────

class RotateurClesAPI:
    def __init__(self, cles: list[str]):
        self.cles = cles
        self.index = 0
        self.client = Groq(api_key=self.cles[0]) if self.cles else None

    def cle_courante_masquee(self) -> str:
        cle = self.cles[self.index]
        return f"...{cle[-4:]}" if len(cle) > 4 else "****"

    def cle_suivante(self) -> bool:
        """Passe à la clé suivante. Retourne False si toutes les clés sont épuisées."""
        if self.index + 1 >= len(self.cles):
            return False
        self.index += 1
        self.client = Groq(api_key=self.cles[self.index])
        log.warning(f"  → Rotation vers la clé API #{self.index + 1} ({self.cle_courante_masquee()})")
        return True


def classifier_document(rotateur: RotateurClesAPI, texte: str) -> dict | None:
    """
    Envoie un document au modèle courant. Retourne le JSON parsé, ou None si
    le document doit être ignoré (erreur non liée au quota), ou lève RateLimitError
    si la clé courante est épuisée (à charge de l'appelant de tourner la clé).
    """
    completion = rotateur.client.chat.completions.create(
        model=MODELE,
        max_tokens=250,
        temperature=0,
        messages=[
            {"role": "system", "content": TYPOLOGIE_PROMPT},
            {"role": "user", "content": f'Texte à analyser :\n"""{texte}"""'},
        ],
    )
    reponse = completion.choices[0].message.content.strip()
    reponse = re.sub(r"```json\s*|\s*```", "", reponse).strip()
    return json.loads(reponse)


class SessionATerminer(Exception):
    """Levée quand la session doit s'arrêter (quota épuisé, aucune clé valide)."""


def classifier_avec_rotation(rotateur: RotateurClesAPI, texte: str) -> dict | None:
    """
    Classifie un document en tournant automatiquement les clés API en cas de
    quota atteint ou de clé invalide.

    Retourne le JSON classifié, ou None si le document lui-même pose problème
    (réponse illisible, requête rejetée) — à ignorer définitivement.
    Lève SessionATerminer si la session doit s'arrêter (plus aucune clé
    disponible). Laisse remonter les erreurs systémiques (ERREURS_SESSION)
    à l'appelant, qui décide s'il faut arrêter la session — ces erreurs ne
    doivent PAS entraîner le marquage du document comme traité.
    """
    while True:
        try:
            return classifier_document(rotateur, texte)
        except RateLimitError:
            log.warning(f"  Quota atteint sur la clé #{rotateur.index + 1}")
            if not rotateur.cle_suivante():
                raise SessionATerminer("quota épuisé sur toutes les clés API")
        except AuthenticationError as e:
            log.error(f"  Clé API #{rotateur.index + 1} invalide : {e}")
            if not rotateur.cle_suivante():
                raise SessionATerminer("plus aucune clé API valide")
        except ERREURS_PERMANENTES_DOC as e:
            log.warning(f"  Document ignoré (erreur définitive) : {e}")
            return None


# ─── Chargement / sauvegarde ───────────────────────────────────────────────────

def charger_corpus_source() -> list[dict]:
    with open(CORPUS_LLM_JSON, encoding="utf-8") as f:
        return json.load(f)


def charger_corpus_classe(corpus_source: list[dict]) -> list[dict]:
    """Charge le corpus déjà classé s'il existe, sinon part du corpus source."""
    if OUTPUT_CLASSE.exists():
        with open(OUTPUT_CLASSE, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(corpus_source))  # copie profonde


def sauvegarder_corpus_classe(corpus: list[dict]):
    with open(OUTPUT_CLASSE, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)


def charger_checkpoint() -> dict:
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            return json.load(f)
    return {"traites": []}


def sauvegarder_checkpoint(checkpoint: dict):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    if Groq is None:
        log.error("Librairie groq non installée. Lance : pip install groq")
        return

    cles = charger_cles_api()
    if not cles:
        log.error("Aucune clé API Groq trouvée (GROQ_API_KEY_1, ... ou GROQ_API_KEY).")
        log.error("Configure ton fichier .env — voir .env.example")
        return

    log.info(f"{len(cles)} clé(s) API Groq disponible(s) pour cette session")

    if not CORPUS_LLM_JSON.exists():
        log.error(f"Fichier introuvable : {CORPUS_LLM_JSON}")
        log.error("Lance d'abord : python fusionner_corpus_llm.py")
        return

    corpus_source = charger_corpus_source()
    corpus_classe = charger_corpus_classe(corpus_source)
    index_par_url = {d["url"]: d for d in corpus_classe if d.get("url")}

    checkpoint = charger_checkpoint()
    traites = set(checkpoint.get("traites", []))

    a_traiter = [
        d for d in corpus_source
        if d.get("url") and d["url"] not in traites
        and index_par_url.get(d["url"], {}).get("categorie_dominante_llm") is None
    ]

    total = len(corpus_source)
    log.info(f"Corpus total       : {total:,} documents")
    log.info(f"Déjà classifiés    : {total - len(a_traiter):,}")
    log.info(f"Restants           : {len(a_traiter):,}")
    log.info("=" * 60)

    if not a_traiter:
        log.info("✓ Corpus entièrement classifié.")
        return

    rotateur = RotateurClesAPI(cles)
    n_succes = 0
    n_echecs = 0
    n_erreurs_consecutives = 0

    try:
        for i, doc in enumerate(a_traiter, 1):
            url   = doc["url"]
            texte = doc.get("texte", "")

            if not texte or not texte.strip():
                traites.add(url)
                continue

            try:
                classif = classifier_avec_rotation(rotateur, texte)
            except SessionATerminer as e:
                log.warning(f"Arrêt de la session : {e}")
                break
            except ERREURS_SESSION as e:
                n_erreurs_consecutives += 1
                log.warning(
                    f"  Erreur réseau/serveur ({n_erreurs_consecutives}/{MAX_ERREURS_CONSECUTIVES}), "
                    f"document non marqué (sera retraité) : {e}"
                )
                if n_erreurs_consecutives >= MAX_ERREURS_CONSECUTIVES:
                    log.error("Trop d'erreurs consécutives — arrêt de la session.")
                    break
                continue
            except Exception as e:
                log.warning(f"  Erreur inattendue, document ignoré : {e}")
                classif = None

            n_erreurs_consecutives = 0

            if classif is None:
                n_echecs += 1
                traites.add(url)
                continue

            entree = index_par_url.get(url)
            if entree is None:
                entree = dict(doc)
                corpus_classe.append(entree)
                index_par_url[url] = entree

            for cat in CATEGORIES:
                entree[f"score_{cat}_llm"] = classif.get(f"score_{cat}_llm", 0)
            entree["categorie_dominante_llm"] = classif.get("categorie_dominante_llm", "non_classe")
            entree["score_total_llm"] = sum(entree[f"score_{cat}_llm"] for cat in CATEGORIES)

            traites.add(url)
            n_succes += 1

            if n_succes % SAUVEGARDE_TOUS_LES == 0:
                sauvegarder_corpus_classe(corpus_classe)
                checkpoint["traites"] = sorted(traites)
                sauvegarder_checkpoint(checkpoint)
                log.info(f"  [{i}/{len(a_traiter)}] {n_succes} classifiés (clé #{rotateur.index + 1}) — checkpoint sauvé")

            time.sleep(DELAI_API)
    finally:
        sauvegarder_corpus_classe(corpus_classe)
        checkpoint["traites"] = sorted(traites)
        checkpoint["derniere_session"] = {
            "horodatage": datetime.now(timezone.utc).isoformat(),
            "succes": n_succes,
            "echecs": n_echecs,
            "cles_utilisees": rotateur.index + 1,
        }
        sauvegarder_checkpoint(checkpoint)

    restants = total - len(traites)
    log.info("=" * 60)
    log.info(f"""
╔═══════════════════════════════════════════════════════════════╗
║       CLASSIFICATION LLM — SESSION TERMINÉE                    ║
╠═══════════════════════════════════════════════════════════════╣
║  Classifiés cette session : {n_succes:>6,}                             ║
║  Échecs (ignorés)         : {n_echecs:>6,}                             ║
║  Clés API utilisées       : {rotateur.index + 1:>6,} / {len(cles)}                          ║
║  Total classifié          : {total - restants:>6,} / {total:<6,}                    ║
║  Restants                 : {restants:>6,}                             ║
╠═══════════════════════════════════════════════════════════════╣
║  Relance : python classifier_llm_corpus.py                     ║
╚═══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    run()
