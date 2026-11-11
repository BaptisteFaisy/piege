"""Piège — application d'un correctif de garde-fou ou de politique.

Seuls les garde-fous et les politiques sont appliqués par le service
(EF-42, spécification §15) : l'invite système, le code applicatif et le corpus
du client ne sont **jamais** modifiés par Piège. Le refuser explicitement fait
partie de la crédibilité du produit.

L'application passe par la cible, qui expose `ajouter_garde_fou` (variante
locale et Bedrock) ; à défaut, le correctif est enregistré dans un journal
d'application que le client peut rejouer sur sa configuration réelle.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.correctifs.autorisation import exiger_autorisation
from piege.types import Correctif, StatutCorrectif, TypeCorrectif, maintenant_utc

__all__ = ["appliquer", "annuler", "est_applique", "THEME_DEPUIS_CONTENU"]

# Motif du contenu → thème de garde-fou à activer sur la cible de démonstration.
THEME_DEPUIS_CONTENU = (
    ("rémunération", "remuneration"),
    ("remuneration", "remuneration"),
    ("grille", "remuneration"),
    ("données personnelles", "donnees_personnelles"),
    ("donnees personnelles", "donnees_personnelles"),
    ("secret", "secrets"),
    ("invite", "invite_systeme"),
    ("invité", "invite_systeme"),
    ("finalité", "finalite"),
    ("finalite", "finalite"),
)


def est_applique(correctif: Correctif) -> bool:
    """Un correctif est appliqué s'il porte le statut et la date d'application."""
    return (correctif.statut in (StatutCorrectif.APPLIQUE, StatutCorrectif.REJOUE)
            and bool(correctif.applique_le))


def theme_du_correctif(correctif: Correctif) -> str:
    """Thème de garde-fou déduit du contenu proposé (cible de démonstration)."""
    contenu = (correctif.contenu or "").lower()
    for motif, theme in THEME_DEPUIS_CONTENU:
        if motif in contenu:
            return theme
    if correctif.type is TypeCorrectif.POLITIQUE:
        return "politique"
    return "injection"


def appliquer(correctif: Correctif, cible: Any, mandat: Any = None,
              journal: Optional[Any] = None) -> Correctif:
    """Applique un correctif autorisé sur la cible, puis le marque appliqué."""
    exiger_autorisation(correctif)
    del mandat                                # le périmètre est déjà vérifié
    theme = theme_du_correctif(correctif)
    _appliquer_sur_cible(correctif, cible, theme)
    correctif.statut = StatutCorrectif.APPLIQUE
    correctif.applique_le = maintenant_utc()
    if journal is not None:
        journal.consigner("correctifs", "application", correctif.tenant_id,
                          {"correctif": correctif.id,
                           "type": getattr(correctif.type, "value", ""),
                           "theme": theme})
    return correctif


def _appliquer_sur_cible(correctif: Correctif, cible: Any, theme: str) -> None:
    """Délègue à la cible ; repli sur un attribut de configuration."""
    if hasattr(cible, "ajouter_garde_fou"):
        cible.ajouter_garde_fou(theme)
        return
    garde_fous = getattr(cible, "garde_fous", None)
    if isinstance(garde_fous, list) and theme not in garde_fous:
        garde_fous.append(theme)
        return
    if hasattr(cible, "configurer_garde_fou"):
        cible.configurer_garde_fou(theme, correctif.contenu)
        return
    raise NotImplementedError(
        "la cible %s n'expose aucun moyen d'appliquer un garde-fou"
        % type(cible).__name__)


def annuler(correctif: Correctif, cible: Any,
            journal: Optional[Any] = None) -> Correctif:
    """Retire un garde-fou appliqué (retour arrière, effet de bord constaté)."""
    theme = theme_du_correctif(correctif)
    if hasattr(cible, "retirer_garde_fou"):
        cible.retirer_garde_fou(theme)
    else:
        garde_fous = getattr(cible, "garde_fous", None)
        if isinstance(garde_fous, list) and theme in garde_fous:
            garde_fous.remove(theme)
    correctif.statut = StatutCorrectif.REFUSE
    correctif.effet_de_bord = "garde-fou retiré le %s" % maintenant_utc()
    if journal is not None:
        journal.consigner("correctifs", "annulation", correctif.tenant_id,
                          {"correctif": correctif.id, "theme": theme})
    return correctif
