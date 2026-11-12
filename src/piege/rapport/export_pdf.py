"""Piège — export PDF du rapport client (#88), en bibliothèque standard.

Le rapport Markdown est bien pour le portail, mais le RSSI doit le présenter à
sa direction et l'assureur veut un document formel. Ce module produit un **vrai
PDF** (lisible par tout lecteur) sans aucune dépendance tierce : il écrit la
structure PDF minimale (catalogue, pages, flux de contenu, police Helvetica) à
la main.

Limites assumées et documentées : rendu texte uniquement (pas d'images ni de
tableaux graphiques), encodage Latin-1/WinAnsi (les caractères hors Latin-1 sont
remplacés). Pour un livrable riche, `export_html` produit une version HTML
imprimable en PDF via le navigateur, avec la mise en forme complète.
"""

from __future__ import annotations

from typing import Iterable, Optional

__all__ = ["export_pdf", "export_html", "markdown_vers_lignes", "echapper_pdf",
           "LIGNES_PAR_PAGE", "encoder_texte"]

LIGNES_PAR_PAGE = 52
HAUTEUR_PAGE = 842          # A4 en points
MARGE_GAUCHE = 50
MARGE_HAUTE = 792
INTERLIGNE = 14
TAILLE_POLICE = 10


def encoder_texte(texte: str) -> bytes:
    """Encode en Latin-1 (WinAnsi) ; remplace ce qui n'est pas représentable."""
    normalise = (texte or "").replace("\u2014", "-").replace("\u2013", "-")
    normalise = normalise.replace("\u2019", "'").replace("\u2018", "'")
    normalise = normalise.replace("\u201c", '"').replace("\u201d", '"')
    normalise = normalise.replace("\u00a0", " ").replace("\u2022", "-")
    return normalise.encode("latin-1", "replace")


def echapper_pdf(texte: str) -> str:
    r"""Échappe les caractères réservés d'une chaîne PDF : \ ( et )."""
    return texte.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def markdown_vers_lignes(markdown: str) -> list[str]:
    """Aplatit le Markdown en lignes de texte (titres préfixés, puces en tirets)."""
    lignes = []
    for brute in (markdown or "").splitlines():
        texte = brute.rstrip()
        if texte.startswith("### "):
            lignes.append("")
            lignes.append(texte[4:].upper())
        elif texte.startswith("## "):
            lignes.append("")
            lignes.append(texte[3:].upper())
            lignes.append("-" * min(60, len(texte[3:])))
        elif texte.startswith("# "):
            lignes.append(texte[2:].upper())
            lignes.append("=" * min(60, len(texte[2:])))
        elif texte.startswith("|"):
            lignes.append(_ligne_tableau(texte))
        elif texte.lstrip().startswith("- "):
            lignes.append("  " + texte.lstrip())
        elif texte.startswith("> "):
            lignes.append("  " + texte[2:])
        else:
            lignes.append(texte)
    return lignes


def _ligne_tableau(ligne: str) -> str:
    """Transforme une ligne de tableau Markdown en texte aligné."""
    if set(ligne.replace("|", "").strip()) <= set("-: "):
        return ""
    cellules = [c.strip() for c in ligne.strip("|").split("|")]
    return "  " + " | ".join(cellules)


def _flux_contenu(lignes: Iterable[str]) -> bytes:
    """Construit le flux de contenu d'une page (texte positionné)."""
    morceaux = ["BT", "/F1 %d Tf" % TAILLE_POLICE,
                "%d %d Td" % (MARGE_GAUCHE, MARGE_HAUTE),
                "%d TL" % INTERLIGNE]
    for ligne in lignes:
        morceaux.append("(%s) Tj T*" % echapper_pdf(ligne))
    morceaux.append("ET")
    return "\n".join(morceaux).encode("latin-1", "replace")


def _pages(lignes: list[str]) -> list[list[str]]:
    """Découpe les lignes en pages."""
    return [lignes[i:i + LIGNES_PAR_PAGE]
            for i in range(0, max(1, len(lignes)), LIGNES_PAR_PAGE)] or [[]]


def _objet(numero: int, contenu: str) -> bytes:
    """Un objet PDF indirect."""
    return ("%d 0 obj\n%s\nendobj\n" % (numero, contenu)).encode("latin-1")


def export_pdf(markdown: str, titre: str = "Rapport Piège") -> bytes:
    """Rend un rapport Markdown en octets PDF (structure minimale valide)."""
    lignes = markdown_vers_lignes(markdown)
    pages = _pages(lignes)
    objets: list[bytes] = []
    n_pages = len(pages)
    # Numérotation : 1=catalogue, 2=pages, 3=police, puis (page, contenu) par page.
    ids_pages = [4 + 2 * i for i in range(n_pages)]
    kids = " ".join("%d 0 R" % i for i in ids_pages)
    objets.append(_objet(1, "<< /Type /Catalog /Pages 2 0 R >>"))
    objets.append(_objet(2, "<< /Type /Pages /Kids [%s] /Count %d >>"
                         % (kids, n_pages)))
    objets.append(_objet(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                            "/Encoding /WinAnsiEncoding >>"))
    for index, page in enumerate(pages):
        id_page = ids_pages[index]
        id_contenu = id_page + 1
        flux = _flux_contenu(page)
        objets.append(_objet(id_page,
                             "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 %d] "
                             "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
                             % (HAUTEUR_PAGE, id_contenu)))
        en_tete = ("%d 0 obj\n<< /Length %d >>\nstream\n"
                   % (id_contenu, len(flux))).encode("latin-1")
        objets.append(en_tete + flux + b"\nendstream\nendobj\n")
    return _assembler(objets, titre)


def _assembler(objets: list[bytes], titre: str) -> bytes:
    """Assemble le fichier PDF complet avec sa table xref."""
    corps = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    deplacements = []
    for objet in objets:
        deplacements.append(len(corps))
        corps += objet
    xref_pos = len(corps)
    n = len(objets) + 1
    corps += ("xref\n0 %d\n" % n).encode("latin-1")
    corps += b"0000000000 65535 f \n"
    for deplacement in deplacements:
        corps += ("%010d 00000 n \n" % deplacement).encode("latin-1")
    corps += ("trailer\n<< /Size %d /Root 1 0 R /Info << /Title (%s) >> >>\n"
              "startxref\n%d\n%%%%EOF\n" % (n, echapper_pdf(titre),
                                            xref_pos)).encode("latin-1")
    return bytes(corps)


def export_html(markdown: str, titre: str = "Rapport Piège",
                langue: str = "fr") -> str:
    """Rend le rapport en HTML imprimable (mise en forme complète, → PDF navigateur)."""
    echap = lambda s: (s.replace("&", "&amp;").replace("<", "&lt;")     # noqa: E731
                       .replace(">", "&gt;"))
    corps = []
    for ligne in (markdown or "").splitlines():
        if ligne.startswith("# "):
            corps.append("<h1>%s</h1>" % echap(ligne[2:]))
        elif ligne.startswith("## "):
            corps.append("<h2>%s</h2>" % echap(ligne[3:]))
        elif ligne.startswith("### "):
            corps.append("<h3>%s</h3>" % echap(ligne[4:]))
        elif ligne.startswith("|"):
            corps.append("<div class='tab'>%s</div>" % echap(ligne))
        elif ligne.lstrip().startswith("- "):
            corps.append("<li>%s</li>" % echap(ligne.lstrip()[2:]))
        elif ligne.strip():
            corps.append("<p>%s</p>" % echap(ligne))
    return _gabarit_html(titre, langue, "\n".join(corps))


def _gabarit_html(titre: str, langue: str, corps: str) -> str:
    """Gabarit HTML autonome, sans dépendance externe, prêt à imprimer."""
    return ("<!DOCTYPE html><html lang='%s'><head><meta charset='utf-8'>"
            "<title>%s</title><style>"
            "body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;"
            "padding:0 1rem;color:#12151c;line-height:1.5}"
            "h1{border-bottom:2px solid #5aa9ff}h2{margin-top:1.6rem;color:#1d3a5f}"
            ".tab{font-family:monospace;white-space:pre;background:#f4f6fa;"
            "padding:.2rem .4rem;border-radius:4px}"
            "li{margin:.2rem 0}@media print{body{margin:0}}"
            "</style></head><body>%s</body></html>"
            % (langue, titre, corps))
