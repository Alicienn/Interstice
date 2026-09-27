"""Parseur des fichiers XML de la base LEGI (DILA).

Quatre formes de fichier, reconnues par leur élément racine :
- `TEXTE_VERSION` (texte/version/LEGITEXT…) : métadonnées d'une version de texte ;
- `TEXTELR` (texte/struct/LEGITEXT…) : sommaire de 1er niveau d'un texte ;
- `SECTION_TA` (LEGISCTA…) : une section (partie, livre, titre, chapitre…) et ses enfants ;
- `ARTICLE` (LEGIARTI…) : une *version* d'article.

Tout le reste est signalé par `parse()` → `Inconnu`, pour que l'ingestion puisse
prouver qu'aucun fichier n'a été ignoré en silence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=False)


@dataclass
class LienStruct:
    """Enfant d'un nœud de sommaire, avec sa propre période de validité."""
    kind: str  # "section" | "article"
    id: str
    cid: str | None
    titre: str  # intitulé de section, ou numéro d'article
    etat: str
    debut: str | None
    fin: str | None
    niv: int | None
    position: int


@dataclass
class Lien:
    typelien: str
    sens: str  # "source" : cet article agit sur / cite la cible ; "cible" : l'inverse
    id: str | None
    cidtexte: str | None
    naturetexte: str | None
    num: str | None
    numtexte: str | None
    datesignatexte: str | None
    nortexte: str | None
    libelle: str


@dataclass
class Titre:
    """Intitulé daté d'un niveau de sommaire dans un CONTEXTE."""
    id: str
    titre: str
    debut: str | None
    fin: str | None


@dataclass
class Contexte:
    texte_cid: str | None
    texte_nature: str | None
    texte_titre: str | None
    niveaux: list[list[Titre]] = field(default_factory=list)  # un niveau peut avoir plusieurs intitulés datés


@dataclass
class TexteVersion:
    id: str
    cid: str
    nature: str
    titre: str
    titrefull: str
    etat: str | None
    date_debut: str | None
    date_fin: str | None
    num: str | None
    nor: str | None
    date_publi: str | None
    date_texte: str | None
    derniere_modification: str | None
    versions_a_venir: list[str]
    autorite: str | None
    ministere: str | None
    visas_html: str | None
    signataires_html: str | None
    tp_html: str | None
    nota_html: str | None
    abro_html: str | None
    rect_html: str | None


@dataclass
class TexteStruct:
    id: str
    cid: str
    nature: str
    derniere_modification: str | None
    versions: list[dict]
    enfants: list[LienStruct]


@dataclass
class Section:
    id: str
    titre: str
    commentaire: str | None
    contexte: Contexte
    enfants: list[LienStruct]


@dataclass
class Article:
    id: str
    ancien_id: str | None
    num: str | None
    etat: str | None
    date_debut: str | None
    date_fin: str | None
    type: str | None
    contexte: Contexte
    versions: list[dict]  # {id, etat, debut, fin, num}
    nota_html: str | None
    html: str | None
    liens: list[Lien]


@dataclass
class EliVersions:
    """Fichier `eli/…/versions.xml` : alias ELI → versions (articles ou textes)."""
    versions: list[dict]


@dataclass
class Inconnu:
    racine: str


Objet = TexteVersion | TexteStruct | Section | Article | EliVersions | Inconnu


# ---------------------------------------------------------------- utilitaires

def _t(el: etree._Element | None, path: str) -> str | None:
    if el is None:
        return None
    node = el.find(path)
    if node is None or node.text is None:
        return None
    v = node.text.strip()
    return v or None


def _inner_html(el: etree._Element | None) -> str | None:
    """HTML interne d'un élément `CONTENU` (None si vide)."""
    if el is None:
        return None
    parts = [el.text or ""]
    for child in el:
        parts.append(etree.tostring(child, encoding="unicode", with_tail=True))
    html = "".join(parts).strip()
    return html or None


def _contenu(root: etree._Element, bloc: str) -> str | None:
    return _inner_html(root.find(f"{bloc}/CONTENU"))


def _date(v: str | None) -> str | None:
    return v.strip() if v and v.strip() else None


def _niv(v: str | None) -> int | None:
    try:
        return int(v) if v else None
    except ValueError:
        return None


def _liens_struct(parent: etree._Element | None) -> list[LienStruct]:
    out: list[LienStruct] = []
    if parent is None:
        return out
    for pos, el in enumerate(parent):
        if el.tag == "LIEN_SECTION_TA":
            out.append(LienStruct("section", el.get("id", ""), el.get("cid"), (el.text or "").strip(),
                                  el.get("etat", ""), _date(el.get("debut")), _date(el.get("fin")),
                                  _niv(el.get("niv")), pos))
        elif el.tag == "LIEN_ART":
            out.append(LienStruct("article", el.get("id", ""), None, el.get("num", "") or "",
                                  el.get("etat", ""), _date(el.get("debut")), _date(el.get("fin")),
                                  None, pos))
    return out


def _contexte(root: etree._Element) -> Contexte:
    texte = root.find("CONTEXTE/TEXTE")
    if texte is None:
        return Contexte(None, None, None)
    titre_txt = texte.find("TITRE_TXT")
    ctx = Contexte(texte.get("cid"), texte.get("nature"),
                   (titre_txt.get("c_titre_court") or (titre_txt.text or "").strip()) if titre_txt is not None else None)
    tm = texte.find("TM")
    while tm is not None:
        ctx.niveaux.append([Titre(t.get("id", ""), (t.text or "").strip(), _date(t.get("debut")), _date(t.get("fin")))
                            for t in tm.findall("TITRE_TM")])
        tm = tm.find("TM")
    return ctx


def _versions(root: etree._Element, lien_tag: str) -> list[dict]:
    out = []
    for v in root.findall("VERSIONS/VERSION"):
        lien = v.find(lien_tag)
        if lien is None:
            continue
        out.append({"id": lien.get("id"), "etat": lien.get("etat") or v.get("etat") or None,
                    "debut": _date(lien.get("debut")), "fin": _date(lien.get("fin")), "num": lien.get("num") or None})
    return out


# ---------------------------------------------------------------- parseurs

def _texte_version(root: etree._Element) -> TexteVersion:
    chron = root.find("META/META_SPEC/META_TEXTE_CHRONICLE")
    ver = root.find("META/META_SPEC/META_TEXTE_VERSION")
    return TexteVersion(
        id=_t(root, "META/META_COMMUN/ID") or "",
        cid=_t(chron, "CID") or _t(root, "META/META_COMMUN/ID") or "",
        nature=_t(root, "META/META_COMMUN/NATURE") or "",
        titre=_t(ver, "TITRE") or "",
        titrefull=_t(ver, "TITREFULL") or _t(ver, "TITRE") or "",
        etat=_t(ver, "ETAT"),
        date_debut=_t(ver, "DATE_DEBUT"),
        date_fin=_t(ver, "DATE_FIN"),
        num=_t(chron, "NUM"),
        nor=_t(chron, "NOR"),
        date_publi=_t(chron, "DATE_PUBLI"),
        date_texte=_t(chron, "DATE_TEXTE"),
        derniere_modification=_t(chron, "DERNIERE_MODIFICATION"),
        versions_a_venir=[v.text.strip() for v in (chron.findall("VERSIONS_A_VENIR/VERSION_A_VENIR") if chron is not None else [])
                          if v.text and v.text.strip()],
        autorite=_t(ver, "AUTORITE"),
        ministere=_t(ver, "MINISTERE"),
        visas_html=_contenu(root, "VISAS"),
        signataires_html=_contenu(root, "SIGNATAIRES"),
        tp_html=_contenu(root, "TP"),
        nota_html=_contenu(root, "NOTA"),
        abro_html=_contenu(root, "ABRO"),
        rect_html=_contenu(root, "RECT"),
    )


def _texte_struct(root: etree._Element) -> TexteStruct:
    chron = root.find("META/META_SPEC/META_TEXTE_CHRONICLE")
    return TexteStruct(
        id=_t(root, "META/META_COMMUN/ID") or "",
        cid=_t(chron, "CID") or _t(root, "META/META_COMMUN/ID") or "",
        nature=_t(root, "META/META_COMMUN/NATURE") or "",
        derniere_modification=_t(chron, "DERNIERE_MODIFICATION"),
        versions=_versions(root, "LIEN_TXT"),
        enfants=_liens_struct(root.find("STRUCT")),
    )


def _section(root: etree._Element) -> Section:
    return Section(
        id=_t(root, "ID") or "",
        titre=_t(root, "TITRE_TA") or "",
        commentaire=_t(root, "COMMENTAIRE"),
        contexte=_contexte(root),
        enfants=_liens_struct(root.find("STRUCTURE_TA")),
    )


def _article(root: etree._Element) -> Article:
    meta = root.find("META/META_SPEC/META_ARTICLE")
    liens = []
    for el in root.findall("LIENS/LIEN"):
        liens.append(Lien(el.get("typelien", ""), el.get("sens", ""), el.get("id") or None, el.get("cidtexte") or None,
                          el.get("naturetexte") or None, el.get("num") or None, el.get("numtexte") or None,
                          _date(el.get("datesignatexte")), el.get("nortexte") or None, (el.text or "").strip()))
    return Article(
        id=_t(root, "META/META_COMMUN/ID") or "",
        ancien_id=_t(root, "META/META_COMMUN/ANCIEN_ID"),
        num=_t(meta, "NUM"),
        etat=_t(meta, "ETAT"),
        date_debut=_t(meta, "DATE_DEBUT"),
        date_fin=_t(meta, "DATE_FIN"),
        type=_t(meta, "TYPE"),
        contexte=_contexte(root),
        versions=_versions(root, "LIEN_ART"),
        nota_html=_contenu(root, "NOTA"),
        html=_contenu(root, "BLOC_TEXTUEL"),
        liens=liens,
    )


def _eli(root: etree._Element) -> EliVersions:
    return EliVersions([{"id": v.get("id"), "etat": v.get("etat") or None,
                         "debut": _date(v.get("debut")), "fin": _date(v.get("fin"))}
                        for v in root.findall("VERSION")])


_PARSEURS = {
    "TEXTE_VERSION": _texte_version,
    "TEXTELR": _texte_struct,
    "SECTION_TA": _section,
    "ARTICLE": _article,
    "VERSIONS": _eli,
}


def parse(data: bytes) -> Objet:
    """Parse un fichier XML LEGI. Lève `etree.XMLSyntaxError` si le XML est invalide."""
    root = etree.fromstring(data, _PARSER)
    fn = _PARSEURS.get(root.tag)
    return fn(root) if fn else Inconnu(root.tag)
