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
MAX_JETONS_SORTIE = 500
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
        self.max_jetons_sortie = int(spec.get("max_jetons_sortie", MAX_JETONS_SORTIE))
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
        reponse = self.fournisseur.completer(
            messages, graine=hash_stable(texte) & 0xFFFFFFFF,
            max_jetons=self.max_jetons_sortie, temperature=self.temperature)
        duree = int((time.monotonic() - debut) * 1000)
        self.appels_modele += 1
        cout = (reponse.brut or {}).get("cout")
        if cout is not None:
            self.cout_cumule += float(cout)
        self._meta = {"jetons_entree": reponse.jetons_entree,
                      "jetons_sortie": reponse.jetons_sortie,
                      "latence_ms": duree, "modele": reponse.modele or self.modele,
                      "cout": cout}
        return (reponse.texte or "").strip()

    def statistiques(self) -> dict:
        """Consommation réelle de la cible : appels, jetons, coût mesuré."""
        return {"appels_modele": self.appels_modele, "modele": self.modele,
                "cout_mesure": round(self.cout_cumule, 6)}

    def documents_utilises(self, texte: str, session: str) -> list[Document]:
        """Documents qui seraient récupérés pour une requête (diagnostic)."""
        from piege.cibles.recherche import rechercher

        return rechercher(texte, self._index_session(session), self.k)
