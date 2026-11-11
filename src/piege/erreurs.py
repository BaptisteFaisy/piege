"""Piège — Hiérarchie d'erreurs et codes d'échec.

Chaque refus du moteur porte un code stable : le corps d'erreur de l'API
l'utilise tel quel (`CONTRACTS.md` §7) et le journal l'enregistre avec la
règle violée. Une erreur de domaine n'est jamais masquée par une
`Exception` générique : le code permet de distinguer « mandat expiré »,
« budget épuisé » et « hors périmètre » dans le rapport.
"""

from __future__ import annotations

__all__ = [
    "ErreurPiege", "Introuvable", "RoleInsuffisant", "MandatInvalide",
    "MandatExpire", "HorsPerimetre",
    "ProductionInterdite", "BudgetEpuise", "ArretUrgence",
    "CorpusLegitimeAbsent", "AutorisationHumaineAbsente", "ValeurHorsPlage",
    "TechniqueInconnue", "TenantInconnu", "FournisseurIndisponible",
    "CODE_HTTP",
]


class ErreurPiege(Exception):
    """Erreur de domaine du moteur Piège."""

    code = "erreur_piege"
    statut_http = 400

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}

    def vers_dict(self) -> dict:
        """Corps d'erreur API (contrat gelé)."""
        return {"erreur": {"code": self.code, "message": self.message,
                           "regle": self.details.get("regle", "")}}


class Introuvable(ErreurPiege):
    """Ressource absente du tenant courant (n'expose pas les autres tenants)."""

    code = "introuvable"
    statut_http = 404


class RoleInsuffisant(ErreurPiege):
    """Le rôle porté par le jeton n'est pas habilité pour cette action."""

    code = "role_insuffisant"
    statut_http = 403


class MandatInvalide(ErreurPiege):
    """Aucun mandat valide ne couvre l'exécution demandée."""

    code = "mandat_invalide"
    statut_http = 403


class MandatExpire(MandatInvalide):
    """Le mandat existe mais sa fenêtre de validité est fermée."""

    code = "mandat_expire"
    statut_http = 403


class HorsPerimetre(ErreurPiege):
    """La cible ou la technique sort du périmètre du mandat."""

    code = "hors_perimetre"
    statut_http = 403


class ProductionInterdite(ErreurPiege):
    """Atteinte à la production, interdite par le mandat ou par le catalogue."""

    code = "production_interdite"
    statut_http = 403


class BudgetEpuise(ErreurPiege):
    """Budget d'appels ou de jetons épuisé : arrêt propre."""

    code = "budget_epuise"
    statut_http = 429


class ArretUrgence(ErreurPiege):
    """Arrêt d'urgence actif : la campagne s'interrompt proprement."""

    code = "arret_urgence"
    statut_http = 409


class CorpusLegitimeAbsent(ErreurPiege):
    """La famille G exige un corpus de demandes légitimes (EF-34)."""

    code = "corpus_legitime_absent"
    statut_http = 422


class AutorisationHumaineAbsente(ErreurPiege):
    """Un correctif ne peut être appliqué sans accord humain explicite (EF-42)."""

    code = "autorisation_absente"
    statut_http = 403


class ValeurHorsPlage(ErreurPiege):
    """Valeur hors plage (impact, exposition, exploitabilité) : jamais bornée."""

    code = "valeur_hors_plage"
    statut_http = 400


class TechniqueInconnue(ErreurPiege):
    """Identifiant de technique absent du catalogue."""

    code = "technique_inconnue"
    statut_http = 404


class TenantInconnu(ErreurPiege):
    """Identité de tenant absente ou incohérente avec la requête."""

    code = "tenant_inconnu"
    statut_http = 403


class FournisseurIndisponible(ErreurPiege):
    """Le fournisseur de modèle n'a pas répondu ou a renvoyé une sortie invalide."""

    code = "fournisseur_indisponible"
    statut_http = 502


CODE_HTTP = {
    "erreur_piege": 400,
    "introuvable": 404,
    "role_insuffisant": 403,
    "mandat_invalide": 403,
    "mandat_expire": 403,
    "hors_perimetre": 403,
    "production_interdite": 403,
    "budget_epuise": 429,
    "arret_urgence": 409,
    "corpus_legitime_absent": 422,
    "autorisation_absente": 403,
    "valeur_hors_plage": 400,
    "technique_inconnue": 404,
    "tenant_inconnu": 403,
    "fournisseur_indisponible": 502,
}
