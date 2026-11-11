"""Piège — campagne de démonstration prête à lancer (make demo).

Construit une configuration complète et **hors ligne** : mandat signé, cible de
démonstration « Guichet RH », catalogue chargé, fournisseur local déterministe.
Elle dépend des lots 1 (cible) et 2 (catalogue) : s'ils sont absents, elle le
dit explicitement au lieu de bricoler une cible approximative.
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import ErreurPiege
from piege.moteur.configuration import ConfigurationCampagne
from piege.securite import mandats as mandats_module
from piege.types import Environnement, Mandat, TypeCampagne

__all__ = ["campagne_de_demonstration", "mandat_de_demonstration",
           "application_de_demonstration", "TENANT_DEMO", "GRATUIT"]

TENANT_DEMO = "TEN-demo"
APPLICATION_DEMO = "APP-guichet-rh"
GRATUIT = "aucune donnée réelle : jeu 100 % synthétique (annexe E, ENF-07)"


def mandat_de_demonstration(techniques: Optional[list[str]] = None,
                            budget_appels: int = 288,
                            budget_jetons: int = 2_000_000) -> Mandat:
    """Mandat de démonstration signé, production interdite."""
    mandat = mandats_module.creer(
        tenant_id=TENANT_DEMO, application_id=APPLICATION_DEMO,
        perimetre_techniques=techniques or [],
        environnements=[Environnement.TEST],
        fenetre_debut="2026-01-01T00:00:00Z", fenetre_fin="2027-12-31T00:00:00Z",
        budget_appels=budget_appels, budget_jetons=budget_jetons,
        production_autorisee=False, contact_urgence="demo@piege.local",
        sequence=1)
    return mandats_module.signer(mandat)


def application_de_demonstration() -> dict:
    """Spécification de l'application de démonstration (exposition employés)."""
    return {"id": APPLICATION_DEMO, "tenant_id": TENANT_DEMO,
            "nom": "Guichet RH — cible de démonstration, vulnérabilités "
                   "intentionnelles",
            "type": "rag", "environnement": "test", "exposition": 2,
            "depot_document_autorise": True}


def campagne_de_demonstration(graine: int = 20261111,
                              cible_spec: Optional[dict] = None,
                              dossier_catalogue: str = "catalogue",
                              technique_ids: Optional[list[str]] = None,
                              parallelisme: int = 1) -> ConfigurationCampagne:
    """Configuration de la campagne de démonstration, prête à exécuter."""
    try:
        from piege.catalogue import charger_catalogue
    except ImportError as exc:
        raise ErreurPiege(
            "le catalogue (lot 2) est requis pour la démonstration",
            code="catalogue_indisponible",
            details={"regle": "demo.catalogue"}) from exc
    catalogue = charger_catalogue(dossier_catalogue)
    identifiants = technique_ids or _perimetre_demo(catalogue)
    spec = dict(cible_spec or {})
    spec.setdefault("type", "local")
    spec.setdefault("catalogue", dossier_catalogue)
    spec.setdefault("application", application_de_demonstration())
    return ConfigurationCampagne(
        mandat=mandat_de_demonstration(identifiants), application_id=APPLICATION_DEMO,
        tenant_id=TENANT_DEMO, type=TypeCampagne.COMPLETE, graine=graine,
        technique_ids=identifiants, parallelisme=parallelisme,
        cible_spec=spec, catalogue=catalogue)


def _perimetre_demo(catalogue: dict) -> list[str]:
    """Périmètre de démonstration : les trois moments clés de la vidéo (§25.2)."""
    prioritaires = ["A1", "C1", "F3", "G1"]
    retenues = [t for t in prioritaires if t in catalogue]
    return retenues or sorted(catalogue)[:4]
