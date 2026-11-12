"""Piège — chaîne de preuves : un élément vérifiable par étape de campagne.

Une campagne ne se résume pas à un chiffre. Chaque étape de la chaîne (mandat
signé, périmètre, attaque, jugement, découverte, correctif, rejeu, limites)
laisse **un élément de preuve** : ce qui a été fait, la source où le vérifier,
et l'empreinte de la trace qui le fonde. Rien n'est affirmé sans trace :
l'empreinte est recalculable à partir de l'enregistrement d'origine, la
citation est verbatim.

La chaîne est **dérivée** de ce qui est déjà stocké (campagne, exécutions,
découvertes, correctifs, preuves de rejeu) : elle ne modifie rien, n'invente
aucune étape et ne comble aucun vide. Une étape sans trace n'apparaît pas — un
verdict non statué ne laisse pas de preuve de jugement.
"""

from __future__ import annotations

from typing import Any, Optional

from piege.rapport.traductions import traduire
from piege.types import canonical, empreinte

__all__ = ["chaines_preuves", "chaines_depuis_entrepot", "rendu_preuves",
           "ETAPES"]

# Ordre de la chaîne : du cadre légal à la limite constatée.
ETAPES = ("mandat", "perimetre", "attaque", "jugement", "decouverte",
          "correctif", "rejeu", "limites")
_LONGUEUR = 160


def _valeur(valeur: Any) -> str:
    """Valeur d'énumération ou de texte, en clair."""
    if valeur is None:
        return ""
    return getattr(valeur, "value", None) or str(valeur)


def _court(texte: str) -> str:
    """Extrait borné, sur une seule ligne."""
    return (texte or "").replace("\n", " ").strip()[:_LONGUEUR]


def _element(etape: str, statut: str, preuve: str, source: str,
             trace: Any) -> dict:
    """Élément de preuve : statut, extrait, source et empreinte de la trace."""
    return {"etape": etape, "statut": _valeur(statut),
            "preuve": _court(preuve), "source": _court(source),
            "empreinte": empreinte(canonical(trace))}


def _mandat(campagne, mandat) -> list:
    """Preuve du cadre : le mandat signé qui a autorisé l'exécution."""
    if mandat is None:
        return []
    return [_element("mandat", mandat.statut,
                     "mandat signé le %s — périmètre : %s"
                     % (mandat.signe_le, ", ".join(mandat.perimetre_techniques)),
                     mandat.id, mandat.vers_dict())]


def _perimetre(campagne) -> list:
    """Preuve de couverture : ce qui était prévu, ce qui a été exécuté."""
    prevues = list(campagne.techniques_prevues or [])
    executees = list(campagne.techniques_executes or [])
    manque = [t for t in prevues if t not in executees]
    if not prevues:
        statut = "vide"
    elif not manque:
        statut = "complet"
    else:
        statut = "partiel"
    preuve = "%d/%d technique(s) exécutée(s)" % (len(executees), len(prevues))
    if manque:
        preuve += " — non exécutées : %s" % ", ".join(manque)
    return [_element("perimetre", statut, preuve, campagne.id,
                     {"prevues": prevues, "executes": executees})]


def _attaques(executions) -> list:
    """Preuve de l'attaque : sonde envoyée et réponse obtenue."""
    elements = []
    for execution in executions:
        sonde = (execution.sondes_envoyees or [""])[0]
        elements.append(_element(
            "attaque", execution.statut,
            "sonde : %s → réponse : %s" % (_court(sonde), _court(execution.reponse_brute)),
            execution.id, execution.vers_dict()))
    return elements


def _jugements(executions) -> list:
    """Preuve du jugement : verdict, citation et confiance.

    Une exécution **non statuée** (juge indisponible) ne laisse pas de preuve
    de jugement : on ne prouve rien par une absence de mesure.
    """
    elements = []
    for execution in executions:
        verdict = getattr(execution.verdict, "value", None) or execution.verdict
        if not verdict:
            continue
        elements.append(_element(
            "jugement", verdict,
            execution.citation or execution.motif,
            execution.id,
            {"verdict": _valeur(verdict), "impact": execution.impact,
             "confiance": execution.confiance, "citation": execution.citation,
             "garde_fou_declenche": execution.garde_fou_declenche}))
    return elements


def _decouvertes(findings) -> list:
    """Preuve des découvertes : sévérité, titre et statut de la faille."""
    return [_element("decouverte", finding.statut,
                     "%s — %s" % (_valeur(finding.severite), finding.titre),
                     finding.id, finding.vers_dict())
            for finding in findings]


def _correctifs(correctifs) -> list:
    """Preuve des correctifs : contenu, statut et auteur de l'autorisation."""
    return [_element("correctif", correctif.statut,
                     "%s — %s" % (_valeur(correctif.type), correctif.contenu),
                     correctif.id, correctif.vers_dict())
            for correctif in correctifs]


def _rejeux(preuves) -> list:
    """Preuve de rejeu : la trace immuable qui fonde une fermeture."""
    return [_element("rejeu", "preuve", preuve.verbatim, preuve.id,
                     preuve.vers_dict())
            for preuve in preuves]


def _limites(campagne) -> list:
    """Preuve des limites : ce qui a interrompu la campagne, ou rien."""
    arrets = list(campagne.arrets or [])
    return [_element("limites", "limite" if arrets else "aucune",
                     "; ".join(arrets) or "aucune interruption",
                     campagne.id, {"arrets": arrets})]


def chaines_preuves(campagne, executions, findings, correctifs=None,
                    preuves=None, mandat=None) -> list:
    """Construit la chaîne de preuves d'une campagne (une preuve par étape)."""
    elements = []
    elements += _mandat(campagne, mandat)
    elements += _perimetre(campagne)
    elements += _attaques(executions)
    elements += _jugements(executions)
    elements += _decouvertes(findings)
    elements += _correctifs(correctifs or [])
    elements += _rejeux(preuves or [])
    elements += _limites(campagne)
    ordre = {etape: rang for rang, etape in enumerate(ETAPES)}
    return sorted(elements, key=lambda e: (ordre.get(e["etape"], len(ordre)),
                                           e["source"]))


def chaines_depuis_entrepot(entrepot: Any, campagne_id: str,
                            tenant: str) -> list:
    """Construit la chaîne depuis l'entrepôt (campagne, exécutions, trouvailles)."""
    from piege.types import (Campagne, Correctif, Execution, Finding, Mandat,
                             Preuve, depuis_dict)

    brut = entrepot.lire("campagnes", campagne_id, tenant_id=tenant)
    if not brut:
        return []
    campagne = depuis_dict(Campagne, brut)
    executions = [depuis_dict(Execution, e) for e in
                  entrepot.lister("executions", tenant_id=tenant,
                                  campagne_id=campagne_id)]
    findings = [depuis_dict(Finding, f) for f in
                entrepot.lister("findings", tenant_id=tenant,
                                campagne_id=campagne_id)]
    correctifs = []
    for finding in findings:
        for identifiant in finding.correctif_ids or []:
            record = entrepot.lire("correctifs", identifiant, tenant_id=tenant)
            if record:
                correctifs.append(depuis_dict(Correctif, record))
    preuves = [depuis_dict(Preuve, p) for p in
               entrepot.lister("preuves", tenant_id=tenant,
                               campagne_id=campagne_id)]
    mandat_brut = entrepot.lire("mandats", campagne.mandat_id, tenant_id=tenant)
    mandat = depuis_dict(Mandat, mandat_brut) if mandat_brut else None
    return chaines_preuves(campagne, executions, findings, correctifs, preuves,
                           mandat)


def rendu_preuves(chain, langue: str = "fr") -> str:
    """Rend la chaîne de preuves en tableau Markdown (FR/EN)."""
    if not chain:
        return ""
    t = lambda cle: traduire(cle, langue)                     # noqa: E731
    lignes = ["## %s" % t("preuves"), "", t("preuves_intro"), "",
              "| %s | %s | %s | %s | %s |" % (t("etape"), t("statut"),
                                              t("preuve"), t("source"),
                                              t("empreinte")),
              "|---|---|---|---|---|"]
    for element in chain:
        lignes.append("| %s | %s | %s | %s | `%s` |" % (
            element["etape"], _cellule(element["statut"]),
            _cellule(element["preuve"]), _cellule(element["source"]),
            element["empreinte"].replace("sha256:", "")[:16]))
    return "\n".join(lignes)


def _cellule(texte: str) -> str:
    """Cellule Markdown : une ligne, sans caractère de séparation."""
    return (texte or "").replace("|", "\\|").replace("\n", " ").strip()
