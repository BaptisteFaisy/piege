"""Piège — entrepot local : JSON sur disque, hors ligne, atomique.

Implémentation par défaut (CI, `make demo`, recette locale). Garanties :
écriture atomique (fichier temporaire + `os.replace`), filtrage systématique
par tenant, immuabilité des preuves, journal append-only chaîné, purge de
tenant prouvée (R20).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Optional

from piege.erreurs import ErreurPiege
from piege.stockage.base import PREFIXES, TABLES
from piege.types import Preuve, canonical, empreinte, maintenant_utc

__all__ = ["EntrepotLocal"]


class EntrepotLocal:
    """Entrepôt JSON : un fichier par table, dans un dossier configurable."""

    def __init__(self, dossier: str = "donnees-locales"):
        self.dossier = dossier
        self._verrou = threading.RLock()
        os.makedirs(self.dossier, exist_ok=True)

    # ------------------------------------------------------------ bas niveau
    def _chemin(self, table: str) -> str:
        if table not in TABLES:
            raise ErreurPiege("table inconnue : %r" % table, code="table_inconnue",
                              details={"regle": "stockage.table"})
        return os.path.join(self.dossier, "%s.json" % table)

    def _charger(self, table: str) -> dict:
        chemin = self._chemin(table)
        if not os.path.isfile(chemin):
            return {}
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)

    def _sauver(self, table: str, donnees: dict) -> None:
        """Écriture atomique : jamais de fichier tronqué en cas d'arrêt."""
        chemin = self._chemin(table)
        descripteur, temporaire = tempfile.mkstemp(dir=self.dossier, suffix=".tmp")
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8") as f:
                json.dump(donnees, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(temporaire, chemin)
        finally:
            if os.path.exists(temporaire):
                os.unlink(temporaire)

    def _allouer(self, table: str, enregistrement: dict) -> str:
        """Identifiant fourni ou alloué (séquence par table, jamais un modèle)."""
        if enregistrement.get("id"):
            return str(enregistrement["id"])
        sequences = self._charger("journal").get("__sequences__", {})
        suivant = int(sequences.get(table, 0)) + 1
        sequences[table] = suivant
        journal = self._charger("journal")
        journal["__sequences__"] = sequences
        self._sauver("journal", journal)
        annee = maintenant_utc()[:4]
        return "%s-%s-%04d" % (PREFIXES.get(table, "ID"), annee, suivant)

    # ---------------------------------------------------------------- écriture
    def ecrire(self, table: str, enregistrement: dict) -> str:
        """Écrit un enregistrement ; refuse d'écraser une preuve existante."""
        with self._verrou:
            donnees = self._charger(table)
            identifiant = self._allouer(table, enregistrement)
            if table == "preuves" and identifiant in donnees:
                raise ErreurPiege(
                    "une preuve est immuable : elle se remplace par une "
                    "nouvelle preuve datée", code="preuve_immuable",
                    details={"regle": "stockage.immuabilite", "id": identifiant})
            copie = dict(enregistrement)
            copie["id"] = identifiant
            copie.setdefault("ecrit_le", maintenant_utc())
            donnees[identifiant] = copie
            self._sauver(table, donnees)
            return identifiant

    def lire(self, table: str, identifiant: str, tenant_id: str = "") -> Optional[dict]:
        """Lit un enregistrement ; `None` s'il est absent ou d'un autre tenant."""
        with self._verrou:
            enregistrement = self._charger(table).get(identifiant)
        if enregistrement is None:
            return None
        if tenant_id and enregistrement.get("tenant_id") not in (None, tenant_id):
            return None
        return dict(enregistrement)

    def lister(self, table: str, tenant_id: str = "", **filtres) -> list[dict]:
        """Liste les enregistrements d'un tenant, filtrés, triés par identifiant."""
        with self._verrou:
            donnees = self._charger(table)
        sortie = []
        for identifiant in sorted(donnees):
            if identifiant.startswith("__"):
                continue
            enregistrement = donnees[identifiant]
            if tenant_id and enregistrement.get("tenant_id") != tenant_id:
                continue
            if not self._correspond(enregistrement, filtres):
                continue
            sortie.append(dict(enregistrement))
        return sortie

    @staticmethod
    def _correspond(enregistrement: dict, filtres: dict) -> bool:
        """Vérifie les filtres simples (égalité, appartenance à une liste)."""
        for cle, attendue in filtres.items():
            valeur = enregistrement.get(cle)
            if isinstance(valeur, list):
                if attendue not in valeur:
                    return False
            elif valeur != attendue:
                return False
        return True

    # ------------------------------------------------------------------ journal
    def ecrire_journal(self, evenement: dict) -> str:
        """Ajoute une ligne au journal chaîné (append-only, jamais modifiée)."""
        with self._verrou:
            journal = self._charger("journal")
            lignes = journal.setdefault("lignes", [])
            sequences = journal.get("__sequences__", {})
            identifiant = evenement.get("id") or "JRN-%06d" % (len(lignes) + 1)
            evenement = dict(evenement)
            evenement["id"] = identifiant
            lignes.append(evenement)
            journal["__sequences__"] = sequences
            self._sauver("journal", journal)
            return identifiant

    def lire_journal(self) -> list[dict]:
        """Lignes du journal, dans l'ordre d'écriture."""
        with self._verrou:
            return list(self._charger("journal").get("lignes", []))

    # -------------------------------------------------------------------- purge
    def supprimer_tenant(self, tenant_id: str) -> Preuve:
        """Purge toutes les tables d'un tenant et rend une preuve datée."""
        supprimes = {}
        with self._verrou:
            for table in TABLES:
                if table == "journal":
                    continue
                donnees = self._charger(table)
                touches = [k for k, v in donnees.items()
                           if not k.startswith("__") and v.get("tenant_id") == tenant_id]
                for cle in touches:
                    del donnees[cle]
                if touches:
                    self._sauver(table, donnees)
                    supprimes[table] = sorted(touches)
        return self._preuve_purge(tenant_id, supprimes)

    def _preuve_purge(self, tenant_id: str, supprimes: dict) -> Preuve:
        """Construit et stocke la preuve de purge (identifiants supprimés)."""
        contenu = canonical({"tenant": tenant_id, "supprimes": supprimes,
                             "date": maintenant_utc()})
        preuve = Preuve(id="", type="purge", campagne_id="", tenant_id=tenant_id,
                        chemin=os.path.join(self.dossier, "purges",
                                            "%s.json" % tenant_id),
                        empreinte=empreinte(contenu), date=maintenant_utc(),
                        verbatim="")
        dossier = os.path.dirname(preuve.chemin)
        os.makedirs(dossier, exist_ok=True)
        with open(preuve.chemin, "w", encoding="utf-8") as f:
            f.write(contenu)
        preuve.id = self.ecrire("preuves", preuve.vers_dict())
        return preuve
