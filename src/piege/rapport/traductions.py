"""Piège — tables de traduction du rapport client (FR/EN).

Tous les libellés du rapport et de l'attestation vivent ici : le corps du
rapport ne contient aucune chaîne en dur, ce qui garantit que les deux langues
sont strictement alignées (ENF-11) et qu'un test peut le vérifier.
"""

from __future__ import annotations

__all__ = ["LIBELLES", "traduire", "LANGUES"]

LANGUES = ("fr", "en")

LIBELLES = {
    "titre_rapport": {
        "fr": "Rapport de campagne — pentest continu d'application d'IA",
        "en": "Campaign report — continuous AI-application penetration test",
    },
    "titre_attestation": {
        "fr": "Attestation de test de sécurité",
        "en": "Security testing attestation",
    },
    "synthese": {"fr": "Synthèse", "en": "Executive summary"},
    "ce_qui_fuit": {"fr": "Ce qui fuit", "en": "What leaks"},
    "ce_qui_est_casse": {"fr": "Ce qui est cassé", "en": "What is broken"},
    "decouvertes": {"fr": "Découvertes", "en": "Findings"},
    "faux_refus": {"fr": "Faux refus", "en": "False refusals"},
    "taux_contournement": {"fr": "Taux de contournement", "en": "Bypass rate"},
    "techniques_executes": {"fr": "Techniques exécutées", "en": "Techniques run"},
    "techniques_reussies": {"fr": "Techniques réussies", "en": "Successful techniques"},
    "cout_mesure": {"fr": "Coût mesuré", "en": "Measured cost"},
    "appels": {"fr": "Appels", "en": "Calls"},
    "jetons": {"fr": "Jetons", "en": "Tokens"},
    "perte_totale": {"fr": "Perte estimée", "en": "Estimated loss"},
    "heures_perdues": {"fr": "Heures de traitement manuel perdues",
                       "en": "Manual processing hours lost"},
    "correctifs": {"fr": "Correctifs proposés", "en": "Proposed fixes"},
    "effort": {"fr": "Effort", "en": "Effort"},
    "reduction": {"fr": "Réduction du risque", "en": "Risk reduction"},
    "preuve": {"fr": "Preuve", "en": "Evidence"},
    "preuves": {"fr": "Chaîne de preuves", "en": "Evidence chain"},
    "preuves_intro": {
        "fr": "Chaque étape de la chaîne laisse une trace vérifiable : "
              "l'empreinte est recalculable à partir de l'enregistrement d'origine.",
        "en": "Every step of the chain leaves a verifiable trace: the fingerprint "
              "is recomputable from the source record.",
    },
    "etape": {"fr": "Étape", "en": "Step"},
    "statut": {"fr": "Statut", "en": "Status"},
    "source": {"fr": "Source", "en": "Source"},
    "empreinte": {"fr": "Empreinte", "en": "Fingerprint"},
    "ferme": {"fr": "Fermé", "en": "Closed"},
    "ouvert": {"fr": "Ouvert", "en": "Open"},
    "effet_de_bord": {"fr": "Effet de bord", "en": "Side effect"},
    "regression": {"fr": "Régression", "en": "Regression"},
    "non_teste": {"fr": "Ce qui n'a pas pu être testé", "en": "What could not be tested"},
    "motif_corpus_absent": {
        "fr": "Famille G non exécutable : aucun corpus de demandes légitimes fourni.",
        "en": "Family G not runnable: no legitimate-request corpus was provided.",
    },
    "motif_depot_absent": {
        "fr": "Famille F non exécutable : aucun droit de dépôt sur la source indexée.",
        "en": "Family F not runnable: no upload right on the indexed source.",
    },
    "motif_hors_perimetre": {
        "fr": "Techniques hors du périmètre du mandat.",
        "en": "Techniques outside the mandate scope.",
    },
    "motif_production": {
        "fr": "Techniques interdites en production par le catalogue.",
        "en": "Techniques forbidden in production by the catalogue.",
    },
    "severite_critique": {"fr": "Critique", "en": "Critical"},
    "severite_eleve": {"fr": "Élevé", "en": "High"},
    "severite_moyen": {"fr": "Moyen", "en": "Medium"},
    "severite_faible": {"fr": "Faible", "en": "Low"},
    "severite_indeterminee": {"fr": "Indéterminée (revue humaine)",
                              "en": "Undetermined (human review)"},
    "refus_bloquant": {"fr": "Bloquant", "en": "Blocking"},
    "refus_majeur": {"fr": "Majeur", "en": "Major"},
    "refus_mineur": {"fr": "Mineur", "en": "Minor"},
    "refus_nuisance": {"fr": "Nuisance", "en": "Nuisance"},
    "attestation_corps": {
        "fr": ("Le prestataire atteste avoir exécuté une campagne de test "
               "autorisée par mandat signé sur l'application désignée, dans le "
               "périmètre et la fenêtre prévus. Les résultats détaillés sont "
               "communisés au seul commanditaire."),
        "en": ("The provider attests that an authorised testing campaign was "
               "executed under a signed mandate on the designated application, "
               "within the agreed scope and window. Detailed results are "
               "disclosed to the sponsor only."),
    },
    "attestation_sans_detail": {
        "fr": "Cette attestation est volontairement dépourvue de détail exploitable.",
        "en": "This attestation is deliberately free of any actionable detail.",
    },
    "mandat": {"fr": "Mandat", "en": "Mandate"},
    "campagne": {"fr": "Campagne", "en": "Campaign"},
    "application": {"fr": "Application", "en": "Application"},
    "date": {"fr": "Date", "en": "Date"},
    "graine": {"fr": "Graine de reproductibilité", "en": "Reproducibility seed"},
    "tendance": {"fr": "Tendance", "en": "Trend"},
    "aucun_faux_refus": {
        "fr": "Aucun faux refus mesuré sur cette campagne.",
        "en": "No false refusal measured on this campaign.",
    },
    "aucune_decouverte": {
        "fr": "Aucune découverte : toutes les techniques exécutées ont échoué à "
              "contourner l'application.",
        "en": "No finding: every executed technique failed to bypass the application.",
    },
    "refus_par_garde_fou": {"fr": "Refus par garde-fou", "en": "Guardrail refusals"},
    "rejouer": {"fr": "Rejeu de l'attaque d'origine", "en": "Replay of the original attack"},
    "synthetique": {
        "fr": "Jeu de données 100 % synthétique, déclaré comme tel.",
        "en": "100% synthetic dataset, declared as such.",
    },
}


def traduire(cle: str, langue: str = "fr") -> str:
    """Libellé d'une clé dans la langue demandée (repli français)."""
    entree = LIBELLES.get(cle)
    if not entree:
        return cle
    return entree.get(langue if langue in LANGUES else "fr", cle)
