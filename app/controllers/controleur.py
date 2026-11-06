"""Contrôleur : enchaîne les étapes des modèles. Ne calcule rien et n'affiche rien."""
from app.models.benchmark import mesurer
from app.models.calculs import (analyse_black_friday, calculer_panier, construire_comparatif,
                            prix_par_produit, synthese)
from app.models.chargement import (Journal, charger_catalogue, charger_historique, charger_tout,
                               controler_historique, controler_prix, medianes, nettoyer, rapprocher)


class Controleur:
    def run(self):
        journal = Journal()
        catalogue = charger_catalogue()
        historique = charger_historique()
        controler_historique(historique, journal)
        med = medianes(historique)

        articles = nettoyer(charger_tout(), journal)            # étapes 1 et 2
        articles = rapprocher(articles, catalogue, journal)     # étape 3
        controler_prix(articles, med, journal)

        par_produit = prix_par_produit(articles)
        lignes, non_comparables = construire_comparatif(par_produit, catalogue)  # étape 4
        gagnes, moyens, top3 = synthese(lignes)                                  # étape 5
        panier = calculer_panier(par_produit, catalogue)                         # étape 6
        bf_detail, bf_resume = analyse_black_friday(historique)                  # étape 7
        benchmark = mesurer(historique, list(catalogue))                         # étape 8

        return {"journal": journal.entrees, "lignes": lignes, "non_comparables": non_comparables,
                "gagnes": gagnes, "moyens": moyens, "top3": top3, "panier": panier,
                "bf_detail": bf_detail, "bf_resume": bf_resume, "benchmark": benchmark}
