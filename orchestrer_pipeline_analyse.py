"""
orchestrer_pipeline_analyse.py — Enchaîne tout le pipeline d'analyse sans intervention manuelle
=================================================================================================
Exécute dans l'ordre les étapes qui, jusqu'ici, étaient lancées à la main après chaque
session de classification LLM :

  1. Classifier_bacot.py            — classification lexicale + clustering (analyse_bacot/)
  2. fusionner_corpus_llm.py        — reconstruit data/corpus_llm.json (entrée du LLM)
  3. classifier_llm_corpus.py       — classification LLM via Groq, checkpointée/reprenable
  4. generer_graphiques.py          — data/graphiques.json
  5. generer_graphiques_tweets.py   — data/graphiques_tweets.json
  6. API_bacot/database.py          — reconstruit bacot.db à partir des fichiers ci-dessus

Chaque étape est indépendante en sortie (elle écrit ses propres fichiers) : si l'une
d'elles échoue, les suivantes tournent quand même avec les données disponibles les plus
récentes, et l'échec est journalisé. La reconstruction de la base (étape 6) est toujours
tentée en dernier, pour que l'API ne serve jamais un état plus obsolète que nécessaire.

Conçu pour être appelé par le Planificateur de tâches Windows via run_classification_llm.bat
(tâche "BacotClassificationLLM", toutes les 12h) — aucune étape ne nécessite d'interaction.

Usage :
    python orchestrer_pipeline_analyse.py
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).parent

# Force l'UTF-8 pour chaque étape lancée en sous-processus : garantit que les
# print() avec symboles Unicode (✓, ✗, ⚠…) ne font pas planter la chaîne quand
# la sortie est redirigée vers un fichier log (codepage cp1252 par défaut sur
# Windows), même si un script individuel oublie le reconfigure() de stdout.
ENV_ETAPES = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

ETAPES = [
    ("Classification lexicale + clustering", [sys.executable, "Classifier_bacot.py"], BASE),
    ("Fusion corpus pour classification LLM", [sys.executable, "fusionner_corpus_llm.py"], BASE),
    ("Classification LLM (Groq, checkpointée)", [sys.executable, "classifier_llm_corpus.py"], BASE),
    ("Génération graphiques (presse/commentaires)", [sys.executable, "generer_graphiques.py"], BASE),
    ("Génération graphiques (tweets)", [sys.executable, "generer_graphiques_tweets.py"], BASE),
    ("Reconstruction de la base SQLite", [sys.executable, "database.py"], BASE / "API_bacot"),
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log("=" * 70)
    log("DÉMARRAGE — Pipeline d'analyse complet (Bacot)")
    log("=" * 70)

    echecs = []

    for nom, commande, cwd in ETAPES:
        log(f"\n--- {nom} ---")
        debut = datetime.now()
        resultat = subprocess.run(commande, cwd=cwd, env=ENV_ETAPES)
        duree = (datetime.now() - debut).total_seconds()

        if resultat.returncode == 0:
            log(f"✓ {nom} — terminé en {duree:.0f}s")
        else:
            log(f"✗ {nom} — code retour {resultat.returncode} (après {duree:.0f}s)")
            echecs.append(nom)

    log("\n" + "=" * 70)
    if echecs:
        log(f"TERMINÉ AVEC {len(echecs)} ÉTAPE(S) EN ÉCHEC : {', '.join(echecs)}")
    else:
        log("TERMINÉ — toutes les étapes ont réussi.")
    log("=" * 70)

    sys.exit(1 if echecs else 0)


if __name__ == "__main__":
    main()
