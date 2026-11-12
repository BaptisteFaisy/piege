"""Piège — contexte d'exécution de l'API (injection de dépendances).

L'API ne construit rien elle-même : elle reçoit un entrepôt, un catalogue, un
fournisseur et des cibles. C'est ce qui permet de la tester entièrement hors
ligne, et de la déployer telle quelle en Lambda (le contexte est créé une fois
au démarrage, hors du gestionnaire).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = ["Api", "creer_api"]


@dataclass
class Api:
    """Tout ce dont les routes ont besoin, résolu une seule fois."""

    entrepot: Any = None
    catalogue: Optional[dict] = None
    fournisseur: Any = None
    juge: Optional[Any] = None
    cibles: dict = field(default_factory=dict)
    dossier_donnees: str = "donnees-locales"
    dossier_corpus: str = "demo/corpus"
    dossier_catalogue: str = "catalogue"
    arret_global: bool = False

    def cible(self, application_id: str, spec: Optional[dict] = None) -> Any:
        """Cible d'une application, mise en cache pour la durée du contexte."""
        if application_id in self.cibles:
            return self.cibles[application_id]
        try:
            from piege.cibles import creer_cible
        except ImportError as exc:
            from piege.erreurs import ErreurPiege

            raise ErreurPiege(
                "aucun adaptateur de cible disponible (lot 1 absent) : "
                "injecter une cible dans le contexte d'API",
                code="cible_indisponible",
                details={"regle": "api.cible"}) from exc

        specification = dict(spec or {})
        # `PIEGE_CIBLE_TYPE` bascule toute l'instance sur une cible à modèle réel
        # (inferhub) sans toucher au portail ni au code : c'est l'interrupteur
        # « simulateur déterministe » ↔ « vrai modèle ».
        specification.setdefault("type", os.environ.get("PIEGE_CIBLE_TYPE", "local"))
        specification.setdefault("id", application_id)
        specification.setdefault("application_id", application_id)
        specification.setdefault("corpus", self.dossier_corpus)
        cible = creer_cible(specification)
        self.cibles[application_id] = cible
        return cible


def creer_api(spec: Optional[dict] = None) -> Api:
    """Construit un contexte d'API par défaut (entrepôt local, hors ligne)."""
    spec = dict(spec or {})
    from piege.stockage import creer_entrepot

    dossier = spec.get("donnees") or os.environ.get("PIEGE_DONNEES",
                                                    "donnees-locales")
    api = Api(dossier_donnees=dossier,
              dossier_corpus=spec.get("corpus", "demo/corpus"),
              dossier_catalogue=spec.get("catalogue", "catalogue"))
    api.entrepot = spec.get("entrepot") or creer_entrepot(
        {"type": "local", "dossier": dossier})
    return api
