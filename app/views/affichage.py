"""Vue : affichage console et écriture des fichiers dans exports/. Ne calcule rien."""
import csv
from datetime import datetime
from pathlib import Path

from app.models.chargement import ENSEIGNES

EXPORTS = Path(__file__).resolve().parents[2] / "exports"


def _ecrire_csv(dossiers, nom, lignes, colonnes):
    for dossier in dossiers:
        dossier.mkdir(parents=True, exist_ok=True)
        with open(dossier / nom, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
            w.writeheader()
            w.writerows(lignes)


def _ecrire_texte(dossiers, nom, texte):
    for dossier in dossiers:
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / nom).write_text(texte + "\n", encoding="utf-8")


def rediger_synthese(res):
    out = [f"Produits comparables (dans au moins 2 enseignes) : {len(res['lignes'])}", "",
           "Nombre de fois où l'enseigne est la moins chère :"]
    out += [f"  {e} : {res['gagnes'].get(e, 0)}" for e in ENSEIGNES]
    out += ["", "Écart moyen par rapport au prix le plus bas :"]
    out += [f"  {e} : {res['moyens'][e] if res['moyens'][e] is not None else 'n/a'} %" for e in ENSEIGNES]
    out += ["", "Les trois produits où comparer rapporte le plus :"]
    out += [f"  {l['produit']} : écart de {l['ecart_fcfa']} FCFA ({l['ecart_pct']} %), "
            f"moins chère chez {l['moins_chere']}" for l in res["top3"]]
    return "\n".join(out)


def rediger_panier(p):
    out = ["Panier de rentrée", "", "Total dans une seule enseigne :"]
    for e in ENSEIGNES:
        if p["complets"][e]:
            out.append(f"  {e} : {p['totaux'][e]} FCFA (panier complet)")
        else:
            out.append(f"  {e} : {p['totaux'][e]} FCFA, incomplet, manque : {', '.join(p['manquants'][e])}")
    out += ["", f"Achat optimisé (chaque article là où il est le moins cher) : {p['meilleur_total']} FCFA"]
    out += [f"  {d['quantite']} × {d['produit']} : {d['enseigne_min']} à {d['prix_unitaire']} FCFA"
            for d in p["detail"]]
    if p["non_dispo"]:
        out.append(f"Articles introuvables dans les trois enseignes : {', '.join(p['non_dispo'])}")
    return "\n".join(out)


def rediger_black_friday(resume):
    return ("Black Friday (24–30/11/2025) contre moyenne annuelle, écart moyen par enseigne :\n"
            + "\n".join(f"  {e} : {resume[e]} %" for e in ENSEIGNES))


def rediger_complexite(r):
    return (
        "Mesure de complexité\n"
        f"Lignes d'historique : {r['lignes']}\n"
        f"Requêtes (produit × enseigne) : {r['requetes']}\n"
        f"Recherche naïve (parcours complet de la liste à chaque requête) : {r['t_naive'] * 1000:.1f} ms\n"
        f"Index dict : construction {r['t_build'] * 1000:.1f} ms, interrogations {r['t_lookup'] * 1000:.2f} ms\n"
        f"Résultats identiques : {'oui' if r['concordant'] else 'non'}\n\n"
        "Explication : la recherche naïve coûte O(n) par requête, soit O(n×m) pour m requêtes. "
        "L'index est construit une seule fois en O(n), puis chaque requête se fait en O(1) en moyenne, "
        "soit O(n+m) au total."
    )


def ecrire_exports(res):
    """Écrit les résultats dans exports/ (version courante) et dans un sous-dossier daté (archive)."""
    horodatage = datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
    dossiers = [EXPORTS, EXPORTS / "archives" / horodatage]

    colonnes = ["produit_id", "produit", "categorie", *ENSEIGNES,
                "moins_chere", "prix_min", "ecart_fcfa", "ecart_pct", "nb_enseignes"]
    lignes = [{**{k: l[k] for k in ("produit_id", "produit", "categorie", "moins_chere",
                                    "prix_min", "ecart_fcfa", "ecart_pct", "nb_enseignes")},
               **{e: l["prix"].get(e, "") for e in ENSEIGNES}} for l in res["lignes"]]
    _ecrire_csv(dossiers, "comparatif.csv", lignes, colonnes)
    _ecrire_csv(dossiers, "panier.csv", res["panier"]["detail"],
                ["produit_id", "produit", "quantite", "enseigne_min", "prix_unitaire", "sous_total"])
    _ecrire_csv(dossiers, "historique_black_friday.csv", res["bf_detail"],
                ["enseigne", "produit_id", "moyenne_semaine", "moyenne_annee", "ecart_pct"])
    _ecrire_csv(dossiers, "journal_nettoyage.csv", res["journal"],
                ["boutique", "type", "element", "detail"])
    _ecrire_texte(dossiers, "synthese.txt", "\n\n".join([rediger_synthese(res), rediger_panier(res["panier"]),
                                            rediger_black_friday(res["bf_resume"])]))
    _ecrire_texte(dossiers, "complexite.txt", rediger_complexite(res["benchmark"]))


def afficher_console(res):
    print(f"Journal : {len(res['journal'])} entrées")
    print(f"Produits comparables : {len(res['lignes'])} | non comparables : "
          f"{[n[0] for n in res['non_comparables']]}")
    print()
    print(rediger_synthese(res))
    print()
    print(rediger_panier(res["panier"]))
    print()
    print(rediger_black_friday(res["bf_resume"]))
    print()
    print(rediger_complexite(res["benchmark"]))