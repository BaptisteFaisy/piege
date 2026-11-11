# Observabilité — ce qui est mesuré, où, et comment

**Tout est mesuré, rien n'est estimé.** Le coût d'une campagne vient des jetons
réellement consommés (ENF-10, KPI-7) ; une estimation ne sert que de base de
comparaison, jamais de chiffre publié.

## Ce qui est collecté

| Module | Collecte | Consommé par |
|---|---|---|
| `compteurs.py` | Appels, jetons entrée/sortie, coût, répartition par modèle — thread-safe | Moteur (lot 3), rapport (lot 12) |
| `couts.py` | Table de tarifs unique, coût par échange, coût mesuré, coût par tenant | Rapport, vue responsable de compte (EF-63) |
| `traces.py` | Traces structurées avec durées, export JSON Lines | Portail, Amazon Quick (lot 13), AgentCore Observability |
| `budget.py` | Budget restant, écart à la projection de l'annexe F (R17) | Portail, API `/budget`, revue |
| `agentcore.py` | Projection OTLP et publication CloudWatch (boto3 paresseux) | Déploiement (lot 14) |

## La table de tarifs

Un seul endroit, une seule vérité (`couts.py`) : `nova-lite` 0,06 / 0,24 ;
`modele-fort` 3,00 / 15,00 ; `inferhub-flash` 0,00075 / 0,00375 dollar par
million de jetons (entrée / sortie). Un modèle inconnu lève une erreur au lieu
de basculer sur un tarif deviné : une facture fausse est précisément ce que ce
service promet de ne jamais produire.

## La règle des 25 % (R17)

`ecart_projection` compare le coût mesuré à la projection de l'annexe F
(3,35 $ en mixte, 0,17 $ en Nova Lite, 8,91 $ en modèle fort). Au-delà de 25 %
d'écart, dans un sens comme dans l'autre, la revue est obligatoire : une
sous-estimation est aussi suspecte qu'un dépassement.

## Hors ligne par défaut

Aucun réseau, aucun compte AWS, aucun paquet tiers : compteurs, traces, coûts
et export JSON Lines tournent en local. La publication vers CloudWatch exige
`boto3` et des identifiants, et le dit explicitement s'ils manquent.
