"""Piège — énumérations du domaine (valeurs gelées, CONTRACTS.md §3.1).

Extrait de `piege.types` pour respecter la limite de 500 lignes par fichier.
Les valeurs sont ASCII minuscules sans accent : ce sont celles qui circulent
dans l'API, le stockage et les rapports.
"""

from __future__ import annotations

from enum import Enum

class Environnement(str, Enum):
    """Environnement de déploiement de la cible."""

    TEST = "test"
    PREPROD = "preprod"
    PROD = "production"


class TypeApplication(str, Enum):
    """Nature de l'application d'IA ciblée."""

    RAG = "rag"
    AGENT = "agent"
    CHATBOT = "chatbot"
    DOCUMENTAIRE = "documentaire"


class StatutMandat(str, Enum):
    """Cycle de vie d'un mandat signé."""

    BROUILLON = "brouillon"
    VALIDE = "valide"
    EXPIRE = "expire"
    REVOQUE = "revoque"


class StatutCampagne(str, Enum):
    """Cycle de vie d'une campagne."""

    PLANIFIEE = "planifiee"
    EN_COURS = "en_cours"
    SUSPENDUE = "suspendue"
    INTERROMPUE = "interrompue"
    TERMINEE = "terminee"


class TypeCampagne(str, Enum):
    """Nature d'une campagne."""

    COMPLETE = "complete"
    CIBLEE = "ciblee"
    FAMILLE = "famille"
    FAUX_REFUS = "faux_refus"
    REJEU = "rejeu"


class Famille(str, Enum):
    """Les huit familles du catalogue."""

    A = "injection_directe"
    B = "injection_indirecte"
    C = "extraction"
    D = "perimetre"
    E = "garde_fous"
    F = "empoisonnement_corpus"
    G = "faux_refus"
    H = "abus_fonctionnel"


class VerdictValeur(str, Enum):
    """Verdict du juge sur une tentative."""

    REUSSI = "reussi"
    ECHOUE = "echoue"
    AMBIGU = "ambigu"


class Severite(str, Enum):
    """Sévérité d'une découverte (calculée par code, jamais par un modèle)."""

    CRITIQUE = "critique"
    ELEVE = "eleve"
    MOYEN = "moyen"
    FAIBLE = "faible"
    INDETERMINEE = "indeterminee"


class SeveriteRefus(str, Enum):
    """Sévérité d'un faux refus (symétrique de la sévérité de fuite)."""

    BLOQUANT = "bloquant"
    MAJEUR = "majeur"
    MINEUR = "mineur"
    NUISANCE = "nuisance"


class StatutFinding(str, Enum):
    """Cycle de vie d'une découverte."""

    OUVERT = "ouvert"
    EN_CORRECTION = "en_correction"
    FERME = "ferme"
    FAUX_POSITIF = "faux_positif"
    REVUE = "revue"


class TypeCorrectif(str, Enum):
    """Nature d'un correctif. Le service n'applique que `garde_fou` et
    `politique` ; les autres sont proposés au client (CONTRACTS.md §10)."""

    GARDE_FOU = "garde_fou"
    POLITIQUE = "politique"
    PROMPT = "prompt"
    DOCUMENT = "document"


class StatutCorrectif(str, Enum):
    """Cycle de vie d'un correctif."""

    PROPOSE = "propose"
    AUTORISE = "autorise"
    APPLIQUE = "applique"
    REJOUE = "rejoue"
    REFUSE = "refuse"


class ClasseRefus(str, Enum):
    """Classe d'une réponse à une demande légitime (famille G)."""

    COMPLETE = "reponse_complete"
    PARTIELLE = "reponse_partielle"
    REFUS = "refus"
    REFUS_PARTIEL = "refus_partiel"
    HORS_SUJET = "hors_sujet"


class CauseRefus(str, Enum):
    """Cause identifiée d'un faux refus."""

    GARDE_FOU = "garde_fou"
    THEME_TROP_LARGE = "theme_trop_large"
    MODELE = "modele"
    CONTEXTE = "contexte"
    CORPUS_ABSENT = "corpus_absent"
    AUTRE = "autre"
    JUSTIFIE = "justifie"


class ProductionAutorisee(str, Enum):
    """Règle de production d'une technique (cf. Annexe A)."""

    JAMAIS = "jamais"
    SUR_MANDAT = "sur_mandat"
    OUI = "oui"
