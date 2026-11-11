"""Piège — journal append-only chaîné par empreinte.

Chaque événement (sonde, réponse, refus de Policy, accord humain, purge) est
journalisé de façon immuable (ENF-04). La chaîne d'empreintes rend toute
suppression ou altération détectable (spécification §19.2). Le marqueur
`sonde_de_test` distingue explicitement une sonde de test du trafic réel :
un journal de test ne doit jamais pouvoir passer pour la preuve d'une attaque
réelle (spécification §22, dernière ligne).
"""

from __future__ import annotations

from typing import Callable, Optional

from piege.types import Decision, canonical, empreinte, maintenant_utc

__all__ = ["Journal", "entree_journal", "MARQUEUR_SONDE_TEST",
           "MARQUEUR_TRAFIC_REEL"]

MARQUEUR_SONDE_TEST = "sonde_de_test"
MARQUEUR_TRAFIC_REEL = "trafic_reel"
EMPREEINTE_GENESIS = "sha256:" + "0" * 64


def entree_journal(qui: str, quoi: str, tenant: str, details: Optional[dict] = None,
                   sonde_de_test: bool = True, precedente: str = EMPREEINTE_GENESIS,
                   date: Optional[str] = None) -> dict:
    """Construit une ligne de journal signée par empreinte chaînée."""
    ligne = {
        "date": date or maintenant_utc(),
        "qui": qui,
        "quoi": quoi,
        "tenant": tenant,
        "marqueur": MARQUEUR_SONDE_TEST if sonde_de_test else MARQUEUR_TRAFIC_REEL,
        "details": dict(details or {}),
        "empreinte_precedente": precedente,
    }
    ligne["empreinte"] = empreinte(canonical(ligne))
    return ligne


def verifier_ligne(ligne: dict) -> bool:
    """Vérifie l'empreinte d'une ligne prise isolément."""
    copie = {k: v for k, v in ligne.items() if k != "empreinte"}
    return ligne.get("empreinte") == empreinte(canonical(copie))


class Journal:
    """Journal d'une campagne : append-only, chaîné, vérifiable."""

    def __init__(self, ecrire: Optional[Callable[[dict], None]] = None):
        self._lignes: list[dict] = []
        self._ecrire = ecrire

    @property
    def derniere_empreinte(self) -> str:
        """Empreinte de la dernière ligne (genèse si le journal est vide)."""
        return self._lignes[-1]["empreinte"] if self._lignes else EMPREEINTE_GENESIS

    def consigner(self, qui: str, quoi: str, tenant: str,
                  details: Optional[dict] = None,
                  sonde_de_test: bool = True) -> dict:
        """Ajoute une ligne chaînée et la transmet à l'entrepôt éventuel."""
        ligne = entree_journal(qui, quoi, tenant, details, sonde_de_test,
                               self.derniere_empreinte)
        self._lignes.append(ligne)
        if self._ecrire is not None:
            self._ecrire(ligne)
        return ligne

    def consigner_decision(self, decision: Decision, tenant: str,
                           qui: str = "politique") -> dict:
        """Journalise une décision de Policy, accord compris (traçabilité)."""
        return self.consigner(
            qui, "autorise" if decision.accorde else "refus", tenant,
            {"outil": decision.outil, "regle": decision.regle,
             "code": decision.code, "motif": decision.motif})

    def lignes(self) -> list[dict]:
        """Copie des lignes : le journal ne se modifie pas de l'extérieur."""
        return [dict(ligne) for ligne in self._lignes]

    def refus(self) -> list[dict]:
        """Les refus uniquement : c'est ce flux qui alimente la démonstration."""
        return [ligne for ligne in self._lignes if ligne["quoi"] == "refus"]

    def verifier_chaine(self) -> bool:
        """Vrai si aucune ligne n'a été altérée ni supprimée."""
        precedente = EMPREEINTE_GENESIS
        for ligne in self._lignes:
            if ligne.get("empreinte_precedente") != precedente:
                return False
            if not verifier_ligne(ligne):
                return False
            precedente = ligne["empreinte"]
        return True
