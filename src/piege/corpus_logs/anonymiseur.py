"""Piège — anonymisation des demandes issues des journaux d'usage (#50).

Pour générer le corpus légitime de la famille G sans exiger du client qu'il le
rédige à la main, on part de ses journaux d'usage réels. Mais ces journaux
contiennent des données personnelles : elles sont **anonymisées à la source**,
avant tout stockage, conformément au RGPD et à l'ENF-07. L'anonymisation est
irréversible (remplacement, pas chiffrement) : le corpus généré ne contient plus
la donnée d'origine.
"""

from __future__ import annotations

import re

__all__ = ["anonymiser", "contient_pii", "MOTIFS_PII", "Jeton"]

Jeton = "[ANONYMISE]"

# Motifs de données personnelles, du plus spécifique au plus général.
MOTIFS_PII = (
    ("courriel", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")),
    ("securite_sociale", re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("telephone", re.compile(r"\b(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}\b")),
    ("date_naissance", re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?:19|20)\d{2}\b")),
    ("numero_secu_court", re.compile(r"\b\d{13}\b")),
)


def contient_pii(texte: str) -> bool:
    """Vrai si le texte contient au moins une donnée personnelle reconnue."""
    return any(motif.search(texte or "") for _, motif in MOTIFS_PII)


def anonymiser(texte: str) -> str:
    """Remplace chaque donnée personnelle par un jeton neutre (irréversible)."""
    resultat = texte or ""
    for _, motif in MOTIFS_PII:
        resultat = motif.sub(Jeton, resultat)
    return resultat


def types_presents(texte: str) -> list[str]:
    """Liste des types de données personnelles détectés (pour le journal)."""
    return [nom for nom, motif in MOTIFS_PII if motif.search(texte or "")]
