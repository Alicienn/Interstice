"""Extraction des renvois d'un article vers d'autres articles, à partir de son texte.

Les liens LEGI (<LIENS>) sont incomplets : beaucoup de renvois internes (« mentionnés à
l'article 150-0 A ») n'y figurent pas. On les extrait donc du texte :

1. repérage du mot « article(s) » puis d'une liste de numéros séparés par « , », « et »,
   « ou », « à » (plage) ;
2. détermination du texte visé d'après ce qui suit la liste (« du présent code »,
   « du code de la sécurité sociale », « du livre des procédures fiscales », « de l'annexe III »,
   « de la loi n° 2017-1837 du… ») ; à défaut, le texte de l'article lui-même ;
3. résolution par **plus long préfixe existant** : « 150-0 B ter du » → on essaie
   « 150-0 B ter », puis « 150-0 B »… jusqu'à trouver un numéro réel du texte visé.
   Un numéro introuvable est conservé (non résolu) pour l'audit.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from interstice.legi.numeros import normaliser_num

LATINS = ("bis ter quater quinquies sexies septies octies nonies novies decies undecies duodecies terdecies "
          "quaterdecies quindecies sexdecies septdecies octodecies novodecies vicies unvicies duovicies "
          "tervicies quatervicies quinvicies sexvicies septvicies octovicies novovicies tricies").split()
_LATIN = "|".join(sorted(LATINS, key=len, reverse=True))
_SEP = r"[\s  ]*[-‑–]?[\s  ]*"
# un numéro : préfixe éventuel (L., R*, D., A., LO), cœur chiffré, puis suffixes (bis, -0, A, ZA…)
_NUM = (rf"(?:(?:LO|[LRDA])\s?\*?\.?[\s ]?)?\d+(?:[-‑–]\d+)*"
        rf"(?:{_SEP}(?:(?:{_LATIN})\b|0\b|[A-Z]{{1,3}}\b(?![''’])))*")
_LISTE_SEP = r"(?:\s*,\s*(?:et\s+|ou\s+)?|\s+et\s+|\s+ou\s+|\s+à\s+|\s*,?\s*et\s+à\s+)"
RE_RENVOI = re.compile(
    rf"\b[Aa]rt(?:icles?|\.)\s+(?P<liste>{_NUM}(?:{_LISTE_SEP}{_NUM})*)",
)
RE_NUM = re.compile(_NUM)
RE_PLAGE = re.compile(r"^\s+à\s+$")

_ANNEXES = {"I": "I", "1": "I", "II": "II", "2": "II", "III": "III", "3": "III", "IV": "IV", "4": "IV"}
RE_CIBLE = re.compile(
    r"^[\s,]*(?:"
    r"(?P<present>d[eu]s?\s+(?:présent|ce|même)\s+(?:code|livre))"
    r"|(?P<annexe>de\s+l['’]annexe\s+(?P<num_annexe>IV|III|II|I|[1-4])\b(?:\s+(?:au|du)\s+(?P<code_annexe>code\s+général\s+des\s+impôts))?)"
    r"|(?P<acte>d[eu]\s+(?:la\s+|l['’])?(?P<nature>loi(?:\s+organique)?|ordonnance|décret|arrêté)\s+n[°o]\s*(?P<numtexte>[\d-]+))"
    r"|(?P<code>d[eu]\s+(?:(?:la|l['’])\s*)?(?P<titre>(?:code|livre)\s+[^,.;:()]{3,90}))"
    r")",
    re.I,
)


@dataclass
class Renvoi:
    position: int
    brut: str  # numéro tel qu'écrit
    num: str | None  # numéro résolu (forme LEGI) ou None
    cible_cid: str | None  # texte visé (None si non déterminé)
    plage: str | None  # "debut" / "fin" pour « articles X à Y »
    contexte_cible: str  # formule qui a déterminé le texte visé ("" = texte courant par défaut)


# Résolveur : (texte_cid, candidat normalisé) -> numéro LEGI exact ou None
Resolveur = Callable[[str, str], str | None]
# Résolution d'un intitulé : "code de la sécurité sociale" -> cid ; ("loi", "2017-1837") -> cid ; annexe "III" -> cid
ResolveurTexte = Callable[[str, str], str | None]


def _candidats(brut: str) -> list[str]:
    """Préfixes décroissants d'un numéro, par jetons : '150-0 B ter' → ['150-0 B ter', '150-0 B', '150-0']."""
    jetons = re.split(r"(?<=\S)(?=[\s ]+\S)", brut.strip())
    out = []
    for i in range(len(jetons), 0, -1):
        c = "".join(jetons[:i]).strip()
        if c and c not in out:
            out.append(c)
    return out


def extraire(texte: str, source_cid: str, resoudre_num: Resolveur, resoudre_texte: ResolveurTexte) -> list[Renvoi]:
    out: list[Renvoi] = []
    dernier_code: str | None = None
    for m in RE_RENVOI.finditer(texte):
        liste = m.group("liste")
        # numéros et séparateurs de la liste
        nums, seps, pos = [], [], 0
        for n in RE_NUM.finditer(liste):
            seps.append(liste[pos:n.start()])
            nums.append((n.group(0), m.start("liste") + n.start()))
            pos = n.end()
        suite = texte[m.end("liste"): m.end("liste") + 160]
        cible, formule = _cible(suite, source_cid, dernier_code, resoudre_texte)
        if formule and cible and cible != source_cid and "même" not in formule.lower():
            dernier_code = cible
        for i, (brut, p) in enumerate(nums):
            plage = None
            if i + 1 < len(nums) and RE_PLAGE.match(seps[i + 1] if i + 1 < len(seps) else ""):
                plage = "debut"
            elif i > 0 and RE_PLAGE.match(seps[i]):
                plage = "fin"
            num = None
            if cible:
                for c in _candidats(brut):
                    num = resoudre_num(cible, normaliser_num(c) or "")
                    if num:
                        break
            out.append(Renvoi(p, brut.strip(), num, cible, plage, formule))
    return out


def _cible(suite: str, source_cid: str, dernier_code: str | None,
           resoudre_texte: ResolveurTexte) -> tuple[str | None, str]:
    m = RE_CIBLE.match(suite)
    if not m:
        return source_cid, ""
    formule = m.group(0).strip(" ,")
    if m.group("present"):
        if "même" in formule.lower() and dernier_code:
            return dernier_code, formule
        return source_cid, formule
    if m.group("annexe"):
        return resoudre_texte("annexe", _ANNEXES[m.group("num_annexe").upper()]), formule
    if m.group("acte"):
        return resoudre_texte(m.group("nature").lower().split()[0], m.group("numtexte")), formule
    return resoudre_texte("titre", m.group("titre")), formule
