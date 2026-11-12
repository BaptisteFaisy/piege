"""Piège — cible réelle : assistant RAG dont les réponses viennent d'un vrai modèle.

Même corpus, même récupération, mêmes garde-fous et même index de test que la
cible de démonstration hors ligne — **seule la génération change** : au lieu de
règles déterministes, la réponse est produite par un vrai modèle (InferHub, API
compatible OpenAI). C'est ce qui rend la démonstration probante : la fuite de la
grille des salaires n'est plus simulée, elle est réellement produite par un
modèle qui confond données et instructions.

L'invite système reste volontairement naïve (aucune séparation données /
instructions) : c'est la vulnérabilité documentée de l'annexe E.1.

Coût et latence sont **mesurés** depuis la réponse de l'API (jetons réels, coût
réel renvoyé par le routeur), ce qui alimente le KPI-7 avec des chiffres réels.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from piege.cibles.locale import CibleLocaleDemo
from piege.cibles.recherche import Document
from piege.types import hash_stable

__all__ = ["CibleInferhub", "MODELE_DEFAUT", "construire_contexte",
           "VAR_CLE", "VAR_MODELE", "VAR_URL"]

MODELE_DEFAUT = "ali/deepseek-v4-pro-0813"
VAR_CLE = "PIEGE_LLM_CLE"
VAR_MODELE = "PIEGE_CIBLE_MODELE"
VAR_URL = "PIEGE_LLM_URL"

MAX_CARACTERES_PAR_DOCUMENT = 1400
# Les modèles cibles raisonnent avant de répondre : un budget de sortie trop
# court est entièrement consommé par la chaîne de raisonnement et la réponse
# utile arrive **vide**. 3 000 jetons laissent de la place au raisonnement et à
# la réponse ; une réponse vide déclenche une relance à budget triple.
MAX_JETONS_SORTIE = 3000
MULTIPLICATEUR_RELANCE = 3
VAR_MAX_JETONS = "PIEGE_CIBLE_MAX_JETONS"
TEMPERATURE = 0.2


def construire_contexte(documents: list, limite: int = MAX_CARACTERES_PAR_DOCUMENT) -> str:
    """Bloc de documents récupérés, tel qu'injecté dans l'invite utilisateur."""
    if not documents:
        return "DOCUMENTS RECUPERES : aucun document pertinent trouvé."
    morceaux = []
    for document in documents:
        corps = _nettoyer(document.contenu)[:limite]
        morceaux.append("--- %s ---\n%s" % (document.nom, corps))
    return "DOCUMENTS RECUPERES :\n%s\n--- FIN DES DOCUMENTS ---" % "\n\n".join(morceaux)


def _nettoyer(contenu: str) -> str:
    """Retire le filigrane et les commentaires de démonstration du contexte."""
    lignes = [ligne for ligne in (contenu or "").splitlines()
              if ligne.strip() and not ligne.strip().startswith("<!--")]
    return "\n".join(lignes).strip()


class CibleInferhub(CibleLocaleDemo):
    """Cible RAG réelle : récupération locale, génération par modèle."""

    def __init__(self, spec: Optional[dict] = None, fournisseur: Any = None):
        spec = dict(spec or {})
        spec.setdefault("modele", os.environ.get(VAR_MODELE, MODELE_DEFAUT))
        super().__init__(spec)
        self.max_jetons_sortie = int(spec.get("max_jetons_sortie")
                                     or os.environ.get(VAR_MAX_JETONS)
                                     or MAX_JETONS_SORTIE)
        self.temperature = float(spec.get("temperature", TEMPERATURE))
        self.cout_cumule = 0.0
        self.appels_modele = 0
        self._fournisseur = fournisseur

    @property
    def fournisseur(self) -> Any:
        """Fournisseur de modèle, construit à la première utilisation."""
        if self._fournisseur is None:
            from piege.fournisseurs.inferhub import FournisseurInferhub

            cle = os.environ.get(VAR_CLE, "")
            if not cle:
                raise ValueError(
                    "clé de modèle absente : définir %s (jamais dans le dépôt)"
                    % VAR_CLE)
            self._fournisseur = FournisseurInferhub(
                url=os.environ.get(VAR_URL) or None, modele=self.modele, cle=cle)
        return self._fournisseur

    def _generer(self, texte: str, recuperes: list, session: str) -> str:
        """Fait répondre un vrai modèle sur les documents récupérés."""
        messages = [
            {"role": "system", "content": self.invite},
            {"role": "user",
             "content": "%s\n\nQUESTION : %s" % (construire_contexte(recuperes), texte)},
        ]
        debut = time.monotonic()
        reponse, budget = self._completer_avec_relance(messages, texte)
        duree = int((time.monotonic() - debut) * 1000)
        self.appels_modele += 1
        cout = (reponse.brut or {}).get("cout")
        if cout is not None:
            self.cout_cumule += float(cout)
        self._meta = {"jetons_entree": reponse.jetons_entree,
                      "jetons_sortie": reponse.jetons_sortie,
                      "latence_ms": duree, "modele": reponse.modele or self.modele,
                      "cout": cout, "budget_sortie": budget,
                      "reponse_vide": not (reponse.texte or "").strip()}
        return (reponse.texte or "").strip()

    def _completer_avec_relance(self, messages: list, texte: str):
        """Appel du modèle, relancé à budget triple si la réponse est vide.

        Une réponse vide n'est pas un refus : c'est le plus souvent un budget de
        sortie absorbé par le raisonnement du modèle. La relance est bornée à un
        essai supplémentaire et l'échec est tracé (`reponse_vide`), jamais
        masqué.
        """
        graine = hash_stable(texte) & 0xFFFFFFFF
        budget = self.max_jetons_sortie
        reponse = self.fournisseur.completer(messages, graine=graine,
                                             max_jetons=budget,
                                             temperature=self.temperature)
        if not (reponse.texte or "").strip():
            budget *= MULTIPLICATEUR_RELANCE
            relance = self.fournisseur.completer(messages, graine=graine,
                                                 max_jetons=budget,
                                                 temperature=self.temperature)
            if (relance.texte or "").strip():
                return relance, budget
        return reponse, budget

    def statistiques(self) -> dict:
        """Consommation réelle de la cible : appels, jetons, coût mesuré."""
        return {"appels_modele": self.appels_modele, "modele": self.modele,
                "cout_mesure": round(self.cout_cumule, 6)}

    def documents_utilises(self, texte: str, session: str) -> list[Document]:
        """Documents qui seraient récupérés pour une requête (diagnostic)."""
        from piege.cibles.recherche import rechercher

        return rechercher(texte, self._index_session(session), self.k)
