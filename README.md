# Analyse comparative de marché

Application console Python qui compare les prix de trois boutiques (Marché Lagune, Baobab Shop, Comptoir Ivoire)
à partir de fichiers CSV, JSON et Excel. Elle rapproche les produits d'un catalogue commun, signale les anomalies
dans un journal, compare les offres disponibles et calcule un panier au meilleur prix.

## Installation

```bash
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

Placer les fichiers fournis dans `data/` puis :

```bash
python main.py
```

## Structure

```
analyse_comparative/
├── .gitignore
├── config.py              # chemins, enseignes, règles
├── main.py                # point d'entrée
├── requirements.txt
├── data/                  # fichiers sources (non versionnés)
├── exports/               # fichiers générés (non versionnés)
└── app/
    ├── controllers/       # enchaîne les étapes
    ├── models/            # chargement, calculs, benchmark
    └── views/             # affichage console et exports
```

## Sorties (`exports/`)

- `comparatif.csv` : prix par enseigne, enseigne la moins chère, écart en FCFA et en %
- `panier.csv` : panier de rentrée au meilleur prix
- `historique_black_friday.csv` : prix de la semaine du Black Friday contre moyenne annuelle
- `journal_nettoyage.csv` : anomalies détectées et traitements appliqués
- `synthese.txt` : synthèse, panier et Black Friday en texte
- `complexite.txt` : mesure du temps, recherche naïve contre index dict

## Principes

- Les fichiers sources ne sont jamais modifiés : le nettoyage se fait en mémoire.
- Un prix absent, une rupture ou un prix aberrant n'est jamais retenu comme « le moins cher ».
- Le rapprochement se fait par une table de correspondance référence → `produit_id`, avec un contrôle de cohérence sur la marque.
