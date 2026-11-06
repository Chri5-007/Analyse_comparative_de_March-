"""Point d'entrée : vérifie les dépendances, lance l'analyse, puis affiche et exporte les résultats."""
import importlib.util
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
REQUIREMENTS = RACINE / "requirements.txt"


def verifier_dependances():
    """Lit requirements.txt et installe les bibliothèques absentes de l'interpréteur courant."""
    if not REQUIREMENTS.exists():
        return
    manquants = []
    for ligne in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        nom = ligne.split(">")[0].split("=")[0].split("<")[0].strip()
        if importlib.util.find_spec(nom) is None:
            manquants.append(ligne)
    if manquants:
        print("Bibliothèques manquantes, installation en cours :", ", ".join(manquants))
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def main():
    verifier_dependances()

    from app.controllers.controleur import Controleur
    from app.views.affichage import afficher_console, ecrire_exports

    resultats = Controleur().run()
    ecrire_exports(resultats)
    afficher_console(resultats)


if __name__ == "__main__":
    main()
