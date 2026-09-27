"""Lecture des fichiers du BOFiP open data (voir les DTD dans `BOFiP/infos/` des archives).

Arborescence d'une archive :
    BOFiP/documents/Contenu/<type de contenu>/<série>/<NNN-PGP>/<AAAA-MM-JJ>/{document.xml, data.html}
    BOFiP/documents/Image/<NNN-PGP>/<AAAA-MM-JJ>/{document.xml, data1.jpg}
    BOFiP/documents/Attachment/<NNN-PGP>/<AAAA-MM-JJ>/{document.xml, data1.pdf}
    BOFiP/documents/PlanClassement/8-PGP/<AAAA-MM-JJ>/{document.xml, data.xml}
    BOFiP/infos/{document,data,plan}.dtd

`document.xml` : métadonnées Dublin Core (`dc:title`, `dc:date`, `dc:subject` = série puis division,
`dc:identifier` = PGP puis permalien, `dc:relation type=…`) et bloc `bofip:bodgfip` (`contenu_type`,
`contenu_niveau`, `contenu_id` = identifiant BOI daté).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from interstice.legi.html import html_vers_texte

RE_PGP = re.compile(r"^\d+-PGP$")
RE_BOI_DATE = re.compile(r"^(?P<base>.+?)-(?P<date>\d{8})$")


@dataclass
class Meta:
    type_document: str  # Contenu | Image | Attachment | PlanClassement
    pgp: str
    titre: str | None = None
    date: str | None = None
    createur: str | None = None
    sujets: list[str] = field(default_factory=list)
    permalien: str | None = None
    format: str | None = None
    fichiers: list[tuple[str, str]] = field(default_factory=list)  # (dataType, dataRef)
    relations: list[tuple[str, str, str]] = field(default_factory=list)  # (type, cible_type, cible_pgp)
    type_contenu: str | None = None
    niveau: str | None = None
    boi: str | None = None


def _local(el) -> str:
    return etree.QName(el).localname


def _txt(el) -> str:
    return re.sub(r"\s+", " ", el.text or "").strip()


def lire_document_xml(data: bytes) -> Meta:
    racine = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    if _local(racine) != "document":
        raise ValueError(f"racine inattendue <{_local(racine)}>")
    m = Meta(type_document=racine.get("type") or "", pgp="")
    for el in racine.iter():
        if not isinstance(el.tag, str):
            continue
        nom = _local(el)
        if nom == "part":
            dt = el.find("dataType")
            dr = el.find("dataRef")
            m.fichiers.append((_txt(dt) if dt is not None else "", _txt(dr) if dr is not None else ""))
        elif nom == "title":
            m.titre = _txt(el)
        elif nom == "date":
            m.date = _txt(el)
        elif nom == "creator":
            m.createur = _txt(el)
        elif nom == "subject":
            m.sujets.append(_txt(el))
        elif nom == "format":
            m.format = _txt(el)
        elif nom == "identifier":
            v = _txt(el)
            if RE_PGP.match(v):
                m.pgp = v
            elif v.startswith("http"):
                m.permalien = v
        elif nom == "relation":
            v = _txt(el)
            cible_type, _, cible = v.rpartition(":")
            m.relations.append((el.get("type") or "", cible_type, cible))
        elif nom == "contenu_type":
            m.type_contenu = _txt(el)
        elif nom == "contenu_niveau":
            m.niveau = _txt(el)
        elif nom == "contenu_id":
            m.boi = re.sub(r"\s+", "", el.text or "")  # quelques identifiants publiés contiennent une espace
    if not m.pgp:
        raise ValueError("identifiant PGP absent (dc:identifier)")
    return m


def boi_base(boi: str | None) -> str | None:
    """« BOI-IR-BASE-10-20230118 » → « BOI-IR-BASE-10 » ; ACTU-… inchangé."""
    if not boi:
        return None
    m = RE_BOI_DATE.match(boi)
    return m.group("base") if m and boi.startswith("BOI-") else boi


# ------------------------------------------------------------------------ HTML → texte

_CORPS = re.compile(r"<body\b[^>]*>(.*)</body\s*>", re.S | re.I)
_TITRE_H = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1\s*>", re.S | re.I)
_NUM_P = re.compile(r"<p\b[^>]*>\s*(\d{1,5})\s*</p\s*>", re.I)
_BR = re.compile(r"<br\s*/?>", re.I)


def corps_html(data: str) -> str:
    m = _CORPS.search(data)
    return (m.group(1) if m else data).strip()


def html_vers_texte_bofip(html: str | None) -> str:
    """Texte brut pour l'indexation et la lecture par le LLM.

    Intertitres h1…h6 → lignes « ## … » à « ####### … » (niveau + 1) ; paragraphes numérotés
    du BOFiP (« <p>150</p> ») → « § 150 », forme sous laquelle la doctrine est citée.
    """
    if not html:
        return ""
    s = _NUM_P.sub(lambda m: f"<p>§ {m.group(1)}</p>", html)
    s = _TITRE_H.sub(lambda m: f"<p>{'#' * (int(m.group(1)) + 1)} {_BR.sub(' ', m.group(2))}</p>", s)
    return html_vers_texte(s)


# ------------------------------------------------------------------------ plan de classement

@dataclass
class NoeudPlan:
    pgp: str
    parent: str | None
    position: int
    libelle: str
    code: str
    profondeur: int


def lire_plan(data: bytes) -> list[NoeudPlan]:
    racine = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))
    if racine.tag != "navigationTree":
        raise ValueError(f"racine de plan inattendue <{racine.tag}>")
    out: list[NoeudPlan] = []

    def descendre(el, parent: str | None, prof: int) -> None:
        for i, d in enumerate(e for e in el if e.tag == "doc"):
            out.append(NoeudPlan(d.get("id"), parent, i, re.sub(r"\s+", " ", d.get("label") or "").strip(),
                                 d.get("nodeId") or "", prof))
            descendre(d, d.get("id"), prof + 1)

    descendre(racine, None, 0)
    return out


# ------------------------------------------------------------------------ chemins d'archive

@dataclass(frozen=True)
class CheminDoc:
    type_document: str  # Contenu | Image | Attachment | PlanClassement
    pgp: str
    date: str
    repertoire: str  # chemin du répertoire de version dans l'archive
    type_contenu_dossier: str | None = None
    serie_dossier: str | None = None


_RE_CHEMIN = re.compile(
    r"^(?P<rep>(?:\./)?BOFiP/documents/(?P<type>[^/]+)/(?:(?P<tc>[^/]+)/(?P<serie>[^/]+)/)?"
    r"(?P<pgp>\d+-PGP)/(?P<date>\d{4}-\d{2}-\d{2}))/(?P<fichier>[^/]+)$")


def analyser_chemin(nom: str) -> tuple[CheminDoc, str] | None:
    """Répertoire de document et nom de fichier pour un membre de l'archive (None si hors documents)."""
    m = _RE_CHEMIN.match(nom)
    if not m:
        return None
    return CheminDoc(m["type"], m["pgp"], m["date"], m["rep"], m["tc"], m["serie"]), m["fichier"]
