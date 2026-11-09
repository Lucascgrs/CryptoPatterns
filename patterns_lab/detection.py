"""
L'analyse d'un historique : indicateurs, pivots, toutes les figures demandées,
supports et résistances.

    analyse = analyser(bougies, Reglages(), "BTC", "4h")
    analyse.figures          # liste de Figure, triée par date de début
    analyse.tableau()        # la même chose en tableau, pour l'affichage
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import chandeliers, chartistes, config, drapeaux, harmoniques, zones
from .chartistes import Marche
from .figures import CATALOGUE, FAMILLES, INVALIDEE, SANS_CASSURE, Figure, types_de
from .indicateurs import atr as calcul_atr
from .indicateurs import rsi as calcul_rsi
from .pivots import Pivots, structure, zigzag

TOUS_LES_TYPES = tuple(CATALOGUE)


@dataclass
class Reglages:
    sensibilite: float = config.SENSIBILITE        # taille minimale d'une vague, en ATR
    tolerance: float = config.TOLERANCE            # en % de la hauteur de la figure
    range_largeur: float = config.RANGE_LARGEUR    # en ATR
    range_duree: int = config.RANGE_DUREE          # en bougies
    niveau_touches: int = config.NIVEAU_TOUCHES
    types: list = field(default_factory=lambda: list(TOUS_LES_TYPES))

    def vers_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def depuis_dict(cls, d: dict) -> "Reglages":
        connus = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        r = cls(**connus)
        r.types = [t for t in r.types if t in CATALOGUE]
        return r

    def verifier(self) -> None:
        if not 0.5 <= self.sensibilite <= 20:
            raise ValueError("Sensibilité : entre 0,5 et 20 ATR.")
        if not 1 <= self.tolerance <= 60:
            raise ValueError("Tolérance : entre 1 et 60 %.")
        if self.range_largeur <= 0 or self.range_duree < 5:
            raise ValueError("Range : largeur positive et au moins 5 bougies.")


@dataclass
class Analyse:
    symbole: str
    intervalle: str
    provenance: str
    bougies: pd.DataFrame
    atr: np.ndarray
    rsi: np.ndarray
    pivots: Pivots
    structure: list
    figures: list
    niveaux: list
    reglages: Reglages

    @property
    def n(self) -> int:
        return len(self.bougies)

    def date(self, i: int) -> pd.Timestamp:
        return self.bougies.index[min(max(int(i), 0), self.n - 1)]

    def tableau(self, horizon: int = config.HORIZON) -> pd.DataFrame:
        """Une ligne par figure ; l'index est la position de la figure dans `figures`."""
        c = self.bougies["Close"].to_numpy()
        lignes = []
        for k, f in enumerate(self.figures):
            variation = np.nan
            if f.signal is not None and f.signal + horizon < self.n and f.sens:
                variation = f.sens * (c[f.signal + horizon] / c[f.signal] - 1)
            lignes.append({
                "Début": self.date(f.debut),
                "Signal": self.date(f.signal) if f.signal is not None else pd.NaT,
                "Figure": f.nom_complet,
                "Famille": f.famille,
                "Sens": {1: "▲", -1: "▼"}.get(f.sens, "?"),
                "Statut": f.statut,
                "Prix": float(c[f.signal]) if f.signal is not None else np.nan,
                "Objectif": f.objectif,
                "Invalidation": f.invalidation,
                f"Après {horizon}": variation,
                "_k": k,
            })
        df = pd.DataFrame(lignes)
        if not df.empty:
            df = df.set_index("_k")
            df.index.name = None
        return df


def analyser(bougies: pd.DataFrame, reglages: Reglages | None = None, symbole: str = "",
             intervalle: str = "", provenance: str = "") -> Analyse:
    reglages = reglages or Reglages()
    types = set(reglages.types)
    o = bougies["Open"].to_numpy(dtype=float)
    h = bougies["High"].to_numpy(dtype=float)
    b = bougies["Low"].to_numpy(dtype=float)
    c = bougies["Close"].to_numpy(dtype=float)
    atr = calcul_atr(h, b, c, config.PERIODE_ATR)
    rsi = calcul_rsi(c, config.PERIODE_RSI)
    m = Marche(o, h, b, c, atr)
    tolerance = reglages.tolerance / 100

    pv = zigzag(h, b, atr, reglages.sensibilite)
    figures: list[Figure] = []

    def voulu(*noms):
        return any(t in types for t in noms)

    if len(pv) >= 4:
        if voulu("double_sommet", "double_creux", "triple_sommet", "triple_creux"):
            figures += chartistes.doubles_et_triples(m, pv, tolerance)
        if voulu("tete_epaules", "tete_epaules_inverse"):
            figures += chartistes.tete_epaules(m, pv, tolerance)
        if voulu(*types_de("Triangles et biseaux"), "canal_ascendant", "canal_descendant", "rectangle"):
            figures += chartistes.deux_droites(m, pv, tolerance)
        if voulu("tasse_anse", "tasse_inversee"):
            figures += chartistes.tasses(m, pv, tolerance)
        if voulu(*types_de("Harmoniques")):
            figures += harmoniques.harmoniques(pv, types)
        if voulu(*types_de("Divergences")):
            figures += harmoniques.divergences(pv, rsi, types)
    if voulu("drapeau_haussier", "drapeau_baissier", "fanion_haussier", "fanion_baissier"):
        figures += drapeaux.drapeaux(m)
    if "range" in types:
        figures += zones.ranges(m, reglages.range_largeur, reglages.range_duree)
    if voulu(*types_de("Chandeliers")):
        figures += chandeliers.reperer(m, types)

    figures = [f for f in figures if f.type in types]
    for f in figures:
        if f.statut in (INVALIDEE, SANS_CASSURE):
            f.objectif = np.nan             # une figure ratée n'a plus d'objectif
    figures.sort(key=lambda f: (f.debut, f.fin))
    return Analyse(symbole=symbole, intervalle=intervalle, provenance=provenance,
                   bougies=bougies, atr=atr, rsi=rsi, pivots=pv, structure=structure(pv),
                   figures=figures, niveaux=zones.niveaux(pv, atr, reglages.niveau_touches),
                   reglages=reglages)


def compter(analyse: Analyse) -> pd.DataFrame:
    """Nombre de figures par famille et par type, avec leur statut."""
    if not analyse.figures:
        return pd.DataFrame()
    df = pd.DataFrame([{"Famille": f.famille, "Figure": f.nom, "Statut": f.statut}
                       for f in analyse.figures])
    df["Famille"] = pd.Categorical(df["Famille"], categories=FAMILLES, ordered=True)
    tableau = df.pivot_table(index=["Famille", "Figure"], columns="Statut", aggfunc="size",
                             fill_value=0, observed=True)
    tableau["Total"] = tableau.sum(axis=1)
    return tableau.sort_index()
