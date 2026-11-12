"""Piège — génération du corpus légitime depuis les journaux d'usage (#50).

C'est ce qui lève le principal frein commercial de la famille G : plus besoin
que le client rédige 50 demandes à la main. On lit ses journaux d'usage, on
**anonymise** chaque demande, on **déduplique**, on **estime la criticité**, et
on produit un `CorpusLegitime` conforme au contrat — directement consommable par
`piege.familles.faux_refus.executer`.

Le générateur refuse de produire un corpus tronqué : en dessous du minimum
(50 demandes, EF-30) il lève une erreur explicite plutôt que de publier un
chiffre de faux refus sur un échantillon trop petit.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.corpus_logs.anonymiseur import anonymiser, contient_pii, types_presents
from piege.corpus_logs.criticite import DETAIL, estimer_criticite
from piege.erreurs import CorpusLegitimeAbsent
from piege.types import (CorpusLegitime, DemandeLegitime, maintenant_utc)

__all__ = ["generer_corpus", "normaliser_entrees", "MINIMUM_DEMANDES"]

MINIMUM_DEMANDES = 50


def normaliser_entrees(entrees: Iterable[dict], frequence_defaut: int = 1) -> list[dict]:
    """Anonymise, déduplique et compte la fréquence de chaque demande.

    `entrees` : itérable de dicts avec au moins une clé `texte` (et une clé
    optionnelle `frequence`). Les demandes identiques (après anonymisation et
    normalisation) sont fusionnées, leur fréquence additionnée : c'est ce qui
    donne le poids réel d'une demande récurrente. Le texte conservé est le texte
    anonymisé d'origine, pas la clé normalisée.
    """
    frequences: dict[str, int] = {}
    textes: dict[str, str] = {}
    ordre: list[str] = []
    for entree in entrees or []:
        brut = str(entree.get("texte", "") or "")
        texte = anonymiser(brut).strip()
        if not texte:
            continue
        cle = _cle_normalisation(texte)
        if cle not in frequences:
            ordre.append(cle)
            frequences[cle] = 0
            textes[cle] = texte
        frequences[cle] += int(entree.get("frequence", frequence_defaut) or 1)
    return [{"texte": textes[cle], "frequence": frequences[cle]} for cle in ordre]


def _cle_normalisation(texte: str) -> str:
    """Clé de dédoublonnage : minuscules, ponctuation aplatie."""
    import re

    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", texte.lower())).strip()


def generer_corpus(entrees: Iterable[dict], application_id: str, tenant_id: str,
                   source: str = "journaux_d_usage",
                   minimum: int = MINIMUM_DEMANDES,
                   identifiant: str = "") -> CorpusLegitime:
    """Construit un `CorpusLegitime` anonymisé depuis des journaux d'usage."""
    normalisees = normaliser_entrees(entrees)
    if len(normalisees) < minimum:
        raise CorpusLegitimeAbsent(
            "corpus généré de %d demandes, minimum %d (EF-30) : la famille G "
            "refuse de publier un taux de faux refus sur un échantillon trop "
            "petit" % (len(normalisees), minimum),
            code="corpus_legitime_absent",
            details={"regle": "famille_g.corpus.minimum",
                     "disponibles": len(normalisees)})
    demandes = []
    for index, item in enumerate(normalisees, start=1):
        texte = item["texte"]
        demandes.append(DemandeLegitime(
            id="DL-%04d" % index, texte=texte,
            criticite=estimer_criticite(texte),
            frequence_mensuelle=max(1, item["frequence"]), langue="fr",
            attendu="réponse complète", etiquette=DETAIL))
    return CorpusLegitime(
        id=identifiant or "CORP-%s" % application_id,
        application_id=application_id, tenant_id=tenant_id, demandes=demandes,
        source=source, charge_le=maintenant_utc())


def statistiques_pii(entrees: Iterable[dict]) -> dict:
    """Compte les types de PII rencontrés (journal d'anonymisation, sans donnée)."""
    compte: dict[str, int] = {}
    total = 0
    for entree in entrees or []:
        texte = str(entree.get("texte", "") or "")
        if contient_pii(texte):
            total += 1
            for type_ in types_presents(texte):
                compte[type_] = compte.get(type_, 0) + 1
    return {"entrees_avec_pii": total, "par_type": compte}


def valider_minimum(corpus: Optional[CorpusLegitime],
                    minimum: int = MINIMUM_DEMANDES) -> None:
    """Vérifie le minimum ; lève si insuffisant (jamais de corpus tronqué)."""
    if corpus is None or len(corpus.demandes) < minimum:
        raise CorpusLegitimeAbsent(
            "corpus de %d demandes, minimum %d"
            % (len(corpus.demandes) if corpus else 0, minimum),
            code="corpus_legitime_absent",
            details={"regle": "famille_g.corpus.minimum"})
