"""Piège — corpus de demandes légitimes (famille G, EF-30).

Un faux refus n'est détectable que si l'on sait ce qui est légitime : seul le
client peut le dire. Ce module charge son corpus, le valide et refuse de
produire un chiffre vide quand il manque (EF-34).

Format attendu (JSON, celui de `demo/corpus-legitime/demandes.json`) :

    {"id": ..., "application_id": ..., "tenant_id": ..., "source": ...,
     "charge_le": ..., "demandes": [{"id", "texte", "criticite",
     "frequence_mensuelle", "langue", "attendu", "etiquette"}, …]}
"""

from __future__ import annotations

import json
import os
from typing import Optional

from piege.erreurs import CorpusLegitimeAbsent, ValeurHorsPlage
from piege.types import (CorpusLegitime, DemandeLegitime, depuis_dict,
                         maintenant_utc)

__all__ = ["charger_corpus", "valider_corpus", "depuis_donnees",
           "MINIMUM_DEMANDES", "CRITICITES"]

MINIMUM_DEMANDES = 50
CRITICITES = (1, 2, 3, 4)
CHEMIN_DEMO = os.path.join("demo", "corpus-legitime", "demandes.json")


def charger_corpus(chemin: str = "") -> CorpusLegitime:
    """Charge un corpus depuis un fichier JSON ; erreur explicite s'il manque."""
    cible = chemin or CHEMIN_DEMO
    if not os.path.isfile(cible):
        raise CorpusLegitimeAbsent(
            "aucun corpus de demandes légitimes trouvé (%s) : la famille G "
            "n'est pas exécutable et aucun chiffre ne sera publié" % cible,
            code="corpus_legitime_absent",
            details={"regle": "famille_g.corpus", "chemin": cible})
    with open(cible, encoding="utf-8") as f:
        return depuis_donnees(json.load(f))


def depuis_donnees(donnees: dict) -> CorpusLegitime:
    """Construit le corpus depuis sa forme JSON, demandes comprises."""
    if not isinstance(donnees, dict) or "demandes" not in donnees:
        raise ValeurHorsPlage("corpus illisible : clé 'demandes' absente",
                              code="valeur_hors_plage",
                              details={"regle": "famille_g.corpus"})
    demandes = [depuis_dict(DemandeLegitime, item)
                for item in donnees["demandes"]]
    corpus = CorpusLegitime(
        id=str(donnees.get("id") or "CORP-sans-id"),
        application_id=str(donnees.get("application_id", "")),
        tenant_id=str(donnees.get("tenant_id", "")),
        demandes=demandes, source=str(donnees.get("source", "")),
        charge_le=str(donnees.get("charge_le") or maintenant_utc()))
    valider_corpus(corpus)
    return corpus


def valider_corpus(corpus: Optional[CorpusLegitime],
                   minimum: int = MINIMUM_DEMANDES) -> CorpusLegitime:
    """Valide un corpus : présent, assez fourni, criticités conformes."""
    if corpus is None or not corpus.demandes:
        raise CorpusLegitimeAbsent(
            "corpus de demandes légitimes absent ou vide : la famille G refuse "
            "de produire un chiffre vide (EF-34)",
            code="corpus_legitime_absent", details={"regle": "famille_g.corpus"})
    if len(corpus.demandes) < minimum:
        raise ValeurHorsPlage(
            "corpus de %d demandes, minimum exigé %d (EF-30)"
            % (len(corpus.demandes), minimum), code="valeur_hors_plage",
            details={"regle": "famille_g.corpus.minimum"})
    for demande in corpus.demandes:
        _valider_demande(demande)
    return corpus


def _valider_demande(demande: DemandeLegitime) -> None:
    """Contrôle une demande : texte non vide, criticité 1..4, fréquence >= 1."""
    if not str(demande.texte or "").strip():
        raise ValeurHorsPlage("demande %s : texte vide" % demande.id,
                              code="valeur_hors_plage",
                              details={"regle": "famille_g.demande"})
    if demande.criticite not in CRITICITES:
        raise ValeurHorsPlage(
            "demande %s : criticité %r hors %s"
            % (demande.id, demande.criticite, list(CRITICITES)),
            code="valeur_hors_plage", details={"regle": "famille_g.criticite"})
    if demande.frequence_mensuelle < 1:
        raise ValeurHorsPlage(
            "demande %s : fréquence mensuelle %d < 1"
            % (demande.id, demande.frequence_mensuelle),
            code="valeur_hors_plage", details={"regle": "famille_g.frequence"})


def repartition(corpus: CorpusLegitime) -> dict[int, int]:
    """Répartition des demandes par criticité métier (annexe E.3)."""
    compte: dict[int, int] = {c: 0 for c in CRITICITES}
    for demande in corpus.demandes:
        compte[demande.criticite] = compte.get(demande.criticite, 0) + 1
    return compte
