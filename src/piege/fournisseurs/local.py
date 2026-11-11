"""Piège — fournisseur local : déterministe, hors ligne, sans modèle.

Sert à la CI, à `make demo` et au harnais d'évaluation. Deux comportements :

- `completer` rend un texte déterministe dérivé du dernier message et de la
  graine (aucun aléa non reproductible) ;
- `sortie_structuree` délègue au **juge hors ligne du lot 5** pour ne pas
  dupliquer ses règles de classification : la sortie est alors l'objet JSON
  attendu par `piege.agents.juge.schema`.

Ce fournisseur déclare des jetons **simulés mais cohérents** (proportionnels à
la longueur des messages) pour que la mesure de coût du lot 11 s'exerce.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable, Optional

from piege.erreurs import FournisseurIndisponible
from piege.fournisseurs.base import ReponseModele
from piege.types import hash_stable

__all__ = ["FournisseurLocal", "estimer_jetons", "extraire_transcription"]

JETONS_PAR_CARACTERES = 4
REPONSES = (
    "Je réponds à partir des documents disponibles.",
    "Cette demande sort de mon périmètre, je ne peux pas y répondre.",
    "Voici les éléments demandés, issus du corpus indexé.",
    "Merci de préciser votre demande auprès du service concerné.",
)


def estimer_jetons(texte: str) -> int:
    """Estimation déterministe du nombre de jetons (1 jeton ≈ 4 caractères)."""
    return max(1, len(texte or "") // JETONS_PAR_CARACTERES)


def extraire_transcription(messages: list[dict]) -> str:
    """Extrait la transcription d'un message de juge (bloc entre `---`)."""
    for message in reversed(messages or []):
        contenu = str(message.get("content", ""))
        trouve = re.search(r"---\n(.*?)\n---", contenu, re.S)
        if trouve:
            return trouve.group(1)
        if "TRANSCRIPTION" in contenu:
            return contenu.split("TRANSCRIPTION", 1)[1].strip().strip("-").strip()
    return ""


def _classifieur_par_defaut(transcription: str) -> dict:
    """Délègue au juge déterministe du lot 5 (import paresseux, zéro duplicat)."""
    try:
        from piege.agents.juge.local import (juger_deterministe)
        from piege.types import Famille, ProductionAutorisee, Technique
    except ImportError as exc:
        raise FournisseurIndisponible(
            "le juge hors ligne (lot 5) est requis par le fournisseur local",
            code="fournisseur_indisponible",
            details={"regle": "fournisseur.local.juge"}) from exc
    technique = Technique(
        id="LOCAL", famille=Famille.A, nom="juge local", objectif="verdict",
        preconditions=[], environnement=[], production=ProductionAutorisee.JAMAIS,
        budget_appels=1, tours_max=1, sonde_initiale="", mesures=[],
        juge_reussi_si="")
    return juger_deterministe(technique, transcription).vers_dict()


class FournisseurLocal:
    """Fournisseur déterministe ; `classificateur` injectable pour les tests."""

    nom = "local"

    def __init__(self, modele: str = "local-deterministe",
                 classificateur: Optional[Callable[[str], dict]] = None):
        self.modele = modele
        self._classificateur = classificateur or _classifieur_par_defaut

    def completer(self, messages: list[dict], graine: int,
                  max_jetons: int = 1500, temperature: float = 0.0) -> ReponseModele:
        """Texte déterministe : choix indexé par la graine et le contenu."""
        texte_source = str(messages[-1].get("content", "")) if messages else ""
        index = (graine ^ hash_stable(texte_source)) % len(REPONSES)
        texte = REPONSES[index][:max(1, max_jetons * JETONS_PAR_CARACTERES)]
        entree = sum(estimer_jetons(str(m.get("content", ""))) for m in messages)
        return ReponseModele(texte=texte, jetons_entree=entree,
                             jetons_sortie=estimer_jetons(texte),
                             modele=self.modele,
                             brut={"graine": graine, "temperature": temperature})

    def sortie_structuree(self, messages: list[dict], schema: dict,
                          graine: int) -> dict:
        """Objet JSON conforme au schéma, obtenu par classification locale."""
        if not isinstance(schema, dict):
            raise FournisseurIndisponible(
                "schéma de sortie invalide", code="fournisseur_indisponible",
                details={"regle": "fournisseur.local.schema"})
        transcription = extraire_transcription(messages)
        sortie = self._classificateur(transcription)
        sortie = self._normaliser_enum(sortie)
        sortie["graine"] = graine
        return sortie

    @staticmethod
    def _normaliser_enum(sortie: dict) -> dict:
        """Les énumérations redeviennent des chaînes (sortie JSON attendue)."""
        propre = {}
        for cle, valeur in sortie.items():
            propre[cle] = getattr(valeur, "value", valeur)
        return propre

    def empreinte(self, texte: str) -> str:
        """Empreinte stable d'une réponse (traçabilité hors ligne)."""
        return hashlib.sha256((texte or "").encode("utf-8")).hexdigest()[:16]
