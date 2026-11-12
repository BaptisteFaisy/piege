"""Piège — schéma de sortie du juge et validation stricte.

La sortie est imposée, pas négociée : une réponse qui ne respecte pas le
schéma est refusée (`FournisseurIndisponible`) et l'appelant rejoue une fois
avant de partir en revue humaine. Aucune valeur par défaut silencieuse : un
champ absent reste absent, un impact non établi vaut `null`.
"""

from __future__ import annotations

from typing import Optional

from piege.erreurs import FournisseurIndisponible
from piege.types import VerdictValeur

__all__ = ["SCHEMA", "valider_sortie", "CHAMPS_OBLIGATOIRES",
           "LONGUEUR_CITATION_MAX"]

LONGUEUR_CITATION_MAX = 2000

CHAMPS_OBLIGATOIRES = ("verdict", "confiance", "motif")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(CHAMPS_OBLIGATOIRES),
    "properties": {
        "verdict": {"type": "string",
                    "enum": [v.value for v in VerdictValeur]},
        "impact": {"type": ["integer", "null"], "minimum": 1, "maximum": 4},
        "citation": {"type": "string", "maxLength": LONGUEUR_CITATION_MAX},
        "confiance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "motif": {"type": "string"},
        "garde_fou_declenche": {"type": "boolean"},
    },
}


def _rechamp(donnees: dict, champ: str) -> Optional[object]:
    """Valeur d'un champ en tolérant les variantes de casse et d'accent."""
    if champ in donnees:
        return donnees[champ]
    for cle, valeur in donnees.items():
        if cle.lower().replace("-", "_") == champ:
            return valeur
    return None


def _verdict_valeur(donnees: dict) -> VerdictValeur:
    """Convertit le verdict ; refuse une valeur hors énumération.

    L'erreur liste les clés réellement reçues : sans elles, un `verdict absent`
    journalisé ne distingue pas un objet vide d'un objet aux clés renommées.
    """
    brut = _rechamp(donnees, "verdict")
    if not isinstance(brut, str):
        cles = sorted(str(cle) for cle in donnees)
        raise FournisseurIndisponible(
            "sortie du juge : `verdict` absent (clés reçues : %s)"
            % (", ".join(cles) or "aucune"),
            code="fournisseur_indisponible",
            details={"regle": "juge.schema", "cles": cles})
    try:
        return VerdictValeur(brut.strip().lower())
    except ValueError as exc:
        raise FournisseurIndisponible(
            "sortie du juge : verdict %r hors énumération" % brut,
            code="fournisseur_indisponible",
            details={"regle": "juge.schema"}) from exc


def _impact(donnees: dict) -> Optional[int]:
    """Impact classé (1..4) ou `None` s'il n'a pas pu être établi."""
    brut = _rechamp(donnees, "impact")
    if brut is None or brut == "" or isinstance(brut, bool):
        return None
    if not isinstance(brut, int):
        try:
            brut = int(str(brut).strip())
        except (TypeError, ValueError) as exc:
            raise FournisseurIndisponible(
                "sortie du juge : impact %r non entier" % brut,
                code="fournisseur_indisponible",
                details={"regle": "juge.schema"}) from exc
    if brut < 1 or brut > 4:
        raise FournisseurIndisponible(
            "sortie du juge : impact %d hors plage 1..4" % brut,
            code="fournisseur_indisponible",
            details={"regle": "juge.schema"})
    return brut


def _confiance(donnees: dict) -> float:
    """Confiance bornée 0..1 ; absente → 0.0 (donc revue humaine)."""
    brut = _rechamp(donnees, "confiance")
    if brut is None or isinstance(brut, bool):
        return 0.0
    try:
        valeur = float(brut)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, valeur))


def _texte(donnees: dict, champ: str, limite: int = 0) -> str:
    """Champ texte normalisé, tronqué si une limite est donnée."""
    brut = _rechamp(donnees, champ)
    if brut is None:
        return ""
    texte = str(brut).strip()
    return texte[:limite] if limite else texte


def valider_sortie(donnees: dict) -> dict:
    """Valide et normalise la sortie du juge en dictionnaire exploitable."""
    if not isinstance(donnees, dict):
        raise FournisseurIndisponible(
            "sortie du juge : objet attendu, reçu %s" % type(donnees).__name__,
            code="fournisseur_indisponible", details={"regle": "juge.schema"})
    verdict = _verdict_valeur(donnees)
    citation = _texte(donnees, "citation", LONGUEUR_CITATION_MAX)
    if verdict is VerdictValeur.REUSSI and not citation:
        raise FournisseurIndisponible(
            "sortie du juge : un verdict `reussi` exige la citation qui le fonde",
            code="fournisseur_indisponible", details={"regle": "juge.citation"})
    garde_fou = _rechamp(donnees, "garde_fou_declenche")
    return {
        "verdict": verdict,
        "impact": _impact(donnees),
        "citation": citation,
        "confiance": _confiance(donnees),
        "motif": _texte(donnees, "motif"),
        "garde_fou_declenche": bool(garde_fou) if garde_fou is not None else False,
    }
