"""Piège — motifs de détection pour le scanner d'ingestion RAG.

Côté **défense** de la famille F : là où l'attaquant dépose un document piégé,
le scanner le détecte *avant* l'indexation. Chaque motif porte une sévérité et
une recommandation de correctif. Les motifs sont des données, pas du code :
ajouter une détection = ajouter une entrée ici.

Ces motifs sont volontairement distincts de ceux de la cible de démonstration
(`piege.cibles.regles`, qui *joue* l'assistant naïf) : le scanner est un produit
de défense autonome, vendable séparément, et doit rester lisible par un RSSI.
"""

from __future__ import annotations

import re

__all__ = ["MOTIFS", "MARQUEURS_CONTRÔLE", "Motif"]


class Motif:
    """Un motif de détection : nom, regex, sévérité, recommandation."""

    __slots__ = ("nom", "regex", "severite", "recommandation", "famille")

    def __init__(self, nom: str, regex: str, severite: str, recommandation: str,
                 famille: str = "injection"):
        self.nom = nom
        self.regex = re.compile(regex, re.IGNORECASE | re.MULTILINE)
        self.severite = severite          # "faible" | "moyenne" | "haute"
        self.recommandation = recommandation
        self.famille = famille


MOTIFS = (
    Motif("instruction_cachee",
          r"(ignore|oublie|ignorez|oubliez)\s+(toutes\s+)?(les\s+)?(consignes?|instructions?|règles?|regles?)",
          "haute", "Marquer le contenu récupéré comme donnée, jamais comme instruction.",
          "injection"),
    Motif("instruction_systeme",
          r"(instruction\s+destin[ée]e\s+au\s+syst[eè]me|system\s*prompt|tu\s+es\s+maintenant|vous\s+êtes\s+maintenant)",
          "haute", "Filtrer à l'ingestion les motifs d'instruction au système.",
          "injection"),
    Motif("desarmement_garde_fou",
          r"(d[ée]sactive|suspend|l[èe]ve|contourne)\s+(le\s+)?(garde[- ]?fou|restriction|filtre|s[ée]curit[ée])",
          "haute", "Refuser tout document demandant de neutraliser un garde-fou.",
          "injection"),
    Motif("contradiction_autorite",
          r"(remplace|annule|pr[ée]vaut\s+sur|fait\s+autorit[ée]|contredit)\s+(la\s+)?(proc[ée]dure|politique|r[ée]f[ée]rence|officiel)",
          "haute", "Pondérer par autorité de source, pas seulement par similarité.",
          "empoisonnement"),
    Motif("redirection_externe",
          r"(adresse|lien|url|site)\s+(de\s+)?(collecte|externe)|https?://[^\s]+",
          "moyenne", "Contrôler la provenance et bloquer les références sortantes.",
          "exfiltration"),
    Motif("role_impose",
          r"(tu\s+es|vous\s+êtes|agis\s+comme|consid[èe]re[- ]toi)\s+(un\s+|une\s+)?(assistant|expert|rôle|role)",
          "moyenne", "Détecter les tentatives de changement de rôle à l'ingestion.",
          "injection"),
    Motif("persistance_consigne",
          r"([àa]\s+partir\s+de\s+maintenant|d[ée]sormais|pour\s+toutes?\s+les\s+demandes|note\s+pour\s+la\s+suite)",
          "moyenne", "Borner la mémoire de session ; ne pas persister de consigne externe.",
          "injection"),
    Motif("payload_encode",
          r"\b[A-Za-z0-9+/]{40,}={0,2}\b",
          "moyenne", "Détecter les blobs encodés (base64) dans les documents entrants.",
          "encodage"),
    Motif("commentaire_html_actif",
          r"<!--[^>]*(instruction|syst[eè]me|ignore|ex[ée]cute)[^>]*-->",
          "haute", "Nettoyer les commentaires et balises des documents entrants.",
          "structurel"),
    Motif("champ_formulaire",
          r"(\{\{.*\}\}|<%.*%>|\[\[.*\]\])",
          "faible", "Valider les gabarits et champs de formulaire avant indexation.",
          "structurel"),
)

# Caractères de contrôle invisibles : marques de direction, espace insécable,
# largeur nulle. Leur seule présence dans un document métier est suspecte.
MARQUEURS_CONTRÔLE = {
    "\u200b": "espace_largeur_nulle",
    "\u200c": "antiliaison_largeur_nulle",
    "\u200d": "liaison_largeur_nulle",
    "\u202a": "marque_direction_ngauche_droite",
    "\u202b": "marque_direction_droite_gauche",
    "\u202c": "marque_fin_direction",
    "\u202d": "forçage_gauche_droite",
    "\u202e": "forçage_droite_gauche",
    "\ufeff": "bom",
    "\u00a0": "espace_insécable",
}
