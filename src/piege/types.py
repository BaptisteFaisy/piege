"""Piège — Types et contrats partagés du moteur.

Ce module est le **contrat gelé** du projet (voir `docs/CONTRACTS.md` §3).
Il ne contient aucune dépendance hors bibliothèque standard et aucune logique
métier : uniquement les enregistrements du domaine. Les énumérations vivent
dans `piege.types_enum`, les utilitaires (horloge, empreinte, hachage stable,
sérialisation) dans `piege.types_base` — les deux sont réexportés ici.

Règles : pas de `datetime.now()` ailleurs que dans `types_base`, pas de
`hash()` de Python (salé par processus), pas de valeur par défaut silencieuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from piege.types_base import (Record, canonical, depuis_dict, empreinte,
                              fixer_horloge, hash_stable, horloge,
                              maintenant_utc)
from piege.types_enum import (CauseRefus, ClasseRefus, Environnement, Famille,
                              ProductionAutorisee, Severite, SeveriteRefus,
                              StatutCampagne, StatutCorrectif, StatutFinding,
                              StatutMandat, TypeApplication, TypeCampagne,
                              TypeCorrectif, VerdictValeur)

__all__ = [
    "Environnement", "TypeApplication", "StatutMandat", "StatutCampagne",
    "TypeCampagne", "Famille", "VerdictValeur", "Severite", "SeveriteRefus",
    "StatutFinding", "TypeCorrectif", "StatutCorrectif", "ClasseRefus",
    "CauseRefus", "ProductionAutorisee", "Record", "Tenant", "Application",
    "Mandat", "Technique", "Campagne", "Reponse", "Verdict", "Execution",
    "Finding",
    "Correctif", "Preuve", "DemandeLegitime", "CorpusLegitime", "FauxRefus",
    "Decision", "maintenant_utc", "fixer_horloge", "horloge", "hash_stable",
    "empreinte", "canonical", "depuis_dict",
]


@dataclass
class Tenant(Record):
    """Client (locataire) du service : aucune donnée personnelle n'est stockée."""

    id: str
    nom_client: str
    contact_commanditaire: str
    retention_jours: int = 365


@dataclass
class Application(Record):
    """Application d'IA déclarée comme cible (EF-01)."""

    id: str
    tenant_id: str
    nom: str
    type: TypeApplication
    acces: str
    modele: str
    environnement: Environnement
    exposition: int
    corpus_ref: str = ""
    garde_fous: list[str] = field(default_factory=list)
    depot_document_autorise: bool = False


@dataclass
class Mandat(Record):
    """Mandat signé : condition bloquante d'exécution (EF-03, EF-04)."""

    id: str
    tenant_id: str
    application_id: str
    perimetre_techniques: list[str]
    environnements: list[Environnement]
    fenetre_debut: str
    fenetre_fin: str
    budget_appels: int
    budget_jetons: int
    production_autorisee: bool
    contact_urgence: str
    signe_le: str
    signature: str
    statut: StatutMandat = StatutMandat.BROUILLON


@dataclass
class Technique(Record):
    """Une technique du catalogue : de la donnée, jamais du code (§18.4)."""

    id: str
    famille: Famille
    nom: str
    objectif: str
    preconditions: list[str]
    environnement: list[Environnement]
    production: ProductionAutorisee
    budget_appels: int
    tours_max: int
    sonde_initiale: str
    mesures: list[str]
    juge_reussi_si: str
    correctifs_suggeres: list[str] = field(default_factory=list)
    gabarit_document: str = ""
    deterministe: bool = True
    variantes: list[dict] = field(default_factory=list)


@dataclass
class Campagne(Record):
    """Campagne : exécution d'un ensemble de techniques sous mandat."""

    id: str
    mandat_id: str
    application_id: str
    tenant_id: str
    type: TypeCampagne
    graine: int
    statut: StatutCampagne
    debutee_le: str = ""
    terminee_le: str = ""
    appels: int = 0
    jetons: int = 0
    cout_mesure: float = 0.0
    techniques_prevues: list[str] = field(default_factory=list)
    techniques_executes: list[str] = field(default_factory=list)
    arrets: list[str] = field(default_factory=list)


@dataclass
class Reponse(Record):
    """Réponse brute de la cible à une sonde."""

    texte: str
    garde_fou_declenche: bool = False
    garde_fou_id: str = ""
    jetons_entree: int = 0
    jetons_sortie: int = 0
    latence_ms: int = 0
    brut: dict = field(default_factory=dict)
    session: str = ""


@dataclass
class Verdict(Record):
    """Verdict structuré du juge (EF-20, EF-21).

    `impact` est un **fait classé** de 1 à 4 — jamais une sévérité : la
    sévérité est calculée ensuite par `piege.severite` (règle C5).
    """

    verdict: Optional[VerdictValeur]
    impact: Optional[int]
    citation: str
    confiance: float
    motif: str
    garde_fou_declenche: bool
    graine: int = 0
    modele: str = ""
    revue_humaine: bool = False
    version_invite: str = ""


@dataclass
class Execution(Record):
    """Trace d'une tentative : sonde, réponse, verdict, coût (EF-14)."""

    id: str
    campagne_id: str
    technique_id: str
    application_id: str
    tenant_id: str
    statut: str
    sondes_envoyees: list[str]
    reponse_brute: str
    jetons: int
    latence_ms: int
    verdict: Optional[VerdictValeur]
    impact: Optional[int]
    confiance: float
    citation: str
    motif: str
    garde_fou_declenche: bool
    revue_humaine: bool
    graine: int
    tours: int = 0
    modele: str = ""
    erreur: str = ""


@dataclass
class Finding(Record):
    """Découverte : une ou plusieurs techniques révélant la même faille."""

    id: str
    application_id: str
    tenant_id: str
    campagne_id: str
    technique_ids: list[str]
    famille: Famille
    severite: Severite
    impact: Optional[int]
    exploitabilite: Optional[int]
    exposition: int
    score: Optional[int]
    statut: StatutFinding
    titre: str
    description: str
    citation: str
    preuve_ids: list[str]
    correctif_ids: list[str]
    ouvert_le: str
    ferme_le: str = ""
    preuve_fermeture_ids: list[str] = field(default_factory=list)


@dataclass
class Correctif(Record):
    """Correctif proposé, puis éventuellement appliqué et rejoué."""

    id: str
    finding_id: str
    application_id: str
    tenant_id: str
    type: TypeCorrectif
    contenu: str
    effort: int
    reduction_risque: str
    statut: StatutCorrectif
    autorise_par: str = ""
    autorise_le: str = ""
    applique_le: str = ""
    rejoue_le: str = ""
    effet_de_bord: str = ""
    regression: str = ""


@dataclass
class Preuve(Record):
    """Preuve immuable (transcription, capture, attestation)."""

    id: str
    type: str
    campagne_id: str
    tenant_id: str
    chemin: str
    empreinte: str
    date: str
    verbatim: str = ""


@dataclass
class DemandeLegitime(Record):
    """Demande réelle (anonymisée) fournie par le client pour la famille G."""

    id: str
    texte: str
    criticite: int
    frequence_mensuelle: int = 1
    langue: str = "fr"
    attendu: str = ""
    etiquette: str = ""


@dataclass
class CorpusLegitime(Record):
    """Corpus de demandes légitimes d'une application."""

    id: str
    application_id: str
    tenant_id: str
    demandes: list[DemandeLegitime]
    source: str
    charge_le: str


@dataclass
class FauxRefus(Record):
    """Faux refus mesuré, avec sa perte estimée."""

    id: str
    campagne_id: str
    application_id: str
    tenant_id: str
    demande_id: str
    reponse_ref: str
    classe: ClasseRefus
    cause: CauseRefus
    frequence_mensuelle: int
    criticite_metier: int
    perte: int
    severite: SeveriteRefus
    minutes_manuelles: int = 12


@dataclass
class Decision(Record):
    """Décision de Policy : ce qui est autorisé, et la règle violée sinon."""

    accorde: bool
    regle: str
    motif: str
    outil: str = ""
    faits: dict = field(default_factory=dict)
    code: str = ""
