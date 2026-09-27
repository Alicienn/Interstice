"""Conversion du HTML LEGI en texte brut lisible (indexation plein texte, contexte LLM)."""

from __future__ import annotations

import re

from lxml import html as lhtml

_BLOCS = {"p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"}
_ESPACES = re.compile(r"[ \t  ]+")
_LIGNES = re.compile(r"\n{3,}")


def html_vers_texte(html: str | None) -> str:
    if not html:
        return ""
    try:
        frag = lhtml.fragment_fromstring(html, create_parent="div")
    except Exception:  # HTML irréparable : on retire grossièrement les balises
        return _nettoyer(re.sub(r"<[^>]+>", " ", html))
    parts: list[str] = []

    def walk(el) -> None:
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag == "br":
            parts.append("\n")
        elif tag in _BLOCS:
            parts.append("\n")
        if el.text and tag not in ("script", "style"):
            parts.append(el.text)
        for child in el:
            walk(child)
            if isinstance(child.tag, str) and child.tag in ("td", "th"):
                parts.append(" | ")
            if child.tail:
                parts.append(child.tail)
        if tag in _BLOCS and tag != "br":
            parts.append("\n")

    walk(frag)
    return _nettoyer("".join(parts))


def _nettoyer(s: str) -> str:
    lignes = [_ESPACES.sub(" ", l).strip(" |") for l in s.split("\n")]
    return _LIGNES.sub("\n\n", "\n".join(lignes)).strip()
