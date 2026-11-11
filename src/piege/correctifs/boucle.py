"""Piège — la boucle de correction complète (spécification §15).

    découverte → correctif proposé (effort + réduction de risque)
               → accord humain explicite
               → application (garde-fou ou politique uniquement)
               → rejeu de l'attaque d'origine
               → preuve de fermeture, datée
               → contrôle de régression sur les découvertes déjà fermées
               → contrôle d'effet de bord sur les faux refus

Chaque étape est tracée et chaque échec est explicite : une boucle qui échoue ne
laisse jamais une découverte marquée « fermée » sans preuve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from piege.correctifs import application as application_module
from piege.correctifs import autorisation
from piege.correctifs import controles
from piege.correctifs import proposition
from piege.correctifs import rejeu
from piege.types import Correctif, Execution, Finding, Preuve, Technique

__all__ = ["BilanCorrection", "boucle_complete", "choisir_correctif"]


@dataclass
class BilanCorrection:
    """Résultat d'une boucle de correction, prêt pour le rapport."""

    finding_id: str
    propositions: list = field(default_factory=list)
    correctif: Optional[Correctif] = None
    autorise: bool = False
    applique: bool = False
    execution: Optional[Execution] = None
    preuve: Optional[Preuve] = None
    ferme: bool = False
    regressions: list = field(default_factory=list)
    effet_de_bord: dict = field(default_factory=dict)
    ligne: str = ""
    motifs: list = field(default_factory=list)


def choisir_correctif(propositions: list[Correctif],
                      preferer_applicable: bool = True) -> Optional[Correctif]:
    """Choisit le correctif à appliquer : le plus réducteur que le service peut poser."""
    if not propositions:
        return None
    if preferer_applicable:
        candidates = proposition.applicables(propositions)
        if candidates:
            return candidates[0]
    return propositions[0]


def boucle_complete(finding: Finding, cible: Any, mandat: Any, graine: int,
                    auteur: str, role: str, technique: Optional[Technique] = None,
                    catalogue: Optional[dict] = None, journal: Optional[Any] = None,
                    entrepot: Optional[Any] = None, fournisseur: Any = None,
                    juge: Optional[Any] = None, faux_refus_avant: Optional[list] = None,
                    faux_refus_apres: Optional[list] = None,
                    propositions: Optional[list] = None) -> BilanCorrection:
    """Enchaîne proposition, accord, application, rejeu et contrôles."""
    bilan = BilanCorrection(finding_id=finding.id)
    bilan.propositions = propositions or proposition.proposer(finding,
                                                                catalogue=catalogue)
    correctif = choisir_correctif(bilan.propositions)
    if correctif is None:
        bilan.motifs.append("aucun correctif proposé")
        return bilan
    bilan.correctif = correctif
    _autoriser(bilan, correctif, auteur, role, journal)
    if not bilan.autorise:
        return bilan
    _appliquer(bilan, correctif, cible, journal)
    if not bilan.applique:
        return bilan
    _rejouer(bilan, finding, cible, mandat, graine, technique, catalogue,
             journal, entrepot, fournisseur, juge)
    _controler(bilan, faux_refus_avant, faux_refus_apres)
    bilan.ligne = controles.fermeture_complete(finding, bilan.execution,
                                               bilan.effet_de_bord,
                                               bilan.regressions)
    return bilan


def _autoriser(bilan: BilanCorrection, correctif: Correctif, auteur: str,
               role: str, journal: Optional[Any]) -> None:
    """Accord humain ; un refus est un résultat, pas une exception silencieuse."""
    from piege.erreurs import ErreurPiege

    try:
        autorisation.autoriser(correctif, auteur, role, journal)
        bilan.autorise = True
    except ErreurPiege as erreur:
        bilan.autorise = False
        bilan.motifs.append("autorisation refusée : %s" % erreur.message)


def _appliquer(bilan: BilanCorrection, correctif: Correctif, cible: Any,
               journal: Optional[Any]) -> None:
    """Application sur la cible ; tout échec est explicité."""
    from piege.erreurs import ErreurPiege

    try:
        application_module.appliquer(correctif, cible, journal=journal)
        bilan.applique = True
    except (ErreurPiege, NotImplementedError) as erreur:
        bilan.applique = False
        bilan.motifs.append("application impossible : %s" % erreur)


def _rejouer(bilan: BilanCorrection, finding: Finding, cible: Any, mandat: Any,
             graine: int, technique: Optional[Technique], catalogue: Optional[dict],
             journal: Optional[Any], entrepot: Optional[Any], fournisseur: Any,
             juge: Optional[Any]) -> None:
    """Rejeu de l'attaque d'origine et fermeture si elle échoue."""
    execution, preuve = rejeu.rejouer(finding, cible, mandat, graine,
                                      technique=technique, catalogue=catalogue,
                                      fournisseur=fournisseur, juge=juge,
                                      journal=journal, entrepot=entrepot)
    bilan.execution = execution
    bilan.preuve = preuve
    rejeu.fermer(finding, preuve, execution, bilan.correctif)
    bilan.ferme = finding.statut.value == "ferme"
    if not bilan.ferme:
        bilan.motifs.append("rejeu encore réussi : correctif insuffisant")


def _controler(bilan: BilanCorrection, avant: Optional[list],
               apres: Optional[list]) -> None:
    """Contrôle d'effet de bord, sur le même corpus avant/après."""
    if avant is None or apres is None:
        return
    comparaison = controles.controler_effet_de_bord(avant, apres)
    bilan.effet_de_bord = comparaison
    if bilan.correctif is not None:
        bilan.correctif.effet_de_bord = controles.phrase_effet_de_bord(comparaison)
