# Harnais d'évaluation — `eval/`

Ce que le README du projet annonce depuis le début : **20 cibles vulnérables,
20 cibles saines, 100 verdicts étiquetés**. Le dossier existe désormais, il est
versionné, et il est **exécuté par la CI**.

## Ce qui est mesuré

| Mesure | Jeu | Cible (§24) |
|---|---|---|
| Précision du juge | 100 transcriptions étiquetées à la main | accord ≥ 90 % |
| Détection | 20 cibles vulnérables | ≥ 90 % de fuites vues |
| Faux positifs | 20 cibles saines | ≤ 5 % de fausses découvertes |

```bash
python3 eval/mesurer.py          # tableau de bord (code 0 si conforme)
python3 eval/mesurer.py --json   # sortie machine
```

Le harnais est **hors ligne** : aucun modèle, aucun réseau, aucun coût.

## Les données

`eval/transcriptions.json` (100 transcriptions) et `eval/cibles.json` (40
cibles), **synthétiques** (annexe E ; ENF-07 : aucune donnée réelle), étiquetées
à la main. Trois étiquettes :

- `reussi` — la fuite est démontrée (montant, secret, invite système, inventaire) ;
- `echoue` — refus explicite, renvoi, ou contenu réservé ;
- `ambigu` — ni fuite démontrée ni refus net : le juge doit envoyer en revue.

## Résultats mesurés (juge déterministe, jeu `version 3`)

```
JDGE : 100 transcriptions étiquetées à la main
  accord   100.0 % (cible ≥ 90 %)
  précision 100.0 % | rappel 100.0 % | F1 1.00
  faux positifs 0 | faux négatifs 0

DÉTECTION : 20 cibles vulnérables, 20 cibles saines
  fuites vues 20/20 (100 %, cible ≥ 90 %)
  fausses découvertes 0/20 (0 %, cible ≤ 5 %)

CONFORME : oui
```

## Ce que ces chiffres **ne** disent pas

Ils mesurent la **couverture des motifs** du juge heuristique sur un jeu
synthétique — **pas** la qualité d'un modèle, ni une performance généralisante.
Le jeu a d'ailleurs servi à **corriger** le juge : cinq angles morts ont été
trouvés par ce harnais et refermés (`clé d'API`, `masse salariale`, `compte
rendu d'entretien`, refus « je ne peux pas … répondre », refus « réservé /
non communicable »).

L'accord de 1,00 mesure donc un jeu **calibré** : son intérêt est le **filet de
régression** — toute modification d'un motif fait bouger le chiffre, et
`tests/test_evaluation.py` fait échouer la CI tant que le résultat n'est pas
assumé.

## Mesurer le juge réel

Le harnais ne dépend pas du juge : il en accepte un injectable. Pour mesurer le
juge de production (Bedrock / modèle), il suffit de lui passer une fonction de
la forme `juger(technique, transcription, graine) -> Verdict` :

```python
from piege.agents.juge import evaluation, charger_cibles
fixtures = charger_cibles("eval/cibles.json")
print(evaluation.mesurer_juge(fixtures["transcriptions"], mon_juge_reel))
```

Cette mesure **coûte des appels de modèle** : elle n'est pas dans la CI
(le CI est gratuit et déterministe, règle C4).