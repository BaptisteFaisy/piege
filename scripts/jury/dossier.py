#!/usr/bin/env python3
"""Piège — dossier jury en une commande (`make jury`).

Rassemble dans un dossier reproductible tout ce que le jury peut vérifier
sans rien installer :

- la campagne de démonstration **hors ligne** (cible vulnérable, 3 techniques) ;
- son rapport en français et en anglais, et l'attestation tierce ;
- la **boucle de correction complète** : découverte ouverte → correctif proposé
  → accord humain → application → rejeu → **preuve de fermeture datée** ;
- la table des 20 recettes prouvées (`scripts/preuves/recettes.py`) ;
- les statuts recalculés de la traçabilité (`scripts/preuves/tracabilite.py`) ;
- le rapport du harnais d'évaluation (`eval/mesurer.py`).

Aucun modèle, aucun réseau, aucun coût : tout tourne en local.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "src"))

from piege.correctifs.application import appliquer
from piege.correctifs.autorisation import autoriser
from piege.correctifs.proposition import proposer
from piege.correctifs.rejeu import fermer, rejouer
from piege.moteur import executer_campagne
from piege.moteur.demo import campagne_de_demonstration
from piege.rapport.attestation import attestation
from piege.rapport.preuves import chaines_depuis_entrepot
from piege.rapport.rapport import rapport_depuis_entrepot
from piege.stockage import creer_entrepot
from piege.types import Finding, depuis_dict

GRAINE = 20261111


def _spec_cible() -> dict:
    with open(os.path.join(RACINE, "demo", "cible", "guichet-rh.json"),
              encoding="utf-8") as f:
        return json.load(f)


def _config(entrepot):
    """Configuration de la campagne de démonstration, dans l'entrepôt donné."""
    config = campagne_de_demonstration(
        graine=GRAINE, cible_spec=_spec_cible(),
        dossier_catalogue=os.path.join(RACINE, "catalogue"))
    config.entrepot = entrepot
    return config


def _ecrire(chemin: str, contenu: str) -> None:
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)


def _lancer(commande: list) -> str:
    """Lance une commande du dépôt et rend sa sortie (texte)."""
    resultat = subprocess.run(commande, cwd=RACINE, capture_output=True,
                              text=True, timeout=600,
                              env=dict(os.environ,
                                       PYTHONPATH=os.path.join(RACINE, "src")))
    if resultat.returncode != 0:
        return "%s (échec : %s)" % (commande[-1], resultat.stderr.strip()[:200])
    return resultat.stdout


def _valeur(valeur) -> str:
    return getattr(valeur, "value", None) or str(valeur or "")


def _cloture(decouverte, config, dossier: str) -> str:
    """Boucle de correction complète : ouverture → fermeture prouvée."""
    from piege.cibles import creer_cible

    # La cible est reconstruite depuis la spécification : c'est elle qui reçoit
    # le garde-fou, puis qui est rejouée — le rejeu doit viser la cible
    # corrigée, pas une autre instance.
    spec = dict(config.cible_spec)
    spec["corpus"] = os.path.join(RACINE, "demo", "corpus")
    cible = creer_cible(spec)
    propositions = proposer(decouverte, catalogue=config.catalogue)
    # Le service n'applique que garde-fou et politique (jamais le document du
    # client) : on ne retient donc que ces correctifs-là.
    applicables = [p for p in propositions
                   if _valeur(p.type) in ("garde_fou", "politique")]
    if not applicables:
        return "# Clôture\n\nAucun correctif applicable (garde-fou ou politique).\n"
    correctif = applicables[0]
    autoriser(correctif, "jury@piege.local", "commanditaire")
    appliquer(correctif, cible, mandat=config.mandat)
    identifiant = (decouverte.technique_ids or [""])[0]
    technique = config.catalogue.get(identifiant)
    execution, preuve = rejouer(decouverte, cible, config.mandat, graine=GRAINE,
                                 technique=technique,
                                 catalogue=config.catalogue)
    fermer(decouverte, preuve, execution)
    lignes = [
        "# Boucle de correction — ouverture → fermeture prouvée", "",
        "- Découverte : **%s** (%s, impact %s)" % (decouverte.id,
                                                     _valeur(decouverte.severite),
                                                     decouverte.impact),
        "- Statut initial : `ouvert` — citation : %s" % (decouverte.citation[:120]),
        "- Correctif proposé : `%s` (%s, effort %s, risque %s)"
        % (correctif.id, _valeur(correctif.type), correctif.effort,
           correctif.reduction_risque),
        "- Accord humain : %s (%s)" % (correctif.autorise_par, correctif.autorise_le),
        "- Application : %s — le garde-fou est posé sur la cible" % correctif.applique_le,
        "- Rejeu de l'attaque d'origine : verdict **%s**"
        % _valeur(execution.verdict),
        "- Preuve de fermeture : `%s`, empreinte `%s`, datée %s"
        % (preuve.id, preuve.empreinte[:23] + "…", preuve.date),
        "- Statut final : **%s** (%s)" % (_valeur(decouverte.statut),
                                          decouverte.ferme_le), "",
        "La fermeture n'est pas une déclaration : elle repose sur le rejeu de "
        "l'attaque d'origine, dont l'empreinte est recalculable.", "",
    ]
    texte = "\n".join(lignes)
    _ecrire(os.path.join(dossier, "cloture.md"), texte)
    return texte


def _index(dossier: str, campagne, findings, preuves: list) -> str:
    """Écrit l'index du dossier : ce qu'est chaque pièce, et ce qu'elle prouve."""
    lignes = [
        "# Dossier jury — Piège", "",
        "Généré par `make jury` : tout est **hors ligne, reproductible, gratuit**.", "",
        "| Pièce | Ce qu'elle prouve |", "|---|---|",
        "| `campagne.json` | La campagne de démonstration : techniques, verdicts, coûts |",
        "| `rapport-fr.md` / `rapport-en.md` | Le rapport client, dans les deux langues (EF-50, EF-51) |",
        "| `attestation.md` | L'attestation tierce, datée et pauvre en détail (EF-53) |",
        "| `cloture.md` | La boucle complète : ouverture → accord → application → rejeu → **preuve de fermeture** (R11) |",
        "| `recettes.md` | Les 20 recettes du cahier, chacune reliée à son test (R1–R20) |",
        "| `tracabilite.md` | Les statuts recalculés des exigences (EF/ENF/KPI) |",
        "| `evaluation.json` | La précision du juge et la détection, mesurées (§24) |",
        "| `preuves.json` | La chaîne de preuves de la campagne (une empreinte par étape) |",
        "", "## Campagne", "",
        "- identifiant : `%s`" % campagne.id,
        "- techniques exécutées : %s" % ", ".join(campagne.techniques_executes or []),
        "- découvertes : %d" % len(findings),
        "- coût mesuré : %s" % campagne.cout_mesure,
        "- éléments de preuve : %d" % len(preuves),
        "", "## Reproduire", "",
        "```bash", "make ci        # gardes + tests", "make jury      # ce dossier",
        "```", "",
    ]
    _ecrire(os.path.join(dossier, "INDEX.md"), "\n".join(lignes))
    return "\n".join(lignes)


def _decouverte_privilegiee(findings: list):
    """La découverte à fermer : celle de la fuite de la grille (A1).

    Les faux refus (famille G) sont des constats de pertes, pas des fuites à
    corriger : les fermer ne prouverait rien.
    """
    for finding in findings:
        if "A1" in (finding.technique_ids or []):
            return finding
    return findings[0]


def _application(config, campagne):
    """Application de la campagne (la spec de démo, complétée comme l'API)."""
    from piege.types import Application

    spec = dict(config.cible_spec.get("application") or {})
    spec.setdefault("id", campagne.application_id)
    spec.setdefault("tenant_id", campagne.tenant_id)
    spec.setdefault("nom", campagne.application_id)
    spec.setdefault("type", "rag")
    spec.setdefault("acces", "")
    spec.setdefault("modele", "")
    spec.setdefault("environnement", "test")
    spec.setdefault("exposition", 2)
    return depuis_dict(Application, spec)


def _ecrire_pieces(entrepot, campagne, config, sortie: str) -> list:
    """Écrit les pièces du dossier et rend la liste des preuves de la campagne."""
    # Les découvertes sont synthétisées à partir des exécutions réussies
    # (comme le fait la route API) : sans cette étape, rien n'est découvert.
    from piege.rapport.synthese import synthetiser_findings
    from piege.types import Execution

    executions = [depuis_dict(Execution, b) for b in
                  entrepot.lister("executions", tenant_id=campagne.tenant_id,
                                  campagne_id=campagne.id)]
    synthetiser_findings(campagne, executions, _application(config, campagne),
                         config.catalogue, entrepot)

    bruts = entrepot.lister("findings", tenant_id=campagne.tenant_id,
                             campagne_id=campagne.id)
    findings = [depuis_dict(Finding, b) for b in bruts]
    _ecrire(os.path.join(sortie, "campagne.json"),
            json.dumps(campagne.vers_dict(), ensure_ascii=False, indent=1))
    for langue in ("fr", "en"):
        _ecrire(os.path.join(sortie, "rapport-%s.md" % langue),
                rapport_depuis_entrepot(entrepot, campagne.id,
                                        campagne.tenant_id, langue))
    _ecrire(os.path.join(sortie, "attestation.md"),
            attestation(campagne, [f.vers_dict() for f in findings], "fr",
                        destinataire="Jury du hackathon"))
    _ecrire(os.path.join(sortie, "recettes.md"),
            _lancer([sys.executable, "scripts/preuves/recettes.py", "--markdown"]))
    _ecrire(os.path.join(sortie, "tracabilite.md"),
            _lancer([sys.executable, "scripts/preuves/tracabilite.py"]))
    _ecrire(os.path.join(sortie, "evaluation.json"),
            _lancer([sys.executable, "eval/mesurer.py", "--json"]))
    preuves = chaines_depuis_entrepot(entrepot, campagne.id, campagne.tenant_id)
    _ecrire(os.path.join(sortie, "preuves.json"),
            json.dumps(preuves, ensure_ascii=False, indent=1))
    return findings, preuves


def main(argv=None) -> int:
    """Construit le dossier jury."""
    arguments = argv if argv is not None else sys.argv[1:]
    sortie = (arguments[0] if arguments else
              os.path.join(RACINE, "dossier-jury"))
    if os.path.isdir(sortie):
        shutil.rmtree(sortie)
    os.makedirs(sortie, exist_ok=True)

    entrepot = creer_entrepot({"type": "local",
                                "dossier": os.path.join(sortie, "donnees")})
    config = _config(entrepot)
    campagne = executer_campagne(config)
    findings, preuves = _ecrire_pieces(entrepot, campagne, config, sortie)

    if findings:
        _cloture(_decouverte_privilegiee(findings), config, sortie)
    else:
        _ecrire(os.path.join(sortie, "cloture.md"),
                "# Clôture\n\nAucune découverte : rien à fermer.\n")
    _index(sortie, campagne, findings, preuves)
    print("dossier jury : %s" % sortie)
    print("  campagne %s | %d découverte(s) | %d preuve(s) | coût %s"
          % (campagne.id, len(findings), len(preuves), campagne.cout_mesure))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))