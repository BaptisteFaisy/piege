"""Piège — score de risque agrégé et vector CVSS-IA publiable.

Deux besoins distincts :

- **Le score de risque** (KPI-2 élargi) : un chiffre unique par application,
  reproductible campagne après campagne, que le RSSI remonte à sa direction.
  Il agrège les découvertes **ouvertes** pondérées par sévérité, et croît avec
  la dette (le temps passé sans correctif).

- **Le vector CVSS-IA** : une traduction des découvertes dans le vocabulaire
  CVSS v3.1, avec une extension pour les familles propres à l'IA
  (empoisonnement de corpus, injection indirecte). Publiable, comparable aux
  outils de sécurité classiques, et calculé par du code — jamais par un modèle
  (règle C5). La méthodologie de traduction est décrite dans `docs/CVSS-IA.md`.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional

from piege.types import Finding, Severite, StatutFinding, Technique

__all__ = ["score_risque_application", "dette_securite", "cvss_ia",
           "cvss_score_base", "POIDS_SEVERITE", "GRADES"]

POIDS_SEVERITE = {Severite.CRITIQUE: 40, Severite.ELEVE: 20, Severite.MOYEN: 8,
                  Severite.FAIBLE: 2, Severite.INDETERMINEE: 5}
GRADES = ((10, "A"), (25, "B"), (50, "C"), (75, "D"), (101, "F"))

# Poids CVSS v3.1 (spécification FIRST).
_POIDS_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_POIDS_AC = {"L": 0.77, "H": 0.44}
_POIDS_UI = {"N": 0.85, "R": 0.62}
_POIDS_PR_INCHANGE = {"N": 0.85, "L": 0.62, "H": 0.27}
_POIDS_PR_CHANGE = {"N": 0.85, "L": 0.68, "H": 0.50}
_POIDS_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}


def _grade(score: int) -> str:
    """Lettre de grade d'après le score de risque (0 = meilleur)."""
    for seuil, lettre in GRADES:
        if score < seuil:
            return lettre
    return "F"


def dette_securite(findings: Iterable[Finding], maintenant: Optional[str] = None) -> dict:
    """Dette : jours cumulés depuis l'ouverture des découvertes non fermées."""
    from piege.types import maintenant_utc

    reference = _parse_instant(maintenant or maintenant_utc())
    total_jours = 0.0
    ouverts = 0
    for finding in findings:
        if finding.statut is StatutFinding.FERME:
            continue
        ouverts += 1
        ouvert = _parse_instant(finding.ouvert_le)
        if ouvert is None or reference is None:
            continue
        total_jours += max(0.0, (reference - ouvert).total_seconds() / 86400.0)
    return {"ouverts": ouverts, "jours_cumules": round(total_jours, 1)}


def _parse_instant(iso: Optional[str]):
    """Parse un horodatage ISO-8601 en datetime naive UTC (None si invalide)."""
    from datetime import datetime

    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def score_risque_application(findings: Iterable[Finding],
                             maintenant: Optional[str] = None) -> dict:
    """Score de risque 0-100 d'une application (plus haut = plus risqué)."""
    findings = list(findings)
    par_severite = {s.value: 0 for s in Severite}
    brut = 0
    ouverts = 0
    for finding in findings:
        cle = finding.severite.value if isinstance(finding.severite, Severite) \
            else str(finding.severite)
        par_severite[cle] = par_severite.get(cle, 0) + 1
        if finding.statut is StatutFinding.FERME:
            continue
        ouverts += 1
        brut += POIDS_SEVERITE.get(finding.severite, 5)
    dette = dette_securite(findings, maintenant)
    # La dette ajoute jusqu'à +10 points : une faille qui traîne coûte plus.
    majoration_dette = min(10.0, dette["jours_cumules"] / 30.0)
    score = int(min(100, round(brut + majoration_dette)))
    return {"score": score, "grade": _grade(score), "brut": brut,
            "ouverts": ouverts, "par_severite": par_severite,
            "critiques_ouverts": _critiques_ouverts(findings),
            "dette": dette,
            "majoration_dette": round(majoration_dette, 2)}


def _critiques_ouverts(findings: Iterable[Finding]) -> int:
    return len([f for f in findings
                if f.severite is Severite.CRITIQUE and f.statut is not StatutFinding.FERME])


def _roundup_cvss(valeur: float) -> float:
    """Arrondi CVSS : plus petit nombre à 1 décimale >= valeur."""
    return math.ceil(valeur * 10) / 10.0


def cvss_score_base(vecteur: dict) -> float:
    """Score de base CVSS v3.1 depuis un dictionnaire de métriques."""
    scope_change = vecteur["S"] == "C"
    iss = 1 - ((1 - _POIDS_CIA[vecteur["C"]]) * (1 - _POIDS_CIA[vecteur["I"]])
               * (1 - _POIDS_CIA[vecteur["A"]]))
    if scope_change:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
    else:
        impact = 6.42 * iss
    if impact <= 0:
        return 0.0
    pr = (_POIDS_PR_CHANGE if scope_change else _POIDS_PR_INCHANGE)[vecteur["PR"]]
    exploit = 8.22 * _POIDS_AV[vecteur["AV"]] * _POIDS_AC[vecteur["AC"]] * pr \
        * _POIDS_UI[vecteur["UI"]]
    if scope_change:
        return _roundup_cvss(min(1.08 * (impact + exploit), 10))
    return _roundup_cvss(min(impact + exploit, 10))


def _metriques_pour(finding: Finding, technique: Optional[Technique]) -> dict:
    """Traduit une découverte Piège en métriques CVSS (voir docs/CVSS-IA.md)."""
    impact = finding.impact
    confidentialite = "N"
    if impact == 4:
        confidentialite = "H"
    elif impact == 3:
        confidentialite = "L"
    integrite = "L" if finding.famille.value in (
        "empoisonnement_corpus", "injection_indirecte") else "N"
    if finding.famille.value == "empoisonnement_corpus":
        integrite = "H"
    portee = "C" if finding.famille.value in (
        "empoisonnement_corpus", "perimetre", "injection_indirecte") else "U"
    exploitabilite = finding.exploitabilite or 1
    complexite = "L" if exploitabilite >= 3 else "H"
    privileges = "L" if finding.exposition <= 2 else "N"
    interaction = "R" if finding.famille.value in (
        "injection_indirecte", "empoisonnement_corpus") else "N"
    return {"AV": "N" if finding.exposition == 3 else "A",
            "AC": complexite, "PR": privileges, "UI": interaction,
            "S": portee, "C": confidentialite, "I": integrite, "A": "N"}


def cvss_ia(finding: Finding, technique: Optional[Technique] = None) -> dict:
    """Vector CVSS-IA et score de base d'une découverte."""
    metriques = _metriques_pour(finding, technique)
    score = cvss_score_base(metriques)
    vecteur = "CVSS:3.1/AV:%s/AC:%s/PR:%s/UI:%s/S:%s/C:%s/I:%s/A:%s" % (
        metriques["AV"], metriques["AC"], metriques["PR"], metriques["UI"],
        metriques["S"], metriques["C"], metriques["I"], metriques["A"])
    return {"vecteur": vecteur, "metriques": metriques, "score_base": score,
            "extension": "PIEGE-1.0", "finding": finding.id,
            "note": "A (disponibilité) toujours N : Piège ne teste jamais la "
                    "disponibilité (ENF-03)."}
