"""Piège — projection de la politique locale sur AgentCore Policy.

La référence normative reste l'évaluateur local (`securite.politique`) : c'est
lui qui est testé, versionné et rejouable. Ce module (a) exporte la politique
sous une forme déclarative projetable sur AgentCore Policy, et (b) permet de
**vérifier la concordance** entre la décision distante et la décision locale.

Point ouvert du chapitre 31 (§31, point 6) : la syntaxe exacte des politiques
AgentCore doit être confirmée en S1. L'export produit donc une structure
neutre (règles nommées, faits requis, effet) plutôt qu'un texte supposé
conforme ; la traduction finale est une fonction à part, documentée comme
telle, et les règles Cedar de `galons` servent de précédent.
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import FournisseurIndisponible
from piege.securite import politique
from piege.types import Decision

__all__ = ["exporter_regles", "exporter_politique", "traduire_cedar",
           "AdaptateurAgentCore"]

DESCRIPTION_REGLES = {
    "mandat.statut": "exiger mandat.statut == valide",
    "mandat.fenetre": "exiger mandat.fenetre contient maintenant()",
    "perimetre.application": "exiger cible.id dans mandat.applications",
    "perimetre.technique": "exiger technique.id dans mandat.techniques",
    "perimetre.environnement": "exiger cible.environnement dans mandat.environnements",
    "perimetre.technique.environnement":
        "exiger technique.environnement contient cible.environnement",
    "production.catalogue": "interdire technique.production == jamais",
    "production.mandat": "exiger mandat.production_autorisee == vrai",
    "budget.appels": "exiger campagne.appels_restants > 0",
    "budget.jetons": "exiger campagne.jetons_restants > technique.budget_jetons",
    "arret.urgence": "interdire arret_urgence.actif == vrai",
    "correctif.autorisation": "exiger correctif.autorisation_humaine == vrai",
    "correctif.role":
        "exiger correctif.autorise_par dans roles[commanditaire, analyste]",
    "correctif.type": "exiger correctif.type dans [garde_fou, politique]",
    "depot.index": "exiger index.cible == index_de_test",
}


def exporter_regles() -> list[dict]:
    """Liste ordonnée des règles : identifiant, exigence, effet."""
    return [
        {"ordre": ordre, "regle": identifiant, "exigence": exigence,
         "effet": "refuser et journaliser"}
        for ordre, (identifiant, exigence) in enumerate(DESCRIPTION_REGLES.items())
    ]


def exporter_politique(outils: Optional[tuple] = None) -> dict:
    """Politique complète exportable : outils couverts, règles, faits requis."""
    return {
        "version": "1.0",
        "outils": list(outils or politique.OUTILS_CIBLE
                       + (politique.OUTIL_GARDE_APPLIQUE,)),
        "regles": exporter_regles(),
        "faits_requis": sorted({
            "mandat_statut", "mandat_debut", "mandat_fin", "maintenant",
            "cible_id", "mandat_application_id", "technique_id",
            "mandat_techniques", "technique_environnement",
            "cible_environnement", "mandat_environnements",
            "technique_production", "production_autorisee",
            "campagne_appels_restants", "campagne_jetons_restants",
            "arret_urgence", "correctif_autorisation_humaine",
            "correctif_autorise_par", "correctif_type", "index_cible",
            "index_de_test", "depot_production",
        }),
        "principe": "les règles sont appliquées par la passerelle, jamais par "
                    "l'invite de l'agent",
    }


def traduire_cedar(politique_exportee: Optional[dict] = None) -> str:
    """Traduction textuelle indicative (syntaxe à confirmer en S1)."""
    export = politique_exportee or exporter_politique()
    lignes = ["// Piège — politique de périmètre (projection AgentCore Policy)",
              "// Syntaxe indicative : à confirmer en S1 (chapitre 31, point 6)."]
    for regle in export["regles"]:
        lignes.append("forbid(principal, action, resource)")
        lignes.append('  when { context.%s } // %s'
                      % (regle["regle"].replace(".", "_"), regle["exigence"]))
        lignes.append("  unless { context.%s == true };" % regle["regle"].replace(".", "_"))
    return "\n".join(lignes) + "\n"


class AdaptateurAgentCore:
    """Rejoue une décision distante et vérifie sa concordance avec le local."""

    def __init__(self, client=None, region: str = "eu-west-3"):
        self._client = client
        self.region = region

    def client(self):
        """Client AgentCore (boto3 importé paresseusement, jamais en tête)."""
        if self._client is not None:
            return self._client
        try:
            import boto3                                       # noqa: PLC0415
        except ImportError as exc:
            raise FournisseurIndisponible(
                "boto3 absent : AgentCore Policy injoignable hors AWS",
                code="fournisseur_indisponible",
                details={"regle": "agentcore.client"}) from exc
        self._client = boto3.client("bedrock-agentcore", region_name=self.region)
        return self._client

    def evaluer(self, outil: str, faits: dict) -> Decision:
        """Décision distante ; `FournisseurIndisponible` sans accès AWS."""
        if self._client is None:
            self.client()
        raise FournisseurIndisponible(
            "appel distant AgentCore Policy à câbler en S1 (syntaxe à "
            "confirmer) ; la décision locale fait foi",
            code="fournisseur_indisponible", details={"regle": "agentcore.appel"})

    def verifier_concordance(self, outil: str, faits: dict,
                             distante: Optional[Decision] = None) -> dict:
        """Compare la décision locale et la décision distante (ou injouée)."""
        locale = politique.evaluer(outil, faits)
        if distante is None:
            return {"concordance": None, "locale": locale.vers_dict(),
                    "distante": None,
                    "motif": "décision distante indisponible hors AWS"}
        return {"concordance": (locale.accorde == distante.accorde
                                and locale.regle == distante.regle),
                "locale": locale.vers_dict(), "distante": distante.vers_dict()}
