"""Modèle, étape 8 : temps d'exécution, recherche naïve contre index dict."""
import time
from collections import defaultdict

from app.models.chargement import ENSEIGNES


def moyenne_naive(historique, pid, source):
    valeurs = [h["prix"] for h in historique if h["produit_id"] == pid and h["source"] == source]
    return sum(valeurs) / len(valeurs) if valeurs else None


def construire_index(historique):
    index = defaultdict(list)
    for h in historique:
        index[(h["produit_id"], h["source"])].append(h["prix"])
    return index


def mesurer(historique, pids):
    requetes = [(p, s) for p in pids for s in ENSEIGNES]

    t0 = time.perf_counter()
    naive = [moyenne_naive(historique, p, s) for p, s in requetes]
    t_naive = time.perf_counter() - t0

    t0 = time.perf_counter()
    index = construire_index(historique)
    t_build = time.perf_counter() - t0

    t0 = time.perf_counter()
    indexe = []
    for p, s in requetes:
        v = index.get((p, s))
        indexe.append(sum(v) / len(v) if v else None)
    t_lookup = time.perf_counter() - t0

    concordant = all((a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-9)
                     for a, b in zip(naive, indexe))
    return {"lignes": len(historique), "requetes": len(requetes), "t_naive": t_naive,
            "t_build": t_build, "t_lookup": t_lookup, "concordant": concordant}
