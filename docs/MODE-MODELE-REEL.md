# Mode « vrai modèle » — basculer du simulateur vers un LLM réel

Piège tourne par défaut sur un **simulateur déterministe hors ligne** : la cible
répond par règles et le juge classe par motifs. C'est ce qui rend la CI et
`make demo` reproductibles, gratuits et sans réseau.

Le mode « vrai modèle » remplace les deux par de véritables appels à un modèle,
via une API compatible OpenAI (InferHub par défaut ; Bedrock en production).
La fuite n'est plus simulée : elle est réellement produite par un modèle qui
confond données et instructions.

## Ce qui change, ce qui ne change pas

| Brique | Mode hors ligne | Mode vrai modèle |
|---|---|---|
| Récupération RAG | locale, score TF-IDF | **identique** (locale, déterministe) |
| Garde-fous de la cible | règles | **identiques** (refus avant tout appel) |
| Index de test famille F | isolé, détruit | **identique** |
| Génération de la réponse | règles | **modèle réel** |
| Verdict du juge | règles | **modèle réel**, sortie structurée |
| Politique de périmètre | code | **identique** (jamais déléguée au modèle) |
| Sévérité | code | **identique** (règle C5 : jamais par un modèle) |

Rien de ce qui garantit la sécurité du test ne dépend du modèle : le périmètre,
le budget, l'arrêt d'urgence et la sévérité restent du code.

## Activation

```bash
export PIEGE_LLM_CLE="…"                     # jamais dans le dépôt
export PIEGE_CIBLE_TYPE=inferhub             # cible à modèle réel
export PIEGE_CIBLE_MODELE=ali/deepseek-v4-pro-0813
export PIEGE_FOURNISSEUR=inferhub            # juge sur modèle réel
export PIEGE_LLM_MODELE=ali/qwen3.8-27b      # modèle du juge (différent = jury hétérogène)
export PIEGE_MAX_TECHNIQUES=8                # plafond anti-abus en instance publique
python3 -m piege.api.serveur --port 8080
```

La spécification de cible `demo/cible/guichet-rh-inferhub.json` décrit la même
application que la cible de démonstration, avec `"type": "inferhub"`.

En systemd, la clé passe par un `EnvironmentFile` en `0600` hors du dépôt :
jamais en clair dans l'unité, jamais dans le code, jamais dans les journaux.

## Coût et latence mesurés

Le routeur renvoie le coût réel de chaque appel : il est capté dans
`ReponseModele.brut["cout"]`, cumulé par la cible (`statistiques()`) et reporté
par l'observabilité (KPI-7). Ordre de grandeur constaté avec
`ali/deepseek-v4-pro-0813` : ~0,00001 $ par appel, 3 à 6 s par appel.

Une campagne de 4 techniques coûte donc moins d'un centième de centime et dure
quelques dizaines de secondes. Une campagne complète (60 techniques, ~288
appels) reste sous le dollar mais prend plusieurs minutes : c'est exactement ce
que borne `PIEGE_MAX_TECHNIQUES` sur une instance publique.

## Garde-fous du mode public

1. **Plafond de techniques** : au-delà, la demande est refusée avec un message
   explicite — jamais tronquée en silence.
2. **Budget du mandat** : appels et jetons plafonnés dans le code (ENF-02),
   arrêt propre au seuil.
3. **Clé hors dépôt** : variable d'environnement ou `EnvironmentFile` en 0600.
4. **Aucune donnée personnelle** : le corpus reste le jeu synthétique
   filigrané ; le mode réel ne change rien à l'ENF-07.

## Repasser hors ligne

Supprimer `PIEGE_CIBLE_TYPE` et `PIEGE_FOURNISSEUR` (ou les mettre à `local`) :
la CI et `make demo` reviennent au simulateur déterministe, sans clé ni réseau.
