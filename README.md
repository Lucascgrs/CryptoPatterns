# CryptoPatterns

Repérer automatiquement les figures de l'analyse technique sur les cryptos, à
l'échelle de temps de ton choix, les voir sur le graphique et mesurer ce qui
s'est passé après elles :

- les **retournements** : double et triple sommet/creux, tête-épaules (et inversée) ;
- les **triangles et biseaux** : ascendant, descendant, symétrique, biseaux,
  élargissement ;
- les **canaux et ranges** : canal ascendant/descendant, rectangle, range
  (période de consolidation) ;
- les **continuations** : drapeaux, fanions, tasse avec anse ;
- les **harmoniques** : Gartley, chauve-souris, papillon, crabe, AB=CD ;
- les **divergences** du RSI ;
- les **chandeliers japonais** : doji, marteau, avalement, étoile du matin,
  trois soldats… (20 figures) ;
- et, en plus, les **supports et résistances** et la **structure** du marché
  (sommets et creux plus hauts ou plus bas).

Tout est algorithmique : chaque figure obéit à une règle écrite, affichée dans
le catalogue, et rejouée telle quelle. Aucun modèle, aucun apprentissage.

## Lancer

```bash
cd CryptoPatterns
pip install -r requirements.txt
python Dashboard.py
```

numba est facultatif. Sans lui, la détection tourne en Python pur, en plus lent.

## L'interface

Cinq pages, dans la barre de gauche.

### Données

Choisis les cryptos, les échelles (1m à 1w) et la profondeur (90 jours à
« Tout », c'est-à-dire depuis l'ouverture de Binance en 2017), puis
« Télécharger / mettre à jour ». Rien de ce qui est déjà téléchargé n'est
effacé : relancer complète seulement ce qui manque.

« Importer depuis CryptoSupertrend » reprend les historiques déjà téléchargés
pour l'autre projet. Ils sont copiés, puis fusionnés sans rien effacer.

**N'importe quelle échelle.** Binance ne sert que 1m, 3m, 5m, 15m, 30m, 1h, 2h,
4h, 6h, 8h, 12h, 1d, 3d et 1w. Toute autre échelle (10m, 45m, 3h, 2d…) se tape
directement dans les autres pages. Elle est construite à partir de la plus
grande échelle téléchargée qui la divise : 45m à partir de 15m, 2d à partir
de 1d. Le résultat a été vérifié : les bougies 1h construites à partir de 15m
sont identiques, au centime près, à celles de Binance.

### Graphique

La page principale.

À gauche :
- la crypto, l'échelle et la source : l'historique téléchargé (les N
  dernières bougies, ou une période), ou bien « En direct », c'est-à-dire les
  1000 dernières bougies lues sur Binance, pour n'importe quelle crypto ;
- les figures à chercher, par famille ;
- les réglages de la détection.

À droite :
- le **graphique** en chandeliers, avec les figures repérées. La molette
  zoome, la barre d'outils déplace la vue et la maison y revient ;
- la **liste des figures**, à filtrer par famille et par statut. Un clic sur
  une ligne, ou sur une figure du graphique, la sélectionne : elle est mise en
  évidence, avec son objectif et son niveau d'invalidation ;
- la **fiche** de la figure sélectionnée : ses dates, ses prix, ce qu'elle
  annonce et la règle qui l'a reconnue. « Précédente / Suivante » passe les
  figures en revue une à une.

Couleurs : vert pour une figure haussière, rouge pour une baissière, bleu pour
une figure neutre, dont la direction dépend de la cassure.

Options d'affichage :
- les vagues du zigzag ;
- les étiquettes HH / HL / LH / LL de la structure ;
- les supports et résistances ;
- les chandeliers ;
- le volume ou le RSI dans le panneau du bas. Avec le RSI, les droites des
  divergences y sont tracées.

« Exporter » met la liste dans Excel ; « Image » enregistre la vue en PNG.

### En ce moment

Pour plusieurs cryptos et plusieurs échelles à la fois, les figures qui
viennent de se confirmer (depuis au plus N bougies) et celles qui sont en
train de se former. Les données sont lues sur Binance à l'instant.

Pour une figure en formation :
- **Niveau** est le prix à franchir pour la confirmer ;
- **Écart** est le chemin qui reste à parcourir.

La page peut se relancer seule toutes les X minutes. Un double-clic ouvre la
figure dans la page Graphique.

### Statistiques

Pour chaque sorte de figure, sur tout l'historique choisi (cryptos ×
échelles), le tableau répond à la question : que fait le prix ensuite ?

| Colonne | Ce qu'elle mesure |
|---|---|
| Repérées / Confirmées | combien de figures terminées, combien ont cassé dans le bon sens |
| Bon sens | part des cas où le prix, N bougies après le signal, est allé dans le sens attendu |
| Hasard | la même chose pour n'importe quelle bougie du même historique |
| Écart | Bon sens − Hasard, en points : ce que la figure apporte vraiment |
| Objectif atteint / Invalidée | le premier des deux niveaux touché dans les N bougies |
| Trade net moyen | une règle fixe : entrée à la clôture du signal, sortie à l'objectif, à l'invalidation ou au bout de N bougies ; frais payés deux fois |
| Écart 1re / 2e moitié | l'écart sur chaque moitié de la période |

Pourquoi le hasard : sur une période où le prix monte, toute figure haussière
« marche » plus d'une fois sur deux. Seul l'écart au hasard dit si la figure
apporte quelque chose.

Pourquoi deux moitiés : une figure qui ne bat le hasard que sur une moitié de
la période est fragile.

Lecture des couleurs :
- **vert** : mieux que le hasard sur les deux moitiés, et trade gagnant en
  moyenne ;
- **rouge** : moins bien que le hasard sur les deux moitiés ;
- **gris** : moins de 30 exemples, résultat peu fiable.

Trois onglets :
- **Résumé** : le tableau, à regrouper par figure, par figure et échelle, ou
  par figure et crypto ;
- **Graphique** : l'écart au hasard de chaque figure, avec les deux moitiés ;
- **Occurrences** : chaque figure, une par ligne ; un double-clic l'ouvre sur
  le graphique.

Tout s'exporte dans Excel.

Premier coup d'œil sur BTC (1h, 4h et 1d, de 2022 à 2026, jugé après 20
bougies) : la plupart des figures font à peu près comme le hasard. Les rares
écarts nets reposent sur quelques dizaines de cas, ou ne tiennent que sur une
moitié de la période.

### Catalogue

Pour chacune des 54 figures :
- son dessin type ;
- ce qu'elle annonce ;
- la règle exacte avec laquelle le programme la reconnaît ;
- comment l'objectif et l'invalidation sont fixés.

## Comment c'est calculé

**L'unité de mesure est l'ATR** (Average True Range sur 14 bougies, de
Wilder) : l'amplitude moyenne d'une bougie. Une vague « de 3 ATR » est une vraie
vague sur BTC comme sur DOGE, en 5 minutes comme en 1 semaine. C'est ce qui
permet d'utiliser les mêmes réglages à toutes les échelles.

**Les sommets et les creux (zigzag).** On suit le prix : pendant une hausse, on
retient le plus haut atteint. Dès que le prix redescend de *sensibilité × ATR*
sous ce plus haut, celui-ci devient un sommet, et on suit la baisse ; on fait de
même pour les creux. Avec une sensibilité basse, on obtient plus de pivots, donc
de plus petites figures ; avec une sensibilité haute, seulement les grandes.

**Les figures chartistes** sont lues sur ces pivots.

- *Double sommet* : trois pivots sommet – creux – sommet, avec des sommets à
  la tolérance près.
- *Triangle* : une droite passe par les sommets, une autre par les creux ;
  leurs pentes et leur resserrement décident du nom (triangle, biseau, canal,
  rectangle, élargissement). La figure grandit pivot par pivot (de 5 à 8) tant
  qu'elle n'a pas cassé.

**Les drapeaux** et **les ranges** sont cherchés bougie par bougie : leurs
oscillations sont trop petites pour le zigzag.

**Les chandeliers** comparent chaque bougie à la moyenne des corps des 14
précédentes et à la tendance qui précède. En crypto, le marché ne ferme
jamais : les conditions d'écart (« gap ») des définitions boursières sont
abandonnées.

**Statut d'une figure :**
- **en formation** : elle est dessinée, mais le prix n'a pas encore franchi le
  niveau qui la confirme ;
- **confirmée** : il l'a franchi (clôture au-delà de la ligne de cou, de la
  droite du triangle, du bord du range…) ;
- **invalidée** : le prix est d'abord sorti du mauvais côté ;
- **sans cassure** : rien ne s'est passé dans le délai.

**Aucun regard vers le futur.** Un sommet n'est connu qu'au moment où le prix
s'en est assez éloigné, et non au moment où il se forme. Une figure n'est donc
datée qu'à la confirmation de son dernier pivot. Le signal est la plus tardive
de ces deux bougies : la cassure, ou le moment où la figure devient visible.

Ce point a été vérifié sur 4 échelles et 8 dates. On a coupé l'historique à
une date T, puis, séparément, remplacé tous les prix postérieurs à T par une
marche au hasard. Dans les deux cas, les figures dont le signal tombe avant T
sont exactement les mêmes.

Le test a mis au jour un piège, corrigé depuis : choisir après coup la plus
grande figure, ou effacer un double sommet qui devient un triple, fait
disparaître des signaux qu'on aurait vus en direct, et embellit les
statistiques.

## Réglages

| Réglage | Défaut | Effet |
|---|---|---|
| Taille des vagues | 3 ATR | taille minimale d'un mouvement entre deux pivots |
| Tolérance | 15 % | écart admis entre deux sommets « égaux », ou entre un pivot et sa droite, en % de la hauteur de la figure |
| Range : largeur | 4 ATR | bande dans laquelle doivent tenir toutes les clôtures |
| Range : durée | 30 bougies | durée minimale d'un range |
| Support / résistance | 3 contacts | pivots au même niveau, à ½ ATR près, pour tracer un niveau |
| Juger après | 20 bougies | horizon des colonnes « Après N » et des statistiques |

## En ligne de commande

```bash
python main.py telecharger                        # 10 cryptos, 15m à 1w, 4 ans
python main.py telecharger BTC ETH --intervalles 1h,4h,1d --tout
python main.py importer                           # les historiques de CryptoSupertrend
python main.py inventaire
python main.py analyser BTC 4h                    # figures des 5000 dernières bougies + image PNG
python main.py analyser ETH 45m --bougies 2000 --chandeliers
python main.py analyser SOL 1h --direct           # 1000 dernières bougies lues sur Binance
python main.py direct --intervalles 15m,1h,4h,1d  # ce qui se forme en ce moment
python main.py stats BTC --intervalles 1h,4h,1d --horizon 20 --excel
python main.py catalogue
```

Les commandes qui détectent acceptent :
- `--sensibilite` et `--tolerance` ;
- `--figures`, avec des types ou des familles séparés par des virgules (par
  exemple `--figures Retournements,triangle_symetrique`) ;
- `--chandeliers`, qui ajoute les figures de chandeliers.

## Organisation

```
CryptoPatterns/
├── Dashboard.py             interface graphique
├── main.py                  ligne de commande
├── patterns_lab/
│   ├── config.py            cryptos, échelles, réglages par défaut
│   ├── donnees.py           Binance (parallèle, incrémental), échelles construites, direct, import
│   ├── indicateurs.py       ATR et RSI de Wilder
│   ├── pivots.py            zigzag et structure HH / HL / LH / LL
│   ├── figures.py           le catalogue et la fiche d'une figure
│   ├── chartistes.py        doubles, triples, tête-épaules, triangles, biseaux, canaux, tasses
│   ├── drapeaux.py          drapeaux et fanions
│   ├── zones.py             ranges, supports et résistances
│   ├── harmoniques.py       XABCD, AB=CD, divergences du RSI
│   ├── chandeliers.py       les 20 figures de chandeliers
│   ├── detection.py         l'analyse complète d'un historique
│   ├── statistiques.py      ce qui suit chaque figure, comparé au hasard
│   ├── dessin.py            bougies et figures sur un graphique matplotlib
│   ├── rapport.py           exports Excel
│   └── interface/           les cinq pages de l'application
├── donnees/                 historiques et réglages de l'interface (ignoré par git)
└── resultats/               exports Excel et images (ignoré par git)
```
