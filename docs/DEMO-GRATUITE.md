# Démos gratuites — trois routes, **0 €**

La démo qui impressionne le jury (un vrai modèle qui fuit) coûte, en principe,
des appels de modèle. Elle n'a pas besoin d'être payante pour être crédible :
elle peut être **rejouée**. Voici les trois routes, toutes gratuites, toutes
reproductibles sur un poste sans compte AWS, sans clé d'API et sans réseau.

| Route | Ce qu'elle montre | Coût |
|---|---|---|
| `make demo` | La boucle complète : attaque → réponse → verdict → sévérité → correctif → rejeu → preuve de fermeture, sur la cible vulnérable de démonstration | **0 €** |
| `make demo-reel` | Une **campagne réelle** (vrai modèle) rejouée depuis l'enregistrement | **0 €** |
| `make jury` | Le dossier complet remis au jury (rapports, attestation, recettes, traçabilité, évaluation, clôture) | **0 €** |

## 1. `make demo` — la boucle, hors ligne

```bash
make demo       # campagne de démonstration (cible vulnérable, juge déterministe)
make rapport    # rapport FR + EN de cette campagne
```

Déterministe (graine fixée), 100 % local, aucun appel. C'est la démo que l'on
peut faire **cent fois** sans consommer un centime.

## 2. `make demo-reel` — la campagne réelle, rejouée

```bash
make demo-reel
```

La campagne `CMP-1113` a été enregistrée le 2026-11-12 contre un **vrai modèle**
(cible `ali/deepseek-v4-pro-0813`, juge `ag/gemini-3.8-flash-high`) : 5 appels,
5 941 jetons, **0,00005 $** mesurés, une découverte confirmée (C4, impact 3).

Le rejoueur relit ces enregistrements (`demo/reel/campagne-reelle.json`) et les
rejoue **tels quels** :

- il **alimente le magasin local** (`donnees-locales/`), donc `make rapport`
  et le portail servent ensuite la campagne réelle — findings, chaîne de
  preuves, attestation — sans clé et sans compte ;
- il écrit une **narration** (`demo-reel.md`) : pour chaque technique, la sonde
  envoyée, la réponse réelle du modèle, le verdict, la citation, le coût.

Aucun appel n'est fait : **0 €**, et le résultat est identique à chaque fois.

```bash
make demo-reel && make rapport      # le rapport FR/EN de la campagne réelle
python3 -m piege.api.serveur        # le portail avec la campagne réelle
```

### Enregistrer une nouvelle campagne réelle

Quand on veut rafraîchir la fixture (et qu'on accepte de payer l'appel) :

```bash
export PIEGE_LLM_CLE=...            # clé hors dépôt, jamais versionnée
python3 -m piege.cli demo --graine <graine> --cible demo/cible/guichet-rh-inferhub.json
```

Le magasin local reçoit alors la campagne ; on extrait la fixture à partir de
lui (opération manuelle, une fois par campagne refreshée).

## 3. `make jury` — le dossier remis au jury

```bash
make jury        # dossier-jury/
```

Réunit la campagne de démonstration, les rapports FR/EN, l'attestation, la
**boucle de correction complète** (ouverture → accord humain → application →
rejeu → preuve de fermeture datée), les 20 recettes prouvées, les statuts
recalculés de la traçabilité, le rapport du harnais d'évaluation et la **démo
réelle rejouée**. Un `INDEX.md` dit ce que chaque pièce prouve.

## Et la vidéo ?

Le script (`docs/VIDEO.md`) peut être joué en scénario sur ces trois routes : la
version « réelle » se filme sur `make demo-reel` — **sans coût d'inférence**,
puisque les réponses du modèle sont déjà enregistrées.

## Ce qui reste payant, et pourquoi

Seul l'**enregistrement** d'une nouvelle campagne réelle coûte de l'inférence
(ici 0,00005 $ pour 5 appels). Tout le reste — rejeu, rapport, attestation,
preuves, fermeture, évaluation — est gratuit et déterministe. C'est un choix
délibéré : une démo reproductible ne doit pas dépendre d'un quota.