#!/usr/bin/env python3
"""Piège — démo « réelle » **gratuite** : rejeu d'une campagne enregistrée.

La démo qui impressionne le jury (un vrai modèle qui fuit) coûte des appels
de modèle. Ce script **rejoue** une campagne réelle déjà enregistrée : les
réponses du vrai modèle sont relues telles quelles, la boucle complète tourne
(rapport, découverte, chaîne de preuves), et le coût est de **0 €** — aucune
clé, aucun compte, aucun réseau.

Deux sorties :
- le **magasin local** alimenté (`donnees-locales/` par défaut) : le portail,
  `make rapport` et l'API servent alors la campagne réelle enregistrée ;
- une **narration** Markdown (`demo-reel.md`) : sonde → réponse réelle → verdict
  → citation → coût, ligne par ligne.

Usage :
    python3 scripts/jury/demo-reel.py                    # rejoue dans donnees-locales
    python3 scripts/jury/demo-reel.py --magasin /tmp/x   # ailleurs
    python3 scripts/jury/demo-reel.py --sortie /tmp/demo-reel.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "src"))

FIXTURE = os.path.join(RACINE, "demo", "reel", "campagne-reelle.json")
MAGASIN_DEFAUT = os.path.join(RACINE, "donnees-locales")
TABLES = ("campagnes", "executions", "findings", "mandats", "applications")


def _valeur(valeur) -> str:
    return getattr(valeur, "value", None) or str(valeur or "")


def charger(chemin: str) -> dict:
    """Charge la fixture de la campagne réelle enregistrée."""
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def ecrire_magasin(dossier: str, fixture: dict) -> dict:
    """Alimente le magasin local avec la campagne enregistrée (écriture JSON)."""
    os.makedirs(dossier, exist_ok=True)
    for table in TABLES:
        records = fixture.get(table) or {}
        if not records:
            continue
        with open(os.path.join(dossier, "%s.json" % table), "w",
                  encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=1, sort_keys=True)
    return {table: len(fixture.get(table) or {}) for table in TABLES}


def _extrait(texte: str, longueur: int = 320) -> str:
    """Extrait lisible d'une réponse (une seule ligne)."""
    return " ".join((texte or "").split())[:longueur]


def narrer(fixture: dict) -> str:
    """Narration de la démo : ce qui a été dit, statué, et ce que ça a coûté."""
    source = fixture.get("source", {})
    campagnes = list((fixture.get("campagnes") or {}).values())
    entete = campagnes[0] if campagnes else {}
    lignes = [
        "# Démo réelle — rejouée, **0 €**", "",
        "> Cette démo rejoue des réponses **enregistrées** d'un vrai modèle : "
        "aucun appel, aucune clé, aucun coût. Le contenu est synthétique "
        "(annexe E) — aucune donnée réelle.", "",
        "- Campagne : `%s` — graine `%s`" % (entete.get("id", "?"),
                                             entete.get("graine", "?")),
        "- Cible : %s" % source.get("cible", "?"),
        "- Juge : %s" % source.get("juge", "?"),
        "- Enregistrée le : %s" % (source.get("enregistree_le") or "?"),
        "- Coût réel mesuré à l'époque : **%s $** · %s appels · %s jetons"
        % (entete.get("cout_mesure", 0), entete.get("appels", 0),
           entete.get("jetons", 0)),
        "- **Coût de cette rejouée : 0 $**", "",
    ]
    for execution in sorted((fixture.get("executions") or {}).values(),
                            key=lambda e: e.get("technique_id", "")):
        technique = execution.get("technique_id", "?")
        sonde = (execution.get("sondes_envoyees") or [""])[0]
        verdict = execution.get("verdict") or "non statué"
        marque = "REUSSI" if verdict == "reussi" else "ECHEC"
        lignes += [
            "## %s — %s — verdict **%s** (confiance %s)"
            % (marque, technique, verdict, execution.get("confiance")),
            "",
            "- **Sonde envoyée** : %s" % _extrait(sonde, 200),
            "- **Réponse du modèle** : %s" % _extrait(execution.get("reponse_brute", "")),
            "- **Motif du juge** : %s" % _extrait(execution.get("motif", ""), 200),
        ]
        if execution.get("citation"):
            lignes.append("- **Citation** : %s" % _extrait(execution["citation"], 220))
        lignes += ["- Coût de l'appel : %s $ · %s jetons · %s ms"
                   % (execution.get("cout", 0), execution.get("jetons", 0),
                      execution.get("latence_ms", 0)), ""]
    for finding in (fixture.get("findings") or {}).values():
        lignes += [
            "## Découverte — %s (%s)" % (finding.get("titre", "?"),
                                        finding.get("severite", "?")),
            "",
            "- Techniques : %s" % ", ".join(finding.get("technique_ids") or []),
            "- Description : %s" % _extrait(finding.get("description", ""), 240),
            "- Statut : %s" % finding.get("statut", "?"),
            "",
        ]
    return "\n".join(lignes) + "\n"


def main(argv=None) -> int:
    """Rejoue la campagne réelle enregistrée et narre la démo."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--fixture", default=FIXTURE)
    analyseur.add_argument("--magasin", default=MAGASIN_DEFAUT)
    analyseur.add_argument("--sortie", default=os.path.join(RACINE, "demo-reel.md"))
    args = analyseur.parse_args(argv)

    if not os.path.isfile(args.fixture):
        print("fixture absente : %s" % args.fixture, file=sys.stderr)
        return 2
    fixture = charger(args.fixture)
    compte = ecrire_magasin(args.magasin, fixture)
    texte = narrer(fixture)
    with open(args.sortie, "w", encoding="utf-8") as f:
        f.write(texte)
    campagnes = list((fixture.get("campagnes") or {}).values())
    identifiant = campagnes[0].get("id", "?") if campagnes else "?"
    print("démo réelle rejouée : campagne %s" % identifiant)
    print("  magasin : %s (%s)" % (args.magasin,
                                  ", ".join("%s %d" % (t, n)
                                            for t, n in compte.items() if n)))
    print("  narration : %s" % args.sortie)
    print("  coût de la rejouée : 0 $")
    return 0


if __name__ == "__main__":
    sys.exit(main())