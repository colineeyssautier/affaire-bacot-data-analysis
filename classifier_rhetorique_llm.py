"""
classifier_rhetorique_llm.py — Classification LLM des segments rhétoriques
===========================================================================
Envoie chaque unité argumentative extraite par analyser_rhetorique.py
à l'API Claude pour classification précise selon la typologie adaptée
de la méthode Mazan appliquée à l'affaire Bacot.

Prérequis :
    - data/rhetorique.json (produit par analyser_rhetorique.py)
    - pip install anthropic

Usage :
    python classifier_rhetorique_llm.py

Produit :
    data/rhetorique_classifiee.json
    data/kwic_mots_pivots.json
"""

import sys
import json
import time
import re
import logging
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from groq import Groq
    CLIENT = Groq()  # lit GROQ_API_KEY dans l'environnement
    log_client = True
except ImportError:
    CLIENT = None
    log_client = False

# ─── Configuration ────────────────────────────────────────────────────────────

RHETORIQUE_JSON = Path("data/rhetorique.json")
OUTPUT_CLASSIF  = Path("data/rhetorique_classifiee.json")
OUTPUT_KWIC     = Path("data/kwic_mots_pivots.json")
CHECKPOINT      = Path("data/rhetorique_checkpoint.json")

# Nombre max d'unités à classifier par session (0 = tout d'un coup)
MAX_PAR_SESSION = 0

CORPUS_PATHS = [
    Path("corpus_bacot/corpus_final.json"),
    Path("corpus_bacot/corpus_bacot.json"),
]

DOCS_PRIMAIRES = [
    {"id": "jsl_j1",     "url": "https://www.lejsl.com/faits-divers-justice/2021/06/21/suivez-le-proces-de-valerie-bacot"},
    {"id": "jsl_j2",     "url": "https://www.lejsl.com/faits-divers-justice/2021/06/22/proces-de-valerie-bacot-suivez-en-direct-la-deuxieme-journee-d-audience"},
    {"id": "jsl_j3",     "url": "https://www.lejsl.com/faits-divers-justice/2021/06/23/suivez-le-proces-de-valerie-bacot"},
    {"id": "jsl_verdict","url": "https://www.lejsl.com/faits-divers-justice/2021/06/25/proces-de-valerie-bacot-l-heure-du-verdict"},
    {"id": "senat",      "url": "https://www.senat.fr/compte-rendu-commissions/20211101/ddf_bacot.html"},
]

# Compatibilité avec le reste du script
URL_JSL   = DOCS_PRIMAIRES[2]["url"]
URL_SENAT = DOCS_PRIMAIRES[4]["url"]

# Délai entre appels API (évite le rate limiting)
DELAI_API = 1.5

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─── Typologie adaptée Bacot ──────────────────────────────────────────────────

TYPOLOGIE_PROMPT = """
Tu analyses des segments de texte issus de deux documents primaires
sur l'affaire Valérie Bacot (procès 2021, France) :
  - Le live du Journal de Saône-et-Loire (retranscription quasi-directe des audiences)
  - Le compte rendu de la déposition de Valérie Bacot au Sénat (novembre 2021)

Contexte : Valérie Bacot a tué son mari après 25 ans de viols, violences et
proxénétisme. Elle a été condamnée à 4 ans dont 3 avec sursis et libérée
le jour même du verdict.

Classe ce segment selon la TYPOLOGIE suivante (une seule catégorie) :

1. TEMOIGNAGE_SURVIE
   La parole décrit directement les violences subies, l'emprise, la peur,
   l'absence perçue d'alternative. Registre factuel ou émotionnel de la victime.

2. LEGITIMATION_JURIDIQUE
   Arguments sur le cadre légal : légitime défense différée, qualification
   des faits, précédent Jacqueline Sauvage, réforme législative nécessaire.

3. EMPRISE_EXPLIQUEE
   Description ou explication du mécanisme d'emprise psychologique,
   contrôle coercitif, conditionnement, syndrome traumatique.
   Peut venir d'un expert, d'un avocat, ou de Valérie elle-même.

4. SILENCE_INSTITUTIONNEL
   Ce que l'entourage, les institutions, la société n'ont pas fait.
   "Tout le monde savait". Complicité passive, inaction.

5. RENVERSEMENT_VICTIMAIRE
   Moment où Valérie est implicitement ou explicitement questionnée
   comme responsable ou suspecte. Remise en question de ses choix,
   évocation d'alternatives qu'elle aurait pu saisir.

6. POLITISATION
   Cadrage systémique : féminisme, féminicide, patriarcat, violences
   structurelles, réforme du droit, enjeux de société.

7. DIMENSION_EMOTIONNELLE
   Registre émotionnel pur : larmes, silence, honte, dignité, courage.
   Description de l'atmosphère, des gestes, du non-verbal.

8. NARRATION_FACTUELLE
   Description neutre des faits du procès ou de l'audience, sans
   dimension argumentative ou émotionnelle particulière.

Réponds UNIQUEMENT en JSON strict, sans texte avant ni après :
{
  "categorie": "NOM_CATEGORIE",
  "confiance": 0.0,
  "locuteur_probable": "valerie_bacot|defense|accusation|expert|senat|narrateur|indetermine",
  "registre": "factuel|emotionnel|juridique|politique|mixte",
  "justification": "Une phrase courte expliquant le classement.",
  "mots_cles_detectes": ["mot1", "mot2"]
}
"""


# ─── Appel API Claude ─────────────────────────────────────────────────────────

def classifier_segment(texte: str, source: str) -> dict:
    """
    Envoie un segment à l'API Claude pour classification rhétorique.
    Retourne le résultat JSON parsé.
    """
    if not CLIENT:
        log.error("Librairie groq non installée. Lance : pip install groq")
        return {}

    source_label = "live JSL (procès)" if source == "jsl" else "compte rendu sénatorial"

    prompt = f"""Source : {source_label}

Segment à classifier :
\"\"\"{texte}\"\"\"
"""

    try:
        completion = CLIENT.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=400,
            messages=[
                {"role": "system", "content": TYPOLOGIE_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        texte_reponse = completion.choices[0].message.content.strip()

        # Nettoie si entouré de ```json ... ```
        texte_reponse = re.sub(r"```json\s*|\s*```", "", texte_reponse).strip()

        return json.loads(texte_reponse)

    except json.JSONDecodeError as e:
        log.warning(f"JSON invalide : {e}")
        return {}
    except Exception as e:
        log.warning(f"Erreur API : {e}")
        return {}


# ─── Checkpoint ───────────────────────────────────────────────────────────────

def charger_checkpoint() -> list[dict]:
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            deja = json.load(f)
        log.info(f"Checkpoint : {len(deja)} unités déjà classifiées")
        return deja
    return []


def sauvegarder_checkpoint(resultats: list[dict]):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=2)


# ─── Classification des unités argumentatives ─────────────────────────────────

def classifier_toutes_unites(rhetorique: dict) -> tuple[list[dict], bool]:
    """
    Classifie les unités argumentatives via l'API Groq.
    Reprend depuis le checkpoint si une session précédente a été interrompue.
    Retourne (résultats_complets, tout_terminé).
    """
    toutes_unites = [
        u for u in rhetorique.get("unites", [])
        if u.get("texte") and len(u.get("texte", "")) >= 30
    ]

    deja_classifiees = charger_checkpoint()
    textes_connus = {u.get("texte", "") for u in deja_classifiees}

    a_traiter = [u for u in toutes_unites if u.get("texte", "") not in textes_connus]

    log.info(f"Total unités    : {len(toutes_unites)}")
    log.info(f"Déjà classifiées: {len(deja_classifiees)}")
    log.info(f"Restantes       : {len(a_traiter)}")

    if not a_traiter:
        log.info("✓ Toutes les unités ont déjà été classifiées.")
        return deja_classifiees, True

    if MAX_PAR_SESSION > 0:
        session = a_traiter[:MAX_PAR_SESSION]
        log.info(f"Cette session   : {len(session)} unités (MAX_PAR_SESSION={MAX_PAR_SESSION})")
    else:
        session = a_traiter
        log.info(f"Cette session   : {len(session)} unités (session complète)")

    log.info("=" * 60)

    for i, unite in enumerate(session, 1):
        texte  = unite.get("texte", "")
        source = unite.get("source", "")

        log.info(f"  [{len(deja_classifiees) + i}/{len(toutes_unites)}] {texte[:60]}...")

        classif = classifier_segment(texte, source)

        if classif:
            unite_enrichie = {**unite, "classification_llm": classif}
            log.info(
                f"    → {classif.get('categorie','?')} "
                f"(confiance: {classif.get('confiance',0):.1f}) "
                f"| {classif.get('justification','')[:60]}"
            )
        else:
            unite_enrichie = {**unite, "classification_llm": {
                "categorie": unite.get("type", "NARRATION_FACTUELLE"),
                "confiance": 0.5,
                "locuteur_probable": unite.get("locuteur", "indetermine"),
                "registre": "mixte",
                "justification": "Classification automatique par défaut (API indisponible)",
                "mots_cles_detectes": [],
            }}

        deja_classifiees.append(unite_enrichie)
        sauvegarder_checkpoint(deja_classifiees)
        time.sleep(DELAI_API)

    tout_fini = len(deja_classifiees) >= len(toutes_unites)
    return deja_classifiees, tout_fini


# ─── Analyse KWIC — mots pivots ───────────────────────────────────────────────

MOTS_PIVOTS = {
    "emprise": {
        "label": "Emprise",
        "description": "Comment le mécanisme d'emprise est nommé, expliqué ou contesté",
        "variantes": [
            "emprise", "sous emprise", "emprise psychologique", "emprise totale",
            "sous son emprise", "emprise de daniel",
        ],
        "contextes": {
            "legitimation": [
                "ne pouvait pas", "impossible", "conditionnée", "n'avait pas le choix",
                "piégée", "survie", "pas d'issue", "sans échappatoire", "était piégée",
                "ne pouvait fuir", "n'avait pas la force", "n'osait pas", "terreur",
                "paralysée", "résignée", "impuissante", "soumise", "dominée",
            ],
            "questionnement": [
                "pouvait partir", "aurait pu", "pourquoi pas", "choix", "décidé",
                "n'a pas quitté", "restée", "pourquoi rester", "elle pouvait",
                "elle aurait dû", "rien ne l'empêchait", "libre de", "aurait pu fuir",
                "n'a pas appelé", "n'a pas prévenu",
            ],
            "explication": [
                "mécanisme", "syndrome", "traumatisme", "psychologique", "contrôle",
                "cycle", "violence", "conditionnement", "manipulation", "dépendance",
                "isolation", "coercitif", "expert", "psychiatre", "psychologue",
                "stockholm", "intériorisé", "progressif", "s'installe", "progressivement",
            ],
        }
    },
    "savait": {
        "label": "Tout le monde savait",
        "description": "Le silence collectif et la complicité passive de l'entourage",
        "variantes": [
            "savait", "savaient", "tout le monde savait", "au courant", "informé",
            "était au courant", "n'ignorait pas", "certains savaient",
        ],
        "contextes": {
            "accusation": [
                "n'a rien fait", "silence", "complice", "fermé les yeux", "ignoré",
                "n'a pas agi", "n'a pas signalé", "n'a pas protégé", "laissé faire",
                "inaction", "complicité", "toléré", "banalisé", "refusé de voir",
                "nié", "rien dit", "detourné les yeux",
            ],
            "explication": [
                "peur", "honte", "tabou", "violence conjugale", "difficile",
                "culture du silence", "normalisation", "pas leur affaire",
                "vie privée", "s'en mêler", "osé", "craignaient", "intimidés",
                "dépendance", "solidarité de façade", "problème de famille",
            ],
            "institution": [
                "école", "médecin", "gendarmerie", "police", "assistante",
                "travailleur social", "juge", "parquet", "service social",
                "protection de l'enfance", "signalement", "plainte", "rapport",
                "administration", "mairie", "curé", "infirmière", "hospitalier",
            ],
        }
    },
    "victime": {
        "label": "Statut de victime",
        "description": "Comment le statut de victime de Valérie est affirmé, nuancé ou contesté",
        "variantes": [
            "victime", "victime de", "victime principale", "vraie victime",
            "première victime", "aussi une victime", "n'est pas une victime",
        ],
        "contextes": {
            "affirmation": [
                "innocente", "survie", "défendre", "protéger", "soutien",
                "a subi", "a vécu", "violences", "traumatisée", "brisée",
                "femme battue", "femme violée", "enfants", "pas le choix",
                "courage", "libérée", "justice rendue", "enfin reconnue",
            ],
            "contestation": [
                "coupable", "responsable", "choix", "meurtre", "préméditation",
                "n'est pas", "certes mais", "prétexte", "alibi", "manipulatrice",
                "calculatrice", "intérêt", "argent", "héritage", "profité",
                "n'avait qu'à", "mensonge", "version des faits",
            ],
            "ambivalence": [
                "aussi", "mais", "même si", "quand même", "pourtant",
                "certes", "néanmoins", "toutefois", "bien que", "malgré",
                "en même temps", "d'un côté", "de l'autre", "complexe",
                "nuancé", "difficile à dire", "pas si simple",
            ],
        }
    },
    "choix": {
        "label": "La question du choix",
        "description": "Si Valérie avait ou non une alternative à l'acte",
        "variantes": [
            "choix", "choisir", "décider", "alternative", "solution",
            "autre option", "autre issue", "autre voie", "autre moyen",
        ],
        "contextes": {
            "negation": [
                "pas le choix", "aucun choix", "aucune alternative", "impossible", "piégée",
                "n'avait pas", "sans issue", "acculée", "dos au mur", "pas d'autre",
                "dernier recours", "seule solution", "rien d'autre", "pas d'échappatoire",
                "toutes les portes fermées", "acte désespéré",
            ],
            "affirmation": [
                "pouvait", "aurait pu", "partir", "police", "appeler", "fuir",
                "quitter", "divorce", "séparation", "hébergement", "association",
                "refuge", "foyer", "plainte", "gendarmerie", "signalement",
                "famille", "voisins", "aide", "recours", "autre façon",
            ],
            "nuance": [
                "difficile", "peur", "emprise", "complexe", "comprendre",
                "théoriquement", "en pratique", "facile à dire", "pas si simple",
                "avec du recul", "aurait fallu", "pour quelqu'un sous",
                "victimes de violence", "souvent", "rarement", "statistiquement",
            ],
        }
    },
    "legitime_defense": {
        "label": "Légitime défense",
        "description": "Le cadre juridique et son absence dans le droit français",
        "variantes": [
            "légitime défense", "legitime defense", "défense différée",
            "jacqueline sauvage", "defense legitime", "legit defense",
        ],
        "contextes": {
            "soutien": [
                "réforme", "changer la loi", "droit", "reconnaître", "nécessaire",
                "devrait", "faudrait", "manque", "absence", "vide juridique",
                "adapter", "évoluer", "moderniser", "prendre en compte",
                "proposition de loi", "amendement", "débat parlementaire",
            ],
            "technique": [
                "juridique", "code pénal", "qualification", "jurisprudence",
                "article", "alinéa", "immédiateté", "proportionnalité",
                "critère", "condition", "exigence", "temporalité",
                "élément constitutif", "intention", "préméditation", "état de nécessité",
            ],
            "comparaison": [
                "angleterre", "canada", "étranger", "pays", "royaume-uni",
                "états-unis", "pays-bas", "belgique", "suisse", "australie",
                "ailleurs", "d'autres pays", "législation étrangère",
                "battered woman", "syndrome", "common law",
            ],
        }
    },
    "violence": {
        "label": "Les violences",
        "description": "Comment les violences subies sont nommées, quantifiées, qualifiées",
        "variantes": [
            "violence", "violences", "violent", "violente", "violents",
            "violences conjugales", "violences domestiques",
        ],
        "contextes": {
            "enumeration": [
                "coups", "gifles", "frappée", "battue", "blessée",
                "viol", "violée", "proxénète", "prostituée", "forcée",
                "depuis des années", "depuis l'enfance", "pendant des années",
                "depuis l'âge de", "toute sa vie", "quotidienne", "répétée",
            ],
            "minimisation": [
                "certes", "mais", "quand même", "malgré tout", "tout de même",
                "ça n'excuse pas", "ça ne justifie pas", "on comprend mais",
                "certes mais", "même si", "n'empêche", "reste que",
            ],
            "gravite": [
                "grave", "graves", "extrême", "insupportable", "inhumain",
                "enfer", "calvaire", "cauchemar", "subi", "vécu", "enduré",
                "25 ans", "toute une vie", "enfants", "devant les enfants",
                "traumatisée", "traumatisme", "séquelles",
            ],
        }
    },
    "verdict": {
        "label": "Le verdict",
        "description": "Comment la condamnation est perçue — juste, clément, sévère",
        "variantes": [
            "verdict", "condamnée", "condamnation", "peine", "sentence",
            "4 ans", "quatre ans", "sursis", "libérée",
        ],
        "contextes": {
            "clemence": [
                "clément", "clémente", "juste", "humain", "compréhensif",
                "bien", "raisonnable", "proportionné", "sage", "correct",
                "soulagement", "libération", "enfin", "reconnu", "acquitté",
            ],
            "severite": [
                "trop sévère", "sévère", "injuste", "trop lourd", "incompréhensible",
                "honte", "scandale", "pas normal", "devrait être acquittée",
                "devrait pas aller en prison", "prison ferme", "inacceptable",
            ],
            "indulgence": [
                "trop doux", "trop léger", "impunité", "n'a pas payé",
                "3 ans avec sursis", "sursis", "rentrée chez elle", "libre",
                "pas assez", "meurtre", "a tué", "prémédité",
            ],
        }
    },
}

def extraire_kwic(texte: str, mot_pivot: str, variantes: list[str],
                  window: int = 80) -> list[dict]:
    """
    Extrait toutes les occurrences d'un mot pivot avec contexte gauche/droite.
    """
    occurrences = []
    texte_lower = texte.lower()

    for variante in variantes:
        start = 0
        while True:
            idx = texte_lower.find(variante, start)
            if idx == -1:
                break

            # Contexte
            debut_ctx = max(0, idx - window)
            fin_ctx   = min(len(texte), idx + len(variante) + window)

            contexte_gauche = texte[debut_ctx:idx].strip()
            terme_trouve    = texte[idx:idx + len(variante)]
            contexte_droite = texte[idx + len(variante):fin_ctx].strip()

            occurrences.append({
                "variante":         variante,
                "contexte_gauche":  contexte_gauche[-60:] if len(contexte_gauche) > 60 else contexte_gauche,
                "terme":            terme_trouve,
                "contexte_droite":  contexte_droite[:60] if len(contexte_droite) > 60 else contexte_droite,
                "position":         idx,
                "contexte_complet": texte[debut_ctx:fin_ctx].strip(),
            })

            start = idx + 1

    return occurrences


def classifier_contexte_kwic(occurrence: dict, contextes_def: dict) -> str:
    """
    Classifie une occurrence KWIC selon les patterns de contexte définis.
    Retourne la catégorie de contexte ou 'neutre'.
    """
    texte_ctx = (
        occurrence["contexte_gauche"] + " " + occurrence["contexte_droite"]
    ).lower()

    scores = {}
    for cat, termes in contextes_def.items():
        score = sum(1 for t in termes if t in texte_ctx)
        if score > 0:
            scores[cat] = score

    if not scores:
        return "neutre"
    return max(scores, key=scores.get)


def _chercher_texte(doc_id: str, url: str, corpus_index: dict) -> str:
    """Cherche le texte d'un document par URL exacte puis partielle."""
    texte = corpus_index.get(url, {}).get("text", "")
    if texte:
        return texte
    # Fallback : recherche par fragment d'URL
    fragment = url.split("/")[-1][:20]
    for key, doc in corpus_index.items():
        if fragment and fragment in key:
            texte = doc.get("text", "")
            if texte:
                return texte
    return ""


def analyser_kwic(corpus_index: dict) -> dict:
    """
    Analyse KWIC sur tous les documents primaires.
    """
    # Charge les textes
    textes: dict[str, str] = {}
    for doc in DOCS_PRIMAIRES:
        t = _chercher_texte(doc["id"], doc["url"], corpus_index)
        textes[doc["id"]] = t
        mots = len(t.split()) if t else 0
        log.info(f"  [{doc['id']:<12}] {mots} mots" if t else f"  [{doc['id']:<12}] ⚠ non trouvé")

    resultats = {}

    for mot_id, config in MOTS_PIVOTS.items():
        log.info(f"KWIC : '{config['label']}'")

        toutes: list[dict] = []
        par_source: dict[str, int] = {}

        for doc in DOCS_PRIMAIRES:
            occs = extraire_kwic(textes[doc["id"]], mot_id, config["variantes"])
            for occ in occs:
                occ["source"] = doc["id"]
                occ["contexte_classe"] = classifier_contexte_kwic(occ, config["contextes"])
            toutes.extend(occs)
            par_source[doc["id"]] = len(occs)

        # Comptages par classe de contexte
        comptages: dict[str, int] = {}
        for cat in config["contextes"]:
            comptages[cat] = sum(1 for o in toutes if o["contexte_classe"] == cat)
        comptages["neutre"] = sum(1 for o in toutes if o["contexte_classe"] == "neutre")

        total = len(toutes)
        pourcentages = {
            k: round(v / total * 100, 1) if total > 0 else 0
            for k, v in comptages.items()
        }

        log.info(f"  → {total} occurrences : {comptages}")

        resultats[mot_id] = {
            "label":        config["label"],
            "description":  config["description"],
            "total":        total,
            "par_source":   par_source,
            "comptages":    comptages,
            "pourcentages": pourcentages,
            "occurrences":  toutes,
        }

    return resultats


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    Path("data").mkdir(exist_ok=True)

    if not CLIENT:
        log.error("Librairie groq non installée.")
        log.error("Lance : pip install groq")
        log.error("Puis configure ta clé : $env:GROQ_API_KEY='ta-clé'")
        return

    log.info("Client Groq initialisé ✓")

    # ── Charge la rhétorique existante ──
    if not RHETORIQUE_JSON.exists():
        log.error(f"Fichier introuvable : {RHETORIQUE_JSON}")
        log.error("Lance d'abord : python analyser_rhetorique.py")
        return

    with open(RHETORIQUE_JSON, encoding="utf-8") as f:
        rhetorique = json.load(f)

    n_total = len([u for u in rhetorique.get("unites", []) if u.get("texte")])
    log.info(f"Rhétorique chargée : {n_total} unités à classifier")

    # ── Charge le corpus pour le KWIC ──
    corpus_index = {}
    for path in CORPUS_PATHS:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                corpus = json.load(f)
            corpus_index = {doc.get("url", ""): doc for doc in corpus}
            log.info(f"Corpus chargé : {len(corpus_index)} documents")
            break

    # ── Étape 1 : Classification LLM (avec checkpoint) ──
    log.info("=" * 60)
    log.info("ÉTAPE 1 — Classification LLM des segments")
    log.info("=" * 60)

    unites_classifiees, tout_fini = classifier_toutes_unites(rhetorique)

    # Statistiques de classification
    cats_count: dict[str, int] = {}
    for u in unites_classifiees:
        cat = u.get("classification_llm", {}).get("categorie", "INCONNU")
        cats_count[cat] = cats_count.get(cat, 0) + 1

    log.info("\nDistribution des catégories LLM (session courante) :")
    for cat, n in sorted(cats_count.items(), key=lambda x: -x[1]):
        log.info(f"  {cat:<35} : {n:>3}")

    restantes = n_total - len(unites_classifiees)

    if not tout_fini:
        # Session partielle — sauvegarde intermédiaire mais pas le fichier final
        log.info("=" * 60)
        log.info(f"SESSION PARTIELLE : {len(unites_classifiees)}/{n_total} classifiées")
        log.info(f"Restantes         : {restantes} — relance python classifier_rhetorique_llm.py")
        log.info(f"Checkpoint sauvé  : {CHECKPOINT}")
        log.info("=" * 60)
        return

    # ── Tout est classifié → sauvegarde finale + KWIC ──
    output_classif = {
        **rhetorique,
        "unites": unites_classifiees,
        "stats_llm": {
            "total_classifie": len(unites_classifiees),
            "distribution": cats_count,
        }
    }

    with open(OUTPUT_CLASSIF, "w", encoding="utf-8") as f:
        json.dump(output_classif, f, ensure_ascii=False, indent=2)

    log.info(f"✓ {OUTPUT_CLASSIF}")

    # Supprime le checkpoint devenu inutile
    if CHECKPOINT.exists():
        CHECKPOINT.unlink()
        log.info(f"Checkpoint supprimé : {CHECKPOINT}")

    # ── Étape 2 : Analyse KWIC ──
    log.info("=" * 60)
    log.info("ÉTAPE 2 — Analyse KWIC des mots pivots")
    log.info("=" * 60)

    if corpus_index:
        kwic = analyser_kwic(corpus_index)

        with open(OUTPUT_KWIC, "w", encoding="utf-8") as f:
            json.dump(kwic, f, ensure_ascii=False, indent=2)

        log.info(f"✓ {OUTPUT_KWIC}")

        log.info("\nRésumé KWIC :")
        for mot_id, data in kwic.items():
            log.info(f"  '{data['label']}' : {data['total']} occurrences")
            for cat, pct in data["pourcentages"].items():
                if pct > 0:
                    log.info(f"    {cat:<20} : {pct:.1f}%")
    else:
        log.warning("Corpus non trouvé — KWIC ignoré")

    log.info(f"""
╔══════════════════════════════════════════════════╗
║     ANALYSE RHÉTORIQUE LLM TERMINÉE ✓           ║
╠══════════════════════════════════════════════════╣
║  Segments classifiés : {len(unites_classifiees):>5} / {n_total:<5}           ║
║  Mots pivots KWIC    : {len(MOTS_PIVOTS):>5}                     ║
╚══════════════════════════════════════════════════╝
→ data/rhetorique_classifiee.json
→ data/kwic_mots_pivots.json
    """)


if __name__ == "__main__":
    run()
