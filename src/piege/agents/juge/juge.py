"""Piège — appel du juge : une transcription, un verdict structuré.

Le juge n'a aucun outil : il ne reçoit que la transcription et la consigne
fixe. La température est nulle et la sortie structurée est imposée par
`piege.agents.juge.schema`.
"""

from __future__ import annotations

from typing import Optional

from piege.agents.juge import prompts, schema
from piege.erreurs import FournisseurIndisponible
from piege.types import Technique, Verdict

__all__ = ["juger", "sortie_brute"]


def sortie_brute(technique: Technique, transcription: str, fournisseur,
                 graine: int, second: bool = False) -> dict:
    """Interroge le fournisseur et valide sa sortie (un seul essai ici)."""
    if fournisseur is None:
        raise FournisseurIndisponible(
            "aucun fournisseur de modèle pour le juge",
            code="fournisseur_indisponible", details={"regle": "juge.fournisseur"})
    messages = prompts.construire(technique, transcription, second_passage=second)
    return schema.valider_sortie(
        fournisseur.sortie_structuree(messages, schema.SCHEMA, graine))


def juger(technique: Technique, transcription: str, fournisseur, graine: int,
          modele: str = "", essai_max: int = 2) -> Verdict:
    """Rend le verdict structuré d'une tentative (EF-20, EF-21).

    En cas de sortie invalide, un second essai est tenté avec la même graine
    (le fournisseur peut avoir tronqué sa réponse) ; au second échec l'erreur
    remonte : c'est l'appelant qui décide du repli hors ligne ou de la revue
    humaine. Aucune valeur par défaut silencieuse.
    """
    derniere: Optional[Exception] = None
    for essai in range(1, essai_max + 1):
        try:
            donnees = sortie_brute(technique, transcription, fournisseur,
                                   graine + essai - 1)
            return Verdict(
                verdict=donnees["verdict"], impact=donnees["impact"],
                citation=donnees["citation"], confiance=donnees["confiance"],
                motif=donnees["motif"],
                garde_fou_declenche=donnees["garde_fou_declenche"],
                graine=graine, modele=modele, version_invite=prompts.VERSION_INVITE)
        except FournisseurIndisponible as exc:
            derniere = exc
    raise derniere or FournisseurIndisponible("sortie du juge inexploitable",
                                              code="fournisseur_indisponible")
