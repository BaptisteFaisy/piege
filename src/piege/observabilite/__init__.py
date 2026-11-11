"""Piège — observabilité : traces, compteurs, coût mesuré, budget exposé.

Point d'entrée unique du lot 11. Le coût est **mesuré** depuis les jetons
réellement consommés (ENF-10) et l'écart avec la projection de l'annexe F
déclenche la revue R17 au-delà de 25 %.
"""

from piege.observabilite.agentcore import AdaptateurObservability, vers_otlp
from piege.observabilite.budget import (PROJECTION_ANNEXE_F, SEUIL_REVUE,
                                        budget_restant, ecart_projection)
from piege.observabilite.compteurs import Compteur, compteurs_par_modele
from piege.observabilite.couts import (TARIFS, cout, cout_mesure,
                                       cout_par_modele, cout_par_tenant, tarif)
from piege.observabilite.traces import (Trace, compte, exporter_jsonl,
                                        nouveau_compteur, reinitialiser, tracer,
                                        traces)

__all__ = [
    "Compteur", "compteurs_par_modele", "TARIFS", "tarif", "cout",
    "cout_mesure", "cout_par_modele", "cout_par_tenant", "tracer", "compte",
    "nouveau_compteur", "traces", "Trace", "exporter_jsonl", "reinitialiser",
    "budget_restant", "PROJECTION_ANNEXE_F", "SEUIL_REVUE", "ecart_projection",
    "vers_otlp", "AdaptateurObservability",
]
