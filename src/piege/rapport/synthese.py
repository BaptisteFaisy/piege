"""Piège — synthèse des découvertes depuis les exécutions d'une campagne.

Deux règles structurent ce module :

1. **Dédoublonnage** (EF-24) : deux techniques qui révèlent la même faille
   produisent une découverte et deux preuves. L'identité d'une faille est sa
   nature de divulgation (impact) et le motif retenu par le juge — jamais
   l'identifiant de la technique.
2. **Sévérité calculée** (règle C5) : la sévérité sort de `piege.severite`, à
   partir de l'impact classé par le juge, de l'exploitabilité déduite de la
   technique et de l'exposition déclarée de l'application.
"""

from __future__ import annotations

from typing import Any, Optional

from piege import severite
from piege.types import (Application, Campagne, Execution, Famille, Finding,
                         StatutFinding, Technique, hash_stable, maintenant_utc)

__all__ = ["synthetiser_findings", "cle_dedoublonnage", "construire_finding"]


def cle_dedoublonnage(execution: Execution) -> str:
    """Identifiant stable d'une faille : nature de la divulgation + motif."""
    motif = (execution.motif or "").strip().lower()
    return "%s:%s" % (execution.impact, hash_stable(motif))


def construire_finding(executions: list[Execution], campagne: Campagne,
                       application: Application, catalogue: Optional[dict] = None,
                       sequence: int = 1) -> Finding:
    """Construit une découverte à partir des exécutions qui la révèlent."""
    premiere = executions[0]
    technique_ids = sorted({e.technique_id for e in executions})
    exploitabilite = _exploitabilite(technique_ids, catalogue)
    citation = max((e.citation for e in executions if e.citation),
                   key=len, default="")
    finding = Finding(
        id="FINDING-%s-%04d" % (campagne.debutee_le[:4] or "0000", sequence),
        application_id=application.id, tenant_id=campagne.tenant_id,
        campagne_id=campagne.id, technique_ids=technique_ids,
        famille=_famille(technique_ids, catalogue),
        severite=None, impact=premiere.impact,
        exploitabilite=exploitabilite, exposition=application.exposition,
        score=None, statut=StatutFinding.OUVERT,
        titre=_titre(premiere, technique_ids),
        description=_description(premiere, technique_ids),
        citation=citation,
        preuve_ids=[e.id for e in executions], correctif_ids=[],
        ouvert_le=maintenant_utc())
    return severite.classer(finding)


def _exploitabilite(technique_ids: list[str], catalogue: Optional[dict]) -> Optional[int]:
    """Exploitabilité la plus élevée des techniques en cause (la plus réaliste)."""
    valeurs = []
    for identifiant in technique_ids:
        technique = (catalogue or {}).get(identifiant)
        if isinstance(technique, Technique):
            valeurs.append(severite.exploitabilite(technique))
    if not valeurs:
        return None
    return max(valeurs)


def _famille(technique_ids: list[str], catalogue: Optional[dict]) -> Famille:
    """Famille de la première technique connue du catalogue."""
    for identifiant in technique_ids:
        technique = (catalogue or {}).get(identifiant)
        if isinstance(technique, Technique):
            return technique.famille
    return Famille(_famille_depuis_id(technique_ids[0]))


def _famille_depuis_id(technique_id: str) -> str:
    """Valeur de famille déduite de la lettre de l'identifiant."""
    lettres = {c: membre.value for c, membre in
               zip("ABCDEFGH", list(Famille))}
    return lettres.get(technique_id[:1].upper(), Famille.A.value)


def _titre(execution: Execution, technique_ids: list[str]) -> str:
    """Titre lisible d'une découverte."""
    return "Divulgation confirmée par %s (%s)" % (
        ", ".join(technique_ids), execution.motif or "verdict du juge")


def _description(execution: Execution, technique_ids: list[str]) -> str:
    """Description factuelle : ce qui a été observé, et par quelles techniques."""
    return ("Technique(s) %s : %s. Citation fondant le verdict : « %s »."
            % (", ".join(technique_ids), execution.motif or "succès",
               (execution.citation or "")[:300]))


def synthetiser_findings(campagne: Campagne, executions: list[Execution],
                         application: Application, catalogue: Optional[dict] = None,
                         entrepot: Optional[Any] = None) -> list[Finding]:
    """Regroupe les réussites en découvertes dédoublonnées et les classe."""
    groupes: dict[str, list[Execution]] = {}
    for execution in executions:
        if execution.verdict is None or execution.verdict.value != "reussi":
            continue
        groupes.setdefault(cle_dedoublonnage(execution), []).append(execution)
    findings = []
    for sequence, cle in enumerate(sorted(groupes), start=1):
        finding = construire_finding(groupes[cle], campagne, application,
                                     catalogue, sequence)
        if entrepot is not None:
            entrepot.ecrire("findings", finding.vers_dict())
        findings.append(finding)
    return findings
