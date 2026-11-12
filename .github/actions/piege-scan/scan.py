#!/usr/bin/env python3
"""Script de scan de la GitHub Action Piège.

Deux modes :
- `PIEGE_API_URL` renseigné → campagne via le SDK contre une API Piège distante ;
- sinon → scan hors ligne d'une cible locale via le moteur (aucun réseau).

Écrit les sorties dans le format attendu par `$GITHUB_OUTPUT` (clés `findings`,
`critiques`, `campagne_id`) et un résumé lisible sur stdout. Aucune dépendance
tierce ; le jeton n'est jamais affiché.
"""

from __future__ import annotations

import json
import os
import sys


def _ecrire_sortie(cle: str, valeur) -> None:
    """Écrit une sortie GitHub Actions (fichier $GITHUB_OUTPUT)."""
    chemin = os.environ.get("GITHUB_OUTPUT")
    if chemin:
        with open(chemin, "a", encoding="utf-8") as f:
            f.write("%s=%s\n" % (cle, valeur))


def _techniques() -> list:
    brut = os.environ.get("PIEGE_TECHNIQUES", "")
    return [t.strip() for t in brut.split(",") if t.strip()]


def _graine() -> int:
    try:
        return int(os.environ.get("PIEGE_SEED", "0") or "0")
    except ValueError:
        return 0


def scan_distant(api_url: str, jeton: str) -> dict:
    """Lance une campagne via le SDK contre une API Piège distante."""
    from piege.sdk import Client

    client = Client(api_url, jeton)
    sante = client.sante()
    mandats = sante.get("dernier_mandat") or {}
    mandat_id = os.environ.get("PIEGE_MANDAT_ID") or mandats.get("id", "")
    if not mandat_id:
        return {"erreur": "aucun mandat_id (définir PIEGE_MANDAT_ID)"}
    campagne = client.lancer_campagne(mandat_id, graine=_graine(),
                                      technique_ids=_techniques() or None)
    findings = client.lister_findings()
    critiques = [f for f in findings if f.get("severite") == "critique"]
    return {"campagne_id": campagne.get("campagne", {}).get("id", ""),
            "findings": len(findings), "critiques": len(critiques)}


def scan_local(cible_spec: str) -> dict:
    """Scan hors ligne d'une cible locale via le moteur (aucun réseau).

    Les découvertes sont comptées depuis les exécutions réussies (verdict
    `reussi`), les critiques depuis celles d'impact 4. Un entrepôt temporaire
    reçoit les exécutions ; rien n'est écrit dans le dépôt.
    """
    import tempfile

    from piege.moteur import executer_campagne
    from piege.moteur.demo import campagne_de_demonstration
    from piege.stockage import creer_entrepot

    spec = {}
    if cible_spec and os.path.isfile(cible_spec):
        with open(cible_spec, encoding="utf-8") as f:
            spec = json.load(f)
    config = campagne_de_demonstration(graine=_graine(), cible_spec=spec,
                                       technique_ids=_techniques() or None)
    config.entrepot = creer_entrepot({"type": "local",
                                      "dossier": tempfile.mkdtemp(prefix="piege-scan-")})
    campagne = executer_campagne(config)
    executions = config.entrepot.lister("executions", campagne_id=campagne.id)
    reussies = [e for e in executions if e.get("verdict") == "reussi"]
    critiques = [e for e in reussies if e.get("impact") == 4]
    return {"campagne_id": campagne.id, "findings": len(reussies),
            "critiques": len(critiques), "statut": campagne.statut.value}


def main() -> int:
    """Point d'entrée : choisit le mode, écrit les sorties, résume."""
    api_url = os.environ.get("PIEGE_API_URL", "")
    jeton = os.environ.get("PIEGE_TOKEN", "")
    if api_url:
        if not jeton:
            print("::error::PIEGE_TOKEN requis quand PIEGE_API_URL est défini")
            return 1
        resultat = scan_distant(api_url, jeton)
    else:
        resultat = scan_local(os.environ.get("PIEGE_TARGET", ""))
    if "erreur" in resultat:
        print("::error::%s" % resultat["erreur"])
        return 1
    _ecrire_sortie("findings", resultat.get("findings", 0))
    _ecrire_sortie("critiques", resultat.get("critiques", 0))
    _ecrire_sortie("campagne_id", resultat.get("campagne_id", ""))
    print("Piège scan — campagne %s : %s finding(s), %s critique(s)"
          % (resultat.get("campagne_id", "?"), resultat.get("findings", 0),
             resultat.get("critiques", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
