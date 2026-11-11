"""Piège — familles d'attaques spécialisées.

Deux familles exigent un outillage propre, au-delà du couple attaquant/juge :

- `empoisonnement` (famille F) : elle teste la **chaîne documentaire**, pas
  l'assistant. Elle crée un index de test isolé, y dépose un document piégé,
  mesure le relais, l'exécution et la persistance, puis détruit l'index.
- `faux_refus` (famille G) : elle ne cherche pas à faire échouer la sécurité,
  elle joue un utilisateur légitime et mesure ce qui est cassé par excès de
  prudence. Sans corpus de demandes légitimes, elle refuse de produire un
  chiffre vide (EF-34).
"""

__all__: list[str] = []
