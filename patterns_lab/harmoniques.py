"""
Figures harmoniques (XABCD, AB=CD) et divergences du RSI, à partir des pivots.

**Harmoniques.** Cinq pivots consécutifs X, A, B, C, D. On mesure chaque jambe
en proportion de la précédente :
    B  = AB / XA      (de combien B revient sur XA)
    C  = BC / AB
    CD = CD / BC
    D  = AD / XA      (où D s'arrête par rapport à XA)
Chaque figure exige des proportions de Fibonacci précises (voir le catalogue),
à ± 5 % près. Si D est un creux, la figure est haussière ; si c'est un sommet,
baissière. Elle est connue à la confirmation de D, qui est aussi le signal.

**AB=CD.** Quatre pivots A, B, C, D : la jambe CD a la même longueur que AB
(± 10 %), C revenant de 38,2 à 88,6 % sur AB.

**Divergences.** Deux creux consécutifs : le prix fait plus bas, le RSI plus
haut (et le premier RSI est sous 50) : divergence haussière. Deux sommets : le
prix fait plus haut, le RSI plus bas (premier RSI au-dessus de 50) :
divergence baissière. Connue à la confirmation du second pivot.
"""

from __future__ import annotations

import numpy as np

from .figures import CONFIRMEE, Figure
from .pivots import CREUX, SOMMET, Pivots

TOLERANCE = 0.05

# nom : (B, C, CD, D), chaque proportion donnée par (minimum, maximum)
PROPORTIONS = {
    "gartley": ((0.618, 0.618), (0.382, 0.886), (1.27, 1.618), (0.786, 0.786)),
    "chauve_souris": ((0.382, 0.50), (0.382, 0.886), (1.618, 2.618), (0.886, 0.886)),
    "papillon": ((0.786, 0.786), (0.382, 0.886), (1.618, 2.24), (1.27, 1.618)),
    "crabe": ((0.382, 0.618), (0.382, 0.886), (2.24, 3.618), (1.618, 1.618)),
}
NOMS = {
    ("gartley", 1): "gartley_haussier", ("gartley", -1): "gartley_baissier",
    ("chauve_souris", 1): "chauve_souris_haussiere", ("chauve_souris", -1): "chauve_souris_baissiere",
    ("papillon", 1): "papillon_haussier", ("papillon", -1): "papillon_baissier",
    ("crabe", 1): "crabe_haussier", ("crabe", -1): "crabe_baissier",
}


def _dans(valeur, borne):
    bas, haut = borne
    return bas * (1 - TOLERANCE) <= valeur <= haut * (1 + TOLERANCE)


def _harmonique(f: Figure, a: float, d: float, sens: int):
    """Objectif : retour de 61,8 % de AD ; invalidation : D dépassé de 23,6 % de AD."""
    jambe = abs(a - d)
    f.objectif = d + sens * 0.618 * jambe
    f.invalidation = d - sens * 0.236 * jambe
    f.niveau = d
    f.statut = CONFIRMEE
    f.sens_cassure = sens
    f.signal = f.detection


def harmoniques(pv: Pivots, types: set[str]) -> list[Figure]:
    pc = pv.confirmes()
    figures = []
    for k in range(len(pc) - 4):
        ks = range(k, k + 5)
        sens = 1 if pc.type[k + 4] == CREUX else -1        # D est un creux : haussière
        x, a, b, c, d = (sens * pc.prix[j] for j in ks)      # « à l'endroit » : D en bas
        xa, ab, bc, cd = a - x, a - b, c - b, c - d
        if min(xa, ab, bc, cd) <= 0:
            continue
        rb, rc, rcd, rd = ab / xa, bc / ab, cd / bc, (a - d) / xa
        for nom, (pb, pcc, pcd, pd) in PROPORTIONS.items():
            type_ = NOMS[(nom, sens)]
            if type_ not in types:
                continue
            if _dans(rb, pb) and _dans(rc, pcc) and _dans(rcd, pcd) and _dans(rd, pd):
                points = [(int(pc.i[j]), float(pc.prix[j])) for j in ks]
                f = Figure(type=type_, debut=points[0][0], fin=points[-1][0],
                           detection=int(pc.confirme[k + 4]), points=points,
                           etiquettes=[(i, p, lettre) for (i, p), lettre in zip(points, "XABCD")],
                           lignes=[(points[0][0], points[0][1], points[2][0], points[2][1]),
                                   (points[2][0], points[2][1], points[4][0], points[4][1]),
                                   (points[1][0], points[1][1], points[3][0], points[3][1])])
                f.details.update({"B/XA": rb, "C/AB": rc, "CD/BC": rcd, "D/XA": rd})
                _harmonique(f, float(pc.prix[k + 1]), float(pc.prix[k + 4]), sens)
                figures.append(f)
                break
    for k in range(len(pc) - 3):
        sens = 1 if pc.type[k + 3] == CREUX else -1
        type_ = "abcd_haussier" if sens == 1 else "abcd_baissier"
        if type_ not in types:
            continue
        a, b, c, d = (sens * pc.prix[j] for j in range(k, k + 4))
        ab, bc, cd = a - b, c - b, c - d
        if min(ab, bc, cd) <= 0:
            continue
        if _dans(bc / ab, (0.382, 0.886)) and 0.9 <= cd / ab <= 1.1:
            points = [(int(pc.i[j]), float(pc.prix[j])) for j in range(k, k + 4)]
            f = Figure(type=type_, debut=points[0][0], fin=points[-1][0],
                       detection=int(pc.confirme[k + 3]), points=points,
                       etiquettes=[(i, p, lettre) for (i, p), lettre in zip(points, "ABCD")])
            f.details.update({"C/AB": bc / ab, "CD/AB": cd / ab})
            _harmonique(f, float(pc.prix[k]), float(pc.prix[k + 3]), sens)
            figures.append(f)
    return figures


def divergences(pv: Pivots, rsi: np.ndarray, types: set[str]) -> list[Figure]:
    pc = pv.confirmes()
    figures = []
    for k in range(len(pc) - 2):
        sorte = int(pc.type[k + 2])
        i1, i2 = int(pc.i[k]), int(pc.i[k + 2])
        p1, p2 = float(pc.prix[k]), float(pc.prix[k + 2])
        r1, r2 = rsi[i1], rsi[i2]
        if np.isnan(r1) or np.isnan(r2):
            continue
        if sorte == CREUX and p2 < p1 and r2 > r1 and r1 < 50:
            type_, sens = "divergence_haussiere", 1
        elif sorte == SOMMET and p2 > p1 and r2 < r1 and r1 > 50:
            type_, sens = "divergence_baissiere", -1
        else:
            continue
        if type_ not in types:
            continue
        milieu = float(pc.prix[k + 1])
        f = Figure(type=type_, debut=i1, fin=i2, detection=int(pc.confirme[k + 2]),
                   points=[(i1, p1), (i2, p2)], objectif=milieu, invalidation=p2, niveau=p2,
                   statut=CONFIRMEE, sens_cassure=sens)
        f.signal = f.detection
        f.details.update({"RSI 1": float(r1), "RSI 2": float(r2),
                          "ligne RSI": (i1, float(r1), i2, float(r2))})
        figures.append(f)
    return figures
