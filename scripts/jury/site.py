#!/usr/bin/env python3
"""Piège — reconstruit l'état du SITE de démonstration (reproductible, 0 €).

Le site public sert une histoire **complète**, sur des données **réelles** :

- une campagne réelle (vrai modèle via InferHub, coût mesuré 5e-05 $) ;
- une découverte `C4` (extraction de l'inventaire du corpus) ;
- la **boucle de correction entière** : proposition → accord humain → application
  du garde-fou → rejeu de l'attaque d'origine → **preuve de fermeture datée**
  (empreinte `sha256:`) → statut `ferme`.

Tout est rejoué hors modèle, donc gratuit et déterministe : le contenu est
synthétique (annexe E), seules les réponses du modèle sont « réelles »
(enregistrées puis rejouées).

Usage :
    python3 scripts/jury/site.py --magasin <dossier>

Le dossier produit est un magasin local complet : `python3 -m piege.api.serveur
--port 8080 --donnees <dossier> --portail portal` sert alors la démo entière.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "src"))

from piege.cibles import creer_cible
from piege.correctifs.boucle import boucle_complete
from piege.types import Finding, Mandat, depuis_dict

FIXTURE = os.path.join(RACINE, "demo", "reel", "campagne-reelle.json")
SPEC_CIBLE = os.path.join(RACINE, "demo", "cible", "guichet-rh.json")
TABLES = ("campagnes", "executions", "findings", "mandats", "applications")
AUTEUR, ROLE = "anne.rssi", "commanditaire"


def _charger_fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _ecrire_magasin(dossier: str, fixture: dict) -> None:
    """Écrit un magasin local neuf avec la campagne réelle enregistrée."""
    if os.path.isdir(dossier):
        shutil.rmtree(dossier)
    os.makedirs(dossier, exist_ok=True)
    for table in TABLES:
        records = fixture.get(table) or {}
        if not records:
            continue
        with open(os.path.join(dossier, "%s.json" % table), "w",
                  encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=1, sort_keys=True)


def _cible():
    """Cible de démonstration (le correctif y pose un garde-fou)."""
    with open(SPEC_CIBLE, encoding="utf-8") as f:
        spec = json.load(f)
    spec["corpus"] = os.path.join(RACINE, "demo", "corpus")
    return creer_cible(spec)


def _boucle(fixture: dict, entrepot) -> dict:
    """Joue la boucle complète sur la découverte réelle et persiste l'état."""
    from piege.catalogue import charger_catalogue

    catalogue = charger_catalogue(os.path.join(RACINE, "catalogue"))
    mandat = depuis_dict(Mandat, fixture["mandats"]["MAN-2026-0001"])
    finding = depuis_dict(Finding, next(iter(fixture["findings"].values())))
    technique = catalogue[finding.technique_ids[0]]
    bilan = boucle_complete(
        finding, _cible(), mandat, graine=20261113, auteur=AUTEUR, role=ROLE,
        technique=technique, catalogue=catalogue, entrepot=entrepot,
        fournisseur=None, juge=None)
    if bilan.correctif is not None:
        entrepot.ecrire("correctifs", bilan.correctif.vers_dict())
    if bilan.preuve is not None:
        entrepot.ecrire("preuves", bilan.preuve.vers_dict())
    entrepot.ecrire("findings", finding.vers_dict())
    entrepot.ecrire_journal({"qui": "site", "quoi": "boucle_correction",
                             "tenant": finding.tenant_id,
                             "details": {"finding": finding.id,
                                         "preuve": getattr(bilan.preuve, "id", "")},
                             "marqueur": "trafic_reel"})
    return {"ferme": bilan.ferme, "finding": finding.vers_dict(),
            "preuve": bilan.preuve.vers_dict() if bilan.preuve else None,
            "ligne": bilan.ligne}


def main(argv=None) -> int:
    arguments = argv if argv is not None else sys.argv[1:]
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--magasin", default=os.path.join(RACINE, "donnees-locales"))
    analyseur.add_argument("--fixture", default=FIXTURE)
    args = analyseur.parse_args(arguments)

    fixture = _charger_fixture()
    _ecrire_magasin(args.magasin, fixture)
    from piege.stockage import creer_entrepot

    entrepot = creer_entrepot({"type": "local", "dossier": args.magasin})
    resultat = _boucle(fixture, entrepot)
    campagne = list(fixture["campagnes"].values())[0]
    print("site reconstruit : magasin %s" % args.magasin)
    print("  campagne réelle %s | coût mesuré %s $ | découverte %s → %s"
          % (campagne["id"], campagne.get("cout_mesure"),
             resultat["finding"]["id"], resultat["finding"]["statut"]))
    print("  boucle fermée : %s | preuve %s" % (resultat["ferme"],
                                                (resultat["preuve"] or {}).get("id")))
    return 0 if resultat["ferme"] else 1


if __name__ == "__main__":
    sys.exit(main())