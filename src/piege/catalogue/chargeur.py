"""Piège — chargeur YAML : un sous-ensemble strict, sans dépendance tierce.

PyYAML n'est pas disponible sur les runners de CI et le cœur du projet ne doit
avoir aucune dépendance tierce (règle C3). Ce module implémente donc un
sous-ensemble YAML **précis et testé** (CONTRACTS.md §5.1) :

- commentaires (`#`) et lignes vides ;
- `clé: valeur`, cartes imbriquées par indentation de 2 espaces ;
- listes en bloc (`- élément`) et listes en ligne (`[a, b, c]`) ;
- scalaires quotés (`"…"`, `'…'`), entiers, flottants, `true/false`, `null/~` ;
- **booléens : uniquement `true` et `false`** (schéma YAML 1.2). Les formes
  `oui/non/vrai/faux/yes/no/on/off` ne sont volontairement **pas** interprétées
  comme des booléens : `oui` est une valeur d'énumération du catalogue
  (`production: oui`) et doit rester une chaîne ;
- blocs repliés (`>`) et littéraux (`|`) ;
- **non supportés, et refusés avec un message explicite** : ancres, alias,
  flux multi-documents, clés complexes, listes imbriquées en flux.

La sortie est un dictionnaire ou une liste de valeurs Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

__all__ = ["ErreurYaml", "charger_fichier", "charger_texte", "SOUS_ENSEMBLE"]

SOUS_ENSEMBLE = ("cartes", "listes", "listes en ligne", "scalaires quotés",
                 "entiers", "flottants", "booléens", "nuls", "blocs > et |")

_CLE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ .-]*:(\s|$)")
_ENTIER = re.compile(r"^[+-]?\d+$")
_FLOTTANT = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_VRAIS = {"true"}
_FAUX = {"false"}
_NULS = {"null", "~", "none", ""}


class ErreurYaml(Exception):
    """YAML illisible ou hors sous-ensemble : le message dit où."""


@dataclass
class _Ligne:
    """Une ligne significative, avec son indentation et son texte brut."""

    numero: int
    indentation: int
    contenu: str
    brut: str


def _sans_commentaire(texte: str) -> str:
    """Retire le commentaire final, sans casser un `#` quoté."""
    dans_quotes = None
    for index, caractere in enumerate(texte):
        if dans_quotes:
            if caractere == dans_quotes:
                dans_quotes = None
            continue
        if caractere in "\"'":
            dans_quotes = caractere
            continue
        if caractere == "#" and (index == 0 or texte[index - 1] in " \t"):
            return texte[:index]
    return texte


def _decouper(texte: str) -> list:
    """Découpe le texte en lignes significatives (les vides sont conservées)."""
    lignes = []
    for numero, brute in enumerate(texte.splitlines(), 1):
        indentation = len(brute) - len(brute.lstrip(" \t"))
        if "\t" in brute[:indentation]:
            raise ErreurYaml("ligne %d : tabulation dans l'indentation" % numero)
        contenu = _sans_commentaire(brute).rstrip()
        if not contenu.strip():
            lignes.append(_Ligne(numero, -1, "", brute))
            continue
        lignes.append(_Ligne(numero, len(contenu) - len(contenu.lstrip(" ")),
                             contenu.strip(), brute))
    return lignes


class _Analyseur:
    """Analyseur récursif descendant, indentationnel."""

    def __init__(self, lignes: list):
        self.lignes = lignes
        self.i = 0

    def _suivante(self) -> Optional[_Ligne]:
        """Prochaine ligne significative (les vides sont sautées)."""
        while self.i < len(self.lignes):
            ligne = self.lignes[self.i]
            if ligne.indentation == -1:
                self.i += 1
                continue
            return ligne
        return None

    def analyser(self) -> Any:
        """Valeur de premier niveau du document."""
        ligne = self._suivante()
        if ligne is None:
            return None
        valeur = self._bloc(ligne.indentation)
        reste = self._suivante()
        if reste is not None:
            raise ErreurYaml("ligne %d : contenu inattendu après le bloc" % reste.numero)
        return valeur

    def _bloc(self, indentation: int) -> Any:
        """Carte ou liste, selon la première ligne du bloc."""
        ligne = self._suivante()
        if ligne is None:
            return None
        if ligne.contenu == "-" or ligne.contenu.startswith("- "):
            return self._liste(ligne.indentation)
        return self._carte(ligne.indentation)

    def _carte(self, indentation: int) -> dict:
        """Carte : paires `clé: valeur` à l'indentation donnée."""
        resultat: dict = {}
        while True:
            ligne = self._suivante()
            if ligne is None or ligne.indentation < indentation:
                break
            if ligne.indentation > indentation:
                raise ErreurYaml("ligne %d : indentation inattendue" % ligne.numero)
            cle, reste = self._separer(ligne)
            if cle in resultat:
                raise ErreurYaml("ligne %d : clé dupliquée %r" % (ligne.numero, cle))
            self.i += 1
            resultat[cle] = self._valeur(reste, ligne, indentation)
        return resultat

    def _separer(self, ligne: _Ligne) -> tuple:
        """Sépare `clé: valeur` en (clé, reste)."""
        texte = ligne.contenu
        dans_quotes = None
        for index, caractere in enumerate(texte):
            if dans_quotes:
                if caractere == dans_quotes:
                    dans_quotes = None
                continue
            if caractere in "\"'":
                dans_quotes = caractere
                continue
            if caractere == ":" and (index + 1 == len(texte) or texte[index + 1] in " \t"):
                cle = texte[:index].strip().strip("\"'")
                return cle, texte[index + 1:].strip()
        raise ErreurYaml("ligne %d : « clé: valeur » attendu" % ligne.numero)

    def _valeur(self, reste: str, ligne: _Ligne, indentation: int) -> Any:
        """Valeur d'une clé : scalaire, bloc imbriqué ou bloc de texte."""
        if not reste:
            suivante = self._suivante()
            if suivante is not None and suivante.indentation > indentation:
                return self._bloc(suivante.indentation)
            return None
        if reste in (">", "|", ">-", "|-"):
            return self._texte_bloc(reste, indentation)
        return self._scalaire(reste, ligne.numero)

    def _liste(self, indentation: int) -> list:
        """Liste en bloc : `- élément`, élément scalaire ou carte."""
        elements: list = []
        while True:
            ligne = self._suivante()
            if ligne is None or ligne.indentation < indentation:
                break
            if ligne.indentation > indentation:
                raise ErreurYaml("ligne %d : indentation inattendue" % ligne.numero)
            if not (ligne.contenu == "-" or ligne.contenu.startswith("- ")):
                break
            contenu = ligne.contenu[1:]
            colonne = ligne.indentation + 1 + len(contenu) - len(contenu.lstrip(" "))
            reste = contenu.strip()
            if not reste:
                self.i += 1
                suivante = self._suivante()
                elements.append(self._bloc(suivante.indentation)
                                if suivante is not None else None)
            elif _CLE.match(reste):
                ligne.indentation = colonne
                ligne.contenu = reste
                elements.append(self._carte(colonne))
            else:
                self.i += 1
                elements.append(self._scalaire(reste, ligne.numero))
        return elements

    def _texte_bloc(self, style: str, indentation: int) -> str:
        """Bloc de texte replié (`>`) ou littéral (`|`)."""
        bruts = []
        while self.i < len(self.lignes):
            ligne = self.lignes[self.i]
            if ligne.indentation == -1:
                if bruts:
                    bruts.append("")
                self.i += 1
                continue
            if ligne.indentation <= indentation:
                break
            bruts.append(ligne.brut)
            self.i += 1
        while bruts and not bruts[-1]:
            bruts.pop()
        if not bruts:
            return ""
        decalage = min(len(ligne) - len(ligne.lstrip(" ")) for ligne in bruts)
        nettoyes = [ligne[decalage:] if ligne else "" for ligne in bruts]
        if style.startswith("|"):
            return "\n".join(nettoyes) + "\n"
        return " ".join(ligne.strip() for ligne in nettoyes if ligne.strip()) + "\n"

    def _scalaire(self, texte: str, numero: int) -> Any:
        """Scalaire : liste en ligne, guillemet, nombre, booléen, nul ou texte."""
        texte = texte.strip()
        if texte.startswith("[") and texte.endswith("]"):
            return [self._scalaire(morceau.strip(), numero)
                    for morceau in _decouper_liste(texte[1:-1])]
        if texte.startswith("{"):
            raise ErreurYaml("ligne %d : les cartes en flux ne sont pas "
                             "supportées" % numero)
        if texte.startswith("&") or texte.startswith("*"):
            raise ErreurYaml("ligne %d : ancres et alias ne sont pas supportés"
                             % numero)
        if len(texte) >= 2 and texte[0] == texte[-1] and texte[0] in "\"'":
            return _dequoter(texte)
        if texte.lower() in _VRAIS:
            return True
        if texte.lower() in _FAUX:
            return False
        if texte.lower() in _NULS:
            return None
        if _ENTIER.match(texte):
            return int(texte)
        if _FLOTTANT.match(texte):
            return float(texte)
        return texte


def _dequoter(texte: str) -> str:
    """Retire les guillemets ; en double-quoté, interprète les échappements."""
    corps = texte[1:-1]
    if texte[0] == '"':
        return (corps.replace("\\n", "\n").replace("\\t", "\t")
                .replace('\\"', '"').replace("\\\\", "\\"))
    return corps


def _decouper_liste(texte: str) -> list:
    """Découpe une liste en ligne sur les virgules (hors guillemets)."""
    morceaux, courant, dans_quotes = [], "", None
    for caractere in texte:
        if dans_quotes:
            courant += caractere
            if caractere == dans_quotes:
                dans_quotes = None
            continue
        if caractere in "\"'":
            dans_quotes = caractere
            courant += caractere
            continue
        if caractere == ",":
            morceaux.append(courant)
            courant = ""
            continue
        courant += caractere
    if courant.strip():
        morceaux.append(courant)
    return morceaux


def charger_texte(texte: str) -> Any:
    """Charge un document YAML du sous-ensemble à partir d'une chaîne."""
    return _Analyseur(_decouper(texte)).analyser()


def charger_fichier(chemin: str) -> Any:
    """Charge un document YAML du sous-ensemble à partir d'un fichier."""
    with open(chemin, encoding="utf-8") as f:
        return charger_texte(f.read())
