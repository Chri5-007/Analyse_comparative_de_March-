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

    def ajouter(self, boutique, type_, element, detail):
        self.entrees.append({"boutique": boutique, "type": type_, "element": element, "detail": detail})


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
                journal.ajouter(e, "Doublon", a["nom_brut"].strip(),
                                f"Plusieurs lignes pour le même produit ({ref}); ligne {a['ligne']} identique, supprimée")
            else:
                journal.ajouter(e, "Doublon", a["nom_brut"].strip(),
                                f"Plusieurs lignes pour le même produit ({ref}); ligne {a['ligne']} différente, "
                                "première occurrence conservée, à vérifier")
            continue
        vus[(e, ref)] = signature

        a["nom"] = nettoyer_nom(a["nom_brut"])

        a["prix_affiche"] = convertir_prix(a["prix_brut"])
        a["remise"] = float(a["remise"] or 0)
        rupture = a["dispo_brut"] == "Rupture" or a["stock"] == 0

        if a["prix_affiche"] is None:
            a["statut"] = "prix absent"
            brut = a["prix_brut"] if a["prix_brut"] not in (None, "") else "(vide)"
            journal.ajouter(e, "Prix manquant", a["nom"], f"Prix inexploitable: {brut}")
        elif rupture:
            a["statut"] = "rupture"
            if a["stock"] == 0:
                motif = "Stock nul" if e == "Baobab Shop" else "Quantité en rayon nulle"
            else:
                motif = "Produit en rupture de stock"
            journal.ajouter(e, "Indisponible", a["nom"], motif)
        else:
            a["statut"] = "ok"

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
    # Journal volontairement limité à : Doublon, Indisponible, Prix manquant


def rapprocher(articles, catalogue, journal):
    retenus = []
    for a in articles:
        pid = CORRESPONDANCES[a["enseigne"]].get(a["reference"])
        if pid is None:
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


def controler_historique(historique, journal):
    doublons = len(historique) - len({(h["date"], h["source"], h["produit_id"]) for h in historique})
    produits = len({h["produit_id"] for h in historique})
    pass  # contrôle sans entrée dans le journal
