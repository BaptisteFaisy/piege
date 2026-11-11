"""Piège — sécurité : mandats, politique de périmètre, identité, journal.

Le principe architectural central du projet (spécification §17.3) : **les
règles sont appliquées par la passerelle, pas par l'invite**. Ce paquet est la
référence locale de ces règles ; l'adaptateur AgentCore Policy
(`securite.agentcore`) les projette sur le cloud et vérifie que la décision
distante est identique à la décision locale.
"""

from piege.securite.identite import (ROLES, exiger_role, jeton_test,
                                     refuser_tenant_en_parametre, roles,
                                     resoudre_tenant)
from piege.securite.journal import Journal, entree_journal
from piege.securite.mandats import (contenu_canonique, creer, est_expire,
                                    signer, valider)
from piege.securite.politique import evaluer, exiger, lever_refus

__all__ = [
    "creer", "signer", "valider", "est_expire", "contenu_canonique",
    "evaluer", "exiger", "lever_refus", "resoudre_tenant", "exiger_role",
    "roles", "jeton_test", "refuser_tenant_en_parametre", "ROLES", "Journal",
    "entree_journal",
]
