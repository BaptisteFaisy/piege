"""Piège — utilitaires et sérialisation des enregistrements du domaine.

Extrait de `piege.types` (contrat gelé, `docs/CONTRACTS.md` §3) pour respecter
la limite de 500 lignes par fichier. `piege.types` réexporte tout : aucun
autre module n'importe `types_base` directement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from enum import Enum
from typing import Any, Optional

_HORLOGE: Any = None


def horloge() -> str:
    """Horloge injectable : retourne l'heure ISO-8601 UTC courante.

    Les tests la figent avec `fixer_horloge`. Aucun autre module ne lit
    l'heure directement (CONTRACTS.md §6).
    """
    if _HORLOGE is not None:
        return _HORLOGE
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fixer_horloge(iso: Optional[str]) -> None:
    """Fige (ou libère, avec `None`) l'horloge. Usage réservé aux tests."""
    global _HORLOGE
    _HORLOGE = iso


def maintenant_utc() -> str:
    """Alias explicite de `horloge()`."""
    return horloge()


def hash_stable(texte: str) -> int:
    """Hachage 64 bits stable entre processus (blake2b).

    `hash()` de Python est salé par processus : il rendrait les campagnes
    non reproductibles d'un run à l'autre (CONTRACTS.md §6).
    """
    return int.from_bytes(hashlib.blake2b(texte.encode("utf-8"), digest_size=8).digest(), "big")


def empreinte(texte: str) -> str:
    """Empreinte SHA-256 d'une preuve, préfixée `sha256:`."""
    return "sha256:" + hashlib.sha256(texte.encode("utf-8")).hexdigest()


def canonical(objet: Any) -> str:
    """JSON canonique (trié, séparateurs stables) : base des empreintes."""
    return json.dumps(objet, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Record:
    """Base des enregistrements sérialisables du domaine."""

    def vers_dict(self) -> dict:
        """Version JSON de l'enregistrement (énumérations -> `.value`)."""
        return _vers_dict(self)

    def __str__(self) -> str:  # pragma: no cover - confort de debug
        return f"{type(self).__name__}({self.vers_dict()})"


def _vers_dict(objet: Any) -> Any:
    if isinstance(objet, Enum):
        return objet.value
    if isinstance(objet, Record):
        return {f.name: _vers_dict(getattr(objet, f.name)) for f in fields(objet)}
    if isinstance(objet, dict):
        return {k: _vers_dict(v) for k, v in objet.items()}
    if isinstance(objet, (list, tuple)):
        return [_vers_dict(v) for v in objet]
    return objet


def depuis_dict(cls, donnees: dict):
    """Reconstruit un enregistrement depuis sa version JSON.

    Les clés inconnues sont ignorées (compatibilité ascendante) ; les
    énumérations (y compris en liste) sont reconverties ; les champs absents
    prennent leur défaut.
    """
    kwargs = {}
    for f in fields(cls):
        if f.name not in donnees:
            continue
        kwargs[f.name] = _convertir(donnees[f.name], f.type)
    return cls(**kwargs)


_ENUMS: dict = {}


def _registre_enum() -> dict:
    """Table nom → classe d'énumération (import paresseux, sans cycle)."""
    if not _ENUMS:
        from piege import types_enum as module

        for nom in dir(module):
            objet = getattr(module, nom)
            if isinstance(objet, type) and issubclass(objet, Enum):
                _ENUMS[nom] = objet
    return _ENUMS


def _nom_cible(annotation: Any) -> str:
    """Nom brut visé par une annotation texte (`list[X]`, `Optional[X]` → X)."""
    if not isinstance(annotation, str):
        return ""
    texte = annotation.replace(" ", "")
    for enveloppe in ("list[", "Optional["):
        if texte.startswith(enveloppe):
            texte = texte[len(enveloppe):-1]
    return texte


def _enum_pour(annotation: Any):
    """Classe d'énumération visée par une annotation, ou `None`."""
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    return _registre_enum().get(_nom_cible(annotation))


def _convertir(valeur: Any, annotation: Any) -> Any:
    """Reconvertit une valeur (ou une liste de valeurs) en énumération."""
    enum = _enum_pour(annotation)
    if enum is None:
        return valeur
    if isinstance(valeur, list):
        return [v if isinstance(v, enum) else enum(v) for v in valeur]
    if valeur is None or isinstance(valeur, enum):
        return valeur
    return enum(valeur)

