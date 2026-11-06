"""Modèle, étapes 1 à 3 : lecture, nettoyage, rapprochement et journal des anomalies."""
import csv
import json
import re
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from statistics import median

import openpyxl

RACINE = Path(__file__).resolve().parents[2]
DATA = RACINE / "data"

CATALOGUE = DATA / "catalogue_reference.csv"
MARCHE_LAGUNE = DATA / "marche_lagune.csv"
BAOBAB = DATA / "baobab_shop.json"
COMPTOIR = DATA / "comptoir_ivoire.xlsx"
HISTORIQUE = DATA / "historique_prix.csv"

ENSEIGNES = ["Marché Lagune", "Baobab Shop", "Comptoir Ivoire"]
SEUIL_ABERRANT = 3  # un prix est suspect s'il s'écarte de plus de ×3 de la médiane historique

class Journal:
    def __init__(self):
        self.entrees = []

    def ajouter(self, enseigne, reference, probleme, detail, traitement):
        self.entrees.append({"enseigne": enseigne, "reference": reference,
                             "probleme": probleme, "detail": detail, "traitement": traitement})


# ---------- Lecture ----------
def charger_catalogue():
    with open(CATALOGUE, encoding="utf-8", newline="") as f:
        return {r["produit_id"]: r for r in csv.DictReader(f)}


def charger_lagune():
    with open(MARCHE_LAGUNE, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    return [{
        "enseigne": "Marché Lagune", "ligne": i, "reference": r["reference"],
        "nom_brut": r["designation"], "prix_brut": r["prix"], "livraison": 0,
        "remise": 0, "dispo_brut": r["disponibilite"], "stock": None,
        "note": r["note_clients"], "vendeur": "Marché Lagune",
    } for i, r in enumerate(lignes, start=2)]


def charger_baobab():
    with open(BAOBAB, encoding="utf-8") as f:
        items = json.load(f)["items"]
    return [{
        "enseigne": "Baobab Shop", "ligne": i, "reference": it["sku"],
        "nom_brut": it["title"], "prix_brut": it["pricing"]["amount"],
        "livraison": it["pricing"].get("delivery_fee") or 0, "remise": 0,
        "dispo_brut": None, "stock": it["stock"], "note": it["rating"]["average"],
        "vendeur": it["seller"],
    } for i, it in enumerate(items, start=1)]


def charger_comptoir():
    ws = openpyxl.load_workbook(COMPTOIR, data_only=True).active
    sortie = []
    for i, ligne in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        if not ligne[0]:
            continue
        code, article, _rayon, prix, remise, quantite, _maj = ligne[:7]
        sortie.append({
            "enseigne": "Comptoir Ivoire", "ligne": i, "reference": code,
            "nom_brut": article, "prix_brut": prix, "livraison": 0,
            "remise": remise or 0, "dispo_brut": None, "stock": quantite,
            "note": None, "vendeur": "Comptoir Ivoire",
        })
    return sortie


def charger_tout():
    return charger_lagune() + charger_baobab() + charger_comptoir()


def charger_historique():
    with open(HISTORIQUE, encoding="utf-8", newline="") as f:
        return [{"date": r["date"], "source": r["source"], "produit_id": r["produit_id"],
                 "prix": int(r["prix_fcfa"])} for r in csv.DictReader(f)]


# ---------- Nettoyage ----------
def nettoyer_nom(texte):
    return re.sub(r"\s+", " ", str(texte or "")).strip()


def convertir_prix(valeur):
    """'102\u202f900 FCFA' -> 102900 ; 'Prix sur demande' ou vide -> None."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, (int, float)):
        return int(valeur)
    s = str(valeur).replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace("FCFA", "")
    return int(s) if s.isdigit() else None


def nettoyer(articles, journal):
    sortie, vus = [], {}
    for a in articles:
        e, ref = a["enseigne"], a["reference"]
        signature = (a["nom_brut"], a["prix_brut"], a["dispo_brut"], a["stock"], a["note"])
        if (e, ref) in vus:
            if vus[(e, ref)] == signature:
                journal.ajouter(e, ref, "doublon", f"ligne {a['ligne']}, identique", "ligne supprimée")
            else:
                journal.ajouter(e, ref, "doublon", f"ligne {a['ligne']}, contenu différent",
                                "première occurrence conservée, à vérifier")
            continue
        vus[(e, ref)] = signature

        a["nom"] = nettoyer_nom(a["nom_brut"])
        if a["nom"] != a["nom_brut"]:
            journal.ajouter(e, ref, "espaces parasites", repr(a["nom_brut"]), "espaces normalisés")
        if isinstance(a["prix_brut"], str) and a["prix_brut"]:
            journal.ajouter(e, ref, "prix en texte", repr(a["prix_brut"]), "converti en entier")

        a["prix_affiche"] = convertir_prix(a["prix_brut"])
        a["remise"] = float(a["remise"] or 0)
        rupture = a["dispo_brut"] == "Rupture" or a["stock"] == 0

        if a["prix_affiche"] is None:
            a["statut"] = "prix absent"
            journal.ajouter(e, ref, "prix non exploitable", repr(a["prix_brut"]),
                            "produit exclu des comparaisons")
        elif rupture:
            a["statut"] = "rupture"
            journal.ajouter(e, ref, "rupture", a["nom"], "non retenu comme « le moins cher »")
        else:
            a["statut"] = "ok"

        if a["vendeur"] != e:
            journal.ajouter(e, ref, "vendeur tiers", f"vendu par « {a['vendeur']} »",
                            "conservé, signalé (le prix n'est pas celui de l'enseigne)")
        sortie.append(a)
    return sortie


# ---------- Rapprochement ----------
CORRESPONDANCES = {
    "Marché Lagune": {
        "ML-1000": "P01", "ML-1007": "P02", "ML-1014": "P03", "ML-1021": "P04", "ML-1028": "P05",
        "ML-1035": "P06", "ML-1042": "P07", "ML-1049": "P08", "ML-1056": "P09", "ML-1063": "P10",
        "ML-1070": "P11", "ML-1077": "P12", "ML-1084": "P13", "ML-1091": "P14", "ML-1098": "P15",
        "ML-1105": "P16", "ML-1112": "P17", "ML-1119": "P19", "ML-1126": "P20", "ML-1133": "P21",
        "ML-1140": "P22", "ML-1147": "P23", "ML-1154": "P24", "ML-1161": "P25", "ML-1168": "P26",
        "ML-1175": "P27", "ML-1182": "P28", "ML-1189": "P30",
    },
    "Baobab Shop": {
        "BB01412": "P01", "BB02609": "P02", "BB03433": "P03", "BB04915": "P04", "BB05319": "P05",
        "BB06565": "P06", "BB07953": "P07", "BB09460": "P09", "BB10686": "P10", "BB11833": "P11",
        "BB12319": "P12", "BB14669": "P14", "BB15546": "P15", "BB16464": "P16", "BB17618": "P17",
        "BB18398": "P18", "BB19114": "P19", "BB20158": "P20", "BB22196": "P22", "BB23458": "P23",
        "BB24831": "P24", "BB26722": "P26", "BB27999": "P27", "BB28797": "P28", "BB29464": "P29",
        "BB30124": "P30",
    },
    "Comptoir Ivoire": {
        "CI200": "P01", "CI201": "P02", "CI202": "P04", "CI203": "P06", "CI204": "P08",
        "CI205": "P09", "CI206": "P11", "CI207": "P12", "CI208": "P13", "CI209": "P14",
        "CI210": "P15", "CI211": "P16", "CI212": "P20", "CI213": "P21", "CI214": "P22",
        "CI215": "P23", "CI216": "P24", "CI217": "P25", "CI218": "P26", "CI219": "P27",
        "CI220": "P28", "CI221": "P29",
    },
}


def verifier_libelle(a, produit, journal):
    """Contrôle de cohérence : la marque du catalogue doit apparaître dans le libellé."""
    marque = produit["marque"].lower()
    nom = a["nom"].lower()
    if marque in nom:
        return
    proches = get_close_matches(marque, re.findall(r"[\w\-]+", nom), n=1, cutoff=0.75)
    if proches:
        journal.ajouter(a["enseigne"], a["reference"], "libellé à corriger",
                        f"« {proches[0]} » au lieu de « {produit['marque']} »",
                        "faute probable, rapprochement conservé par référence")
    else:
        journal.ajouter(a["enseigne"], a["reference"], "marque absente du libellé", a["nom"],
                        "rapprochement conservé par référence")


def rapprocher(articles, catalogue, journal):
    retenus = []
    for a in articles:
        pid = CORRESPONDANCES[a["enseigne"]].get(a["reference"])
        if pid is None:
            journal.ajouter(a["enseigne"], a["reference"], "non rapproché", a["nom"], "article ignoré")
            continue
        a["produit_id"] = pid
        verifier_libelle(a, catalogue[pid], journal)
        retenus.append(a)
    return retenus


# ---------- Contrôles de prix et d'historique ----------
def medianes(historique):
    groupes = defaultdict(list)
    for h in historique:
        groupes[(h["produit_id"], h["source"])].append(h["prix"])
    return {cle: median(v) for cle, v in groupes.items()}


def controler_prix(articles, med, journal):
    """Un prix trop éloigné de la médiane historique est suspect : on l'écarte et on le signale."""
    for a in articles:
        if a["statut"] != "ok":
            continue
        m = med.get((a["produit_id"], a["enseigne"]))
        if m is None:
            continue
        p = a["prix_affiche"]
        if p > SEUIL_ABERRANT * m or p < m / SEUIL_ABERRANT:
            a["statut"] = "prix aberrant"
            journal.ajouter(a["enseigne"], a["reference"], "prix aberrant",
                            f"{p} FCFA, médiane historique {m:.0f} FCFA",
                            "produit exclu des comparaisons, à vérifier auprès de l'enseigne")


def controler_historique(historique, journal):
    doublons = len(historique) - len({(h["date"], h["source"], h["produit_id"]) for h in historique})
    produits = len({h["produit_id"] for h in historique})
    journal.ajouter("Historique", "-", "contrôle",
                    f"{len(historique)} lignes, {produits} produits, doublons={doublons}",
                    "aucun traitement nécessaire" if doublons == 0 else "doublons à traiter")
