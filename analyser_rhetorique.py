"""
analyser_rhetorique.py — Analyse rhétorique des documents primaires
====================================================================
Analyse les deux documents primaires du corpus :
  - Le live JSL (procès juin 2021)
  - Le compte rendu sénatorial (novembre 2021)

Extrait les unités argumentatives par locuteur et les classe
selon une typologie adaptée de la méthode Mazan.

Produit : data/rhetorique.json

Usage :
    python analyser_rhetorique.py
"""

import sys
import json
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Chemins ──────────────────────────────────────────────────────────────────

CORPUS_PATHS = [
    Path("corpus_bacot/corpus_final.json"),
    Path("corpus_bacot/corpus_bacot.json"),
]
TWEETS_PATH = Path("corpus_bacot/tweets_bacot.json")
OUTPUT = Path("data/rhetorique.json")

# ─── URLs des documents primaires ─────────────────────────────────────────────

DOCS_PRIMAIRES = [
    {
        "id":    "jsl_j1",
        "url":   "https://www.lejsl.com/faits-divers-justice/2021/06/21/suivez-le-proces-de-valerie-bacot",
        "titre": "Procès Valérie Bacot — Jour 1 (JSL live)",
        "date":  "2021-06-21",
        "desc":  "Ouverture du procès, premières audiences, présentation des faits.",
    },
    {
        "id":    "jsl_j2",
        "url":   "https://www.lejsl.com/faits-divers-justice/2021/06/22/proces-de-valerie-bacot-suivez-en-direct-la-deuxieme-journee-d-audience",
        "titre": "Procès Valérie Bacot — Jour 2 (JSL live)",
        "date":  "2021-06-22",
        "desc":  "Dépositions des témoins, questions de la cour.",
    },
    {
        "id":    "jsl_j3",
        "url":   "https://www.lejsl.com/faits-divers-justice/2021/06/23/suivez-le-proces-de-valerie-bacot",
        "titre": "Procès Valérie Bacot — Jour 3 (JSL live)",
        "date":  "2021-06-23",
        "desc":  "Retranscription quasi-directe des audiences par Le Journal de Saône-et-Loire. Document primaire exceptionnel.",
    },
    {
        "id":    "jsl_verdict",
        "url":   "https://www.lejsl.com/faits-divers-justice/2021/06/25/proces-de-valerie-bacot-l-heure-du-verdict",
        "titre": "Procès Valérie Bacot — Verdict (JSL live)",
        "date":  "2021-06-25",
        "desc":  "Plaidoiries finales, réquisitions, verdict : 4 ans dont 3 avec sursis.",
    },
    {
        "id":    "senat",
        "url":   "https://www.senat.fr/compte-rendu-commissions/20211101/ddf_bacot.html",
        "titre": "Déposition au Sénat — Délégation aux droits des femmes",
        "date":  "2021-11-04",
        "desc":  "Compte rendu officiel de la déposition de Valérie Bacot devant le Sénat, avec questions et réponses.",
    },
    {
        "id":    "tweets_presse",
        "url":   "",
        "titre": "Tweets journalistes — Procès live",
        "date":  "2021-06-21",
        "desc":  "Tweets live des journalistes présents en salle d'audience (procès J1–J3, verdict, retranscriptions). Document primaire collectif des 4 jours du procès.",
        "filtre": lambda doc: (
            doc.get("source") == "twitter_x" and
            doc.get("recherche") in [
                "procès_j1", "procès_j2", "procès_j3",
                "verdict", "audience_retranscription",
            ]
        ),
    },
]

# Compatibilité avec le reste du script
URL_JSL   = DOCS_PRIMAIRES[2]["url"]
URL_SENAT = DOCS_PRIMAIRES[4]["url"]

# ─── Locuteurs ────────────────────────────────────────────────────────────────

LOCUTEURS = {
    "valerie_bacot": {
        "label": "Valérie Bacot",
        "couleur": "bleu",
        "description": "Parole directe de Valérie Bacot — témoignage, déposition, réponses",
        "marqueurs": [
            "valérie bacot", "valérie :", "elle dit", "elle répond",
            "elle explique", "elle témoigne", "elle raconte", "elle confie",
            "valérie explique", "valérie dit", "valérie répond",
            "« je ", "« on ", "« il m", "« il nous", "« j'avais",
            "valérie bacot explique", "valérie bacot dit",
        ]
    },
    "defense": {
        "label": "Défense & avocats",
        "couleur": "vert",
        "description": "Arguments des avocats de la défense — Nathalie Tomasini et autres",
        "marqueurs": [
            "tomasini", "maître", "avocat", "la défense", "défenseur",
            "plaidoirie", "plaide", "défense argue", "l'avocat",
            "me tomasini", "nathalie tomasini",
        ]
    },
    "accusation": {
        "label": "Accusation & parquet",
        "couleur": "rouge",
        "description": "Parole du procureur, réquisitions, questions de la cour",
        "marqueurs": [
            "procureur", "parquet", "réquisition", "le président",
            "la présidente", "la cour", "magistrat", "question :",
            "le juge", "la juge", "interroge", "demande à valérie",
        ]
    },
    "expert": {
        "label": "Experts & témoins",
        "couleur": "orange",
        "description": "Psychiatres, psychologues, témoins cités à la barre",
        "marqueurs": [
            "expert", "psychiatre", "psychologue", "témoin",
            "docteur", "professeur", "expertise", "selon l'expert",
            "l'expert explique", "le témoin",
        ]
    },
    "senat": {
        "label": "Sénatrices & institutions",
        "couleur": "violet",
        "description": "Questions et interventions des sénatrices, associations",
        "marqueurs": [
            "billon", "annick billon", "sénatrice", "sénatrices",
            "la délégation", "présidente", "association",
            "nous toutes", "fédération",
        ]
    },
    "narrateur": {
        "label": "Narration journalistique",
        "couleur": "gris",
        "description": "Description factuelle du journaliste, contexte, ambiance",
        "marqueurs": [
            "l'audience", "la salle", "l'auditoire", "le tribunal",
            "les assises", "l'atmosphère", "chalon-sur-saône",
        ]
    },
}

# ─── Typologie argumentative ──────────────────────────────────────────────────

TYPOLOGIE = {
    "temoignage_survie": {
        "label": "Témoignage de survie",
        "description": "Valérie décrit les violences subies, l'emprise, l'absence d'alternative",
        "couleur": "#2c4a6e",
        "termes": [
            "peur", "peureux", "terreur", "terrifié", "violence", "violent",
            "frapper", "frappé", "battre", "battu", "viol", "violer",
            "prostituée", "prostitution", "proxénète", "proxénétisme",
            "survie", "survivre", "pas le choix", "aucun choix",
            "pas d'autre", "échappatoire", "emprise", "contrôle",
            "je ne pouvais pas", "impossible", "protéger", "enfants",
        ]
    },
    "legitimation_juridique": {
        "label": "Légitimation juridique",
        "description": "Arguments sur la légitime défense, le droit, la qualification des faits",
        "couleur": "#4a6741",
        "termes": [
            "légitime défense", "défense différée", "loi", "juridique",
            "droit", "code pénal", "qualification", "requalifier",
            "jacqueline sauvage", "réforme", "jurisprudence",
            "état de nécessité", "contrainte", "préméditation",
            "assassinat", "meurtre", "crime passionnel",
        ]
    },
    "emprise_expliquee": {
        "label": "Emprise expliquée",
        "description": "Mécanisme d'emprise décrit et expliqué — par experts, avocats ou Valérie",
        "couleur": "#8b3a2a",
        "termes": [
            "emprise", "emprise psychologique", "cycle de la violence",
            "syndrome", "traumatisme", "conditionnement", "manipulation",
            "isolation", "isolement", "dépendance", "soumission",
            "contrôle coercitif", "dominé", "dominée",
            "stockholm", "résignation", "intériorisation",
        ]
    },
    "silence_institutionnel": {
        "label": "Silence institutionnel",
        "description": "Ce que l'entourage, les institutions, la société n'ont pas fait",
        "couleur": "#5a4a3a",
        "termes": [
            "savait", "savaient", "tout le monde savait", "silence",
            "taire", "complice", "complicité", "entourage", "famille",
            "institution", "école", "médecin", "assistante sociale",
            "signalement", "protection", "n'a rien fait", "rien dit",
            "fermé les yeux", "ignoré", "toléré",
        ]
    },
    "renversement_victimaire": {
        "label": "Renversement victimaire",
        "description": "Moments où Valérie est questionnée comme suspecte ou responsable",
        "couleur": "#c0392b",
        "termes": [
            "pourquoi pas", "pourquoi ne pas", "partir", "quitter",
            "appeler", "police", "gendarmerie", "préméditation",
            "prémédité", "choix", "elle aurait pu", "elle pouvait",
            "responsabilité", "mais quand même", "n'empêche",
            "voulu", "décidé", "planifié",
        ]
    },
    "politisation": {
        "label": "Politisation & cadrage systémique",
        "description": "Féminisme, réformes, dimension politique et sociétale",
        "couleur": "#6c3483",
        "termes": [
            "féminicide", "féminisme", "féministe", "patriarcat",
            "violences faites aux femmes", "violences conjugales",
            "systémique", "structurel", "inégalité", "réforme",
            "loi", "changer", "société", "nous toutes",
            "continuum", "droits des femmes",
        ]
    },
    "dimension_emotionnelle": {
        "label": "Dimension émotionnelle",
        "description": "Registre émotionnel — larmes, honte, dignité, empathie",
        "couleur": "#1a6b8a",
        "termes": [
            "pleure", "larmes", "sanglots", "émotion", "émue",
            "bouleversé", "bouleversée", "honte", "humiliation",
            "dignité", "courage", "force", "fragilité",
            "silence", "voix brisée", "tête baissée",
            "salle en larmes", "applaudissement",
        ]
    },
}

# ─── Chargement corpus ────────────────────────────────────────────────────────

def charger_document(url: str, corpus_index: dict) -> str:
    doc = corpus_index.get(url, {})
    texte = doc.get('text', '').strip()
    if not texte:
        # Cherche par URL partielle
        for key, val in corpus_index.items():
            if url in key or key in url:
                texte = val.get('text', '').strip()
                if texte:
                    break
    return texte

def charger_tweets_primaires(filtre) -> str:
    """Charge et concatène les tweets correspondant au filtre en un texte analysable."""
    if not TWEETS_PATH.exists():
        print(f"  ⚠ {TWEETS_PATH} introuvable")
        return ""
    with open(TWEETS_PATH, encoding="utf-8") as f:
        tweets = json.load(f)
    matches = sorted(
        [t for t in tweets if filtre(t) and t.get("texte", "").strip()],
        key=lambda t: t.get("datetime", ""),
    )
    if not matches:
        print(f"  ⚠ Aucun tweet correspondant au filtre")
        return ""
    return "\n\n".join(
        f"[{t.get('handle', '')} · {t.get('date', '')}] {t.get('texte', '').strip()}"
        for t in matches
    )


def charger_corpus() -> dict:
    for path in CORPUS_PATHS:
        if path.exists():
            print(f"Corpus : {path}")
            with open(path, encoding='utf-8') as f:
                corpus = json.load(f)
            print(f"  → {len(corpus)} documents")
            return {doc.get('url', ''): doc for doc in corpus if doc.get('url')}
    print("⚠ Corpus introuvable")
    return {}

# ─── Segmentation en paragraphes ──────────────────────────────────────────────

def segmenter(texte: str, min_chars: int = 80) -> list[str]:
    """Découpe le texte en segments cohérents."""
    # Découpe sur les sauts de ligne doubles ou points de fin de phrase longs
    segments = re.split(r'\n{2,}', texte)
    result = []
    for seg in segments:
        seg = seg.strip()
        if len(seg) < min_chars:
            continue
        # Si le segment est très long, le découpe en phrases
        if len(seg) > 600:
            phrases = re.split(r'(?<=[.!?])\s+', seg)
            buffer = ""
            for phrase in phrases:
                buffer += " " + phrase
                if len(buffer) >= 200:
                    result.append(buffer.strip())
                    buffer = ""
            if buffer.strip():
                result.append(buffer.strip())
        else:
            result.append(seg)
    return result

# ─── Détection locuteur ───────────────────────────────────────────────────────

def detecter_locuteur(segment: str) -> str:
    seg_lower = segment.lower()
    scores = {}
    for loc_id, loc_data in LOCUTEURS.items():
        score = sum(1 for m in loc_data["marqueurs"] if m in seg_lower)
        if score > 0:
            scores[loc_id] = score
    if not scores:
        return "narrateur"
    return max(scores, key=scores.get)

# ─── Détection type argumentatif ──────────────────────────────────────────────

def detecter_type(segment: str) -> tuple[str, float]:
    seg_lower = segment.lower()
    scores = {}
    for typ_id, typ_data in TYPOLOGIE.items():
        score = sum(seg_lower.count(t) for t in typ_data["termes"])
        if score > 0:
            scores[typ_id] = score
    if not scores:
        return "dimension_emotionnelle", 0
    best = max(scores, key=scores.get)
    return best, scores[best]

# ─── Extraction des unités argumentatives ─────────────────────────────────────

def extraire_unites(texte: str, source: str) -> list[dict]:
    segments = segmenter(texte)
    unites = []

    for seg in segments:
        locuteur = detecter_locuteur(seg)
        type_arg, score = detecter_type(seg)

        # Ne garde que les segments avec au moins un signal
        if score == 0 and locuteur == "narrateur":
            continue

        # Nettoie le segment
        texte_propre = seg[:450].strip()
        if len(seg) > 450:
            texte_propre += " …"

        unites.append({
            "texte":    texte_propre,
            "locuteur": locuteur,
            "type":     type_arg,
            "score":    score,
            "source":   source,
            "longueur": len(seg),
        })

    return unites

# ─── Analyse statistique ──────────────────────────────────────────────────────

def analyser_patterns(unites: list[dict]) -> dict:
    """Calcule les statistiques de distribution."""
    stats = {
        "par_locuteur": {},
        "par_type":     {},
        "par_locuteur_et_type": {},
    }

    for u in unites:
        loc  = u["locuteur"]
        typ  = u["type"]

        stats["par_locuteur"][loc]  = stats["par_locuteur"].get(loc, 0) + 1
        stats["par_type"][typ]      = stats["par_type"].get(typ, 0) + 1

        key = f"{loc}_{typ}"
        stats["par_locuteur_et_type"][key] = stats["par_locuteur_et_type"].get(key, 0) + 1

    return stats

# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    from collections import defaultdict
    Path("data").mkdir(exist_ok=True)

    corpus_index = charger_corpus()
    if not corpus_index:
        return

    print("\nChargement des documents primaires...")
    docs_charges = {}
    for doc in DOCS_PRIMAIRES:
        if "filtre" in doc:
            texte = charger_tweets_primaires(doc["filtre"])
        else:
            texte = charger_document(doc["url"], corpus_index)
        docs_charges[doc["id"]] = texte
        mots = len(texte.split()) if texte else 0
        etat = f"{mots} mots" if texte else "⚠ non trouvé"
        print(f"  [{doc['id']:<14}] {etat} — {doc['titre'][:50]}")

    toutes_unites = []
    unites_par_source: dict[str, list] = {}
    for doc in DOCS_PRIMAIRES:
        texte = docs_charges[doc["id"]]
        unites = extraire_unites(texte, doc["id"]) if texte else []
        unites_par_source[doc["id"]] = unites
        toutes_unites.extend(unites)
        print(f"  [{doc['id']:<12}] {len(unites)} unités extraites")

    if not toutes_unites:
        print("⚠ Aucune unité argumentative extraite.")
        return

    # Sélectionne les meilleures unités par locuteur × type × source (top 3)
    groupes: dict = defaultdict(list)
    for u in toutes_unites:
        key = (u["locuteur"], u["type"], u["source"])
        groupes[key].append(u)

    unites_selectionnees = []
    for items in groupes.values():
        items.sort(key=lambda x: x["score"], reverse=True)
        unites_selectionnees.extend(items[:3])

    stats_total = analyser_patterns(toutes_unites)

    # Métadonnées des sources
    sources_meta = {}
    for doc in DOCS_PRIMAIRES:
        texte = docs_charges[doc["id"]]
        sources_meta[doc["id"]] = {
            "titre": doc["titre"],
            "url":   doc["url"],
            "date":  doc["date"],
            "mots":  len(texte.split()) if texte else 0,
            "desc":  doc["desc"],
            "n_unites": len(unites_par_source[doc["id"]]),
        }

    output = {
        "meta": {
            "sources":        sources_meta,
            "n_unites_total": len(toutes_unites),
            "n_unites_selec": len(unites_selectionnees),
        },
        "locuteurs":  LOCUTEURS,
        "typologie":  TYPOLOGIE,
        "stats": {
            "total": stats_total,
            "par_source": {
                doc["id"]: analyser_patterns(unites_par_source[doc["id"]])
                for doc in DOCS_PRIMAIRES
            },
        },
        "unites": unites_selectionnees,
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    n_src = sum(1 for t in docs_charges.values() if t)
    print(f"""
╔══════════════════════════════════════════════════╗
║      ANALYSE RHÉTORIQUE GÉNÉRÉE ✓                ║
╠══════════════════════════════════════════════════╣
║  Documents chargés  : {n_src:>5} / {len(DOCS_PRIMAIRES)}               ║
║  Unités extraites   : {len(toutes_unites):>5}                ║
║  Unités sélect.     : {len(unites_selectionnees):>5}                ║
╚══════════════════════════════════════════════════╝
→ data/rhetorique.json
    """)

    print("Distribution par type argumentatif :")
    for typ, n in sorted(stats_total["par_type"].items(), key=lambda x: -x[1]):
        print(f"  {TYPOLOGIE[typ]['label']:<35} : {n:>3} unités")

    print("\nDistribution par locuteur :")
    for loc, n in sorted(stats_total["par_locuteur"].items(), key=lambda x: -x[1]):
        print(f"  {LOCUTEURS[loc]['label']:<30} : {n:>3} unités")


if __name__ == "__main__":
    run()
