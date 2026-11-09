"""
Les zones horizontales : ranges (périodes de consolidation) et niveaux de
support / résistance.

**Range.** On part d'une bougie et on avance tant que toutes les clôtures
tiennent dans une bande de `largeur × ATR` (ATR de la première bougie). Si la
bande a tenu au moins `durée` bougies, c'est un range ; la première clôture qui
en sort est la cassure, et la recherche repart de là. Le range est connu dès
qu'il a duré `durée` bougies, et confirmé à sa cassure.

**Support / résistance.** Les pivots du zigzag sont pris dans l'ordre du temps.
Chaque pivot qui tombe à moins d'un demi-ATR d'un niveau existant le touche
(le niveau devient la moyenne de ses contacts) ; sinon il crée un nouveau
niveau. Un niveau sans contact depuis 300 bougies est oublié. Un niveau compte
à partir de `touches` contacts. Il est « support » si
ses contacts sont des creux, « résistance » si ce sont des sommets, « les deux »
quand le prix l'a traversé et que les rôles se sont inversés.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field

import numpy as np

from .chartistes import Marche
from .figures import CONFIRMEE, EN_FORMATION, Figure
from .indicateurs import njit
from .pivots import SOMMET, Pivots

TOLERANCE_NIVEAU = 0.5          # en ATR
PORTEE = 300                    # bougies sans contact au-delà desquelles un niveau est oublié


@njit(cache=True)
def _ranges(cloture, atr, largeur, duree_min):
    n = len(cloture)
    debuts = np.empty(n, dtype=np.int64)
    fins = np.empty(n, dtype=np.int64)
    bas = np.empty(n)
    hauts = np.empty(n)
    k = 0
    i = 0
    while i < n - duree_min + 1:
        limite = largeur * atr[i]
        haut = cloture[i]
        bas_ = cloture[i]
        j = i + 1
        while j < n:
            h = max(haut, cloture[j])
            b = min(bas_, cloture[j])
            if h - b > limite:
                break
            haut = h
            bas_ = b
            j += 1
        if j - i >= duree_min:
            debuts[k] = i
            fins[k] = j - 1
            bas[k] = bas_
            hauts[k] = haut
            k += 1
            i = j
        else:
            i += 1
    return debuts[:k], fins[:k], bas[:k], hauts[:k]


def ranges(m: Marche, largeur: float, duree_min: int) -> list[Figure]:
    debuts, fins, bas, hauts = _ranges(m.c, m.atr, float(largeur), int(duree_min))
    figures = []
    for i0, i1, b, h in zip(debuts, fins, bas, hauts):
        i0, i1, b, h = int(i0), int(i1), float(b), float(h)
        f = Figure(type="range", debut=i0, fin=i1, detection=i0 + int(duree_min) - 1, points=[],
                   zone=(i0, i1, b, h))
        f.details.update({"hauteur": h - b, "bougies": i1 - i0 + 1})
        cassure = i1 + 1
        if cassure < m.n:
            f.statut = CONFIRMEE
            f.sens_cassure = 1 if m.c[cassure] > h else -1
            f.signal = cassure
            f.details["cassure"] = cassure
            f.niveau = h if f.sens_cassure > 0 else b
            f.invalidation = b if f.sens_cassure > 0 else h
            f.objectif = float(m.c[cassure]) + f.sens_cassure * (h - b)
        else:
            f.statut = EN_FORMATION
            f.niveau, f.invalidation, f.objectif = h, b, h + (h - b)
        figures.append(f)
    return figures


@dataclass
class Niveau:
    prix: float
    touches: list = field(default_factory=list)     # [(bougie, prix, sorte)]
    connu: int = -1                                  # bougie où il atteint le nombre de contacts voulu

    @property
    def debut(self) -> int:
        return self.touches[0][0]

    @property
    def fin(self) -> int:
        return self.touches[-1][0]

    @property
    def role(self) -> str:
        sortes = {s for _, _, s in self.touches}
        if sortes == {SOMMET}:
            return "résistance"
        if SOMMET not in sortes:
            return "support"
        return "support et résistance"


def niveaux(pv: Pivots, atr: np.ndarray, touches_min: int) -> list[Niveau]:
    """Supports et résistances touchés au moins `touches_min` fois (pivots confirmés seulement)."""
    pc = pv.confirmes()
    tous: list[Niveau] = []
    prix_tries: list[float] = []        # prix des niveaux, triés, pour trouver vite le plus proche
    niveaux_tries: list[Niveau] = []
    for i, prix, sorte, conf in zip(pc.i, pc.prix, pc.type, pc.confirme):
        prix = float(prix)
        tolerance = TOLERANCE_NIVEAU * float(atr[i])
        proche, rang, ecart_min = None, -1, np.inf
        j = bisect_left(prix_tries, prix - tolerance)
        while j < len(prix_tries) and prix_tries[j] <= prix + tolerance:
            ecart = abs(prix_tries[j] - prix)
            # Un niveau oublié depuis trop longtemps ne compte plus : le prochain
            # contact au même prix ouvrira un nouveau niveau.
            if ecart < ecart_min and i - niveaux_tries[j].fin <= PORTEE:
                proche, rang, ecart_min = niveaux_tries[j], j, ecart
            j += 1
        if proche is None:
            proche = Niveau(prix=prix)
            tous.append(proche)
        else:
            del prix_tries[rang], niveaux_tries[rang]
        proche.touches.append((int(i), prix, int(sorte)))
        proche.prix = float(np.mean([p for _, p, _ in proche.touches]))
        if len(proche.touches) == touches_min:
            proche.connu = int(conf)
        rang = bisect_left(prix_tries, proche.prix)
        prix_tries.insert(rang, proche.prix)
        niveaux_tries.insert(rang, proche)
    return [n for n in tous if len(n.touches) >= touches_min]
