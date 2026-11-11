"""Doubles de test du moteur (lot 3) : cible, fournisseur, juge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from piege.types import Reponse, VerdictValeur

REPONSE_FUITE = ("Voici les niveaux de salaire du document grille-2026 : "
                 "Niveau 1 : 32 400 EUR brut annuel, Niveau 7 : 78 900 EUR.")
REPONSE_REFUS = "Je ne peux pas répondre à cette demande, contactez le service RH."
REPONSE_NEUTRE = "Le télétravail est possible deux jours par semaine."


@dataclass
class VerdictDouble:
    """Verdict minimal, duck-typé : le moteur n'exige pas la classe du lot 5."""

    verdict: VerdictValeur = VerdictValeur.REUSSI
    impact: Optional[int] = 4
    citation: str = "Niveau 1 : 32 400 EUR brut annuel"
    confiance: float = 0.95
    motif: str = "fuite observée"
    garde_fou_declenche: bool = False
    graine: int = 0
    modele: str = "double"
    revue_humaine: bool = False
    version_invite: str = "double-1.0"


class CibleDouble:
    """Cible conforme au protocole gelé, sans réseau ni modèle."""

    def __init__(self, reponses=None, garde_fou: bool = False,
                 jetons: int = 120):
        self.reponses = list(reponses or [REPONSE_FUITE])
        self.garde_fou = garde_fou
        self.jetons = jetons
        self.appels: list[dict] = []
        self.deposes: list[dict] = []
        self.index_detruits: list[str] = []
        self.evenements: list[dict] = []

    def sonder(self, demande: str, session: str, graine: int) -> Reponse:
        """Enregistre la sonde et rend une réponse déterministe."""
        self.appels.append({"demande": demande, "session": session,
                            "graine": graine})
        texte = self.reponses[min(len(self.appels) - 1, len(self.reponses) - 1)]
        return Reponse(texte=texte, garde_fou_declenche=self.garde_fou,
                       jetons_entree=self.jetons, jetons_sortie=self.jetons // 4,
                       latence_ms=5, session=session)

    def deposer_document(self, chemin: str, contenu: str, session: str) -> str:
        """Dépose un document dans l'index de test (famille F)."""
        self.deposes.append({"chemin": chemin, "contenu": contenu,
                             "session": session})
        return "doc-%d" % len(self.deposes)

    def mesurer(self, requete: str, session: str) -> Reponse:
        """Mesure sans sonde supplémentaire comptabilisée comme attaque."""
        return self.sonder(requete, session, 0)

    def reindexer(self, session: str) -> None:
        """Réindexation de l'index de test."""
        self.evenements.append({"action": "reindexer", "session": session})

    def detruire_index(self, index_id: str) -> None:
        """Destruction de l'index de test (EF-17)."""
        self.index_detruits.append(index_id)

    def journaliser(self, evenement: dict) -> None:
        """Journalisation côté cible."""
        self.evenements.append(evenement)


class FournisseurDouble:
    """Fournisseur de modèle programmable, hors ligne."""

    nom = "double"

    def __init__(self, textes=None, sorties=None):
        self.textes = list(textes or ["réponse du modèle"])
        self.sorties = list(sorties or [])
        self.appels: list[dict] = []

    def completer(self, messages, graine, max_jetons=1500, temperature=0.0):
        """Complétion déterministe."""
        from piege.fournisseurs.base import ReponseModele

        self.appels.append({"messages": messages, "graine": graine})
        texte = self.textes[min(len(self.appels) - 1, len(self.textes) - 1)]
        return ReponseModele(texte=texte, jetons_entree=10, jetons_sortie=5,
                             modele="double")

    def sortie_structuree(self, messages, schema, graine):
        """Sortie structurée programmée."""
        self.appels.append({"messages": messages, "schema": schema,
                            "graine": graine})
        if self.sorties:
            return self.sorties.pop(0)
        return {"verdict": "reussi", "impact": 4, "citation": "extrait",
                "confiance": 0.9, "motif": "double", "garde_fou_declenche": False}


def juge_double(verdict: Optional[VerdictDouble] = None):
    """Fabrique une fonction de jugement injectable dans le moteur."""
    attendu = verdict or VerdictDouble()
    appels: list[dict] = []

    def juger(technique, transcription, fournisseur, graine):
        appels.append({"technique": technique.id, "graine": graine,
                       "transcription": transcription})
        return attendu

    juger.appels = appels
    return juger


@dataclass
class EntrepotDouble:
    """Entrepôt en mémoire : écritures et lectures, sans disque."""

    tables: dict = field(default_factory=dict)
    journal: list = field(default_factory=list)
    purges: list = field(default_factory=list)

    def ecrire(self, table: str, enregistrement: dict) -> str:
        """Écrit et retourne l'identifiant (alloué si absent)."""
        cle = enregistrement.get("id") or "%s-%d" % (
            table, len(self.tables.setdefault(table, {})) + 1)
        copie = dict(enregistrement)
        copie["id"] = cle
        self.tables.setdefault(table, {})[cle] = copie
        return cle

    def lire(self, table: str, identifiant: str, tenant_id: str = ""):
        """Lit un enregistrement, filtré par tenant."""
        enregistrement = self.tables.get(table, {}).get(identifiant)
        if enregistrement and tenant_id and \
                enregistrement.get("tenant_id") not in (None, tenant_id):
            return None
        return dict(enregistrement) if enregistrement else None

    def lister(self, table: str, tenant_id: str = "", **filtres) -> list:
        """Liste les enregistrements d'un tenant."""
        sortie = []
        for enregistrement in self.tables.get(table, {}).values():
            if tenant_id and enregistrement.get("tenant_id") != tenant_id:
                continue
            sortie.append(dict(enregistrement))
        return sortie

    def supprimer_tenant(self, tenant_id: str):
        """Purge enregistrée comme preuve de test."""
        self.purges.append(tenant_id)
        return None

    def ecrire_journal(self, evenement: dict) -> str:
        """Ajoute une ligne de journal."""
        self.journal.append(dict(evenement))
        return "JRN-%d" % len(self.journal)


@dataclass
class JournalDouble:
    """Journal de test : mémorise les lignes sans les écrire."""

    lignes: list = field(default_factory=list)

    def consigner(self, qui, quoi, tenant, details=None, sonde_de_test=True):
        """Ajoute une ligne."""
        ligne = {"qui": qui, "quoi": quoi, "tenant": tenant,
                 "details": details or {}}
        self.lignes.append(ligne)
        return ligne

    def consigner_decision(self, decision, tenant, qui="politique"):
        """Ajoute une décision de politique."""
        return self.consigner(qui, "autorise" if decision.accorde else "refus",
                              tenant, {"regle": decision.regle,
                                       "code": decision.code})

    def refus(self):
        """Lignes de refus uniquement."""
        return [l for l in self.lignes if l["quoi"] == "refus"]
