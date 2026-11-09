"""
Drapeaux et fanions : une pause courte après un mouvement brutal.

Ces pauses sont trop petites pour le zigzag (le recul n'atteint pas la
sensibilité), elles sont donc cherchées bougie par bougie.

**Le mât.** Une bougie b qui fait le plus haut des 20 dernières, et le plus bas
a de ces 20 bougies, tels que la hausse de a à b fasse au moins 5 ATR, à plus
de 0,5 ATR par bougie (ATR d'avant le mât : la hausse se mesure au calme qui la
précédait).

**La pause.** Les bougies qui suivent b. Leurs plus hauts sont enveloppés par
une droite (la droite des moindres carrés, remontée jusqu'au plus haut de la
pause), leurs plus bas aussi. La pause ne doit pas reculer de plus de la
moitié du mât, ni durer plus de deux fois le mât (et jamais plus de 50
bougies).

**La cassure.** Après au moins 3 bougies de pause, la première clôture au-dessus
de la droite haute. Si les deux droites descendent (ou restent plates) en
restant à peu près parallèles, c'est un drapeau ; si elles se rejoignent,
c'est un fanion. Une pause qui monte n'est ni l'un ni l'autre.

Le drapeau n'est connu qu'à sa cassure : c'est la bougie de signal. Les
versions baissières sont cherchées sur le graphique retourné.
"""

from __future__ import annotations

import numpy as np

from .chartistes import Marche, retourner_figure
from .figures import CONFIRMEE, EN_FORMATION, Figure
from .indicateurs import njit

FENETRE_MAT = 20
MAT_MIN = 5.0           # en ATR
PENTE_MIN = 0.5         # en ATR par bougie
RECUL_MAX = 0.5         # en fraction du mât
DUREE_MAX = 50          # bougies
PAUSE_MIN = 3


@njit(cache=True)
def _enveloppe(valeurs, debut, fin, dessus):
    """Droite des moindres carrés sur valeurs[debut:fin], décalée pour envelopper les points."""
    nombre = fin - debut
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    sxy = 0.0
    for t in range(debut, fin):
        x = float(t)
        sx += x
        sy += valeurs[t]
        sxx += x * x
        sxy += x * valeurs[t]
    denominateur = nombre * sxx - sx * sx
    pente = (nombre * sxy - sx * sy) / denominateur if denominateur != 0 else 0.0
    ordonnee = (sy - pente * sx) / nombre
    decalage = -1e300 if dessus else 1e300
    for t in range(debut, fin):
        r = valeurs[t] - (ordonnee + pente * t)
        if dessus:
            decalage = max(decalage, r)
        else:
            decalage = min(decalage, r)
    return pente, ordonnee + decalage


@njit(cache=True)
def _drapeaux(h, l, c, atr, fenetre, mat_min, pente_min, recul_max, duree_max_abs, pause_min):
    n = len(c)
    taille = n // 4 + 1
    sortie = np.empty((taille, 9))
    k = 0
    b = fenetre
    while b < n - 1 and k < taille:
        plus_haut = True
        for t in range(b - fenetre, b):
            if h[t] > h[b]:
                plus_haut = False
                break
        if not plus_haut:
            b += 1
            continue
        a = b - fenetre
        for t in range(b - fenetre, b + 1):
            if l[t] < l[a]:
                a = t
        mat = h[b] - l[a]
        duree_mat = b - a
        if duree_mat < 2 or mat < mat_min * atr[a] or mat < pente_min * atr[a] * duree_mat:
            b += 1
            continue
        duree_max = min(max(2 * duree_mat, 5), duree_max_abs)
        plancher = h[b] - recul_max * mat
        fin_trouvee = -1
        cassure = -1
        sorte = 0
        ph = 0.0
        oh = 0.0
        pb = 0.0
        ob = 0.0
        j = b + 1
        while j < n:
            pause = j - b                        # bougies b .. j-1
            if l[j] < plancher or pause > duree_max:
                break
            if pause >= pause_min + 1:
                ph, oh = _enveloppe(h, b, j, True)
                pb, ob = _enveloppe(l, b + 1, j, False)
                if c[j] > oh + ph * j:
                    du = ph * pause / mat
                    dl = pb * pause / mat
                    if du < -0.05 and dl > 0.05:
                        sorte = 2                # fanion : droites qui convergent
                    elif du <= 0.1 and dl <= 0.1 and abs(du - dl) <= 0.35:
                        sorte = 1                # drapeau : parallèles, plates ou descendantes
                    if sorte > 0:
                        cassure = j
                        fin_trouvee = j - 1
                    break
            elif c[j] > h[b]:
                break                            # le mât continue : pas encore de pause
            j += 1
        if j == n and n - b >= pause_min + 1:
            # Pause encore en cours à la dernière bougie : figure en formation.
            ph, oh = _enveloppe(h, b, n, True)
            pb, ob = _enveloppe(l, b + 1, n, False)
            du = ph * (n - b) / mat
            dl = pb * (n - b) / mat
            if du < -0.05 and dl > 0.05:
                sorte = 2
            elif du <= 0.1 and dl <= 0.1 and abs(du - dl) <= 0.35:
                sorte = 1
            if sorte > 0:
                fin_trouvee = n - 1
        if sorte > 0:
            sortie[k, 0] = a
            sortie[k, 1] = b
            sortie[k, 2] = fin_trouvee
            sortie[k, 3] = cassure
            sortie[k, 4] = sorte
            sortie[k, 5] = ph
            sortie[k, 6] = oh
            sortie[k, 7] = pb
            sortie[k, 8] = ob
            k += 1
            b = max(cassure, b + 1) if cassure > 0 else n
        else:
            b += 1
    return sortie[:k]


def _chercher(m: Marche, types: tuple[str, str]) -> list[Figure]:
    lignes = _drapeaux(m.h, m.b, m.c, m.atr, FENETRE_MAT, MAT_MIN, PENTE_MIN, RECUL_MAX,
                       DUREE_MAX, PAUSE_MIN)
    figures = []
    for a, b, fin, cassure, sorte, ph, oh, pb, ob in lignes:
        a, b, fin, cassure = int(a), int(b), int(fin), int(cassure)
        mat = float(m.h[b] - m.b[a])
        bout = cassure if cassure >= 0 else m.n - 1
        haut = lambda i, ph=ph, oh=oh: oh + ph * i                 # noqa: E731
        bas = lambda i, pb=pb, ob=ob: ob + pb * i                  # noqa: E731
        f = Figure(type=types[0] if sorte == 1 else types[1], debut=a, fin=fin,
                   detection=bout, points=[(a, float(m.b[a])), (b, float(m.h[b]))],
                   lignes=[(b, float(haut(b)), bout, float(haut(bout))),
                           (b + 1, float(bas(b + 1)), bout, float(bas(bout)))],
                   etiquettes=[(a, float(m.b[a]), "mât")],
                   invalidation=float(m.b[b + 1:fin + 1].min()) if fin > b else float(m.b[b]))
        f.details.update({"mât": mat, "bougies du mât": b - a, "bougies de pause": fin - b + 1})
        if cassure >= 0:
            f.statut = CONFIRMEE
            f.sens_cassure = 1
            f.signal = cassure
            f.details["cassure"] = cassure
            f.niveau = float(haut(cassure))
            f.objectif = float(m.c[cassure]) + mat
        else:
            f.statut = EN_FORMATION
            f.niveau = float(haut(m.n))
            f.objectif = f.niveau + mat
        figures.append(f)
    return figures


def drapeaux(m: Marche) -> list[Figure]:
    """Drapeaux et fanions haussiers, puis baissiers (graphique retourné)."""
    figures = _chercher(m, ("drapeau_haussier", "fanion_haussier"))
    for f in _chercher(m.retourne(), ("drapeau_haussier", "fanion_haussier")):
        type_ = "drapeau_baissier" if f.type == "drapeau_haussier" else "fanion_baissier"
        figures.append(retourner_figure(f, type_))
    return figures
