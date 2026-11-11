"""Piège — proposition de correctifs (EF-40, EF-41).

Chaque découverte donne lieu à au moins un correctif proposé, classé par effort
et par réduction de risque. Le service **propose** quatre familles de
correctifs, mais n'en applique que deux (garde-fou et politique) : l'invite
système et le corpus du client ne sont jamais modifiés par Piège
(spécification §15, §21.6).

L'ordre de recommandation suit l'exemple de l'annexe D : d'abord ce qui supprime
la cause (retrait documentaire, réduction totale), ensuite ce qui couvre les
cas futurs (garde-fou), enfin ce qui réduit le risque partiellement (invite).
"""

from __future__ import annotations

from typing import Any, Optional

from piege.types import (Application, Correctif, Finding, StatutCorrectif,
                         TypeCorrectif, maintenant_utc)

__all__ = ["proposer", "type_correctif", "effort_et_reduction",
           "contenu_correctif", "ORDRE_REDUCTION", "SUGGESTIONS_PAR_FAMILLE"]

ORDRE_REDUCTION = {"totale": 0, "forte": 1, "partielle": 2, "faible": 3}

# Type de correctif et couple (effort 1-3, réduction) par suggestion connue.
SUGGESTIONS = {
    "retrait_documentaire": (TypeCorrectif.DOCUMENT, 1, "totale"),
    "perimetre_documentaire": (TypeCorrectif.DOCUMENT, 1, "totale"),
    "ponderation_par_autorite_de_source": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "controle_de_provenance_a_l_ingestion": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "filtrage_des_droits_a_la_reponse": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "isolation_par_identite": (TypeCorrectif.POLITIQUE, 2, "totale"),
    "filtrage_par_tenant": (TypeCorrectif.POLITIQUE, 2, "totale"),
    "journalisation_inconditionnelle": (TypeCorrectif.POLITIQUE, 1, "forte"),
    "politique_d_appel": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "politique_de_composition": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "validation_des_parametres_d_outils": (TypeCorrectif.POLITIQUE, 2, "forte"),
    "plafond_d_appels_par_demande": (TypeCorrectif.POLITIQUE, 1, "forte"),
    "separation_donnees_instructions": (TypeCorrectif.PROMPT, 2, "partielle"),
    "minimisation_de_l_invite": (TypeCorrectif.PROMPT, 2, "partielle"),
    "recadrage_de_l_invite": (TypeCorrectif.PROMPT, 2, "partielle"),
    "minimisation_des_regles_exposees": (TypeCorrectif.PROMPT, 3, "partielle"),
    "memoire_de_session_bornee": (TypeCorrectif.POLITIQUE, 2, "partielle"),
    "fenetre_de_contexto_bornee": (TypeCorrectif.POLITIQUE, 2, "partielle"),
}

# Suggestions par défaut quand le catalogue n'en porte pas pour la technique.
SUGGESTIONS_PAR_FAMILLE = {
    "injection_directe": ["separation_donnees_instructions",
                          "garde_fou_contenu"],
    "injection_indirecte": ["separation_donnees_instructions",
                            "controle_de_provenance_a_l_ingestion"],
    "extraction": ["garde_fou_extraction", "perimetre_documentaire"],
    "perimetre": ["filtrage_des_droits_a_la_reponse", "isolation_par_identite"],
    "garde_fous": ["elargissement_du_garde_fou", "garde_fou_semantique"],
    "empoisonnement_corpus": ["retrait_documentaire",
                              "ponderation_par_autorite_de_source"],
    "faux_refus": ["resserrement_du_theme", "garde_fou_contextuel"],
    "abus_fonctionnel": ["garde_fou_finalite", "plafond_d_appels_par_demande"],
}

# Garde-fous génériques : type, effort et réduction.
GARDE_FOUS_DEFAUT = (TypeCorrectif.GARDE_FOU, 1, "forte")


def type_correctif(suggestion: str) -> TypeCorrectif:
    """Type d'un correctif déduit de son identifiant de suggestion."""
    if suggestion in SUGGESTIONS:
        return SUGGESTIONS[suggestion][0]
    if suggestion.startswith("garde_fou") or suggestion.startswith("filtre"):
        return TypeCorrectif.GARDE_FOU
    if suggestion.startswith("politique") or suggestion.startswith("regle"):
        return TypeCorrectif.POLITIQUE
    if suggestion.startswith("retrait") or suggestion.startswith("perimetre"):
        return TypeCorrectif.DOCUMENT
    return TypeCorrectif.PROMPT


def effort_et_reduction(suggestion: str) -> tuple[int, str]:
    """Effort (1 à 3) et réduction de risque d'une suggestion."""
    if suggestion in SUGGESTIONS:
        return SUGGESTIONS[suggestion][1], SUGGESTIONS[suggestion][2]
    if type_correctif(suggestion) is TypeCorrectif.DOCUMENT:
        return 1, "totale"
    if type_correctif(suggestion) is TypeCorrectif.PROMPT:
        return 2, "partielle"
    return GARDE_FOUS_DEFAUT[1], GARDE_FOUS_DEFAUT[2]


def contenu_correctif(suggestion: str, finding: Finding) -> str:
    """Contenu lisible du correctif proposé, en français, actionnable."""
    type_ = type_correctif(suggestion)
    if type_ is TypeCorrectif.GARDE_FOU:
        return ("Garde-fou : bloquer toute demande relevant de « %s » "
                "(technique %s), quel que soit le contexte, avec un refus "
                "explicite et journalisé."
                % (suggestion.replace("_", " "), ", ".join(finding.technique_ids)))
    if type_ is TypeCorrectif.DOCUMENT:
        return ("Retrait documentaire : exclure du corpus indexé les documents "
                "couvrant « %s », et revoir le périmètre d'indexation pour "
                "empêcher leur retour." % suggestion.replace("_", " "))
    if type_ is TypeCorrectif.POLITIQUE:
        return ("Politique : appliquer « %s » au niveau de la passerelle, afin "
                "que la règle s'impose avant l'exécution de l'outil."
                % suggestion.replace("_", " "))
    return ("Invite système : « %s » — séparer explicitement les données des "
            "instructions. Correctif proposé, à appliquer par le client."
            % suggestion.replace("_", " "))


def _suggestions(finding: Finding, catalogue: Optional[dict]) -> list[str]:
    """Suggestions issues du catalogue, ou défauts par famille."""
    trouvees: list[str] = []
    for identifiant in finding.technique_ids:
        technique = (catalogue or {}).get(identifiant)
        if technique is not None:
            trouvees += list(technique.correctifs_suggeres)
    if not trouvees:
        famille = getattr(finding.famille, "value", str(finding.famille))
        trouvees = list(SUGGESTIONS_PAR_FAMILLE.get(famille, ["garde_fou_generique"]))
    seen: list[str] = []
    for suggestion in trouvees:
        if suggestion not in seen:
            seen.append(suggestion)
    return seen


def proposer(finding: Finding, application: Optional[Application] = None,
             catalogue: Optional[dict] = None, sequence: int = 1) -> list[Correctif]:
    """Propose les correctifs d'une découverte, triés par priorité (EF-41)."""
    del application                       # l'application n'influe pas sur l'ordre
    propositions = []
    for index, suggestion in enumerate(_suggestions(finding, catalogue)):
        type_, effort, reduction = (type_correctif(suggestion),
                                    effort_et_reduction(suggestion)[0],
                                    effort_et_reduction(suggestion)[1])
        propositions.append(Correctif(
            id="COR-%s-%02d" % (finding.id.split("-", 1)[-1], sequence + index),
            finding_id=finding.id, application_id=finding.application_id,
            tenant_id=finding.tenant_id, type=type_,
            contenu=contenu_correctif(suggestion, finding), effort=effort,
            reduction_risque=reduction, statut=StatutCorrectif.PROPOSE,
            autorise_par="", autorise_le="", applique_le="", rejoue_le=""))
    return sorted(propositions, key=_cle_de_tri)


def _cle_de_tri(correctif: Correctif) -> tuple:
    """Priorité : réduction maximale d'abord, puis effort minimal."""
    return (ORDRE_REDUCTION.get(correctif.reduction_risque, 9),
            correctif.effort, correctif.id)


def suggestion_de(correctif: Correctif) -> str:
    """Retrouve l'identifiant de suggestion depuis le contenu (traçabilité)."""
    for suggestion in list(SUGGESTIONS) + ["garde_fou_generique"]:
        if suggestion.replace("_", " ") in correctif.contenu:
            return suggestion
    return ""


def applicables(correctifs: list[Any]) -> list[Any]:
    """Correctifs que le service peut appliquer lui-même (garde-fou, politique)."""
    return [c for c in correctifs
            if c.type in (TypeCorrectif.GARDE_FOU, TypeCorrectif.POLITIQUE)]


def horodatage() -> str:
    """Horodatage courant, pour les écritures de correctifs."""
    return maintenant_utc()
