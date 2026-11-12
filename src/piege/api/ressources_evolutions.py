"""Piège — routes exposant les évolutions : risque, CVSS, scanner, corpus, benchmark, juge.

Ces routes rendent visibles dans le portail les capacités ajoutées par les
évolutions #26/#28/#36/#38/#41/#50/#56. Comme le reste de l'API : identité par
jeton, tenant jamais en paramètre, réponses `{"donnees": …}` / `{"erreur": …}`,
bibliothèque standard uniquement.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.api.aides import exiger_role, lire_ou_erreur
from piege.types import Finding, depuis_dict

__all__ = ["ROUTES", "risque_application", "scanner_document_route",
           "generer_corpus_route", "benchmark_route", "etalonner_juge"]

# Pool de référence synthétique pour la démonstration du benchmark : en
# production il est alimenté par les scores anonymisés de tous les tenants.
# Valeurs volontairement réparties pour que le percentile soit parlant.
POOL_REFERENCE = {
    "finance": [18, 25, 31, 38, 44, 52, 61, 70],
    "sante": [22, 29, 35, 41, 48, 55, 63, 74],
    "rh": [12, 20, 27, 33, 40, 47, 58, 66],
    "retail": [25, 33, 40, 47, 55, 62, 71, 80],
    "industrie": [20, 28, 36, 43, 50, 59, 67, 76],
    "public": [16, 24, 30, 37, 45, 53, 60, 69],
    "services": [21, 30, 38, 45, 52, 60, 68, 77],
    "tech": [10, 17, 24, 30, 37, 45, 54, 62],
    "autre": [20, 28, 35, 42, 50, 57, 65, 73],
}

# Jeu d'étalonnage de démonstration : 100 verdicts étiquetés (spécification §24).
# ~88 % d'accord, avec des faux négatifs et positifs de confiance faible, pour
# montrer que le seuil recommandé écarte les verdicts peu sûrs.
def _jeu_etalonnage_demo() -> list[dict]:
    exemples = []
    for i in range(78):
        exemples.append({"verdict": "reussi", "confiance": 0.93, "etiquette": "reussi"})
    for i in range(10):
        exemples.append({"verdict": "echoue", "confiance": 0.9, "etiquette": "echoue"})
    for i in range(6):
        exemples.append({"verdict": "echoue", "confiance": 0.42, "etiquette": "reussi"})
    for i in range(6):
        exemples.append({"verdict": "reussi", "confiance": 0.38, "etiquette": "echoue"})
    return exemples


def risque_application(api: Any, tenant: str, roles: list, application_id: str,
                       **_) -> dict:
    """Score de risque agrégé + vector CVSS-IA par découverte (#36, #38)."""
    from piege.severite_risque import cvss_ia, score_risque_application

    del roles
    bruts = api.entrepot.lister("findings", tenant_id=tenant,
                                application_id=application_id)
    findings = [depuis_dict(Finding, b) for b in bruts]
    risque = score_risque_application(findings)
    vecteurs = []
    for finding in findings:
        cvss = cvss_ia(finding)
        vecteurs.append({"finding_id": finding.id,
                         "severite": finding.severite.value,
                         "vecteur": cvss["vecteur"],
                         "score_base": cvss["score_base"],
                         "extension": cvss["extension"]})
    return {"application_id": application_id, "risque": risque,
            "cvss": sorted(vecteurs, key=lambda v: -v["score_base"]),
            "note": "Disponibilité toujours N : Piège ne teste jamais la "
                    "disponibilité (ENF-03)."}


def scanner_document_route(api: Any, tenant: str, roles: list, corps: dict,
                           **_) -> dict:
    """Scanne un document candidat à l'indexation (#56)."""
    from piege.scanner_ingestion import scanner_document

    del api, roles
    contenu = str((corps or {}).get("contenu", ""))
    nom = str((corps or {}).get("nom", "document.md"))
    rapport = scanner_document(contenu, nom)
    resultat = rapport.vers_dict()
    resultat["tenant_id"] = tenant
    return resultat


def generer_corpus_route(api: Any, tenant: str, roles: list, corps: dict,
                         **_) -> dict:
    """Génère un corpus légitime anonymisé depuis des journaux d'usage (#50)."""
    from piege.corpus_logs import (generer_corpus, normaliser_entrees,
                                   statistiques_pii)
    from piege.erreurs import CorpusLegitimeAbsent

    exiger_role(roles, ["commanditaire", "proprietaire", "analyste"],
                "générer un corpus")
    entrees = (corps or {}).get("entrees") or []
    application_id = str((corps or {}).get("application_id", ""))
    pii = statistiques_pii(entrees)
    try:
        corpus = generer_corpus(entrees, application_id or "APP-courant", tenant)
    except CorpusLegitimeAbsent as erreur:
        return {"genere": False, "raison": erreur.message, "pii": pii,
                "entrees_recues": len(entrees),
                "demandes_uniques": len(normaliser_entrees(entrees))}
    echantillon = [d.vers_dict() for d in corpus.demandes[:8]]
    return {"genere": True, "corpus_id": corpus.id,
            "demandes": len(corpus.demandes), "pii": pii,
            "repartition_criticite": _repartition(corpus),
            "echantillon_anonymise": echantillon}


def _repartition(corpus) -> dict:
    from piege.corpus_logs.criticite import estimer_criticite  # noqa: F401

    compte = {1: 0, 2: 0, 3: 0, 4: 0}
    for demande in corpus.demandes:
        compte[demande.criticite] = compte.get(demande.criticite, 0) + 1
    return {str(k): v for k, v in compte.items()}


def benchmark_route(api: Any, tenant: str, roles: list,
                    requete: Optional[dict] = None, **_) -> dict:
    """Position anonymisée d'un score dans un pool inter-clients (#41)."""
    from piege.benchmark import Contribution, comparer, empreinte_tenant
    from piege.severite_risque import score_risque_application

    del roles
    requete = requete or {}
    secteur = str(requete.get("secteur", "autre"))
    if secteur not in POOL_REFERENCE:
        secteur = "autre"
    # Score fourni, sinon calculé depuis la dernière application du tenant.
    score = requete.get("score")
    application_id = requete.get("application_id", "")
    if score is None:
        score = _score_courant(api, tenant, application_id)
    score = int(score)
    pool = [Contribution(empreinte_tenant("ref-%d" % i), secteur, s,
                         "2026-11-01T00:00:00Z")
            for i, s in enumerate(POOL_REFERENCE[secteur])]
    resultat = comparer(score, pool, secteur)
    resultat["empreinte_tenant"] = empreinte_tenant(tenant)
    resultat["note"] = ("Pool de référence synthétique pour la démonstration ; "
                        "en production il est alimenté par les scores anonymisés "
                        "de tous les tenants du secteur.")
    return resultat


def _score_courant(api: Any, tenant: str, application_id: str) -> int:
    """Score de risque de l'application courante (0 si aucune découverte)."""
    from piege.severite_risque import score_risque_application

    if not application_id:
        return 0
    bruts = api.entrepot.lister("findings", tenant_id=tenant,
                                application_id=application_id)
    findings = [depuis_dict(Finding, b) for b in bruts]
    return score_risque_application(findings)["score"]


def etalonner_juge(api: Any, tenant: str, roles: list, corps: dict, **_) -> dict:
    """Calibre le juge sur un jeu étiqueté (#26/#28) ; jeu de démo par défaut."""
    from piege.agents.juge.calibration import (etalonner, seuil_optimal,
                                               verifier_cible)

    del api, tenant, roles
    exemples = (corps or {}).get("exemples") or _jeu_etalonnage_demo()
    cible = float((corps or {}).get("cible", 0.90))
    mesures = verifier_cible(exemples, cible)
    seuil = seuil_optimal(exemples, cible)
    return {"etalonnage": etalonner(exemples), "conformite": mesures,
            "seuil": seuil, "jeu_fourni": bool((corps or {}).get("exemples")),
            "n": len(exemples)}


ROUTES = [
    ("GET", "/risque/{application_id}", risque_application),
    ("POST", "/scanner", scanner_document_route),
    ("POST", "/corpus/generer", generer_corpus_route),
    ("GET", "/benchmark", benchmark_route),
    ("POST", "/juge/etalonner", etalonner_juge),
]
