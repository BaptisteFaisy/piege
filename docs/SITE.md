# Le site de démonstration — ce qui est réel, et ce qui ne l'est pas

Le site public sert l'**environnement de travail complet**, sur des données
**réelles de bout en bout** — sauf le contenu, volontairement synthétique.

## Ce qui est réel

| Élément | Réalité |
|---|---|
| L'environnement | **Vrai** : le service `piege-api` tourne, le portail est interactif (lancer une campagne, signer le mandat, corriger, rejouer). |
| La campagne `CMP-1113` | **Réelle** : 5 appels à un **vrai modèle** (cible `ali/deepseek-v4-pro-0813`, juge `ag/gemini-3.8-flash-high`), enregistrée le 2026-11-12. |
| Le coût | **Mesuré** : `5e-05 $` (renvoyé par le routeur, jamais estimé — KPI-7). |
| La découverte `C4` | **Réelle** : l'assistant a énuméré l'inventaire du corpus ; citation verbatim, impact 3, sévérité élevée. |
| La boucle de correction | **Complète** : proposition → accord humain → application du garde-fou → rejeu de l'attaque d'origine → **preuve de fermeture datée** (`sha256:`) → statut `ferme`. |

## Ce qui est synthétique (choix délibéré, ENF-07)

Le **contenu** des données est 100 % synthétique : noms, montants et documents
sont inventés (annexe E). Aucune donnée personnelle réelle ne figure nulle
part. Mettre de la vraie donnée personnelle en ligne serait illégal et
contraire au cadre éthique du projet (et à la règle ENF-07, testée).

> Pour le dire autrement : ce sont les **réponses d'un vrai modèle** sur un
> **jeu de démonstration synthétique**. C'est la combinaison « environnement
> réel + données simulées » qui est exposée, pas des données de clients.

## Reconstruire le site (reproductible, 0 €)

```bash
python3 scripts/jury/site.py --magasin <dossier>
python3 -m piege.api.serveur --port 8080 --donnees <dossier> --portail portal
```

`site.py` régénère l'état complet : la campagne réelle rejouée et la boucle de
correction fermée avec sa preuve. Aucun appel de modèle, aucune clé, aucun coût.

## URL

Le site est servi derrière un tunnel Cloudflare (quick tunnel, URL renouvelée à
chaque redémarrage). Pour obtenir l'URL courante :

```bash
journalctl --user -u piege-tunnel | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```

## Que Cliquer

1. **Findings** — la découverte `C4` est `ferme` : correctif, rejeu et preuve
   `sha256:` sont enregistrés.
2. **Campaign** — lancez une nouvelle campagne (hors ligne, gratuite) : la
   boucle repart de zéro.
3. **Preuves** (chaîne) — chaque étape de la campagne porte son empreinte.
4. **Rapport FR/EN** + **attestation** — les livrables client.