"""Normalisation des numéros d'articles pour la recherche exacte.

« L. 64 A », « L64 A », « l64a » → « L64A » ; « 150-0 B ter » → « 150-0BTER » ;
« R* 196-1 » → « R196-1 ». Le numéro d'origine reste stocké tel quel.
"""

from __future__ import annotations

import re

_TIRETS = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"})
_SUPPR = re.compile(r"[\s.*  ]+")


def normaliser_num(num: str | None) -> str | None:
    if num is None:
        return None
    s = num.translate(_TIRETS).strip()
    s = re.sub(r"^(?:art(?:icle)?s?\.?\s+)", "", s, flags=re.I)
    s = _SUPPR.sub("", s).upper()
    return s or None
