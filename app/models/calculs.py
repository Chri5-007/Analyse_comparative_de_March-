"""Modèle, étapes 4 à 7 : comparatif, synthèse, panier et analyse du Black Friday."""
from collections import Counter, defaultdict

from app.models.chargement import ENSEIGNES

BLACK_FRIDAY = ("2025-11-24", "2025-11-30")
PANIER = {"P04": 1, "P12": 1, "P14": 2, "P15": 1, "P28": 1}


def prix_paye(a):
    """Prix réellement payé par le client, selon le mode de vente de l'enseigne."""
    if a["statut"] != "ok":
        return None
    prix = a["prix_affiche"]
    if a["enseigne"] == "Baobab Shop":
        prix += a["livraison"]                        # amount + delivery_fee
    if a["enseigne"] == "Comptoir Ivoire":
        prix = round(prix * (1 - a["remise"] / 100))  # prix catalogue - remise
    return prix


def prix_par_produit(articles):
    par = {}
    for a in articles:
        p = prix_paye(a)
        if p is not None:
            par.setdefault(a["produit_id"], {})[a["enseigne"]] = p
    return par


def construire_comparatif(par_produit, catalogue):
    lignes, non_comparables = [], []
    for pid in sorted(catalogue):
        prix = par_produit.get(pid, {})
        if len(prix) < 2:
            non_comparables.append((pid, catalogue[pid]["nom"], len(prix)))
            continue
        moins_chere = min(prix, key=prix.get)
        bas, haut = prix[moins_chere], max(prix.values())
        lignes.append({
            "produit_id": pid, "produit": catalogue[pid]["nom"],
            "categorie": catalogue[pid]["categorie"], "prix": prix,
            "moins_chere": moins_chere, "prix_min": bas,
            "ecart_fcfa": haut - bas, "ecart_pct": round((haut - bas) / bas * 100, 1),
            "nb_enseignes": len(prix),
        })
    return lignes, non_comparables


def synthese(lignes):
    gagnes = Counter(l["moins_chere"] for l in lignes)
    ecarts = {e: [] for e in ENSEIGNES}
    for l in lignes:
        for e, p in l["prix"].items():
            ecarts[e].append((p - l["prix_min"]) / l["prix_min"] * 100)
    moyens = {e: (round(sum(v) / len(v), 1) if v else None) for e, v in ecarts.items()}
    top3 = sorted(lignes, key=lambda l: l["ecart_pct"], reverse=True)[:3]
    return gagnes, moyens, top3


def calculer_panier(par_produit, catalogue):
    totaux = {e: 0 for e in ENSEIGNES}
    manquants = {e: [] for e in ENSEIGNES}
    detail, non_dispo, meilleur_total = [], [], 0
    for pid, qte in PANIER.items():
        prix = par_produit.get(pid, {})
        nom = catalogue[pid]["nom"]
        for e in ENSEIGNES:
            if e in prix:
                totaux[e] += prix[e] * qte
            else:
                manquants[e].append(nom)
        if prix:
            e_min = min(prix, key=prix.get)
            meilleur_total += prix[e_min] * qte
            detail.append({"produit_id": pid, "produit": nom, "quantite": qte,
                           "enseigne_min": e_min, "prix_unitaire": prix[e_min],
                           "sous_total": prix[e_min] * qte})
        else:
            non_dispo.append(nom)
    return {"totaux": totaux, "complets": {e: not manquants[e] for e in ENSEIGNES},
            "manquants": manquants, "detail": detail,
            "meilleur_total": meilleur_total, "non_dispo": non_dispo}


def analyse_black_friday(historique):
    debut, fin = BLACK_FRIDAY
    groupes = defaultdict(lambda: {"semaine": [], "annee": []})
    for h in historique:
        g = groupes[(h["source"], h["produit_id"])]
        g["annee"].append(h["prix"])
        if debut <= h["date"] <= fin:
            g["semaine"].append(h["prix"])
    detail = []
    for (source, pid), g in sorted(groupes.items()):
        if not g["semaine"]:
            continue
        m_sem = sum(g["semaine"]) / len(g["semaine"])
        m_an = sum(g["annee"]) / len(g["annee"])
        detail.append({"enseigne": source, "produit_id": pid, "moyenne_semaine": round(m_sem),
                       "moyenne_annee": round(m_an), "ecart_pct": round((m_sem - m_an) / m_an * 100, 1)})
    resume = {}
    for e in ENSEIGNES:
        ecarts = [d["ecart_pct"] for d in detail if d["enseigne"] == e]
        resume[e] = round(sum(ecarts) / len(ecarts), 1) if ecarts else None
    return detail, resume
