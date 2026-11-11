"""Piège — gabarits de documents piégés (famille F).

Le gabarit est une **donnée du catalogue** (`gabarit_document`), pas du code :
ajouter une technique de la famille F consiste à ajouter un fichier Markdown
dans `catalogue/gabarits/`. Ce module le charge, le marque au nom de la
campagne et le rend prêt à déposer.

Le marquage est essentiel : c'est lui qui permet de prouver, après mesure, que
le document a bien été retiré (R7) et de distinguer une sonde de test d'un
document réel du client.
"""

from __future__ import annotations

import os
from typing import Optional

from piege.erreurs import ErreurPiege
from piege.types import Technique, maintenant_utc

__all__ = ["chemin_gabarit", "charger_gabarit", "document_depose",
           "MARQUEUR_DEPOT", "DOSSIER_GABARITS"]

DOSSIER_GABARITS = "gabarits"
MARQUEUR_DEPOT = "DEPOT-TEST-PIEGE"
NOM_FICHIER_DEFAUT = "note-de-service-deposee.md"


def chemin_gabarit(technique: Technique, dossier_catalogue: str = "catalogue") -> str:
    """Chemin absolu du gabarit d'une technique."""
    if not technique.gabarit_document:
        raise ErreurPiege("technique %s : aucun gabarit_document déclaré"
                          % technique.id, code="gabarit_absent",
                          details={"regle": "famille_f.gabarit"})
    return os.path.join(dossier_catalogue, technique.gabarit_document)


def charger_gabarit(technique: Technique,
                    dossier_catalogue: str = "catalogue") -> str:
    """Contenu du gabarit ; erreur explicite s'il est absent du dépôt."""
    chemin = chemin_gabarit(technique, dossier_catalogue)
    if not os.path.isfile(chemin):
        raise ErreurPiege("gabarit introuvable : %s" % chemin,
                          code="gabarit_absent",
                          details={"regle": "famille_f.gabarit",
                                   "technique": technique.id})
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def marquer(contenu: str, campagne_id: str, technique_id: str,
            date: Optional[str] = None) -> str:
    """Ajoute le marqueur immuable de dépôt de test au document."""
    horodatage = date or maintenant_utc()
    entete = ("<!-- %s campagne=%s technique=%s date=%s -->\n"
              % (MARQUEUR_DEPOT, campagne_id, technique_id, horodatage))
    return entete + contenu


def document_depose(technique: Technique, campagne_id: str,
                    dossier_catalogue: str = "catalogue",
                    nom_fichier: str = "",
                    contenu: Optional[str] = None) -> tuple[str, str]:
    """Rend (chemin, contenu) du document à déposer pour une technique."""
    texte = contenu if contenu is not None else charger_gabarit(
        technique, dossier_catalogue)
    nom = nom_fichier or os.path.basename(technique.gabarit_document
                                          or NOM_FICHIER_DEFAUT)
    return nom, marquer(texte, campagne_id, technique.id)


def est_marque(contenu: str) -> bool:
    """Vrai si un contenu porte le marqueur de dépôt de test."""
    return MARQUEUR_DEPOT in (contenu or "")
