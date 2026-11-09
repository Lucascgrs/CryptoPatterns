"""
Ce qui s'est passé après chaque figure : la figure tient-elle ses promesses ?

Pour chaque figure confirmée, à la clôture de sa bougie de signal :

  - **Après N bougies** : la variation du prix N bougies plus tard, comptée dans
    le sens attendu (+2 % après une figure baissière = le prix a baissé de 2 %).
    « Bon sens » si elle est positive.
  - **Le hasard**, pour comparer : sur le même historique, la part de toutes
    les bougies après lesquelles le prix a monté (ou baissé) sur N bougies. Une
    figure haussière qui « marche » 55 % du temps ne vaut rien si le prix
    monte de toute façon 55 % du temps sur cette période.
  - **Le trade** : une règle simple et fixe, rejouée telle quelle. On entre à la
    clôture du signal, dans le sens attendu ; on sort à l'objectif, au niveau
    d'invalidation, ou au bout de N bougies, au premier des trois. Si
    l'objectif et l'invalidation sont touchés dans la même bougie, on compte
    l'invalidation (le pire). Frais : deux ordres.
  - **Les deux moitiés** : l'écart au hasard est calculé séparément sur la
    première et la seconde moitié de la période. Une figure qui ne bat le
    hasard que sur une moitié est fragile.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .detection import Analyse
from .figures import CONFIRMEE, EN_FORMATION, FAMILLES


def hasard(cloture: np.ndarray, horizon: int) -> tuple[float, float, float]:
    """Part des bougies suivies d'une hausse, d'une baisse, et variation moyenne, sur `horizon` bougies."""
    if len(cloture) <= horizon:
        return np.nan, np.nan, np.nan
    r = cloture[horizon:] / cloture[:-horizon] - 1
    return float(np.mean(r > 0)), float(np.mean(r < 0)), float(np.mean(r))


def evaluer(analyse: Analyse, horizon: int, frais: float) -> pd.DataFrame:
    """Une ligne par figure confirmée assez ancienne pour avoir N bougies de recul."""
    df = analyse.bougies
    o, h, b, c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
    n = len(c)
    p_hausse, p_baisse, moyenne = hasard(c, horizon)
    milieu = df.index[0] + (df.index[-1] - df.index[0]) / 2
    lignes = []
    for k, f in enumerate(analyse.figures):
        e = f.signal
        s = f.sens
        if e is None or not s or e + horizon >= n:
            continue
        entree = c[e]
        apres = s * (c[e + horizon] / entree - 1)
        stop = f.invalidation if np.isfinite(f.invalidation) and s * (entree - f.invalidation) > 0 else np.nan
        cible = f.objectif if np.isfinite(f.objectif) and s * (f.objectif - entree) > 0 else np.nan
        tranche = slice(e + 1, e + horizon + 1)
        if s > 0:
            touche_stop = b[tranche] <= stop
            touche_cible = h[tranche] >= cible
        else:
            touche_stop = h[tranche] >= stop
            touche_cible = b[tranche] <= cible
        k_stop = int(np.argmax(touche_stop)) if touche_stop.any() else None
        k_cible = int(np.argmax(touche_cible)) if touche_cible.any() else None
        if k_stop is not None and (k_cible is None or k_stop <= k_cible):
            issue, j = "invalidation", e + 1 + k_stop
            sortie = min(o[j], stop) if s > 0 else max(o[j], stop)          # ouverture au-delà : on sort à l'ouverture
        elif k_cible is not None:
            issue, j = "objectif", e + 1 + k_cible
            sortie = max(o[j], cible) if s > 0 else min(o[j], cible)
        else:
            issue, j = "délai", e + horizon
            sortie = c[j]
        brut = s * (sortie / entree - 1)
        signal = analyse.date(e)
        lignes.append({
            "Crypto": analyse.symbole, "Échelle": analyse.intervalle, "Type": f.type,
            "Figure": f.nom_complet, "Famille": f.famille, "Sens": s,
            "Début": analyse.date(f.debut), "Signal": signal, "Prix": entree,
            "Objectif": f.objectif, "Invalidation": f.invalidation,
            "Après N": apres, "Bon sens": apres > 0,
            "Hasard bon sens": p_hausse if s > 0 else p_baisse, "Hasard moyen": s * moyenne,
            "Issue": issue, "Prix sortie": sortie, "Trade brut": brut, "Trade net": brut - 2 * frais,
            "Bougies en position": j - e, "Moitié": 1 if signal < milieu else 2, "_k": k,
        })
    return pd.DataFrame(lignes)


def reperees(analyse: Analyse) -> pd.DataFrame:
    """Toutes les figures repérées et leur statut, pour le taux de confirmation."""
    return pd.DataFrame([{"Crypto": analyse.symbole, "Échelle": analyse.intervalle, "Type": f.type,
                          "Figure": f.nom_complet, "Famille": f.famille, "Statut": f.statut}
                         for f in analyse.figures])


COLONNES_RESUME = ["Famille", "Figure", "Sens", "Repérées", "Confirmées", "Évaluées",
                   "Bon sens", "Hasard", "Écart", "Variation moyenne", "Hasard moyen",
                   "Objectif atteint", "Invalidée", "Trade net moyen", "Trades gagnants",
                   "Écart 1re moitié", "Écart 2e moitié"]


def resumer(occurrences: pd.DataFrame, toutes: pd.DataFrame, par=()) -> pd.DataFrame:
    """
    Une ligne par figure (et par crypto ou échelle si `par` le demande).
    Les pourcentages sont des fractions (0,55 = 55 %) ; « Écart » est en points.
    """
    par = list(par)
    if occurrences.empty:
        return pd.DataFrame(columns=par + COLONNES_RESUME)
    terminees = toutes[toutes["Statut"] != EN_FORMATION]
    nb_reperees = terminees.groupby(par + ["Type"]).size().rename("Repérées")
    nb_confirmees = terminees[terminees["Statut"] == CONFIRMEE].groupby(par + ["Figure"]).size() \
        .rename("Confirmées")

    def bloc(g: pd.DataFrame) -> pd.Series:
        moities = {}
        for moitie in (1, 2):
            m = g[g["Moitié"] == moitie]
            moities[moitie] = (m["Bon sens"].mean() - m["Hasard bon sens"].mean()) if len(m) else np.nan
        return pd.Series({
            "Famille": g["Famille"].iloc[0], "Type": g["Type"].iloc[0], "Sens": int(g["Sens"].iloc[0]),
            "Évaluées": len(g),
            "Bon sens": g["Bon sens"].mean(), "Hasard": g["Hasard bon sens"].mean(),
            "Écart": g["Bon sens"].mean() - g["Hasard bon sens"].mean(),
            "Variation moyenne": g["Après N"].mean(), "Hasard moyen": g["Hasard moyen"].mean(),
            "Objectif atteint": (g["Issue"] == "objectif").mean(),
            "Invalidée": (g["Issue"] == "invalidation").mean(),
            "Trade net moyen": g["Trade net"].mean(), "Trades gagnants": (g["Trade net"] > 0).mean(),
            "Écart 1re moitié": moities[1], "Écart 2e moitié": moities[2],
        })

    resume = occurrences.groupby(par + ["Figure"], sort=False).apply(bloc, include_groups=False)
    resume = resume.reset_index()
    resume = resume.join(nb_reperees, on=par + ["Type"]).join(nb_confirmees, on=par + ["Figure"])
    ordre = {f: k for k, f in enumerate(FAMILLES)}
    resume["_ordre"] = resume["Famille"].map(ordre)
    resume = resume.sort_values(par + ["_ordre", "Figure"]).drop(columns=["_ordre", "Type"])
    resume["Sens"] = resume["Sens"].map({1: "▲", -1: "▼"})
    return resume[par + COLONNES_RESUME].reset_index(drop=True)
