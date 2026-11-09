"""
Les deux indicateurs dont la détection a besoin.

**ATR** (Average True Range, de Wilder) : l'amplitude moyenne d'une bougie. Il
sert d'unité de mesure. Une vague de 3 ATR est une vraie vague sur n'importe
quelle crypto et à n'importe quelle échelle, alors qu'un seuil en dollars ou en
pourcentage changerait de sens d'une échelle à l'autre.

**RSI** (Relative Strength Index, de Wilder) : sert aux divergences.

Les deux sont calculés comme sur TradingView (`ta.atr`, `ta.rsi`) : moyenne
lissée de facteur 1/période, amorcée par une moyenne simple. Ils ne regardent
que le passé : la valeur de la bougie i ne dépend que des bougies 0 à i.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit
except ImportError:                                    # pragma: no cover
    def njit(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda fonction: fonction


@njit(cache=True)
def atr(haut, bas, cloture, periode):
    """
    ATR de Wilder. Avant la bougie `periode`, faute d'historique, c'est la
    moyenne des amplitudes déjà connues : la valeur reste causale et jamais vide.
    """
    n = len(cloture)
    sortie = np.full(n, np.nan)
    if n == 0:
        return sortie
    tr = np.empty(n)
    tr[0] = haut[0] - bas[0]
    for i in range(1, n):
        tr[i] = max(haut[i] - bas[i], abs(haut[i] - cloture[i - 1]),
                    abs(bas[i] - cloture[i - 1]))
    cumul = 0.0
    for i in range(min(periode, n)):
        cumul += tr[i]
        sortie[i] = cumul / (i + 1)
    for i in range(periode, n):
        sortie[i] = (sortie[i - 1] * (periode - 1) + tr[i]) / periode
    return sortie


@njit(cache=True)
def rsi(cloture, periode):
    n = len(cloture)
    sortie = np.full(n, np.nan)
    if n <= periode:
        return sortie
    hausse = 0.0
    baisse = 0.0
    for i in range(1, periode + 1):
        variation = cloture[i] - cloture[i - 1]
        if variation > 0:
            hausse += variation
        else:
            baisse -= variation
    hausse /= periode
    baisse /= periode
    sortie[periode] = 100.0 if baisse == 0 else 100.0 - 100.0 / (1.0 + hausse / baisse)
    for i in range(periode + 1, n):
        variation = cloture[i] - cloture[i - 1]
        hausse = (hausse * (periode - 1) + max(variation, 0.0)) / periode
        baisse = (baisse * (periode - 1) + max(-variation, 0.0)) / periode
        sortie[i] = 100.0 if baisse == 0 else 100.0 - 100.0 / (1.0 + hausse / baisse)
    return sortie


def moyenne_mobile(valeurs: np.ndarray, periode: int) -> np.ndarray:
    """Moyenne simple des `periode` dernières valeurs (NaN au début)."""
    sortie = np.full(len(valeurs), np.nan)
    if len(valeurs) >= periode:
        cumul = np.cumsum(np.insert(valeurs.astype(float), 0, 0.0))
        sortie[periode - 1:] = (cumul[periode:] - cumul[:-periode]) / periode
    return sortie
