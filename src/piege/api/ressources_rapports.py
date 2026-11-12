"""Piège — routes de restitution : rapport, attestation, tendances, budget, santé.

Le rapport est le livrable client : il affiche **côte à côte** ce qui fuit et ce
qui est cassé (spécification §13.3), en français ou en anglais (EF-51), et il
dit toujours ce qui n'a pas pu être testé et pourquoi (§21.5). L'attestation
destinée à un tiers est volontairement pauvre : aucun extrait exploitable
(EF-53).
"""

from __future__ import annotations

from typing import Any, Optional

from piege.api.aides import exiger_role, lire, lire_ou_erreur
from piege.observabilite import PROJECTION_ANNEXE_F, budget_restant, ecart_projection
from piege.rapport.attestation import attestation
from piege.rapport.preuves import chaines_depuis_entrepot
from piege.rapport.rapport import rapport_depuis_entrepot
from piege.types import Campagne, depuis_dict, maintenant_utc

__all__ = ["ROUTES", "lire_rapport", "lire_attestation", "lire_tendances",
           "lire_budget", "sante"]


def lire_rapport(api: Any, tenant: str, roles: list, campagne_id: str,
                 requete: Optional[dict] = None, **_) -> dict:
    """Rapport complet d'une campagne, en français ou en anglais (R15).

    La réponse porte aussi la **chaîne de preuves** (une trace vérifiable par
    étape) : le client n'a pas à lire le Markdown pour savoir ce qui a été
    fait et où le vérifier.
    """
    del roles
    requete = requete or {}
    langue = str(requete.get("langue", "fr")).lower()
    if langue not in ("fr", "en"):
        langue = "fr"
    lire_ou_erreur(api, "campagnes", campagne_id, tenant)
    chain = chaines_depuis_entrepot(api.entrepot, campagne_id, tenant)
    texte = rapport_depuis_entrepot(api.entrepot, campagne_id, tenant, langue,
                                    preuves=chain)
    return {"campagne_id": campagne_id, "langue": langue, "format": "markdown",
            "rapport": texte, "genere_le": maintenant_utc(), "preuves": chain}


def lire_attestation(api: Any, tenant: str, roles: list, id: str,
                     requete: Optional[dict] = None, **_) -> dict:
    """Attestation datée pour un tiers : pauvre en détails, sans extrait (R16)."""
    exiger_role(roles, ["commanditaire", "analyste"], "générer une attestation")
    requete = requete or {}
    langue = str(requete.get("langue", "fr")).lower()
    campagne = lire_ou_erreur(api, "campagnes", id, tenant)
    findings = api.entrepot.lister("findings", tenant_id=tenant, campagne_id=id)
    texte = attestation(depuis_dict(Campagne, campagne), findings, langue)
    api.entrepot.ecrire_journal({"qui": "api", "quoi": "attestation_generee",
                                 "tenant": tenant,
                                 "details": {"campagne": id, "langue": langue},
                                 "marqueur": "trafic_reel"})
    return {"campagne_id": id, "langue": langue, "attestation": texte,
            "date": maintenant_utc()}


def lire_tendances(api: Any, tenant: str, roles: list, application_id: str,
                   **_) -> dict:
    """Taux de contournement et taux de faux refus, campagne après campagne (EF-52)."""
    del roles
    campagnes = api.entrepot.lister("campagnes", tenant_id=tenant,
                                    application_id=application_id)
    points = []
    for brut in sorted(campagnes, key=lambda c: c.get("debutee_le", "")):
        executions = api.entrepot.lister("executions", tenant_id=tenant,
                                         campagne_id=brut["id"])
        refus = api.entrepot.lister("faux_refus", tenant_id=tenant,
                                    campagne_id=brut["id"])
        points.append(_point(brut, executions, refus))
    return {"application_id": application_id, "points": points,
            "dernier": points[-1] if points else None}


def _point(campagne: dict, executions: list, faux_refus: list) -> dict:
    """Un point de tendance : contournement, faux refus, coût mesuré."""
    executees = [e for e in executions if e.get("statut") == "execute"]
    reussies = [e for e in executees if e.get("verdict") == "reussi"]
    ouverts = [e for e in executees if e.get("verdict") != "reussi"]
    return {
        "campagne_id": campagne.get("id"),
        "date": campagne.get("debutee_le", ""),
        "statut": campagne.get("statut"),
        "techniques_executes": len(executees),
        "techniques_reussies": len(reussies),
        "taux_de_contournement": round(len(reussies) / len(executees), 4)
        if executees else 0.0,
        "faux_refus": len(faux_refus),
        "refus_par_garde_fou": len(ouverts),
        "cout_mesure": float(campagne.get("cout_mesure", 0.0)),
        "appels": int(campagne.get("appels", 0)),
        "jetons": int(campagne.get("jetons", 0)),
    }


def lire_budget(api: Any, tenant: str, roles: list, **_) -> dict:
    """Coût mesuré par campagne et par tenant (EF-63, KPI-7, ENF-10)."""
    del roles
    campagnes = api.entrepot.lister("campagnes", tenant_id=tenant)
    lignes = []
    total = 0.0
    for brut in sorted(campagnes, key=lambda c: c.get("debutee_le", "")):
        campagne = depuis_dict(Campagne, brut)
        cout = float(brut.get("cout_mesure", 0.0))
        total += cout
        lignes.append({"campagne_id": campagne.id, "date": campagne.debutee_le,
                       "appels": campagne.appels, "jetons": campagne.jetons,
                       "cout_mesure": cout,
                       "ecart": ecart_projection(cout)["ecart_relatif"]})
    return {"tenant_id": tenant, "campagnes": lignes,
            "cout_total": round(total, 4),
            "projection_annexe_f": PROJECTION_ANNEXE_F,
            "budget": [budget_restant(depuis_dict(Campagne, c))
                       for c in campagnes[-3:]]}


def sante(api: Any, tenant: str, roles: list, **_) -> dict:
    """État du service : campagne en cours, budget restant, arrêt d'urgence."""
    del roles
    from piege.moteur.arret import RECORDS

    campagnes = api.entrepot.lister("campagnes", tenant_id=tenant)
    en_cours = [c for c in campagnes if c.get("statut") in ("en_cours", "suspendue")]
    arrets = {cle: valeur.etat() for cle, valeur in RECORDS.items() if valeur.actif}
    return {"statut": "ok", "service": "piege", "version": "0.1.0",
            "campagnes": len(campagnes), "en_cours": len(en_cours),
            "campagnes_en_cours": [c.get("id") for c in en_cours],
            "arrets_urgence": arrets,
            "dernier_budget": budget_restant(depuis_dict(Campagne, campagnes[-1]))
            if campagnes else None,
            "horloge": maintenant_utc(),
            "dernier_mandat": _dernier_mandat(api, tenant)}


def _dernier_mandat(api: Any, tenant: str) -> Optional[dict]:
    """Dernier mandat du tenant et sa validité courante."""
    from piege.securite import mandats as mandats_module
    from piege.types import Mandat

    mandats = api.entrepot.lister("mandats", tenant_id=tenant)
    if not mandats:
        return None
    dernier = sorted(mandats, key=lambda m: m.get("signe_le", ""))[-1]
    mandat = depuis_dict(Mandat, dernier)
    return {"id": mandat.id, "statut": mandat.statut.value,
            "valide": not mandats_module.est_expire(mandat),
            "fenetre_fin": mandat.fenetre_fin}


ROUTES = [
    ("GET", "/rapports/{campagne_id}", lire_rapport),
    ("GET", "/attestations/{id}", lire_attestation),
    ("GET", "/tendances/{application_id}", lire_tendances),
    ("GET", "/budget", lire_budget),
    ("GET", "/health", sante),
]
