# Note technique — Corpus narratifs médiatiques, Affaire Valérie Bacot
**Projet Mythodologie** · Version 1.0 · Juin 2026  
Auteure : [Ton nom] · Contact : [email]  
Dépôt GitHub : [URL]

---

## 1. Présentation du projet

Ce corpus a été constitué dans le cadre du projet **Mythodologie**, dont l'objectif est de développer des infrastructures de données ouvertes permettant l'analyse computationnelle des narratifs médiatiques autour d'affaires judiciaires impliquant des violences faites aux femmes.

Le présent corpus porte sur l'affaire Valérie Bacot — affaire jugée en juin 2021 aux Assises de Saône-et-Loire — et vise à cartographier les discours produits autour de ce procès dans la presse française et sur les plateformes numériques, entre 2017 et 2023.

Il s'agit d'un **prototype v1** : les résultats présentés sont préliminaires, la méthode est documentée comme reproductible, et le corpus est conçu pour être enrichi de façon itérative. Cette note accompagne le dataset open publié sur GitHub et constitue son principal document de référence.

**Public cible.** Cette note s'adresse aux chercheurs souhaitant utiliser les données pour orienter ou appuyer une enquête sur les violences conjugales, la médiatisation des affaires judiciaires, ou les mécanismes rhétoriques à l'œuvre dans les procès pour violences faites aux femmes.

---

## 2. L'affaire Valérie Bacot — éléments de contexte

*Les éléments suivants sont tirés des sources primaires contenues dans le corpus, notamment du compte rendu de la commission sénatoriale du 4 novembre 2021 et des articles de presse scrapés.*

Valérie Bacot a été victime pendant plus de vingt-cinq ans de viols, violences physiques et proxénétisme de la part de Daniel Polette, son beau-père devenu son mari. En décembre 2012, elle l'a tué d'une balle dans la nuque alors qu'il l'emmenait se prostituer. Elle a été jugée en juin 2021 aux Assises de Saône-et-Loire et condamnée à quatre ans de prison dont trois avec sursis — libérée le jour même du verdict.

Plusieurs éléments rendent cette affaire particulièrement significative pour une analyse des discours sur les violences conjugales :

**La pétition.** Avant le procès, une pétition de soutien a recueilli plus de 600 000 signatures, signe d'une mobilisation populaire rare pour une affaire de ce type. Elle a directement influencé la médiatisation du procès.

**L'angle mort juridique.** La notion de légitime défense différée — reconnue dans plusieurs pays comme le Canada ou le Royaume-Uni — n'existe pas en droit français. L'affaire Bacot, comme l'affaire Jacqueline Sauvage avant elle, a relancé ce débat législatif.

**Le livre.** En septembre 2021, Valérie Bacot a publié *Tout le monde savait* (Fayard), titre qui est devenu une formule synthétisant la dimension du silence collectif et de la complicité passive de l'entourage et des institutions dans les situations de violence prolongée.

**La dimension institutionnelle.** Le 4 novembre 2021, Valérie Bacot a témoigné devant la délégation aux droits des femmes du Sénat. Ce compte rendu, intégralement scrapé, constitue l'un des documents les plus denses du corpus (11 090 mots).

---

## 3. Description du corpus

### 3.1 Volume et composition

| Type de document | Nombre | Mots moyens |
|---|---|---|
| Articles de presse | 214 | 854 |
| Commentaires YouTube | 739 | 63 |
| **Total** | **953** | — |

### 3.2 Sources et méthode de collecte

Le corpus a été constitué en mai 2026 via plusieurs méthodes de scraping automatisé :

- **Flux RSS Google News** — 8 requêtes thématiques, décodage des URLs via `googlenewsdecoder`
- **URLs manuelles** — 19 sources identifiées manuellement, scrapées via `trafilatura`
- **Commentaires YouTube** — 38 vidéos identifiées via l'API YouTube Data v3, commentaires filtrés par pertinence (mots-clés + longueur minimale de 100 caractères)
- **Pages de recherche internes** — crawl de 13 sources de presse via leurs moteurs de recherche internes

L'extraction du texte des articles a été réalisée avec la librairie `trafilatura`, qui identifie et isole le contenu éditorial en supprimant les éléments de navigation et de mise en page.

### 3.3 Période couverte

Le corpus couvre principalement la période **juin 2021** (procès) à **fin 2022**, avec quelques documents antérieurs (pétition de janvier 2021) et postérieurs (suites judiciaires, réformes législatives).

### 3.4 Sources représentées

Presse nationale généraliste (BFM TV, RTL, Le Parisien, 20 Minutes, TF1 Info, France 3), presse locale (Le JSL, Bien Public), sources institutionnelles (Sénat), et chaînes YouTube grand public et true crime (Canal Crime, Victoria Charlton, Tibo InShape, Faites entrer l'accusé).

---

## 4. Limites connues du corpus

Il est essentiel que les utilisateurs de ce corpus aient conscience des biais et limites suivants avant toute utilisation analytique.

**Biais de sélection par paywall.** Les articles de presse derrière abonnement (Libération, Le Monde, Mediapart, Le Point) n'ont pas pu être scrapés dans leur intégralité. Le corpus surreprésente donc les sources en accès libre, et sous-représente la presse d'analyse et d'opinion.

**Biais algorithmique YouTube.** Les vidéos et commentaires ont été sélectionnés via l'algorithme de recommandation de YouTube, qui favorise le contenu populaire et récent. Les contenus militants ou académiques de faible audience sont probablement sous-représentés.

**Filtre de pertinence.** Les commentaires YouTube ont été filtrés par mots-clés (liste disponible dans `classifier_bacot.py`). Des commentaires hostiles ou de cyberviolence peuvent avoir été écartés si leur lexique ne correspondait pas aux termes du filtre. Ce point est particulièrement important si l'objectif de l'enquête porte sur les discours de haine ou de cyberviolence.

**Absence de dimension genrée des locuteurs.** Il est impossible, sur ce corpus, de savoir si un commentaire a été écrit par une femme ou un homme. Cette information, pourtant pertinente pour analyser la polarisation genrée des réactions, n'est pas disponible.

**Corpus non exhaustif.** Ce corpus ne prétend pas représenter l'ensemble de la production discursive sur l'affaire Bacot. Il constitue un échantillon structuré, utile pour identifier des tendances, pas pour établir des statistiques représentatives.

**Classification préliminaire.** La classification lexicale est un outil de repérage automatique, pas d'interprétation. Un document classé dans la catégorie "soutien victime" peut contenir des éléments de remise en question — la catégorie reflète le registre dominant, pas la totalité du propos.

---

## 5. Méthode de classification

### 5.1 Classification lexicale

Chaque document a été scoré sur 8 catégories de narratifs à partir d'un lexique construit manuellement. Le score d'une catégorie correspond au nombre total d'occurrences des termes de cette catégorie dans le texte. Le document est assigné à la catégorie avec le score le plus élevé.

Les 8 catégories sont :

| Catégorie | Description |
|---|---|
| `soutien_victime` | Compassion, solidarité, validation du geste comme survie |
| `remise_en_question` | Doute sur les choix, évocation d'alternatives, culpabilisation |
| `legitime_defense` | Cadre juridique, précédent Sauvage, réforme législative |
| `discours_feministe` | Approche systémique — patriarcat, féminicide, continuum |
| `emprise_psychologique` | Mécanisme d'emprise, contrôle coercitif, traumatisme |
| `silence_collectif` | Complicité passive, entourage, institutions |
| `sensationnalisme` | Traitement comme fait divers spectaculaire, true crime |
| `jugement_moral` | Jugement sur la légitimité de la peine ou la culpabilité morale |

Le lexique complet est disponible dans le fichier `classifier_bacot.py`. Il peut être modifié et enrichi selon les besoins de l'enquête.

**Ce que cette méthode mesure.** La densité de certains registres lexicaux dans un texte. Elle permet d'identifier rapidement les documents les plus représentatifs d'un narratif donné.

**Ce que cette méthode ne mesure pas.** L'ironie, la nuance, la contradiction interne d'un texte. Un commentaire sarcastique ("bien sûr qu'elle avait le choix, comme toutes les femmes sous emprise...") sera mal classé. Toute utilisation des résultats de classification doit s'accompagner d'une lecture humaine des documents sélectionnés.

### 5.2 Vectorisation TF-IDF et clustering

Une vectorisation TF-IDF (Term Frequency — Inverse Document Frequency) a été appliquée à l'ensemble du corpus pour transformer chaque texte en vecteur mathématique représentant l'importance relative de chaque mot. Un algorithme K-Means a ensuite regroupé les documents en 6 clusters selon leur similarité lexicale globale.

Le clustering est **non supervisé** — les groupes émergent des données sans catégories prédéfinies. Les 6 clusters identifiés ne correspondent pas nécessairement aux 8 catégories narratives. Ils révèlent des regroupements naturels dans le corpus qui peuvent croiser plusieurs narratifs.

---

## 6. Résultats préliminaires

Ces résultats décrivent ce que les outils ont mesuré. Ils ne constituent pas une interprétation causale.

**Le narratif de soutien domine quantitativement.** Il représente la catégorie la plus fréquente du corpus, concentrée à 96% dans les commentaires YouTube. Cela ne signifie pas que l'opinion publique est unanimement favorable à Valérie Bacot — le filtre de pertinence appliqué aux commentaires peut avoir écarté une partie des discours hostiles.

**La fracture presse / YouTube est nette.** La heatmap des scores moyens par type de source montre que la presse nationale et institutionnelle concentre les narratifs juridiques et politiques (légitime défense, silence collectif), tandis que YouTube concentre le soutien émotionnel et le sensationnalisme. Ces deux registres coexistent rarement dans les mêmes sources.

**Le discours féministe est rare mais dense.** Peu de documents sont classés dans cette catégorie, mais ceux qui le sont ont des scores très élevés — ils mobilisent un lexique militant concentré. Ils proviennent presque exclusivement de la presse militante et d'associations.

**Le silence collectif est un narratif de presse.** Les documents les mieux scorés dans cette catégorie sont les plus longs du corpus — le compte rendu sénatorial, les lives du procès, les articles de fond. Ce narratif nécessite de l'espace pour se déployer.

**Le sensationnalisme est concentré sur les chaînes true crime.** Canal Crime, Victoria Charlton et Tibo InShape représentent une part significative de ce cluster. Les commentaires sous ces vidéos mélangent soutien et fascination pour les détails de l'affaire.

---

## 7. Pistes pour l'analyse qualitative

Les questions suivantes peuvent être explorées à partir de ce corpus. Elles nécessitent toutes une lecture humaine des documents identifiés.

**Sur la médiatisation du procès.**
- Comment les médias nationaux et locaux cadrent-ils différemment l'affaire ? Le JSL (presse locale de Saône-et-Loire) couvre-t-il l'affaire sous un angle différent de BFM TV ?
- La pétition a-t-elle changé le registre des articles ? Y a-t-il une inflexion observable avant/après janvier 2021 ?

**Sur les mécanismes rhétoriques.**
- Quels arguments sont utilisés par ceux qui remettent en question le geste de Valérie ? Ressemblent-ils aux stratégies de déresponsabilisation documentées dans l'affaire Mazan ?
- Le mot "emprise" est-il utilisé de façon experte (presse, institutions) ou populaire (commentaires) ? Les deux usages sont-ils compatibles ?

**Sur le silence collectif.**
- Qui est désigné comme responsable du silence ? L'entourage, la famille, les institutions, la société ? La désignation varie-t-elle selon le type de source ?

**Sur la dimension juridique.**
- L'affaire Jacqueline Sauvage est-elle citée comme précédent positif ou comme contre-exemple ? Dans quels types de sources ?

**Sur le sensationnalisme.**
- Les commentaires sous les vidéos true crime expriment-ils les mêmes narratifs que ceux sous les vidéos de presse (BFM, Le Parisien) ? Y a-t-il une différence de registre moral ?

---

## 8. Guide d'utilisation des fichiers

### Fichiers du dataset

| Fichier | Contenu | Usage recommandé |
|---|---|---|
| `corpus_bacot_metadata.csv` | Métadonnées de 953 documents (URL, titre, date, source, scores) | Point d'entrée principal — identifier les documents à lire |
| `corpus_youtube_commentaires.csv` | Texte complet de 739 commentaires YouTube | Analyse du discours populaire, repérage de la cyberviolence |
| `resultats_classification.csv` | Scores des 8 narratifs pour chaque document | Filtrer par narratif, comparer les sources |
| `lexique_narratifs.json` | Les 8 catégories avec leurs termes | Modifier ou enrichir la classification |
| `analyse_bacot_complet.xlsx` | Vue d'ensemble + clusters + citations (48 extraits) | Exploration rapide sans code |

### Outils disponibles

**Dashboard Streamlit** — interface interactive pour explorer le corpus, filtrer par narratif, rechercher une expression dans les textes. Lancer avec `streamlit run dashboard_bacot.py`.

**API FastAPI** — endpoints REST pour accéder au corpus programmatiquement. Documentation disponible sur `/docs` après lancement.

**Scripts Python** — tous les scripts de scraping et de classification sont disponibles et documentés. Ils peuvent être relancés pour enrichir le corpus ou modifier la classification.

### Pour aller plus loin

Pour modifier le lexique de classification et relancer l'analyse sur le corpus existant :

```bash
# 1. Modifier LEXIQUE dans classifier_bacot.py
# 2. Relancer la classification
python classifier_bacot.py
# 3. Relancer l'extraction de citations
python extraire_citations.py
```

---

## 9. Licence et citation

**Données.** Le corpus de métadonnées et les commentaires YouTube sont publiés sous licence **Creative Commons CC BY 4.0**. Vous êtes libre de les utiliser, modifier et redistribuer à condition de citer la source.

**Code.** Les scripts Python sont publiés sous licence **MIT**.

**Citation recommandée.**
> [Ton nom] (2026). *Corpus narratifs médiatiques — Affaire Valérie Bacot*. Projet Mythodologie. GitHub. [URL]

**Note sur les textes d'articles.** Les textes complets des articles de presse ne sont pas inclus dans le dataset open pour des raisons de droit d'auteur. Seules les métadonnées et les URLs sont publiées. Les textes sont accessibles depuis les sources originales via les URLs fournies.

---

*Note technique rédigée par [Ton nom], ingénieure de recherche, Projet Mythodologie, juin 2026.*  
*Prototype v1 — corpus en cours d'enrichissement.*
