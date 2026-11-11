"""Piège — routes des découvertes et des correctifs.

Ces routes portent le moment décisif de la démonstration : proposer un
correctif, obtenir l'accord humain explicite, l'appliquer, rejouer l'attaque
d'origine et rendre la ligne unique qui dit à la fois la fermeture et l'effet de
bord (spécification §25.2, moments 2:00 à 2:35).
"""

from __future__ import annotations

from typing import Any, Optional

from piege.api.aides import ecrire, exiger_role, lire, lire_ou_erreur
from piege.types import (Campagne, Correctif, Finding, Mandat, StatutCampagne,
                         StatutFinding, TypeCampagne, depuis_dict, maintenant_utc)

__all__ = ["ROUTES", "lister_findings", "lire_finding", "proposer_correctifs",
           "lire_correctif", "autoriser_correctif", "rejouer_finding"]


def _catalogue(api: Any) -> dict:
    """Catalogue du contexte, chargé une fois."""
    if api.catalogue is None:
        try:
            from piege.catalogue import charger_catalogue

            api.catalogue = charger_catalogue(api.dossier_catalogue)
        except Exception:                                     # noqa: BLE001
            api.catalogue = {}
    return api.catalogue


def lister_findings(api: Any, tenant: str, roles: list,
                    requete: Optional[dict] = None, **_) -> list:
    """Découvertes du tenant, filtrées (EF-62 : jamais celles d'un autre)."""
    del roles
    requete = requete or {}
    filtres = {}
    for cle in ("severite", "statut", "application_id"):
        if requete.get(cle):
            filtres[cle] = requete[cle]
    return api.entrepot.lister("findings", tenant_id=tenant, **filtres)


def lire_finding(api: Any, tenant: str, roles: list, id: str, **_) -> dict:
    """Découverte complète avec ses preuves et ses correctifs."""
    del roles
    brut = lire_ou_erreur(api, "findings", id, tenant)
    preuves = [lire(api, "preuves", p, tenant) for p in brut.get("preuve_ids", [])]
    correctifs = [lire(api, "correctifs", c, tenant)
                  for c in brut.get("correctif_ids", [])]
    return {"finding": brut,
            "preuves": [p for p in preuves if p],
            "correctifs": [c for c in correctifs if c]}


def proposer_correctifs(api: Any, tenant: str, roles: list, id: str, **_) -> list:
    """Génère les correctifs d'une découverte (EF-40) et les persiste."""
    from piege.correctifs.proposition import proposer

    exiger_role(roles, ["analyste", "commanditaire"], "proposer des correctifs")
    brut = lire_ou_erreur(api, "findings", id, tenant)
    finding = depuis_dict(Finding, brut)
    propositions = proposer(finding, catalogue=_catalogue(api))
    for correctif in propositions:
        ecrire(api, "correctifs", correctif.vers_dict())
    identifiants = sorted(set(brut.get("correctif_ids", []))
                          | {c.id for c in propositions})
    brut["correctif_ids"] = identifiants
    ecrire(api, "findings", brut)
    return [c.vers_dict() for c in propositions]


def lire_correctif(api: Any, tenant: str, roles: list, id: str, **_) -> dict:
    """Correctif proposé, avec effort et réduction de risque (EF-41)."""
    del roles
    return lire_ou_erreur(api, "correctifs", id, tenant)


def autoriser_correctif(api: Any, tenant: str, roles: list, id: str,
                        corps: dict, **_) -> dict:
    """Accord humain, application, rejeu et contrôles en un geste (EF-42/43)."""
    from piege.correctifs.boucle import boucle_complete

    exiger_role(roles, ["commanditaire", "analyste"], "autoriser un correctif")
    brut = lire_ou_erreur(api, "correctifs", id, tenant)
    correctif = depuis_dict(Correctif, brut)
    finding = depuis_dict(Finding, lire_ou_erreur(api, "findings",
                                                  correctif.finding_id, tenant))
    contexte = _contexte_execution(api, tenant, finding, corps)
    auteur = str((corps or {}).get("auteur", roles[0] if roles else ""))
    role = str((corps or {}).get("role", roles[0] if roles else ""))
    propositions = [correctif]
    bilan = boucle_complete(
        finding, contexte["cible"], contexte["mandat"], contexte["graine"],
        auteur=auteur, role=role, technique=contexte["technique"],
        journal=contexte["journal"], entrepot=api.entrepot,
        fournisseur=api.fournisseur, juge=api.juge,
        faux_refus_avant=contexte["faux_refus_avant"],
        faux_refus_apres=contexte["faux_refus_apres"],
        propositions=propositions)
    _persister(api, tenant, finding, bilan.correctif, bilan.preuve)
    return {"finding": finding.vers_dict(),
            "correctif": bilan.correctif.vers_dict() if bilan.correctif else None,
            "ferme": bilan.ferme, "autorise": bilan.autorise,
            "applique": bilan.applique, "effet_de_bord": bilan.effet_de_bord,
            "regressions": bilan.regressions, "ligne": bilan.ligne,
            "motifs": bilan.motifs,
            "preuve": bilan.preuve.vers_dict() if bilan.preuve else None}


def _contexte_execution(api: Any, tenant: str, finding: Finding,
                        corps: dict) -> dict:
    """Résout mandat, cible, technique et journal pour un rejeu."""
    from piege.securite.journal import Journal

    mandat_brut = lire(api, "mandats", str((corps or {}).get("mandat_id", "")),
                       tenant)
    mandat = depuis_dict(Mandat, mandat_brut) if mandat_brut else _mandat_courant(
        api, tenant, finding)
    catalogue = _catalogue(api)
    technique = catalogue.get(finding.technique_ids[0]) if finding.technique_ids \
        else None
    cible = api.cible(finding.application_id,
                      dict((corps or {}).get("cible_spec") or {}))
    return {"mandat": mandat, "cible": cible, "technique": technique,
            "graine": int((corps or {}).get("graine", 0)),
            "journal": Journal(ecrire=getattr(api.entrepot, "ecrire_journal", None)),
            "faux_refus_avant": (corps or {}).get("faux_refus_avant"),
            "faux_refus_apres": (corps or {}).get("faux_refus_apres")}


def _mandat_courant(api: Any, tenant: str, finding: Finding) -> Optional[Mandat]:
    """Mandat de la campagne d'origine, relu depuis l'entrepôt."""
    campagne = lire(api, "campagnes", finding.campagne_id, tenant)
    if not campagne:
        return None
    brut = lire(api, "mandats", campagne.get("mandat_id", ""), tenant)
    return depuis_dict(Mandat, brut) if brut else None


def _persister(api: Any, tenant: str, finding: Finding,
               correctif: Optional[Correctif], preuve: Any) -> None:
    """Écrit l'état final de la découverte, du correctif et de la preuve."""
    if preuve is not None:
        ecrire(api, "preuves", preuve.vers_dict())
    if correctif is not None:
        ecrire(api, "correctifs", correctif.vers_dict())
    ecrire(api, "findings", finding.vers_dict())
    api.entrepot.ecrire_journal({
        "qui": "api", "quoi": "boucle_correction", "tenant": tenant,
        "details": {"finding": finding.id, "statut": finding.statut.value,
                    "correctif": correctif.id if correctif else "",
                    "preuve": preuve.id if preuve else "",
                    "date": maintenant_utc()}, "marqueur": "trafic_reel"})


def rejouer_finding(api: Any, tenant: str, roles: list, id: str,
                    corps: dict, **_) -> dict:
    """Rejoue la technique d'origine depuis une découverte (EF-54, R19)."""
    from piege.correctifs.rejeu import est_ferme, rejouer

    exiger_role(roles, ["analyste", "commanditaire"], "rejouer une découverte")
    brut = lire_ou_erreur(api, "findings", id, tenant)
    finding = depuis_dict(Finding, brut)
    contexte = _contexte_execution(api, tenant, finding, corps)
    campagne = Campagne(id="CMP-REJEU-%s" % id.split("-")[-1],
                        mandat_id=contexte["mandat"].id if contexte["mandat"] else "",
                        application_id=finding.application_id, tenant_id=tenant,
                        type=TypeCampagne.REJEU, graine=contexte["graine"],
                        statut=StatutCampagne.EN_COURS, debutee_le=maintenant_utc())
    execution, preuve = rejouer(finding, contexte["cible"], contexte["mandat"],
                                contexte["graine"], technique=contexte["technique"],
                                campagne=campagne, fournisseur=api.fournisseur,
                                juge=api.juge, entrepot=api.entrepot)
    ecrire(api, "preuves", preuve.vers_dict())
    return {"execution": execution.vers_dict(), "preuve": preuve.vers_dict(),
            "bloque": est_ferme(execution),
            "statut_finding": finding.statut.value
            if finding.statut is StatutFinding.FERME else "ouvert"}


ROUTES = [
    ("GET", "/findings", lister_findings),
    ("GET", "/findings/{id}", lire_finding),
    ("POST", "/findings/{id}/correctifs", proposer_correctifs),
    ("POST", "/findings/{id}/rejouer", rejouer_finding),
    ("GET", "/correctifs/{id}", lire_correctif),
    ("POST", "/correctifs/{id}/autoriser", autoriser_correctif),
]
