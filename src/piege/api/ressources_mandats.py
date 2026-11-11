"""Piège — routes de déclaration : mandats, applications, corpus légitime.

Ces routes matérialisent le parcours du commanditaire (spécification §10.1) :
déclarer l'application, signer le mandat, fournir le corpus de demandes
légitimes sans lequel la famille G n'est pas exécutable.
"""

from __future__ import annotations

from typing import Any

from piege.api.aides import ecrire, exiger_role, lire, lire_ou_erreur
from piege.securite import mandats as mandats_module
from piege.types import (Application, Environnement, Mandat, TypeApplication,
                         depuis_dict, maintenant_utc)

__all__ = ["ROUTES", "creer_mandat", "lire_mandat", "creer_application",
           "charger_corpus_legitime", "lister_applications"]


def creer_mandat(api: Any, tenant: str, roles: list, corps: dict, **_) -> dict:
    """Crée et signe un mandat (EF-03). Signature = accord du commanditaire."""
    exiger_role(roles, ["commanditaire", "analyste"], "créer un mandat")
    mandat = mandats_module.creer(
        tenant_id=tenant,
        application_id=str(corps.get("application_id", "")),
        perimetre_techniques=corps.get("perimetre_techniques") or [],
        environnements=[Environnement(e) for e in
                        (corps.get("environnements") or ["test"])],
        fenetre_debut=str(corps.get("fenetre_debut", "")),
        fenetre_fin=str(corps.get("fenetre_fin", "")),
        budget_appels=int(corps.get("budget_appels", 288)),
        budget_jetons=int(corps.get("budget_jetons", 2_000_000)),
        production_autorisee=bool(corps.get("production_autorisee", False)),
        contact_urgence=str(corps.get("contact_urgence", "")),
        sequence=_sequence(api, tenant, "mandats"))
    if corps.get("signer", True):
        mandats_module.signer(mandat, cle=str(corps.get("cle", "cle-de-demonstration")))
    identifiant = ecrire(api, "mandats", mandat.vers_dict())
    api.entrepot.ecrire_journal({
        "qui": "api", "quoi": "mandat_cree", "tenant": tenant,
        "details": {"mandat": identifiant, "statut": mandat.statut.value,
                    "date": maintenant_utc()}, "marqueur": "trafic_reel"})
    return {"mandat": lire(api, "mandats", identifiant, tenant),
            "statut": mandat.statut.value, "signature": mandat.signature}


def lire_mandat(api: Any, tenant: str, roles: list, id: str, **_) -> dict:
    """Lit un mandat et sa validité à l'instant courant (EF-04)."""
    del roles
    brut = lire_ou_erreur(api, "mandats", id, tenant)
    mandat = depuis_dict(Mandat, brut)
    valide = True
    motif = ""
    try:
        mandats_module.valider(mandat)
    except Exception as erreur:                             # noqa: BLE001
        valide = False
        motif = str(erreur)
    return {"mandat": brut, "valide": valide, "motif": motif,
            "expire": mandats_module.est_expire(mandat)}


def creer_application(api: Any, tenant: str, roles: list, corps: dict, **_) -> dict:
    """Déclare une application cible (EF-01)."""
    exiger_role(roles, ["commanditaire", "analyste", "proprietaire"],
                "déclarer une application")
    application = Application(
        id=str(corps.get("id") or "APP-%d" % _sequence(api, tenant, "applications")),
        tenant_id=tenant, nom=str(corps.get("nom", "")),
        type=TypeApplication(str(corps.get("type", "rag"))),
        acces=str(corps.get("acces", "")), modele=str(corps.get("modele", "")),
        environnement=Environnement(str(corps.get("environnement", "test"))),
        exposition=int(corps.get("exposition", 2)),
        corpus_ref=str(corps.get("corpus_ref", "")),
        garde_fous=list(corps.get("garde_fous") or []),
        depot_document_autorise=bool(corps.get("depot_document_autorise", False)))
    identifiant = ecrire(api, "applications", application.vers_dict())
    return lire(api, "applications", identifiant, tenant)


def lister_applications(api: Any, tenant: str, roles: list, **_) -> list:
    """Liste les applications du tenant."""
    del roles
    return api.entrepot.lister("applications", tenant_id=tenant)


def charger_corpus_legitime(api: Any, tenant: str, roles: list,
                            corps: dict, **_) -> dict:
    """Charge le corpus de demandes légitimes (EF-30) et le valide."""
    from piege.familles.faux_refus.corpus import depuis_donnees

    exiger_role(roles, ["commanditaire", "proprietaire", "analyste"],
                "charger un corpus légitime")
    donnees = dict(corps)
    donnees["tenant_id"] = tenant
    donnees.setdefault("charge_le", maintenant_utc())
    corpus = depuis_donnees(donnees)
    identifiant = ecrire(api, "corpus_legitimes", {
        "id": corpus.id, "tenant_id": tenant,
        "application_id": corpus.application_id, "source": corpus.source,
        "charge_le": corpus.charge_le,
        "demandes": [d.vers_dict() for d in corpus.demandes]})
    return {"id": identifiant, "demandes": len(corpus.demandes),
            "criticites": _repartition(corpus)}


def _repartition(corpus) -> dict:
    from piege.familles.faux_refus.corpus import repartition

    return {str(c): n for c, n in repartition(corpus).items()}


def _sequence(api: Any, tenant: str, table: str) -> int:
    """Prochain numéro de séquence d'un tenant pour une table."""
    return len(api.entrepot.lister(table, tenant_id=tenant)) + 1


ROUTES = [
    ("POST", "/mandats", creer_mandat),
    ("GET", "/mandats/{id}", lire_mandat),
    ("POST", "/applications", creer_application),
    ("GET", "/applications", lister_applications),
    ("POST", "/corpus-legitimes", charger_corpus_legitime),
]
