"""Piège — accord humain explicite avant toute application (EF-42, R10).

Un correctif n'est appliqué que si une personne habilitée l'a autorisé. La
vérification passe par la **politique de périmètre** du lot 10, pas par un test
local : c'est la passerelle qui décide, et son refus est journalisé avec la
règle violée. C'est ce qui rend l'engagement opposable devant un RSSI.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.erreurs import AutorisationHumaineAbsente, ErreurPiege
from piege.securite.politique import OUTIL_GARDE_APPLIQUE, evaluer, lever_refus
from piege.types import (Correctif, StatutCorrectif, TypeCorrectif,
                         maintenant_utc)

__all__ = ["autoriser", "refuser", "est_autorise", "TYPES_APPLICABLES"]

TYPES_APPLICABLES = (TypeCorrectif.GARDE_FOU, TypeCorrectif.POLITIQUE)


def est_autorise(correctif: Correctif) -> bool:
    """Un correctif est autorisé s'il porte le statut et un auteur identifié."""
    return (correctif.statut is StatutCorrectif.AUTORISE
            and bool(correctif.autorise_par) and bool(correctif.autorise_le))


def autoriser(correctif: Correctif, auteur: str, role: str,
              journal: Optional[Any] = None) -> Correctif:
    """Enregistre l'accord humain explicite, après contrôle par la politique.

    `auteur` est l'identité de la personne (imputabilité) et `role` son rôle
    dans le dispositif (habilitation) : seuls `commanditaire` et `analyste`
    peuvent autoriser un correctif.
    """
    if not auteur or not role:
        raise AutorisationHumaineAbsente(
            "un accord humain est nominatif : auteur et rôle requis",
            code="autorisation_absente", details={"regle": "correctif.auteur"})
    decision = evaluer(OUTIL_GARDE_APPLIQUE, {
        "mandat_statut": "valide",
        "correctif_autorisation_humaine": True,
        "correctif_autorise_par": role,
        "correctif_type": getattr(correctif.type, "value", correctif.type),
    })
    if journal is not None:
        journal.consigner(auteur, "accord_correctif", correctif.tenant_id,
                          {"correctif": correctif.id, "role": role,
                           "type": getattr(correctif.type, "value", ""),
                           "accorde": decision.accorde, "regle": decision.regle})
    lever_refus(decision)
    correctif.statut = StatutCorrectif.AUTORISE
    correctif.autorise_par = auteur
    correctif.autorise_le = maintenant_utc()
    return correctif


def refuser(correctif: Correctif, auteur: str, motif: str = "") -> Correctif:
    """Refus humain d'un correctif : tracé, jamais silencieux."""
    if not auteur:
        raise ErreurPiege("un refus humain est nominatif",
                          code="autorisation_absente",
                          details={"regle": "correctif.auteur"})
    correctif.statut = StatutCorrectif.REFUSE
    correctif.autorise_par = auteur
    correctif.autorise_le = maintenant_utc()
    if motif:
        correctif.effet_de_bord = "refus : %s" % motif
    return correctif


def exiger_autorisation(correctif: Correctif) -> None:
    """Garde d'entrée de l'application : refuse sans accord humain valable."""
    if not est_autorise(correctif):
        raise AutorisationHumaineAbsente(
            "correctif %s non autorisé par une personne habilitée : "
            "application refusée" % correctif.id, code="autorisation_absente",
            details={"regle": "correctif.autorisation"})
    if correctif.type not in TYPES_APPLICABLES:
        raise ErreurPiege(
            "le service n'applique que les garde-fous et les politiques ; le "
            "correctif %s (%s) reste à la main du client"
            % (correctif.id, getattr(correctif.type, "value", correctif.type)),
            code="correctif_non_applicable",
            details={"regle": "correctif.type"})
