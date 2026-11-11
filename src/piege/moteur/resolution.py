"""Piège — résolution des composants d'une campagne.

Tout ce que le moteur reçoit est résolu ici, une seule fois, avant la première
sonde : mandat (validé), cible, techniques, fournisseur, journal, entrepôt et
composants injectés. Les imports des autres lots sont **paresseux** : le moteur
tourne avec ce qui est mergé, et dit explicitement ce qui manque.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional

from piege.erreurs import ErreurPiege, TechniqueInconnue
from piege.moteur.configuration import ConfigurationCampagne
from piege.securite import mandats as mandats_module
from piege.securite.journal import Journal
from piege.types import (Application, Environnement, Famille, Mandat, Technique,
                         TypeApplication, depuis_dict)

__all__ = ["resoudre_entrepot", "resoudre_mandat", "resoudre_application",
           "resoudre_cible", "resoudre_techniques", "resoudre_fournisseur",
           "resoudre_journal", "resoudre_attaquant", "resoudre_juge",
           "resoudre_evaluateur"]

VAR_FOURNISSEUR = "PIEGE_FOURNISSEUR"
DOSSIER_CATALOGUE = "catalogue"


def resoudre_entrepot(config: ConfigurationCampagne) -> Any:
    """Entrepôt injecté, sinon l'entrepôt local par défaut."""
    if config.entrepot is not None:
        return config.entrepot
    from piege.stockage import creer_entrepot

    return creer_entrepot({"type": "local",
                           "dossier": os.environ.get("PIEGE_DONNEES",
                                                     "donnees-locales")})


def resoudre_mandat(config: ConfigurationCampagne, entrepot: Any,
                    maintenant: Optional[str] = None) -> Mandat:
    """Mandat fourni ou relu depuis l'entrepôt, puis **validé** (EF-04)."""
    mandat = config.mandat
    if mandat is None:
        if not config.mandat_id:
            raise ErreurPiege("aucun mandat fourni ni identifiant de mandat",
                              code="mandat_invalide",
                              details={"regle": "mandat.present"})
        brut = entrepot.lire("mandats", config.mandat_id)
        if not brut:
            raise ErreurPiege("mandat %s introuvable" % config.mandat_id,
                              code="mandat_invalide",
                              details={"regle": "mandat.present"})
        mandat = depuis_dict(Mandat, brut)
    return mandats_module.valider(mandat, maintenant)


def resoudre_application(config: ConfigurationCampagne, entrepot: Any,
                         mandat: Mandat) -> Application:
    """Application cible : fournie, relue, ou déduite du mandat."""
    if config.application is not None:
        return config.application
    identifiant = config.application_id or mandat.application_id
    brut = entrepot.lire("applications", identifiant, tenant_id=mandat.tenant_id)
    if brut:
        return depuis_dict(Application, brut)
    return Application(id=identifiant, tenant_id=mandat.tenant_id,
                       nom=identifiant, type=TypeApplication.RAG, acces="",
                       modele="", environnement=Environnement.TEST, exposition=2)


def resoudre_cible(config: ConfigurationCampagne, application: Application) -> Any:
    """Cible injectée, sinon construite depuis la spécification (lot 1)."""
    if config.cible is not None:
        return config.cible
    try:
        from piege.cibles import creer_cible
    except ImportError as exc:
        raise ErreurPiege(
            "aucune cible injectée et le lot 1 (piege.cibles) est absent",
            code="cible_indisponible",
            details={"regle": "moteur.cible"}) from exc
    spec = dict(config.cible_spec or {})
    spec.setdefault("application_id", application.id)
    spec.setdefault("corpus_ref", application.corpus_ref)
    return creer_cible(spec)


def resoudre_catalogue(config: ConfigurationCampagne) -> dict:
    """Catalogue injecté, sinon chargé depuis le dossier `catalogue/` (lot 2)."""
    if config.catalogue:
        return dict(config.catalogue)
    try:
        from piege.catalogue import charger_catalogue
    except ImportError as exc:
        raise ErreurPiege(
            "aucun catalogue injecté et le lot 2 (piege.catalogue) est absent",
            code="catalogue_indisponible",
            details={"regle": "moteur.catalogue"}) from exc
    dossier = (config.cible_spec or {}).get("catalogue", DOSSIER_CATALOGUE)
    return charger_catalogue(dossier)


def resoudre_techniques(config: ConfigurationCampagne) -> list[Technique]:
    """Techniques à exécuter : liste directe, identifiants ou familles."""
    if config.techniques:
        return list(config.techniques)
    catalogue = resoudre_catalogue(config)
    if config.technique_ids:
        manquantes = [t for t in config.technique_ids if t not in catalogue]
        if manquantes:
            raise TechniqueInconnue("technique(s) absente(s) du catalogue : %s"
                                    % ", ".join(manquantes),
                                    code="technique_inconnue",
                                    details={"regle": "catalogue.identifiant"})
        return [catalogue[t] for t in config.technique_ids]
    familles = {Famille(f) for f in (config.familles or [])}
    selection = [t for t in catalogue.values() if not familles or t.famille in familles]
    return sorted(selection, key=lambda t: t.id)


def resoudre_fournisseur(config: ConfigurationCampagne, juge: bool = False) -> Any:
    """Fournisseur de modèle : injecté, sinon créé (défaut `local`, hors ligne)."""
    if juge:
        if config.fournisseur_juge is not None:
            return config.fournisseur_juge
        if config.fournisseur is not None:
            return config.fournisseur
    elif config.fournisseur is not None:
        return config.fournisseur
    from piege.fournisseurs import creer_fournisseur

    return creer_fournisseur(os.environ.get(VAR_FOURNISSEUR, "local"))


def resoudre_journal(config: ConfigurationCampagne, entrepot: Any) -> Journal:
    """Journal chaîné, adossé à l'entrepôt quand il est disponible."""
    if config.journal is not None:
        return config.journal
    ecrire = getattr(entrepot, "ecrire_journal", None)
    return Journal(ecrire=ecrire)


def resoudre_attaquant(config: ConfigurationCampagne) -> Callable:
    """Agent attaquant : injecté, lot 4, sinon repli borné hors ligne."""
    if config.attaquant is not None:
        return config.attaquant
    try:
        from piege.agents.attaquant import executer

        return executer
    except ImportError:
        from piege.moteur.replis import attaquant_minimal

        return attaquant_minimal


def resoudre_juge(config: ConfigurationCampagne) -> Optional[Callable]:
    """Fonction de jugement : injectée, sinon celle du lot 5, sinon `None`."""
    if config.juge is not None:
        return config.juge
    try:
        from piege.agents.juge import juger

        return juger
    except ImportError:
        return None


def resoudre_evaluateur(config: ConfigurationCampagne) -> Callable:
    """Évaluateur de politique : injecté, sinon celui du lot 10."""
    if config.evaluateur is not None:
        return config.evaluateur
    from piege.securite.politique import exiger

    return exiger
