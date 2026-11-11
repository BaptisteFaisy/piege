"""Piège — pentest continu des applications d'IA générative.

Le paquet est importable avec `PYTHONPATH=src` (aucune installation requise)
ou après `pip install -e .`. Le cœur n'a **aucune dépendance tierce** : les
backends AWS et les fournisseurs de modèle sont importés paresseusement, à
l'intérieur des fonctions qui s'en servent (CONTRACTS.md §1, règle C3).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
