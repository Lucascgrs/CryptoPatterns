"""
Les figures de chandeliers japonais, sur une à trois bougies.

Vocabulaire : le **corps** va de l'ouverture à la clôture ; les **mèches** (ou
ombres) dépassent au-dessus et au-dessous ; l'**amplitude** va du plus bas au
plus haut. Une bougie est verte si elle clôture plus haut qu'elle n'a ouvert.

Le **corps moyen** est la moyenne des corps des 14 bougies précédentes : il dit
ce qu'est une « grande » bougie à ce moment-là.

La **tendance avant la figure** : le prix est en hausse si la clôture qui
précède la figure dépasse à la fois celle de 5 bougies plus tôt et la moyenne
des 10 dernières clôtures (et inversement pour la baisse). Beaucoup de figures
n'ont de sens qu'après une hausse ou après une baisse.

En crypto, le marché ne ferme jamais : l'ouverture d'une bougie est presque
toujours la clôture de la précédente. Les conditions d'écart (« gap ») des
définitions boursières sont donc abandonnées.

Une figure de chandeliers est connue à la clôture de sa dernière bougie, qui
est aussi la bougie de signal.
"""

from __future__ import annotations

import numpy as np

from .chartistes import Marche
from .figures import CONFIRMEE, Figure
from .indicateurs import moyenne_mobile


def _decale(x: np.ndarray, k: int, defaut=np.nan) -> np.ndarray:
    """x[i - k] à la position i (défaut pour les k premières)."""
    sortie = np.full(len(x), defaut, dtype=float)
    if k < len(x):
        sortie[k:] = x[:len(x) - k]
    return sortie


def reperer(m: Marche, types: set[str]) -> list[Figure]:
    o, h, b, c, atr = m.o, m.h, m.b, m.c, m.atr
    n = m.n
    if n < 20:
        return []
    corps = np.abs(c - o)
    amplitude = h - b
    haut_corps = np.maximum(o, c)
    bas_corps = np.minimum(o, c)
    meche_h = h - haut_corps
    meche_b = bas_corps - b
    verte = c > o
    rouge = c < o
    corps_moyen = _decale(moyenne_mobile(corps, 14), 1)
    mm10 = moyenne_mobile(c, 10)
    hausse = (c > _decale(c, 5)) & (c > mm10)
    baisse = (c < _decale(c, 5)) & (c < mm10)

    def avant(tendance, longueur):
        """Tendance à la bougie qui précède une figure de `longueur` bougies."""
        return _decale(tendance.astype(float), longueur, 0.0) > 0

    def p(x, k):
        return _decale(x, k)

    with np.errstate(invalid="ignore", divide="ignore"):
        assez_grande = amplitude >= 0.5 * atr
        doji = (corps <= 0.1 * amplitude) & assez_grande
        petit_haut = meche_h <= 0.1 * amplitude
        petit_bas = meche_b <= 0.1 * amplitude
        forme_marteau = (meche_b >= 2 * corps) & petit_haut & (corps >= 0.05 * amplitude) & \
            (amplitude >= 0.7 * atr)
        forme_inverse = (meche_h >= 2 * corps) & petit_bas & (corps >= 0.05 * amplitude) & \
            (amplitude >= 0.7 * atr)

        c1, o1, h1, b1 = p(c, 1), p(o, 1), p(h, 1), p(b, 1)
        corps1 = p(corps, 1)
        verte1, rouge1 = p(verte.astype(float), 1) > 0, p(rouge.astype(float), 1) > 0
        avalement_h = rouge1 & verte & (o <= c1) & (c >= o1) & (corps > corps1) & \
            (corps >= 0.5 * corps_moyen)
        avalement_b = verte1 & rouge & (o >= c1) & (c <= o1) & (corps > corps1) & \
            (corps >= 0.5 * corps_moyen)
        harami_h = rouge1 & (corps1 >= corps_moyen) & verte & (haut_corps <= o1) & \
            (bas_corps >= c1) & (corps <= 0.6 * corps1)
        harami_b = verte1 & (corps1 >= corps_moyen) & rouge & (haut_corps <= c1) & \
            (bas_corps >= o1) & (corps <= 0.6 * corps1)
        milieu1 = (o1 + c1) / 2
        penetrante = rouge1 & (corps1 >= corps_moyen) & verte & (o <= c1) & (c > milieu1) & (c < o1)
        nuage = verte1 & (corps1 >= corps_moyen) & rouge & (o >= c1) & (c < milieu1) & (c > o1)
        egal_haut = np.abs(h - h1) <= 0.05 * atr
        egal_bas = np.abs(b - b1) <= 0.05 * atr
        pince_haut = egal_haut & verte1 & rouge & (corps1 >= 0.3 * corps_moyen) & (corps >= 0.3 * corps_moyen)
        pince_bas = egal_bas & rouge1 & verte & (corps1 >= 0.3 * corps_moyen) & (corps >= 0.3 * corps_moyen)

        c2, o2 = p(c, 2), p(o, 2)
        corps2 = p(corps, 2)
        rouge2, verte2 = p(rouge.astype(float), 2) > 0, p(verte.astype(float), 2) > 0
        milieu2 = (o2 + c2) / 2
        etoile_matin = rouge2 & (corps2 >= corps_moyen) & (corps1 <= 0.3 * corps2) & verte & \
            (c > milieu2) & (corps >= 0.5 * corps_moyen)
        etoile_soir = verte2 & (corps2 >= corps_moyen) & (corps1 <= 0.3 * corps2) & rouge & \
            (c < milieu2) & (corps >= 0.5 * corps_moyen)
        grand = corps >= 0.6 * corps_moyen
        grand1, grand2 = p(grand.astype(float), 1) > 0, p(grand.astype(float), 2) > 0
        mh1, mh2 = p(meche_h, 1), p(meche_h, 2)
        mb1, mb2 = p(meche_b, 1), p(meche_b, 2)
        soldats = verte & verte1 & verte2 & grand & grand1 & grand2 & (c > c1) & (c1 > c2) & \
            (o >= o1) & (o <= c1) & (o1 >= o2) & (o1 <= c2) & \
            (meche_h <= 0.3 * corps) & (mh1 <= 0.3 * corps1) & (mh2 <= 0.3 * corps2)
        corbeaux = rouge & rouge1 & rouge2 & grand & grand1 & grand2 & (c < c1) & (c1 < c2) & \
            (o <= o1) & (o >= c1) & (o1 <= o2) & (o1 >= c2) & \
            (meche_b <= 0.3 * corps) & (mb1 <= 0.3 * corps1) & (mb2 <= 0.3 * corps2)
        marubozu = (corps >= 0.9 * amplitude) & (corps >= 1.5 * corps_moyen)

    regles = {
        # type : (condition à la dernière bougie, nombre de bougies)
        "doji_apres_hausse": (doji & avant(hausse, 1), 1),
        "doji_apres_baisse": (doji & avant(baisse, 1), 1),
        "marteau": (forme_marteau & avant(baisse, 1), 1),
        "pendu": (forme_marteau & avant(hausse, 1), 1),
        "marteau_inverse": (forme_inverse & avant(baisse, 1), 1),
        "etoile_filante": (forme_inverse & avant(hausse, 1), 1),
        "avalement_haussier": (avalement_h & avant(baisse, 2), 2),
        "avalement_baissier": (avalement_b & avant(hausse, 2), 2),
        "harami_haussier": (harami_h & avant(baisse, 2), 2),
        "harami_baissier": (harami_b & avant(hausse, 2), 2),
        "penetrante": (penetrante & avant(baisse, 2), 2),
        "nuage_noir": (nuage & avant(hausse, 2), 2),
        "pince_haut": (pince_haut & avant(hausse, 2), 2),
        "pince_bas": (pince_bas & avant(baisse, 2), 2),
        "etoile_du_matin": (etoile_matin & avant(baisse, 3), 3),
        "etoile_du_soir": (etoile_soir & avant(hausse, 3), 3),
        "trois_soldats": (soldats, 3),
        "trois_corbeaux": (corbeaux, 3),
        "marubozu_haussier": (marubozu & verte, 1),
        "marubozu_baissier": (marubozu & rouge, 1),
    }

    figures = []
    for type_, (condition, longueur) in regles.items():
        if type_ not in types:
            continue
        condition = np.asarray(condition, dtype=bool)
        condition[:20] = False                       # corps moyen et tendance pas encore connus
        for i in np.flatnonzero(condition):
            i = int(i)
            debut = i - longueur + 1
            bas_fig = float(b[debut:i + 1].min())
            haut_fig = float(h[debut:i + 1].max())
            f = Figure(type=type_, debut=debut, fin=i, detection=i, points=[],
                       zone=(debut, i, bas_fig, haut_fig), signal=i, statut=CONFIRMEE)
            f.sens_cassure = f.modele.sens
            f.niveau = float(c[i])
            f.invalidation = bas_fig if f.modele.sens > 0 else haut_fig
            figures.append(f)
    return figures
