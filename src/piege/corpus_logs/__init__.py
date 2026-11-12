"""Piège — génération du corpus légitime depuis les journaux d'usage (#50).

Point d'entrée : `generer_corpus(entrees, application_id, tenant_id)` rend un
`CorpusLegitime` anonymisé, dédoublonné, avec criticité estimée — directement
consommable par la famille G. Lève `CorpusLegitimeAbsent` sous le minimum de
50 demandes (EF-30) : jamais de corpus tronqué.
"""

from piege.corpus_logs.anonymiseur import (Jeton, anonymiser, contient_pii,
                                            types_presents)
from piege.corpus_logs.criticite import DETAIL, MOTS_CRITICITE, estimer_criticite
from piege.corpus_logs.generateur import (MINIMUM_DEMANDES, generer_corpus,
                                          normaliser_entrees, statistiques_pii,
                                          valider_minimum)

__all__ = [
    "generer_corpus", "normaliser_entrees", "statistiques_pii",
    "valider_minimum", "MINIMUM_DEMANDES", "anonymiser", "contient_pii",
    "types_presents", "Jeton", "estimer_criticite", "MOTS_CRITICITE", "DETAIL",
]
