"""Piège — rapport client : synthèse, découvertes, faux refus, attestation.

Le rapport affiche côte à côte ce qui fuit et ce qui est cassé (spécification
§13.3) et dit toujours ce qui n'a pas pu être testé (§21.5). L'attestation
tierce est volontairement pauvre en détails (EF-53).
"""

from piege.rapport.attestation import attestation, compte_severites
from piege.rapport.rapport import (bloc_non_teste, rapport,
                                   rapport_depuis_entrepot, resume)
from piege.rapport.synthese import (cle_dedoublonnage, construire_finding,
                                    synthetiser_findings)
from piege.rapport.traductions import LIBELLES, LANGUES, traduire

__all__ = [
    "rapport", "rapport_depuis_entrepot", "resume", "bloc_non_teste",
    "attestation", "compte_severites", "synthetiser_findings",
    "construire_finding", "cle_dedoublonnage", "LIBELLES", "LANGUES",
    "traduire",
]
