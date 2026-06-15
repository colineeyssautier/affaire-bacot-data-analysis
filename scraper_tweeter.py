"""
scraper_twitter_bacot.py — Scraper tweets procès Bacot via Playwright
=====================================================================
Scrape les tweets de la recherche X sur le procès Bacot (juin 2021)
en réutilisant ta session Chrome existante (déjà connectée).

Installation :
    pip install playwright
    playwright install chromium

Usage :
    python scraper_twitter_bacot.py

Produit :
    corpus_bacot/tweets_bacot.json
    corpus_bacot/tweets_bacot.csv
"""

import json
import time
import re
import sys
import csv
import logging
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("Playwright non installé. Lance : pip install playwright && playwright install chromium")
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────────────────────

# URLs de recherche — on scrape les 4 jours du procès + réactions post-verdict
RECHERCHES = [
    {
        "label": "procès_j1",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-21%20until%3A2021-06-22&src=typed_query&f=top",
        "description": "Jour 1 du procès (21 juin 2021)",
    },
    {
        "label": "procès_j2",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-22%20until%3A2021-06-23&src=typed_query&f=top",
        "description": "Jour 2 du procès (22 juin 2021)",
    },
    {
        "label": "procès_j3",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-23%20until%3A2021-06-24&src=typed_query&f=top",
        "description": "Jour 3 du procès (23 juin 2021)",
    },
    {
        "label": "verdict",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-25%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Verdict (25 juin 2021)",
    },
    {
        "label": "audience_retranscription",
        "url": "https://x.com/search?q=Bacot%20audience%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=top",
        "description": "Retranscriptions directes audiences",
    },
]

OUTPUT_DIR    = Path("corpus_bacot")
OUTPUT_JSON   = OUTPUT_DIR / "tweets_bacot.json"
OUTPUT_CSV    = OUTPUT_DIR / "tweets_bacot.csv"

MAX_SCROLLS   = 100     # scrolls max par recherche
SCROLL_PAUSE  = 3.0    # secondes entre chaque scroll
MIN_CHARS     = 30     # longueur minimale d'un tweet à garder

# ─── Requêtes de recherche ────────────────────────────────────────────────────

RECHERCHES = [

    # ══════════════════════════════════════════════════════════════════════
    # 1. PROCÈS — semaine du procès (déjà scrapé mais onglet "latest" aussi)
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "proces_j1_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-21%20until%3A2021-06-22&src=typed_query&f=latest",
        "description": "Jour 1 procès — onglet Récents (21 juin 2021)",
    },
    {
        "label": "proces_j2_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-22%20until%3A2021-06-23&src=typed_query&f=latest",
        "description": "Jour 2 procès — onglet Récents (22 juin 2021)",
    },
    {
        "label": "proces_j3_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-23%20until%3A2021-06-24&src=typed_query&f=latest",
        "description": "Jour 3 procès — onglet Récents (23 juin 2021)",
    },
    {
        "label": "verdict_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-25%20until%3A2021-06-26&src=typed_query&f=latest",
        "description": "Verdict — onglet Récents (25 juin 2021)",
    },
    {
        "label": "valerie_bacot_proces",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2021-06-21%20until%3A2021-06-26&src=typed_query&f=latest",
        "description": "\"Valérie Bacot\" (nom complet) — semaine du procès",
    },
    {
        "label": "daniel_polette_proces",
        "url": "https://x.com/search?q=%22Daniel%20Polette%22%20since%3A2021-06-21%20until%3A2021-06-30&src=typed_query&f=latest",
        "description": "Daniel Polette — pendant et après le procès",
    },
    {
        "label": "tomasini_bacot_proces",
        "url": "https://x.com/search?q=Tomasini%20Bacot%20since%3A2021-06-21%20until%3A2021-06-30&src=typed_query&f=latest",
        "description": "Maître Tomasini (avocate) + Bacot — procès",
    },
    {
        "label": "acquittement_relaxe_bacot",
        "url": "https://x.com/search?q=Bacot%20(acquittement%20OR%20relaxe%20OR%20acquitt%C3%A9e)%20since%3A2021-06-21%20until%3A2021-07-31&src=typed_query&f=latest",
        "description": "Bacot + acquittement/relaxe",
    },
    {
        "label": "sursis_condamnation_bacot",
        "url": "https://x.com/search?q=Bacot%20(sursis%20OR%20condamn%C3%A9e%20OR%20peine)%20since%3A2021-06-25%20until%3A2021-07-15&src=typed_query&f=latest",
        "description": "Bacot + sursis/condamnation/peine",
    },
    {
        "label": "chalon_assises_bacot",
        "url": "https://x.com/search?q=(Chalon%20OR%20%22Sa%C3%B4ne-et-Loire%22)%20Bacot%20since%3A2021-06-21%20until%3A2021-06-30&src=typed_query&f=latest",
        "description": "Chalon-sur-Saône / Saône-et-Loire + Bacot",
    },
    {
        "label": "proxenetisme_inceste_bacot",
        "url": "https://x.com/search?q=Bacot%20(prox%C3%A9n%C3%A9tisme%20OR%20proxen%C3%A9tisme%20OR%20inceste%20OR%20viol)%20since%3A2021-06-01%20until%3A2021-07-31&src=typed_query&f=latest",
        "description": "Bacot + proxénétisme / inceste / viol",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 2. POST-VERDICT IMMÉDIAT — juillet 2021
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_juillet2021_top",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-07-01%20until%3A2021-07-31&src=typed_query&f=top",
        "description": "Bacot — juillet 2021 (Top)",
    },
    {
        "label": "bacot_juillet2021_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-07-01%20until%3A2021-07-31&src=typed_query&f=latest",
        "description": "Bacot — juillet 2021 (Récents)",
    },
    {
        "label": "valerie_bacot_juillet2021",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2021-07-01%20until%3A2021-07-31&src=typed_query&f=latest",
        "description": "\"Valérie Bacot\" — juillet 2021",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 3. LIVRE "TOUT LE MONDE SAVAIT" — sept-nov 2021
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "livre_sortie_sept2021",
        "url": "https://x.com/search?q=%22tout%20le%20monde%20savait%22%20since%3A2021-09-01%20until%3A2021-09-30&src=typed_query&f=latest",
        "description": "\"Tout le monde savait\" — sortie sept 2021",
    },
    {
        "label": "livre_bacot_top",
        "url": "https://x.com/search?q=Bacot%20livre%20since%3A2021-09-01%20until%3A2021-12-31&src=typed_query&f=top",
        "description": "Bacot + livre — second semestre 2021",
    },
    {
        "label": "livre_bacot_latest",
        "url": "https://x.com/search?q=Bacot%20livre%20since%3A2021-09-01%20until%3A2021-12-31&src=typed_query&f=latest",
        "description": "Bacot + livre — second semestre 2021 (Récents)",
    },
    {
        "label": "tout_le_monde_savait_2021",
        "url": "https://x.com/search?q=%22tout%20le%20monde%20savait%22%20Bacot%20since%3A2021-01-01%20until%3A2021-12-31&src=typed_query&f=latest",
        "description": "\"Tout le monde savait\" + Bacot — 2021 complet",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 4. SÉNAT — novembre 2021
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "senat_bacot_top",
        "url": "https://x.com/search?q=Bacot%20s%C3%A9nat%20since%3A2021-10-01%20until%3A2021-12-31&src=typed_query&f=top",
        "description": "Bacot + Sénat — automne 2021 (Top)",
    },
    {
        "label": "senat_bacot_latest",
        "url": "https://x.com/search?q=Bacot%20s%C3%A9nat%20since%3A2021-10-01%20until%3A2021-12-31&src=typed_query&f=latest",
        "description": "Bacot + Sénat — automne 2021 (Récents)",
    },
    {
        "label": "senat_violences_conjugales_2021",
        "url": "https://x.com/search?q=Bacot%20(s%C3%A9nat%20OR%20parlement%20OR%20assembl%C3%A9e)%20since%3A2021-01-01%20until%3A2022-01-01&src=typed_query&f=latest",
        "description": "Bacot + institutions parlementaires 2021",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 5. FIN 2021 — thèmes transversaux
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_aout2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-08-01%20until%3A2021-09-01&src=typed_query&f=latest",
        "description": "Bacot — août 2021",
    },
    {
        "label": "bacot_oct2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-10-01%20until%3A2021-11-01&src=typed_query&f=latest",
        "description": "Bacot — octobre 2021",
    },
    {
        "label": "bacot_nov2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-11-01%20until%3A2021-12-01&src=typed_query&f=latest",
        "description": "Bacot — novembre 2021",
    },
    {
        "label": "bacot_dec2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-12-01%20until%3A2022-01-01&src=typed_query&f=latest",
        "description": "Bacot — décembre 2021",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 6. ANNÉE 2022 — mois par mois
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_jan2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-01-01%20until%3A2022-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2022",
    },
    {
        "label": "bacot_fev2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-02-01%20until%3A2022-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2022",
    },
    {
        "label": "bacot_mars2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-03-01%20until%3A2022-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2022",
    },
    {
        "label": "bacot_avr2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-04-01%20until%3A2022-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2022",
    },
    {
        "label": "bacot_mai2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-05-01%20until%3A2022-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2022",
    },
    {
        "label": "bacot_anniversaire_verdict_2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-06-01%20until%3A2022-07-01&src=typed_query&f=latest",
        "description": "Bacot — juin 2022 (1er anniversaire du verdict)",
    },
    {
        "label": "bacot_juil2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-07-01%20until%3A2022-08-01&src=typed_query&f=latest",
        "description": "Bacot — juillet 2022",
    },
    {
        "label": "bacot_aout2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-08-01%20until%3A2022-09-01&src=typed_query&f=latest",
        "description": "Bacot — août 2022",
    },
    {
        "label": "bacot_sept2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-09-01%20until%3A2022-10-01&src=typed_query&f=latest",
        "description": "Bacot — septembre 2022",
    },
    {
        "label": "bacot_oct2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-10-01%20until%3A2022-11-01&src=typed_query&f=latest",
        "description": "Bacot — octobre 2022",
    },
    {
        "label": "bacot_nov2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-11-01%20until%3A2022-12-01&src=typed_query&f=latest",
        "description": "Bacot — novembre 2022",
    },
    {
        "label": "bacot_dec2022",
        "url": "https://x.com/search?q=Bacot%20since%3A2022-12-01%20until%3A2023-01-01&src=typed_query&f=latest",
        "description": "Bacot — décembre 2022",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 7. ANNÉE 2023 — mois par mois
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_jan2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-01-01%20until%3A2023-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2023",
    },
    {
        "label": "bacot_fev2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-02-01%20until%3A2023-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2023",
    },
    {
        "label": "bacot_mars2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-03-01%20until%3A2023-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2023",
    },
    {
        "label": "bacot_avr2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-04-01%20until%3A2023-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2023",
    },
    {
        "label": "bacot_mai2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-05-01%20until%3A2023-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2023",
    },
    {
        "label": "bacot_anniversaire_verdict_2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-06-01%20until%3A2023-07-01&src=typed_query&f=latest",
        "description": "Bacot — juin 2023 (2e anniversaire du verdict)",
    },
    {
        "label": "bacot_juil2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-07-01%20until%3A2023-08-01&src=typed_query&f=latest",
        "description": "Bacot — juillet 2023",
    },
    {
        "label": "bacot_aout2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-08-01%20until%3A2023-09-01&src=typed_query&f=latest",
        "description": "Bacot — août 2023",
    },
    {
        "label": "bacot_sept2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-09-01%20until%3A2023-10-01&src=typed_query&f=latest",
        "description": "Bacot — septembre 2023",
    },
    {
        "label": "bacot_oct2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-10-01%20until%3A2023-11-01&src=typed_query&f=latest",
        "description": "Bacot — octobre 2023",
    },
    {
        "label": "bacot_nov2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-11-01%20until%3A2023-12-01&src=typed_query&f=latest",
        "description": "Bacot — novembre 2023",
    },
    {
        "label": "bacot_dec2023",
        "url": "https://x.com/search?q=Bacot%20since%3A2023-12-01%20until%3A2024-01-01&src=typed_query&f=latest",
        "description": "Bacot — décembre 2023",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 8. ANNÉE 2024 — mois par mois
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_jan2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-01-01%20until%3A2024-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2024",
    },
    {
        "label": "bacot_fev2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-02-01%20until%3A2024-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2024",
    },
    {
        "label": "bacot_mars2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-03-01%20until%3A2024-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2024",
    },
    {
        "label": "bacot_avr2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-04-01%20until%3A2024-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2024",
    },
    {
        "label": "bacot_mai2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-05-01%20until%3A2024-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2024",
    },
    {
        "label": "bacot_anniversaire_verdict_2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-06-01%20until%3A2024-07-01&src=typed_query&f=latest",
        "description": "Bacot — juin 2024 (3e anniversaire du verdict)",
    },
    {
        "label": "bacot_juil2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-07-01%20until%3A2024-08-01&src=typed_query&f=latest",
        "description": "Bacot — juillet 2024",
    },
    {
        "label": "bacot_aout2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-08-01%20until%3A2024-09-01&src=typed_query&f=latest",
        "description": "Bacot — août 2024",
    },
    {
        "label": "bacot_sept2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-09-01%20until%3A2024-10-01&src=typed_query&f=latest",
        "description": "Bacot — septembre 2024",
    },
    {
        "label": "bacot_oct2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-10-01%20until%3A2024-11-01&src=typed_query&f=latest",
        "description": "Bacot — octobre 2024",
    },
    {
        "label": "bacot_nov2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-11-01%20until%3A2024-12-01&src=typed_query&f=latest",
        "description": "Bacot — novembre 2024",
    },
    {
        "label": "bacot_dec2024",
        "url": "https://x.com/search?q=Bacot%20since%3A2024-12-01%20until%3A2025-01-01&src=typed_query&f=latest",
        "description": "Bacot — décembre 2024",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 9. ANNÉE 2025 — mois par mois
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_jan2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-01-01%20until%3A2025-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2025",
    },
    {
        "label": "bacot_fev2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-02-01%20until%3A2025-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2025",
    },
    {
        "label": "bacot_mars2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-03-01%20until%3A2025-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2025",
    },
    {
        "label": "bacot_avr2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-04-01%20until%3A2025-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2025",
    },
    {
        "label": "bacot_mai2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-05-01%20until%3A2025-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2025",
    },
    {
        "label": "bacot_anniversaire_verdict_2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-06-01%20until%3A2025-07-01&src=typed_query&f=latest",
        "description": "Bacot — juin 2025 (4e anniversaire du verdict)",
    },
    {
        "label": "bacot_juil2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-07-01%20until%3A2025-08-01&src=typed_query&f=latest",
        "description": "Bacot — juillet 2025",
    },
    {
        "label": "bacot_aout2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-08-01%20until%3A2025-09-01&src=typed_query&f=latest",
        "description": "Bacot — août 2025",
    },
    {
        "label": "bacot_sept2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-09-01%20until%3A2025-10-01&src=typed_query&f=latest",
        "description": "Bacot — septembre 2025",
    },
    {
        "label": "bacot_oct2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-10-01%20until%3A2025-11-01&src=typed_query&f=latest",
        "description": "Bacot — octobre 2025",
    },
    {
        "label": "bacot_nov2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-11-01%20until%3A2025-12-01&src=typed_query&f=latest",
        "description": "Bacot — novembre 2025",
    },
    {
        "label": "bacot_dec2025",
        "url": "https://x.com/search?q=Bacot%20since%3A2025-12-01%20until%3A2026-01-01&src=typed_query&f=latest",
        "description": "Bacot — décembre 2025",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 10. ANNÉE 2026 — jusqu'à aujourd'hui
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "bacot_jan2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-01-01%20until%3A2026-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2026",
    },
    {
        "label": "bacot_fev2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-02-01%20until%3A2026-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2026",
    },
    {
        "label": "bacot_mars2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-03-01%20until%3A2026-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2026",
    },
    {
        "label": "bacot_avr2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-04-01%20until%3A2026-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2026",
    },
    {
        "label": "bacot_mai2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-05-01%20until%3A2026-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2026",
    },
    {
        "label": "bacot_juin2026",
        "url": "https://x.com/search?q=Bacot%20since%3A2026-06-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot — juin 2026 (jusqu'à aujourd'hui)",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 11. ANGLES THÉMATIQUES — toutes périodes post-verdict
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "hashtag_ValerieBacot_all",
        "url": "https://x.com/search?q=%23Val%C3%A9rieBacot%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "#ValérieBacot — depuis le verdict",
    },
    {
        "label": "hashtag_JusticePourValerie",
        "url": "https://x.com/search?q=%23JusticePourVal%C3%A9rie%20OR%20%23JusticePourValerie%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "#JusticePourValérie — toutes périodes",
    },
    {
        "label": "hashtag_LibrezValerie",
        "url": "https://x.com/search?q=%23Lib%C3%A9rezVal%C3%A9rie%20OR%20%23LibérezValérie%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "#LibérezValérie — toutes périodes",
    },
    {
        "label": "legitime_defense_post_verdict",
        "url": "https://x.com/search?q=Bacot%20%22l%C3%A9gitime%20d%C3%A9fense%22%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + légitime défense — post-verdict",
    },
    {
        "label": "emprise_post_verdict",
        "url": "https://x.com/search?q=Bacot%20emprise%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + emprise — post-verdict",
    },
    {
        "label": "violences_conjugales_bacot",
        "url": "https://x.com/search?q=Bacot%20%22violences%20conjugales%22%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + violences conjugales",
    },
    {
        "label": "feminicide_bacot_post",
        "url": "https://x.com/search?q=Bacot%20(f%C3%A9minicide%20OR%20feminicide%20OR%20f%C3%A9micide)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + féminicide — post-verdict",
    },
    {
        "label": "nous_toutes_bacot_post",
        "url": "https://x.com/search?q=Bacot%20(NousToutes%20OR%20%22nous%20toutes%22)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + NousToutes — post-verdict",
    },
    {
        "label": "sauvage_bacot_comparaison",
        "url": "https://x.com/search?q=Bacot%20(Sauvage%20OR%20%22Jacqueline%20Sauvage%22)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + Jacqueline Sauvage — post-verdict",
    },
    {
        "label": "tomasini_post_verdict",
        "url": "https://x.com/search?q=Tomasini%20Bacot%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Tomasini (avocate) + Bacot — post-verdict",
    },
    {
        "label": "bacot_media_reportage",
        "url": "https://x.com/search?q=Bacot%20(documentaire%20OR%20reportage%20OR%20interview%20OR%20t%C3%A9moignage)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + documentaire/reportage/interview",
    },
    {
        "label": "bacot_droit_loi",
        "url": "https://x.com/search?q=Bacot%20(loi%20OR%20r%C3%A9forme%20OR%20droit%20OR%20justice)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + loi/réforme/droit — post-verdict",
    },
    {
        "label": "bacot_prison_liberation",
        "url": "https://x.com/search?q=Bacot%20(prison%20OR%20lib%C3%A9r%C3%A9e%20OR%20lib%C3%A9ration%20OR%20sortie)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + prison/libération — post-verdict",
    },
    {
        "label": "tout_le_monde_savait_post",
        "url": "https://x.com/search?q=%22tout%20le%20monde%20savait%22%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "\"Tout le monde savait\" — post-verdict (sans Bacot pour attraper les refs implicites)",
    },
    {
        "label": "bacot_anniversaire_all",
        "url": "https://x.com/search?q=Bacot%20(anniversaire%20OR%20%22il%20y%20a%20un%20an%22%20OR%20%22il%20y%20a%202%20ans%22%20OR%20%22il%20y%20a%203%20ans%22%20OR%20%22il%20y%20a%204%20ans%22%20OR%20%22il%20y%20a%205%20ans%22)%20since%3A2021-06-25%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Bacot + anniversaires (1 an, 2 ans, etc.)",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 12. COMPTES CLÉS — timelines de journalistes et militants
    # ══════════════════════════════════════════════════════════════════════
    # (scraper la timeline d'un compte spécifique en cherchant leur @ + Bacot)

    {
        "label": "compte_noustoutes_bacot",
        "url": "https://x.com/search?q=from%3ANousToutesOrg%20Bacot%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Tweets de @NousToutesOrg mentionnant Bacot",
    },
    {
        "label": "compte_osezlefeminisme_bacot",
        "url": "https://x.com/search?q=from%3AOsezLeFeminisme%20Bacot%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Tweets de @OsezLeFeminisme mentionnant Bacot",
    },
    {
        "label": "compte_muriellerou_bacot",
        "url": "https://x.com/search?q=from%3AMurielleRou%20Bacot%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Tweets de @MurielleRou (journaliste) sur Bacot",
    },
    {
        "label": "compte_tomasini_bacot",
        "url": "https://x.com/search?q=from%3ANathalieTomasini%20since%3A2021-01-01%20until%3A2026-06-11&src=typed_query&f=latest",
        "description": "Tweets de Maître Tomasini (avocate de Bacot)",
    },

    # ══════════════════════════════════════════════════════════════════════
    # 13. RECHERCHES PAR REQUÊTE LARGE — filet de sécurité
    # ══════════════════════════════════════════════════════════════════════

    {
        "label": "valerie_bacot_2022_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2022-01-01%20until%3A2023-01-01&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — 2022 (Top)",
    },
    {
        "label": "valerie_bacot_2023_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2023-01-01%20until%3A2024-01-01&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — 2023 (Top)",
    },
    {
        "label": "valerie_bacot_2024_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2024-01-01%20until%3A2025-01-01&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — 2024 (Top)",
    },
    {
        "label": "valerie_bacot_2025_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2025-01-01%20until%3A2026-01-01&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — 2025 (Top)",
    },
    {
        "label": "valerie_bacot_2026_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2026-01-01%20until%3A2026-06-11&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — 2026 (Top)",
    },
    {
        "label": "bacot_2020_top",
        "url": "https://x.com/search?q=Bacot%20since%3A2020-01-01%20until%3A2021-01-01&src=typed_query&f=top",
        "description": "Bacot — 2020 complet (Top)",
    },
    {
        "label": "bacot_2020_latest",
        "url": "https://x.com/search?q=Bacot%20since%3A2020-01-01%20until%3A2021-01-01&src=typed_query&f=latest",
        "description": "Bacot — 2020 complet (Récents)",
    },
    {
        "label": "valerie_bacot_2020",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2020-01-01%20until%3A2021-01-01&src=typed_query&f=latest",
        "description": "\"Valérie Bacot\" — 2020",
    },

    # ── Pétition — jan-mars 2021 ───────────────────────────────────────
    {
        "label": "petition_jan2021",
        "url": "https://x.com/search?q=Bacot%20p%C3%A9tition%20since%3A2021-01-01%20until%3A2021-02-01&src=typed_query&f=latest",
        "description": "Bacot + pétition — janvier 2021",
    },
    {
        "label": "petition_fev2021",
        "url": "https://x.com/search?q=Bacot%20p%C3%A9tition%20since%3A2021-02-01%20until%3A2021-03-01&src=typed_query&f=latest",
        "description": "Bacot + pétition — février 2021",
    },
    {
        "label": "petition_mars2021",
        "url": "https://x.com/search?q=Bacot%20p%C3%A9tition%20since%3A2021-03-01%20until%3A2021-04-01&src=typed_query&f=latest",
        "description": "Bacot + pétition — mars 2021",
    },
    {
        "label": "petition_top",
        "url": "https://x.com/search?q=Bacot%20p%C3%A9tition%20since%3A2021-01-01%20until%3A2021-06-21&src=typed_query&f=top",
        "description": "Bacot + pétition — jan-juin 2021 (Top)",
    },

    # ── Mois par mois jan-juin 2021 ────────────────────────────────────
    {
        "label": "bacot_jan2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-01-01%20until%3A2021-02-01&src=typed_query&f=latest",
        "description": "Bacot — janvier 2021",
    },
    {
        "label": "bacot_fev2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-02-01%20until%3A2021-03-01&src=typed_query&f=latest",
        "description": "Bacot — février 2021",
    },
    {
        "label": "bacot_mars2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-03-01%20until%3A2021-04-01&src=typed_query&f=latest",
        "description": "Bacot — mars 2021",
    },
    {
        "label": "bacot_avr2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-04-01%20until%3A2021-05-01&src=typed_query&f=latest",
        "description": "Bacot — avril 2021",
    },
    {
        "label": "bacot_mai2021",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-05-01%20until%3A2021-06-01&src=typed_query&f=latest",
        "description": "Bacot — mai 2021",
    },
    {
        "label": "bacot_juin2021_avantproc",
        "url": "https://x.com/search?q=Bacot%20since%3A2021-06-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot — 1-20 juin 2021 (avant procès)",
    },

    # ── Angles thématiques pré-procès ─────────────────────────────────
    {
        "label": "legitime_defense_pre",
        "url": "https://x.com/search?q=Bacot%20%22l%C3%A9gitime%20d%C3%A9fense%22%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot + légitime défense — pré-procès",
    },
    {
        "label": "emprise_pre",
        "url": "https://x.com/search?q=Bacot%20emprise%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot + emprise — pré-procès",
    },
    {
        "label": "feminisme_pre",
        "url": "https://x.com/search?q=Bacot%20(f%C3%A9minisme%20OR%20f%C3%A9ministe%20OR%20NousToutes)%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot + féminisme/NousToutes — pré-procès",
    },
    {
        "label": "sauvage_pre",
        "url": "https://x.com/search?q=Bacot%20Sauvage%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot + Jacqueline Sauvage — pré-procès",
    },
    {
        "label": "proxenete_pre",
        "url": "https://x.com/search?q=Bacot%20(prox%C3%A9n%C3%A8te%20OR%20proxen%C3%A8te%20OR%20Polette)%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Bacot + proxénète/Polette — pré-procès",
    },
    {
        "label": "valerie_bacot_pre_top",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=top",
        "description": "\"Valérie Bacot\" — pré-procès (Top)",
    },
    {
        "label": "valerie_bacot_pre_latest",
        "url": "https://x.com/search?q=%22Val%C3%A9rie%20Bacot%22%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "\"Valérie Bacot\" — pré-procès (Récents)",
    },
    {
        "label": "hashtag_pre",
        "url": "https://x.com/search?q=%23Val%C3%A9rieBacot%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "#ValérieBacot — pré-procès",
    },
    {
        "label": "liberezbacot_pre",
        "url": "https://x.com/search?q=(%23Lib%C3%A9rezVal%C3%A9rie%20OR%20%23LibrezbBacot%20OR%20%22lib%C3%A9rez%20Val%C3%A9rie%22)%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "#LibérezValérie — pré-procès",
    },
    {
        "label": "tomasini_pre",
        "url": "https://x.com/search?q=Tomasini%20Bacot%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Tomasini (avocate) + Bacot — pré-procès",
    },
    {
        "label": "daniel_polette_pre",
        "url": "https://x.com/search?q=%22Daniel%20Polette%22%20since%3A2020-01-01%20until%3A2021-06-21&src=typed_query&f=latest",
        "description": "Daniel Polette — pré-procès",
    },
]


# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG,        # DEBUG pour voir les exemples de tweets rejetés
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraper_twitter.log", encoding="utf-8"),
    ]
)
# Réduit le bruit des libs externes
logging.getLogger("playwright").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


# ─── Extraction des tweets ────────────────────────────────────────────────────

def extraire_tweets_page(page) -> list[dict]:
    """
    Extrait tous les tweets visibles sur la page courante.
    """
    tweets = []

    # Sélecteurs pour les articles tweet
    articles = page.query_selector_all('article[data-testid="tweet"]')

    for article in articles:
        try:
            # Texte du tweet principal + tweet cité éventuel (quote tweet)
            # query_selector_all capture les deux tweetText quand il y a un quote
            texte_els = article.query_selector_all('[data-testid="tweetText"]')
            texte = " ".join(el.inner_text() for el in texte_els if el.inner_text().strip())

            # Titre de l'article partagé (card preview — souvent le seul endroit
            # où "bacot" apparaît quand le tweet est juste un lien)
            card_el = article.query_selector(
                '[data-testid="card.layoutLarge.detail"], '
                '[data-testid="card.layoutSmall.detail"]'
            )
            if card_el:
                card_text = card_el.inner_text().strip()
                if card_text:
                    texte = (texte + " " + card_text).strip()

            if not texte or len(texte) < MIN_CHARS:
                continue

            # Auteur
            auteur_el = article.query_selector('[data-testid="User-Name"]')
            auteur = auteur_el.inner_text() if auteur_el else ""

            # Handle (@username)
            handle_el = article.query_selector('a[href*="/status/"]')
            handle = ""
            url_tweet = ""
            if handle_el:
                href = handle_el.get_attribute("href") or ""
                url_tweet = f"https://x.com{href}" if href.startswith("/") else href
                # Extrait le handle depuis l'URL
                parts = href.strip("/").split("/")
                if parts:
                    handle = "@" + parts[0]

            # Date
            time_el = article.query_selector("time")
            date = time_el.get_attribute("datetime") if time_el else ""

            # Métriques (likes, retweets)
            likes = 0
            retweets = 0
            try:
                like_el = article.query_selector('[data-testid="like"] span')
                rt_el   = article.query_selector('[data-testid="retweet"] span')
                if like_el:
                    likes = int(like_el.inner_text().replace(",", "").replace(" ", "") or 0)
                if rt_el:
                    retweets = int(rt_el.inner_text().replace(",", "").replace(" ", "") or 0)
            except Exception:
                pass

            tweets.append({
                "texte":    texte.strip(),
                "auteur":   auteur.strip().split("\n")[0],
                "handle":   handle,
                "date":     date[:10] if date else "",
                "datetime": date,
                "url":      url_tweet,
                "likes":    likes,
                "retweets": retweets,
                "nb_mots":  len(texte.split()),
            })

        except Exception as e:
            log.debug(f"Erreur extraction tweet : {e}")
            continue

    return tweets


_ANCRES = [
    # ── Identifiants géographiques / personnes de l'affaire ──
    "polette", "clayette", "tomasini", "chalon", "saône", "saone",
    "tout le monde savait",
    # ── Procédure et décision ──
    "procès", "proces", "audience", "assises", "verdict",
    "jugement", "cour d'assises", "condamn", "acquitt", "sursis",
    "peine", "prison",
    # ── Crimes subis ──
    "viol", "proxén", "proxen", "inceste", "prostitut",
    "meurtre", "tué", "tuée",
    # ── Contexte familial / relationnel ──
    "mari", "beau-père", "belle-mère", "conjoint",
    # ── Notions juridiques et féministes ──
    "légitime", "legitime", "défense", "defense",
    "emprise", "violence", "conjugal", "victime",
    "féminicide", "feminicide", "féminisme", "feminisme",
    "nous toutes", "noustoutes",
    # ── Mobilisation et suites ──
    "pétition", "petition", "sénat", "senat",
    "sauvage", "jacqueline",
    "livre", "documentaire", "reportage", "interview",
    # ── Réactions émotionnelles fréquentes sans jargon ──
    "libér", "libere", "injust", "solidar", "honte", "courag",
    "incroyable", "scandaleux", "scandale", "révoltant",
]


def est_requete_specifique(url: str) -> bool:
    """
    Vraie si la requête URL cible spécifiquement Valérie Bacot
    (nom complet, hashtag dédié, compte ciblé, terme co-occurrent fort).
    Dans ce cas la requête garantit la pertinence — pas besoin d'ancrage.
    """
    indicateurs = [
        "Val%C3%A9rie",       # Valérie (accent encodé)
        "Valerie%20Bacot",
        "%23Val%C3%A9rieBacot",
        "%23JusticePourVal",
        "%23Lib%C3%A9rez",
        "from%3A",            # from:user — compte ciblé
        "Daniel%20Polette",
        "Tomasini",
        "NousToutesOrg",
        "OsezLeFeminisme",
        "MurielleRou",
        "NathalieTomasini",
        "tout%20le%20monde%20savait",
    ]
    return any(ind in url for ind in indicateurs)


def est_pertinent(tweet: dict, haute_confiance: bool = False) -> bool:
    """
    Filtre à deux niveaux.

    haute_confiance=True : la requête X elle-même garantit la pertinence
    (nom complet, hashtag dédié, compte ciblé). On ne vérifie que la longueur.

    haute_confiance=False : "Bacot" seul dans la requête — risque de faux positifs
    (homonymes, autres affaires). Exige "bacot" dans le texte + un ancrage contextuel.
    """
    texte = tweet.get("texte", "").lower()

    if haute_confiance:
        return len(texte.strip()) >= MIN_CHARS // 2

    if "bacot" not in texte:
        return False

    if "valérie bacot" in texte or "valerie bacot" in texte:
        return True

    return any(ancre in texte for ancre in _ANCRES)


def dedupliquer(tweets: list[dict]) -> list[dict]:
    """Supprime les doublons par URL et par texte similaire."""
    vus_urls  = set()
    vus_texte = set()
    uniques   = []

    for t in tweets:
        url  = t.get("url", "")
        texte = t.get("texte", "")[:100]  # premiers 100 chars comme signature

        if url and url in vus_urls:
            continue
        if texte in vus_texte:
            continue

        if url:
            vus_urls.add(url)
        vus_texte.add(texte)
        uniques.append(t)

    return uniques


# ─── Scraping d'une recherche ─────────────────────────────────────────────────

def scraper_recherche(page, recherche: dict) -> list[dict]:
    """
    Scrape une page de résultats X avec défilement automatique.
    """
    label = recherche["label"]
    url   = recherche["url"]
    desc  = recherche["description"]

    log.info(f"\n{'='*50}")
    log.info(f"Recherche : {desc}")
    log.info(f"URL : {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)  # attend le chargement initial

        # Vérifie qu'on est bien connecté
        if "login" in page.url.lower() or page.query_selector('[data-testid="loginButton"]'):
            log.error("X demande une connexion — vérifie que tu es connecté dans Chrome")
            return []

    except PWTimeout:
        log.warning("Timeout chargement page — on continue quand même")

    tous_tweets = []
    tweets_avant = 0

    for scroll_n in range(MAX_SCROLLS):
        # Extrait les tweets visibles
        tweets_page = extraire_tweets_page(page)
        tous_tweets.extend(tweets_page)
        tous_tweets = dedupliquer(tous_tweets)

        n_nouveaux = len(tous_tweets) - tweets_avant
        tweets_avant = len(tous_tweets)

        log.info(f"  Scroll {scroll_n+1:>2}/{MAX_SCROLLS} — {len(tous_tweets)} tweets (+{n_nouveaux})")

        # Si plus de nouveaux tweets depuis 3 scrolls, on arrête
        if scroll_n > 3 and n_nouveaux == 0:
            log.info("  → Plus de nouveaux tweets, arrêt du défilement")
            break

        # Défilement
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)

        # Gère les éventuels popups
        try:
            close_btn = page.query_selector('[aria-label="Close"]')
            if close_btn:
                close_btn.click()
        except Exception:
            pass

    # Filtre les tweets pertinents
    hc = est_requete_specifique(url)
    pertinents = [t for t in tous_tweets if est_pertinent(t, haute_confiance=hc)]
    rejetes    = [t for t in tous_tweets if not est_pertinent(t, haute_confiance=hc)]
    mode = "haute confiance" if hc else "ancrage requis"

    log.info(f"\n  Total : {len(tous_tweets)} tweets · {len(pertinents)} pertinents [{mode}]")

    # Affiche 4 exemples de tweets rejetés pour permettre de calibrer le filtre
    if rejetes and not hc:
        log.debug("  Exemples rejetés :")
        for t in rejetes[:4]:
            texte_court = t.get("texte", "")[:90].replace("\n", " ")
            a_bacot = "bacot" in texte_court.lower()
            log.debug(f"    {'[bacot✓]' if a_bacot else '[pas bacot]'} "
                      f"{t.get('handle','')} : {texte_court}")

    return pertinents


# ─── Sauvegarde ───────────────────────────────────────────────────────────────

def sauvegarder(tous_tweets: list[dict]):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Fusionne avec tweets existants si présents
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, encoding="utf-8") as f:
            existants = json.load(f)
        urls_existantes = {t.get("url", "") for t in existants}
        nouveaux = [t for t in tous_tweets if t.get("url", "") not in urls_existantes]
        tous_tweets = existants + nouveaux
        log.info(f"Fusion : {len(existants)} existants + {len(nouveaux)} nouveaux = {len(tous_tweets)} total")

    # JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tous_tweets, f, ensure_ascii=False, indent=2)

    # CSV
    if tous_tweets:
        cols = ["texte", "auteur", "handle", "date", "datetime", "url", "likes", "retweets", "nb_mots"]
        with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(tous_tweets)

    log.info(f"""
╔══════════════════════════════════════════════════╗
║         TWEETS SCRAPÉS ✓                         ║
╠══════════════════════════════════════════════════╣
║  Tweets total   : {len(tous_tweets):>5}                   ║
╚══════════════════════════════════════════════════╝
→ {OUTPUT_JSON}
→ {OUTPUT_CSV}
    """)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run():
    log.info("Démarrage du scraper Twitter/X — Procès Bacot")
    log.info("Utilise ta session Chrome existante (déjà connectée)")

    OUTPUT_DIR.mkdir(exist_ok=True)
    tous_tweets = []

    with sync_playwright() as p:
        # Utilise le profil Chrome existant pour réutiliser la session
        # Cherche le profil Chrome par défaut selon l'OS
        import os
        chrome_profile = None

        # Chemins possibles du profil Chrome sur Windows
        chemins_chrome = [
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data"),
            os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data"),
        ]

        for chemin in chemins_chrome:
            if os.path.exists(chemin):
                chrome_profile = chemin
                log.info(f"Profil navigateur trouvé : {chemin}")
                break

        # Profil hors OneDrive pour éviter les conflits de verrou lors de la sync
        profil_scraping = Path(os.environ.get("LOCALAPPDATA", "C:/Users")) / "playwright_bacot_profile"
        profil_scraping.mkdir(exist_ok=True)

        # Supprime les verrous résiduels si le process précédent a planté
        for lock in [profil_scraping / "lockfile", profil_scraping / "Default" / "LOCK"]:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass

        log.info(f"Profil Playwright : {profil_scraping}")
        log.info("Si c'est la première fois, tu devras te connecter à X manuellement.")

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profil_scraping),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            slow_mo=50,
        )

        page = context.new_page()

        # Vérifie la connexion
        log.info("Vérification de la connexion X...")
        page.goto("https://x.com/home", timeout=30000)
        time.sleep(3)

        if "login" in page.url.lower() or page.query_selector('input[name="text"]'):
            log.info("="*50)
            log.info("Connecte-toi à X dans la fenêtre qui s'est ouverte.")
            log.info("Une fois connecté et sur la page d'accueil, appuie sur Entrée ici.")
            log.info("="*50)
            input(">>> Appuie sur Entrée quand tu es connecté : ")
            page.goto("https://x.com/home", timeout=30000)
            time.sleep(3)

        log.info("Connexion confirmée ✓")

        # Scrape chaque recherche
        for recherche in RECHERCHES:
            tweets = scraper_recherche(page, recherche)

            # Ajoute le label de recherche
            for t in tweets:
                t["recherche"] = recherche["label"]
                t["source"]    = "twitter_x"

            tous_tweets.extend(tweets)
            tous_tweets = dedupliquer(tous_tweets)

            log.info(f"  Cumul total : {len(tous_tweets)} tweets")
            time.sleep(2)

        context.close()

    sauvegarder(tous_tweets)


if __name__ == "__main__":
    run()