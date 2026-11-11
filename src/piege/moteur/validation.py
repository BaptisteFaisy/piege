"""Piège — validation de périmètre à froid (commande `piege validation`).

Répond à la question du commanditaire avant toute exécution : « qu'est-ce que
ce mandat m'autorise à tester, et qu'est-ce qui sera refusé ? » (EF-02, EF-05).
Aucune sonde n'est envoyée : la politique est évaluée sur des faits.
"""

from __future__ import annotations

from typing import Optional

from piege.moteur import resolution
from piege.moteur.configuration import ConfigurationCampagne
from piege.securite import mandats as mandats_module
from piege.securite.politique import evaluer, faits_pour
from piege.types import Campagne, StatutCampagne, TypeCampagne, depuis_dict, Mandat


def valider_perimetre(mandat_id: str, technique_id: str = "",
                      dossier: str = "donnees-locales") -> dict:
    """Vérifie le mandat et, pour chaque technique, ce qui est autorisé."""
    from piege.stockage import creer_entrepot

    entrepot = creer_entrepot({"type": "local", "dossier": dossier})
    mandat = _lire_mandat(entrepot, mandat_id, dossier)
    application = resolution.resoudre_application(
        ConfigurationCampagne(mandat=mandat, application_id=mandat.application_id),
        entrepot, mandat)
    catalogue = _catalogue_ou_vide()
    campagnes = _campagne_vierge(mandat)
    lignes, autorisees = [], []
    for technique in _techniques_a_verifier(catalogue, technique_id):
        decision = _decision(mandat, technique, application, campagnes)
        lignes.append(_formater(technique.id, decision))
        if decision.accorde:
            autorisees.append(technique.id)
    return {"mandat": mandat.id, "statut_mandat": mandat.statut.value,
            "autorise": bool(autorisees), "techniques_autorisees": autorisees,
            "lignes": lignes}


def _lire_mandat(entrepot, mandat_id: str, dossier: str) -> Mandat:
    """Relit et valide un mandat depuis l'entrepôt."""
    brut = entrepot.lire("mandats", mandat_id)
    if not brut:
        from piege.erreurs import ErreurPiege

        raise ErreurPiege("mandat %s introuvable dans %s" % (mandat_id, dossier),
                          code="mandat_invalide",
                          details={"regle": "mandat.present"})
    return mandats_module.valider(depuis_dict(Mandat, brut))


def _catalogue_ou_vide() -> dict:
    """Catalogue si le lot 2 est mergé, dictionnaire vide sinon."""
    try:
        from piege.catalogue import charger_catalogue

        return charger_catalogue("catalogue")
    except (ImportError, FileNotFoundError):
        return {}


def _campagne_vierge(mandat: Mandat) -> Campagne:
    """Campagne fictive servant de support aux faits de politique."""
    return Campagne(id="CMP-VALIDATION", mandat_id=mandat.id,
                    application_id=mandat.application_id,
                    tenant_id=mandat.tenant_id, type=TypeCampagne.COMPLETE,
                    graine=0, statut=StatutCampagne.PLANIFIEE)


def _techniques_a_verifier(catalogue: dict, technique_id: str) -> list:
    """Une technique précise, ou tout le périmètre du mandat."""
    if technique_id:
        return [catalogue[technique_id]] if technique_id in catalogue else []
    return [catalogue[t] for t in sorted(catalogue)]


def _decision(mandat: Mandat, technique, application, campagne: Campagne):
    """Évalue la politique pour un couple mandat/technique."""
    faits = faits_pour(mandat, technique, application, campagne)
    return evaluer("Cible___sonde", faits)


def _formater(technique_id: str, decision) -> str:
    """Ligne lisible du rapport de validation."""
    if decision.accorde:
        return "%-5s AUTORISÉ" % technique_id
    return "%-5s REFUSÉ  [%s] %s" % (technique_id, decision.regle, decision.motif)


def perimetre_techniques(mandat: Mandat, catalogue: Optional[dict] = None) -> list:
    """Techniques applicables d'un mandat (EF-02), triées par identifiant."""
    catalogue = catalogue if catalogue is not None else _catalogue_ou_vide()
    return sorted(t for t in mandat.perimetre_techniques if t in catalogue)
