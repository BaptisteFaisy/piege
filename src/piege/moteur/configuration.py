"""Piège — configuration des campagnes et des techniques.

Les champs gelés par CONTRACTS-INTERFACES §5 sont suivis des injections de
l'amendement S0 (composants remplaçables) puis des compléments du lot 3
(résolution directe du mandat, de la cible et des techniques). Tous les champs
ajoutés sont optionnels : un appelant existant ne change pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from piege.erreurs import ValeurHorsPlage
from piege.types import (Application, Campagne, Famille, Mandat, Technique,
                         TypeCampagne)

__all__ = ["ConfigurationCampagne", "ConfigurationTechnique",
           "PARALLELISME_DEFAUT", "PARALLELISME_MAX"]

PARALLELISME_DEFAUT = 4
PARALLELISME_MAX = 8


@dataclass
class ConfigurationCampagne:
    """Tout ce qu'il faut pour lancer une campagne, sans état caché."""

    mandat_id: str = ""
    application_id: str = ""
    tenant_id: str = ""
    type: TypeCampagne = TypeCampagne.COMPLETE
    graine: int = 0
    technique_ids: Optional[list[str]] = None
    familles: Optional[list[Famille]] = None
    parallelisme: int = PARALLELISME_DEFAUT
    budget_appels: int = 0
    budget_jetons: int = 0
    corpus_legitime_id: str = ""
    cible_spec: dict = field(default_factory=dict)
    arrete_urgence: bool = False
    # --- amendement S0 : composants injectables (None = import paresseux) ---
    attaquant: Optional[Callable] = None
    juge: Optional[Callable] = None
    evaluateur: Optional[Callable] = None
    entrepot: Optional[Any] = None
    fournisseur: Optional[Any] = None
    # --- compléments lot 3 : résolution directe, sans entrepôt ni catalogue ---
    mandat: Optional[Mandat] = None
    application: Optional[Application] = None
    cible: Optional[Any] = None
    techniques: Optional[list[Technique]] = None
    catalogue: Optional[dict] = None
    fournisseur_juge: Optional[Any] = None
    campagne: Optional[Campagne] = None
    campagne_id: str = ""
    journal: Optional[Any] = None
    double_passage: Optional[bool] = None

    def valider(self) -> None:
        """Contrôle les bornes ; aucune valeur n'est bornée en silence."""
        if not 1 <= self.parallelisme <= PARALLELISME_MAX:
            raise ValeurHorsPlage(
                "parallélisme %s hors borne [1..%d]"
                % (self.parallelisme, PARALLELISME_MAX),
                code="valeur_hors_plage", details={"regle": "moteur.parallelisme"})
        if self.budget_appels < 0 or self.budget_jetons < 0:
            raise ValeurHorsPlage("un budget ne peut pas être négatif",
                                  code="valeur_hors_plage",
                                  details={"regle": "moteur.budget"})

    def budget_appels_effectif(self, mandat: Mandat) -> int:
        """Budget d'appels : la configuration ne peut que le resserrer."""
        if not self.budget_appels:
            return mandat.budget_appels
        return min(self.budget_appels, mandat.budget_appels)

    def budget_jetons_effectif(self, mandat: Mandat) -> int:
        """Budget de jetons : la configuration ne peut que le resserrer."""
        if not self.budget_jetons:
            return mandat.budget_jetons
        return min(self.budget_jetons, mandat.budget_jetons)


@dataclass
class ConfigurationTechnique:
    """Contexte d'exécution d'une technique isolée (EF-54 : rejeu)."""

    technique: Technique
    mandat: Mandat
    cible: Any
    campagne: Campagne
    graine: int
    fournisseur: Any = None
    journal: Optional[Any] = None
    budget: Optional[Any] = None
    arret: Optional[Any] = None
    attaquant: Optional[Callable] = None
    juge: Optional[Callable] = None
    evaluateur: Optional[Callable] = None
    entrepot: Optional[Any] = None
    fournisseur_juge: Optional[Any] = None
    index_test: str = ""
