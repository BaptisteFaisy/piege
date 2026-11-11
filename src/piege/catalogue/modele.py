"""Piège — modèle du catalogue : dictionnaire YAML vers `Technique`.

Une technique est une **donnée** (spécification §18.4) : ajouter une technique
au catalogue ne demande aucune modification de code (KPI-4, R18). En
contrepartie, le schéma est strict : un champ absent, un type faux ou une
énumération inconnue produisent une erreur explicite nommant le fichier et la
technique — jamais une valeur par défaut silencieuse.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from piege.catalogue.erreurs import TechniqueInvalide
from piege.types import (Environnement, Famille, ProductionAutorisee, Technique)

__all__ = ["CHAMPS_REQUIS", "vers_technique", "vers_techniques",
           "IDENTIFIANT_MOTIF"]

CHAMPS_REQUIS = ("id", "famille", "nom", "objectif", "environnement",
                 "production", "budget_appels", "tours_max", "sonde_initiale",
                 "juge")
IDENTIFIANT_MOTIF = r"^[A-H][0-9]{1,2}$"


def _exiger(condition: bool, message: str, identifiant: str, fichier: str,
            regle: str) -> None:
    """Lève `TechniqueInvalide` si la condition est fausse."""
    if not condition:
        raise TechniqueInvalide(message, technique_id=identifiant,
                                fichier=fichier, regle=regle)


def _texte(donnees: dict, champ: str, identifiant: str, fichier: str) -> str:
    """Champ texte requis, non vide."""
    valeur = donnees.get(champ)
    _exiger(isinstance(valeur, str) and valeur.strip(),
            "champ %r absent ou vide" % champ, identifiant, fichier,
            "catalogue.champ_requis")
    return valeur.strip()


def _entier(donnees: dict, champ: str, identifiant: str, fichier: str) -> int:
    """Champ entier requis, strictement positif."""
    valeur = donnees.get(champ)
    _exiger(isinstance(valeur, int) and not isinstance(valeur, bool) and valeur >= 1,
            "champ %r doit être un entier >= 1 (reçu %r)" % (champ, valeur),
            identifiant, fichier, "catalogue.champ_entier")
    return int(valeur)


def _liste(donnees: dict, champ: str, identifiant: str, fichier: str,
           obligatoire: bool = False) -> list:
    """Champ liste : absente → liste vide, présente → bien formée."""
    valeur = donnees.get(champ)
    if valeur is None:
        _exiger(not obligatoire, "champ %r absent" % champ, identifiant,
                fichier, "catalogue.champ_requis")
        return []
    _exiger(isinstance(valeur, list), "champ %r doit être une liste" % champ,
            identifiant, fichier, "catalogue.champ_liste")
    return list(valeur)


def _enumeration(valeur: Any, classe, champ: str, identifiant: str,
                 fichier: str):
    """Convertit une valeur en énumération, ou refuse explicitement."""
    try:
        return classe(str(valeur).strip().lower())
    except (ValueError, AttributeError) as exc:
        admises = [membre.value for membre in classe]
        raise TechniqueInvalide(
            "champ %r : %r n'est pas dans %s" % (champ, valeur, admises),
            technique_id=identifiant, fichier=fichier,
            regle="catalogue.enumeration") from exc


def _environnements(donnees: dict, identifiant: str, fichier: str) -> list:
    """Liste d'environnements, non vide."""
    bruts = _liste(donnees, "environnement", identifiant, fichier,
                   obligatoire=True)
    _exiger(bool(bruts), "champ 'environnement' vide", identifiant, fichier,
            "catalogue.champ_requis")
    return [_enumeration(v, Environnement, "environnement", identifiant, fichier)
            for v in bruts]


def _juge(donnees: dict, identifiant: str, fichier: str) -> str:
    """Bloc `juge` : le critère de succès observable est obligatoire."""
    bloc = donnees.get("juge")
    _exiger(isinstance(bloc, dict) and bool(str(bloc.get("reussi_si", "")).strip()),
            "bloc 'juge.reussi_si' absent ou vide", identifiant, fichier,
            "catalogue.juge")
    return str(bloc["reussi_si"]).strip()


def vers_technique(donnees: dict, fichier: str = "") -> Technique:
    """Convertit et valide une technique du catalogue."""
    _exiger(isinstance(donnees, dict), "une technique doit être une carte",
            "", fichier, "catalogue.schema")
    identifiant = str(donnees.get("id", "")).strip()
    _exiger(bool(re.match(IDENTIFIANT_MOTIF, identifiant)),
            "identifiant %r invalide (attendu lettre A-H + numéro)" % identifiant,
            identifiant, fichier, "catalogue.identifiant")
    for champ in CHAMPS_REQUIS:
        _exiger(champ in donnees and donnees[champ] is not None,
                "champ requis %r absent" % champ, identifiant, fichier,
                "catalogue.champ_requis")
    return Technique(
        id=identifiant,
        famille=_enumeration(donnees["famille"], Famille, "famille",
                             identifiant, fichier),
        nom=_texte(donnees, "nom", identifiant, fichier),
        objectif=_texte(donnees, "objectif", identifiant, fichier),
        preconditions=[str(p) for p in
                       _liste(donnees, "preconditions", identifiant, fichier)],
        environnement=_environnements(donnees, identifiant, fichier),
        production=_enumeration(donnees["production"], ProductionAutorisee,
                                "production", identifiant, fichier),
        budget_appels=_entier(donnees, "budget_appels", identifiant, fichier),
        tours_max=_entier(donnees, "tours_max", identifiant, fichier),
        sonde_initiale=_texte(donnees, "sonde_initiale", identifiant, fichier),
        mesures=[str(m) for m in
                 _liste(donnees, "mesures", identifiant, fichier)] or ["verdict"],
        juge_reussi_si=_juge(donnees, identifiant, fichier),
        correctifs_suggeres=[str(c) for c in _liste(
            donnees, "correctifs_suggeres", identifiant, fichier)],
        gabarit_document=str(donnees.get("gabarit_document") or ""),
        deterministe=bool(donnees.get("deterministe", True)),
        variantes=_variantes(donnees, identifiant, fichier))


def _variantes(donnees: dict, identifiant: str, fichier: str) -> list:
    """Variantes de sonde : liste de cartes nommées, toutes valides."""
    brutes = _liste(donnees, "variantes", identifiant, fichier)
    propres = []
    for index, variante in enumerate(brutes):
        _exiger(isinstance(variante, dict) and variante.get("nom")
                and variante.get("sonde"),
                "variante %d : 'nom' et 'sonde' requis" % index, identifiant,
                fichier, "catalogue.variante")
        propres.append({"nom": str(variante["nom"]).strip(),
                        "sonde": str(variante["sonde"]).strip()})
    return propres


def vers_techniques(document: Any, fichier: str = "") -> Iterable[Technique]:
    """Convertit un document de catalogue (`techniques:` ou liste directe)."""
    if isinstance(document, dict):
        brutes = document.get("techniques")
        _exiger(isinstance(brutes, list) and bool(brutes),
                "clé 'techniques' absente ou vide", "", fichier,
                "catalogue.schema")
    elif isinstance(document, list):
        brutes = document
    else:
        raise TechniqueInvalide("document de catalogue illisible", fichier=fichier,
                                regle="catalogue.schema")
    return [vers_technique(brute, fichier) for brute in brutes]
