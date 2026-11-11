"""Piège — erreurs du catalogue : une donnée invalide est refusée, jamais devinée."""

from __future__ import annotations

from piege.erreurs import ErreurPiege

__all__ = ["CatalogueInvalide", "TechniqueInvalide"]


class CatalogueInvalide(ErreurPiege):
    """Le catalogue (ou un de ses fichiers) ne respecte pas le schéma gelé."""

    code = "catalogue_invalide"
    statut_http = 422

    def __init__(self, message: str, fichier: str = "", regle: str = "",
                 details: dict | None = None):
        complements = {"regle": regle or "catalogue.schema"}
        if fichier:
            complements["fichier"] = fichier
        complements.update(details or {})
        super().__init__(message, code=self.code, details=complements)


class TechniqueInvalide(CatalogueInvalide):
    """Une technique précise du catalogue est invalide."""

    code = "technique_invalide"

    def __init__(self, message: str, technique_id: str = "", fichier: str = "",
                 regle: str = ""):
        super().__init__(message, fichier=fichier, regle=regle,
                         details={"technique": technique_id})
        self.technique_id = technique_id
