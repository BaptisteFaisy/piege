"""Piège — mandats : la condition bloquante de toute exécution.

Rien ne s'exécute sans un mandat signé, dans sa fenêtre de validité, couvrant
la cible et la technique demandées (EF-03, EF-04, ENF-01, spécification §21).
Un mandat expiré ne démarre aucune campagne, même de quelques heures.
"""

from __future__ import annotations

from typing import Iterable, Optional

from piege.erreurs import MandatExpire, MandatInvalide, ValeurHorsPlage
from piege.types import (Environnement, Mandat, StatutMandat, canonical,
                         empreinte, maintenant_utc)

__all__ = ["creer", "contenu_canonique", "signer", "valider", "est_expire",
           "CHAMPS_SIGNES"]

# Les champs couverts par la signature : tout ce qui définit le périmètre.
CHAMPS_SIGNES = ("id", "tenant_id", "application_id", "perimetre_techniques",
                 "environnements", "fenetre_debut", "fenetre_fin",
                 "budget_appels", "budget_jetons", "production_autorisee",
                 "contact_urgence")


def creer(tenant_id: str, application_id: str, perimetre_techniques: Iterable[str],
          environnements: Iterable[Environnement], fenetre_debut: str,
          fenetre_fin: str, budget_appels: int, budget_jetons: int,
          production_autorisee: bool, contact_urgence: str,
          sequence: int = 1) -> Mandat:
    """Construit un mandat en brouillon, non signé, donc inexploitable."""
    if budget_appels <= 0 or budget_jetons <= 0:
        raise ValeurHorsPlage("un budget doit être strictement positif",
                              details={"regle": "mandat.budget"})
    if fenetre_fin <= fenetre_debut:
        raise ValeurHorsPlage("fenêtre de validité inversée",
                              details={"regle": "mandat.fenetre"})
    identifiant = "MAN-%s-%04d" % (fenetre_debut[:4], sequence)
    return Mandat(
        id=identifiant, tenant_id=tenant_id, application_id=application_id,
        perimetre_techniques=sorted(set(perimetre_techniques)),
        environnements=[Environnement(e) for e in environnements],
        fenetre_debut=fenetre_debut, fenetre_fin=fenetre_fin,
        budget_appels=budget_appels, budget_jetons=budget_jetons,
        production_autorisee=production_autorisee,
        contact_urgence=contact_urgence, signe_le="", signature="",
        statut=StatutMandat.BROUILLON)


def contenu_canonique(mandat: Mandat) -> str:
    """Contenu signé : JSON canonique des champs de périmètre."""
    donnees = mandat.vers_dict()
    return canonical({champ: donnees[champ] for champ in CHAMPS_SIGNES})


def signer(mandat: Mandat, cle: str = "cle-de-demonstration") -> Mandat:
    """Signe le mandat (empreinte du contenu canonique) et le passe valide.

    La signature n'est pas un dispositif cryptographique de production : c'est
    une empreinte horodatée qui rend toute modification du périmètre
    détectable. Le chapitre 21 rappelle que la validation juridique du
    dispositif réel reste à faire par un juriste.
    """
    mandat.signe_le = maintenant_utc()
    mandat.signature = empreinte(contenu_canonique(mandat) + "|" + cle)
    mandat.statut = StatutMandat.VALIDE
    return mandat


def signature_valide(mandat: Mandat, cle: str = "cle-de-demonstration") -> bool:
    """Vérifie que le contenu signé n'a pas été modifié depuis la signature."""
    if not mandat.signature:
        return False
    return mandat.signature == empreinte(contenu_canonique(mandat) + "|" + cle)


def est_expire(mandat: Mandat, maintenant: Optional[str] = None) -> bool:
    """Vrai si l'instant courant sort de la fenêtre de validité."""
    instant = maintenant or maintenant_utc()
    return not (mandat.fenetre_debut <= instant <= mandat.fenetre_fin)


def valider(mandat: Optional[Mandat], maintenant: Optional[str] = None) -> Mandat:
    """Vérifie qu'un mandat autorise une exécution à l'instant courant.

    Lève `MandatInvalide` (absent, non signé, statut non valide, signature
    incohérente) ou `MandatExpire` (hors fenêtre). Ne retourne jamais `None`.
    """
    if mandat is None:
        raise MandatInvalide("aucun mandat fourni : exécution refusée",
                             details={"regle": "mandat.present"})
    if mandat.statut is not StatutMandat.VALIDE:
        raise MandatInvalide("mandat %s au statut %s : exécution refusée"
                             % (mandat.id, mandat.statut.value),
                             details={"regle": "mandat.statut"})
    if mandat.signature and not signature_valide(mandat):
        raise MandatInvalide("signature du mandat %s incohérente avec son "
                             "périmètre" % mandat.id,
                             details={"regle": "mandat.signature"})
    if est_expire(mandat, maintenant):
        raise MandatExpire("mandat %s hors fenêtre [%s → %s]"
                           % (mandat.id, mandat.fenetre_debut, mandat.fenetre_fin),
                           details={"regle": "mandat.fenetre"})
    return mandat
