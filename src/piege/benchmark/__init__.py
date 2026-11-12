"""Piège — benchmark inter-clients anonymisé (#41).

Point d'entrée : `comparer(score, pool, secteur)` rend la position d'une
application dans le pool (percentile, repères, lecture). Le pool ne contient
que des empreintes non réversibles de tenants — jamais d'identité.
"""

from piege.benchmark.agregat import (SECTEURS, Contribution, comparer,
                                     construire_pool, empreinte_tenant,
                                     percentile, statistiques)

__all__ = ["Contribution", "construire_pool", "percentile", "statistiques",
           "comparer", "empreinte_tenant", "SECTEURS"]
