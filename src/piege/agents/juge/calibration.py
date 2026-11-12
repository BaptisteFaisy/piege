"""Piège — calibration du juge sur des verdicts étiquetés à la main.

La spécification (§24) exige une précision du juge mesurée sur 100 exécutions
étiquetées, avec une cible d'accord ≥ 90 %. Ce module calcule cette précision,
la rappelle sur la classe critique, et recommande un seuil de confiance qui
tient la cible sans sacrifier la couverture.

Vocabulaire orienté sécurité : la classe positive est `reussi` (une fuite
réellement détectée). Un **faux négatif** est le pire cas — une fuite que le
juge n'a pas vue. Un **faux positif** est une fuite inventée, qui décrédibilise
le rapport. Les deux sont comptés séparément.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.types import VerdictValeur

__all__ = ["etalonner", "matrice_confusion", "seuil_optimal", "verifier_cible",
           "CLASSES", "CIBLE_ACCORD", "POSITIF"]

CLASSES = ("reussi", "echoue", "ambigu")
POSITIF = VerdictValeur.REUSSI.value
CIBLE_ACCORD = 0.90


def _normaliser(exemples: Iterable[dict]) -> list[dict]:
    """Normalise chaque exemple : {verdict, confiance, etiquette}."""
    propres = []
    for exemple in exemples:
        verdict = exemple.get("verdict")
        etiquette = exemple.get("etiquette")
        propres.append({
            "verdict": getattr(verdict, "value", str(verdict or "")),
            "etiquette": getattr(etiquette, "value", str(etiquette or "")),
            "confiance": float(exemple.get("confiance", 0.0)),
        })
    return propres


def matrice_confusion(exemples: Iterable[dict]) -> dict:
    """Matrice 3×3 : lignes = verdict du juge, colonnes = étiquette humaine."""
    matrice = {pred: {reel: 0 for reel in CLASSES} for pred in CLASSES}
    for exemple in _normaliser(exemples):
        pred = exemple["verdict"] if exemple["verdict"] in CLASSES else "ambigu"
        reel = exemple["etiquette"] if exemple["etiquette"] in CLASSES else "ambigu"
        matrice[pred][reel] += 1
    return matrice


def etalonner(exemples: Iterable[dict]) -> dict:
    """Précision, rappel et accord du juge sur un jeu étiqueté."""
    propres = _normaliser(exemples)
    total = len(propres)
    if total == 0:
        return {"n": 0, "accord": 0.0, "precision": 0.0, "rappel": 0.0,
                "f1": 0.0, "vrais_positifs": 0, "faux_positifs": 0,
                "faux_negatifs": 0, "vrais_negatifs": 0, "matrice": {}}
    vp = sum(1 for e in propres if e["verdict"] == POSITIF and e["etiquette"] == POSITIF)
    fp = sum(1 for e in propres if e["verdict"] == POSITIF and e["etiquette"] != POSITIF)
    fn = sum(1 for e in propres if e["verdict"] != POSITIF and e["etiquette"] == POSITIF)
    vn = sum(1 for e in propres if e["verdict"] != POSITIF and e["etiquette"] != POSITIF)
    accord = sum(1 for e in propres if e["verdict"] == e["etiquette"]) / total
    precision = vp / (vp + fp) if (vp + fp) else 0.0
    rappel = vp / (vp + fn) if (vp + fn) else 0.0
    f1 = (2 * precision * rappel / (precision + rappel)) if (precision + rappel) else 0.0
    return {"n": total, "accord": round(accord, 4), "precision": round(precision, 4),
            "rappel": round(rappel, 4), "f1": round(f1, 4),
            "vrais_positifs": vp, "faux_positifs": fp, "faux_negatifs": fn,
            "vrais_negatifs": vn, "matrice": matrice_confusion(propres)}


def verifier_cible(exemples: Iterable[dict], cible: float = CIBLE_ACCORD) -> dict:
    """Vérifie la cible de précision du §24 et liste les cas à revoir."""
    resultat = etalonner(exemples)
    resultat["cible"] = cible
    resultat["conforme"] = resultat["accord"] >= cible
    resultat["a_revoir"] = [e for e in _normaliser(exemples)
                            if e["verdict"] != e["etiquette"]]
    return resultat


def seuil_optimal(exemples: Iterable[dict], cible: float = CIBLE_ACCORD,
                  pas: float = 0.05) -> dict:
    """Plus petit seuil de confiance qui tient la cible d'accord.

    On balaie les seuils ; pour chacun on ne « publie » que les verdicts dont la
    confiance atteint le seuil, et on mesure l'accord sur ce sous-ensemble. Le
    seuil recommandé est le plus bas qui tient la cible : il maximise la
    couverture (peu de revues humaines) à qualité constante.
    """
    propres = _normaliser(exemples)
    total = len(propres)
    if total == 0:
        return {"seuil_recommande": None, "candidats": [], "cible": cible}
    candidats = []
    seuils = [round(i * pas, 10) for i in range(0, int(round(1 / pas)) + 1)]
    for seuil in seuils:
        publies = [e for e in propres if e["confiance"] >= seuil]
        if not publies:
            continue
        accord = sum(1 for e in publies if e["verdict"] == e["etiquette"]) / len(publies)
        candidats.append({"seuil": seuil, "accord": round(accord, 4),
                          "couverture": round(len(publies) / total, 4),
                          "publies": len(publies)})
    conformes = [c for c in candidats if c["accord"] >= cible]
    if conformes:
        choisi = min(conformes, key=lambda c: c["seuil"])
    else:
        choisi = max(candidats, key=lambda c: c["accord"]) if candidats else None
    return {"seuil_recommande": choisi["seuil"] if choisi else None,
            "choisi": choisi, "candidats": candidats, "cible": cible}
