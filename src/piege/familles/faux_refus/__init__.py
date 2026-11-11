"""Piège — famille G : refus excessif sur des demandes légitimes.

Le second différenciateur du produit : un assistant qui refuse une demande
parfaitement légitime est un échec au même titre qu'un assistant qui divulgue.
Le rapport client présente les deux chiffres côte à côte.

Point d'entrée : `executer(corpus, cible, graine, journal)`. Sans corpus fourni
par le client, `refuser_sans_corpus` lève `CorpusLegitimeAbsent` : la famille ne
publie jamais un chiffre vide (EF-34).
"""

from piege.familles.faux_refus.classifieur import (MOTIFS_CAUSES, classifier,
                                                   cause, est_justifie)
from piege.familles.faux_refus.corpus import (CRITICITES, MINIMUM_DEMANDES,
                                              charger_corpus, depuis_donnees,
                                              repartition, valider_corpus)
from piege.familles.faux_refus.executant import (executer, executer_demande,
                                                 refuser_sans_corpus,
                                                 taux_de_refus)
from piege.familles.faux_refus.resume import (heures_perdues_totales,
                                              par_cause, par_criticite,
                                              par_severite,
                                              pertes_les_plus_fortes, resume)

__all__ = [
    "executer", "executer_demande", "refuser_sans_corpus", "taux_de_refus",
    "charger_corpus", "valider_corpus", "depuis_donnees", "repartition",
    "MINIMUM_DEMANDES", "CRITICITES", "classifier", "cause", "est_justifie",
    "MOTIFS_CAUSES", "resume", "par_criticite", "par_cause", "par_severite",
    "heures_perdues_totales", "pertes_les_plus_fortes",
]
