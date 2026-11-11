"""Piège — rapport client, en français et en anglais (EF-50, EF-51).

Le rapport est structuré autour du tableau qui fait signer un abonnement
(spécification §13.3) : **ce qui fuit** et **ce qui est cassé**, côte à côte. Il
dit toujours ce qui n'a pas pu être testé et pourquoi (§21.5) : un rapport qui
n'affiche que des succès est un rapport inutile.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from piege import severite
from piege.rapport.traductions import traduire
from piege.types import Campagne, Finding, FauxRefus, Severite, SeveriteRefus

__all__ = ["rapport", "rapport_depuis_entrepot", "resume", "bloc_non_teste"]

ORDRE_SEVERITE = [Severite.CRITIQUE, Severite.ELEVE, Severite.MOYEN,
                  Severite.FAIBLE, Severite.INDETERMINEE]


def resume(campagne: Campagne, findings: Iterable[Finding],
           faux_refus: Iterable[FauxRefus], executions: Optional[list] = None) -> dict:
    """Les chiffres de synthèse (KPI-1, KPI-2, KPI-5, KPI-7)."""
    findings = list(findings)
    faux_refus = list(faux_refus)
    executions = list(executions or [])
    executees = [e for e in executions if getattr(e, "statut", "execute") == "execute"]
    reussies = [e for e in executees
                if getattr(getattr(e, "verdict", None), "value", None) == "reussi"]
    ouverts = [f for f in findings if f.statut.value != "ferme"]
    return {
        "campagne_id": campagne.id,
        "techniques_executes": len(executees),
        "techniques_reussies": len(reussies),
        "taux_de_contournement": round(len(reussies) / len(executees), 4)
        if executees else 0.0,
        "findings": len(findings),
        "critiques_ouverts": len([f for f in ouverts
                                  if f.severite is Severite.CRITIQUE]),
        "ouverts": len(ouverts),
        "faux_refus": len(faux_refus),
        "perte_totale": sum(r.perte for r in faux_refus),
        "heures_perdues": round(sum(severite.heures_perdues(r.frequence_mensuelle,
                                                            r.minutes_manuelles)
                                    for r in faux_refus), 2),
        "cout_mesure": campagne.cout_mesure,
        "appels": campagne.appels,
        "jetons": campagne.jetons,
    }


def rapport(campagne: Campagne, executions: list, findings: list[Finding],
            faux_refus: list[FauxRefus], langue: str = "fr",
            application: Optional[Any] = None,
            non_testes: Optional[list] = None) -> str:
    """Rend le rapport Markdown complet d'une campagne."""
    t = lambda cle: traduire(cle, langue)                     # noqa: E731
    chiffres = resume(campagne, findings, faux_refus, executions)
    parties = [_entete(campagne, application, t),
               _synthese(chiffres, findings, faux_refus, t),
               _decouvertes(findings, t),
               _faux_refus(faux_refus, chiffres, t),
               bloc_non_teste(non_testes or [], t),
               _cout(chiffres, t)]
    return "\n\n".join(p for p in parties if p) + "\n"


def _entete(campagne: Campagne, application: Any, t) -> str:
    """En-tête : identité de la campagne et de la cible."""
    nom = getattr(application, "nom", None) or campagne.application_id
    lignes = ["# %s" % t("titre_rapport"), ""]
    for cle, valeur in (("campagne", campagne.id), ("application", nom),
                        ("mandat", campagne.mandat_id),
                        ("date", campagne.debutee_le or campagne.terminee_le),
                        ("graine", str(campagne.graine))):
        lignes.append("- **%s** : %s" % (t(cle), valeur))
    lignes.append("")
    lignes.append("_%s_" % t("synthetique"))
    return "\n".join(lignes)


def _synthese(chiffres: dict, findings: list, faux_refus: list, t) -> str:
    """Le tableau à deux colonnes : ce qui fuit, ce qui est cassé."""
    par_severite = {s.value: 0 for s in ORDRE_SEVERITE}
    for finding in findings:
        cle = finding.severite.value if hasattr(finding.severite, "value") \
            else str(finding.severite)
        par_severite[cle] = par_severite.get(cle, 0) + 1
    par_refus = {s.value: 0 for s in SeveriteRefus}
    for refus in faux_refus:
        cle = refus.severite.value if hasattr(refus.severite, "value") \
            else str(refus.severite)
        par_refus[cle] = par_refus.get(cle, 0) + 1
    lignes = ["## %s" % t("synthese"), ""]
    lignes.append("| %s | %s |" % (t("ce_qui_fuit"), t("ce_qui_est_casse")))
    lignes.append("|---|---|")
    lignes.append("| %s | %s |" % (_fuite(chiffres, par_severite, t),
                                   _casse(chiffres, par_refus, t)))
    lignes.append("")
    lignes.append("- %s : %.1f %% (%d/%d)"
                  % (t("taux_contournement"),
                     chiffres["taux_de_contournement"] * 100,
                     chiffres["techniques_reussies"],
                     chiffres["techniques_executes"]))
    return "\n".join(lignes)


def _fuite(chiffres: dict, par_severite: dict, t) -> str:
    """Colonne de gauche : les découvertes par sévérité."""
    if not chiffres["findings"]:
        return t("aucune_decouverte")
    morceaux = []
    for severite_cle in ("critique", "eleve", "moyen", "faible", "indeterminee"):
        nombre = par_severite.get(severite_cle, 0)
        if nombre:
            morceaux.append("%d %s" % (nombre, traduire("severite_" + severite_cle,
                                                        "fr" if t("synthese")
                                                        == "Synthèse" else "en")))
    return ", ".join(morceaux)


def _casse(chiffres: dict, par_refus: dict, t) -> str:
    """Colonne de droite : les faux refus et leur perte."""
    if not chiffres["faux_refus"]:
        return t("aucun_faux_refus")
    langue = "fr" if t("synthese") == "Synthèse" else "en"
    bloquants = par_refus.get("bloquant", 0)
    return ("%d %s (%d %s) — %s %d, %s %.1f h/mois"
            % (chiffres["faux_refus"], traduire("faux_refus", langue).lower(),
               bloquants, traduire("refus_bloquant", langue).lower(),
               traduire("perte_totale", langue), chiffres["perte_totale"],
               traduire("heures_perdues", langue).lower(),
               chiffres["heures_perdues"]))


def _decouvertes(findings: list[Finding], t) -> str:
    """Détail des découvertes, avec le calcul de sévérité et les correctifs."""
    if not findings:
        return ""
    lignes = ["## %s" % t("decouvertes"), ""]
    for finding in sorted(findings, key=_cle_tri):
        lignes += _finding(finding, t)
    return "\n".join(lignes)


def _cle_tri(finding: Finding) -> tuple:
    """Tri par gravité décroissante puis date."""
    index = ORDRE_SEVERITE.index(finding.severite) if finding.severite in ORDRE_SEVERITE else 9
    return (index, finding.ouvert_le)


def _finding(finding: Finding, t) -> list[str]:
    """Bloc Markdown d'une découverte."""
    langue = "fr" if t("synthese") == "Synthèse" else "en"
    severite_label = traduire("severite_" + finding.severite.value, langue)
    bloc = ["### %s — %s" % (finding.id, severite_label.upper()),
            "- %s : %s" % (t("application"), finding.application_id),
            "- Techniques : %s" % ", ".join(finding.technique_ids),
            "- Score : %s (impact %s × exploitabilité %s × exposition %s)" % (
                finding.score if finding.score is not None else "—",
                finding.impact if finding.impact is not None else "non établi",
                finding.exploitabilite if finding.exploitabilite is not None else "—",
                finding.exposition),
            "- %s : %s" % (t("preuve"), (finding.citation or "")[:200]),
            "- Statut : %s" % (t("ferme") if finding.statut.value == "ferme"
                               else t("ouvert"))]
    return bloc + [""]


def _faux_refus(faux_refus: list[FauxRefus], chiffres: dict, t) -> str:
    """Bloc faux refus : pertes chiffrées et demandes les plus coûteuses."""
    if not faux_refus:
        return "## %s\n\n%s" % (t("faux_refus"), t("aucun_faux_refus"))
    langue = "fr" if t("synthese") == "Synthèse" else "en"
    lignes = ["## %s" % t("faux_refus"), "",
              "- %s : %d" % (t("faux_refus"), chiffres["faux_refus"]),
              "- %s : %d" % (t("perte_totale"), chiffres["perte_totale"]),
              "- %s : %.1f h/mois" % (t("heures_perdues"),
                                      chiffres["heures_perdues"]), "",
              "| Demande | Criticité | Fréquence | Perte | Sévérité |", "|---|---|---|---|---|"]
    for refus in sorted(faux_refus, key=lambda r: -r.perte)[:10]:
        lignes.append("| %s | %d | %d | %d | %s |" % (
            refus.demande_id, refus.criticite_metier, refus.frequence_mensuelle,
            refus.perte, traduire("refus_" + refus.severite.value, langue)))
    return "\n".join(lignes)


def bloc_non_teste(non_testes: list, t) -> str:
    """Ce qui n'a pas pu être testé, et pourquoi (§21.5)."""
    if not non_testes:
        return ""
    lignes = ["## %s" % t("non_teste"), ""]
    for motif in non_testes:
        lignes.append("- %s" % traduire(motif, "fr" if t("synthese") == "Synthèse"
                                        else "en"))
    return "\n".join(lignes)


def _cout(chiffres: dict, t) -> str:
    """Coût mesuré de la campagne, jamais une estimation (ENF-10)."""
    return "\n".join([
        "## %s" % t("cout_mesure"), "",
        "- %s : %.4f $" % (t("cout_mesure"), chiffres["cout_mesure"]),
        "- %s : %d" % (t("appels"), chiffres["appels"]),
        "- %s : %d" % (t("jetons"), chiffres["jetons"]),
    ])


def rapport_depuis_entrepot(entrepot: Any, campagne_id: str, tenant: str,
                            langue: str = "fr") -> str:
    """Reconstruit le rapport depuis l'entrepôt (utilisé par l'API et la CLI)."""
    from piege.types import Execution, depuis_dict

    brut = entrepot.lire("campagnes", campagne_id, tenant_id=tenant)
    if not brut:
        from piege.erreurs import ErreurPiege

        raise ErreurPiege("campagne %s introuvable" % campagne_id,
                          code="introuvable", details={"regle": "rapport.campagne"})
    campagne = depuis_dict(Campagne, brut)
    executions = [depuis_dict(Execution, e) for e in
                  entrepot.lister("executions", tenant_id=tenant,
                                  campagne_id=campagne_id)]
    findings = [depuis_dict(Finding, f) for f in
                entrepot.lister("findings", tenant_id=tenant,
                                campagne_id=campagne_id)]
    faux_refus = [depuis_dict(FauxRefus, r) for r in
                  entrepot.lister("faux_refus", tenant_id=tenant,
                                  campagne_id=campagne_id)]
    return rapport(campagne, executions, findings, faux_refus, langue)
