"""Piège — événements notifiables et construction des messages (#84).

Les notifications réduisent le délai de fermeture (KPI-3) : un finding critique
doit atteindre la bonne personne en secondes, pas au prochain rapport. Ce module
définit les événements et construit un message **normalisé** (indépendant du
canal) ; Slack et Teams ne font que le projeter dans leur format.

Aucune donnée sensible dans le message : titre, sévérité, identifiants et un
lien vers le portail. La citation d'un finding n'est jamais envoyée sur un
canal de messagerie (minimisation, comme pour le journal).
"""

from __future__ import annotations

from typing import Optional

__all__ = ["EVENEMENTS", "construire", "TITRES", "SEVERITES_VISUELLES"]

EVENEMENTS = ("finding_critique", "approbation_demandee", "correctif_autorise",
              "correctif_applique", "campagne_terminee", "arret_urgence",
              "effet_de_bord", "regression")

TITRES = {
    "finding_critique": {"fr": "Découverte critique", "en": "Critical finding"},
    "approbation_demandee": {"fr": "Correctif en attente d'accord",
                             "en": "Fix awaiting approval"},
    "correctif_autorise": {"fr": "Correctif autorisé", "en": "Fix approved"},
    "correctif_applique": {"fr": "Correctif appliqué", "en": "Fix applied"},
    "campagne_terminee": {"fr": "Campagne terminée", "en": "Campaign complete"},
    "arret_urgence": {"fr": "Arrêt d'urgence", "en": "Emergency stop"},
    "effet_de_bord": {"fr": "Effet de bord détecté", "en": "Side effect detected"},
    "regression": {"fr": "Régression détectée", "en": "Regression detected"},
}

# Sévérité visuelle par événement, pour la couleur du message.
SEVERITES_VISUELLES = {
    "finding_critique": "critique", "arret_urgence": "critique",
    "regression": "eleve", "effet_de_bord": "eleve",
    "approbation_demandee": "moyen", "correctif_autorise": "moyen",
    "correctif_applique": "faible", "campagne_terminee": "faible",
}

_COULEURS = {"critique": "#d4351c", "eleve": "#f4772c", "moyen": "#ffc838",
             "faible": "#00703c"}


def construire(evenement: str, donnees: Optional[dict] = None,
               langue: str = "fr", base_url: str = "") -> dict:
    """Construit un événement normalisé, prêt à projeter sur un canal.

    `donnees` porte les identifiants (finding_id, campagne_id, correctif_id,
    application_id, tenant_id) — jamais de citation ni de contenu de preuve.
    """
    if evenement not in EVENEMENTS:
        raise ValueError("événement inconnu : %r (attendu %s)"
                         % (evenement, list(EVENEMENTS)))
    donnees = dict(donnees or {})
    cle = (evenement, langue if langue in ("fr", "en") else "fr")
    titre = TITRES[evenement].get(cle[1], TITRES[evenement]["fr"])
    severite = SEVERITES_VISUELLES.get(evenement, "faible")
    return {
        "type": evenement,
        "titre": titre,
        "texte": _texte(evenement, donnees, langue),
        "severite": severite,
        "couleur": _COULEURS.get(severite, _COULEURS["faible"]),
        "lien": _lien(evenement, donnees, base_url),
        "donnees": {k: v for k, v in donnees.items()
                    if k in ("finding_id", "campagne_id", "correctif_id",
                             "application_id", "tenant_id", "severite")},
    }


def _texte(evenement: str, donnees: dict, langue: str) -> str:
    """Corps court du message, sans donnée sensible."""
    fr = langue != "en"
    ident = donnees.get("finding_id") or donnees.get("campagne_id") \
        or donnees.get("correctif_id") or ""
    gabarits = {
        "finding_critique": ("Découverte {i} : sévérité critique, correctif à "
                             "étudier.", "Finding {i}: critical severity, fix needed."),
        "approbation_demandee": ("Correctif {i} en attente d'un accord humain "
                                 "explicite.", "Fix {i} awaits explicit human approval."),
        "correctif_autorise": ("Correctif {i} autorisé, application en cours.",
                               "Fix {i} approved, applying."),
        "correctif_applique": ("Correctif {i} appliqué, rejeu de l'attaque en "
                               "cours.", "Fix {i} applied, replaying the attack."),
        "campagne_terminee": ("Campagne {i} terminée.", "Campaign {i} complete."),
        "arret_urgence": ("Arrêt d'urgence déclenché sur {i}.",
                          "Emergency stop triggered on {i}."),
        "effet_de_bord": ("Effet de bord sur {i} : faux refus en hausse.",
                          "Side effect on {i}: false refusals increased."),
        "regression": ("Régression sur {i} : une faille fermée s'est rouverte.",
                       "Regression on {i}: a closed finding reopened."),
    }
    fr_txt, en_txt = gabarits[evenement]
    return (fr_txt if fr else en_txt).format(i=ident or "—")


def _lien(evenement: str, donnees: dict, base_url: str) -> str:
    """Lien profond vers le portail (approbation d'un clic, spécification §84)."""
    if not base_url:
        return ""
    if evenement in ("approbation_demandee", "correctif_autorise",
                     "correctif_applique") and donnees.get("correctif_id"):
        return "%s/#correctif/%s" % (base_url.rstrip("/"), donnees["correctif_id"])
    if donnees.get("finding_id"):
        return "%s/#finding/%s" % (base_url.rstrip("/"), donnees["finding_id"])
    if donnees.get("campagne_id"):
        return "%s/#campagne/%s" % (base_url.rstrip("/"), donnees["campagne_id"])
    return base_url.rstrip("/") + "/"
