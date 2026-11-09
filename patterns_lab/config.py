"""
Réglages du projet, regroupés ici pour ne rien coder en dur ailleurs.

Tout ce qui se change sans toucher à la logique est ici : cryptos suivies,
échelles de temps, réglages par défaut de la détection, frais.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DONNEES = RACINE / "donnees"        # OHLCV bruts, un .parquet par crypto et échelle
DOSSIER_RESULTATS = RACINE / "resultats"    # exports Excel et images

# Les historiques déjà téléchargés pour CryptoSupertrend peuvent être importés
# (copiés et fusionnés) plutôt que téléchargés une seconde fois.
DOSSIER_VOISIN = RACINE.parent / "CryptoSupertrend" / "donnees"

# ---------------------------------------------------------------------------
# Marché
# ---------------------------------------------------------------------------
CRYPTOS_DEFAUT = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "LINK", "AVAX"]
DEVISE_COTATION = "USDT"

STABLECOINS = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "FDUSD", "USDE", "PYUSD", "USDS",
               "USD1", "USDD", "GUSD", "LUSD", "FRAX", "USDG", "RLUSD", "EURC",
               "STETH", "WSTETH", "WBETH", "WEETH", "WBTC"}
MOTIF_STABLECOIN = r"^[A-Z0-9]{0,3}USD[A-Z0-9]{0,3}$"

# Première bougie de Binance (BTCUSDT) : « tout l'historique » part de là.
DEBUT_BINANCE = pd.Timestamp("2017-08-17")

# ---------------------------------------------------------------------------
# Échelles de temps
# ---------------------------------------------------------------------------
# Échelles servies directement par Binance, en minutes. Le mois (1M) est exclu :
# sa durée varie. Toute autre échelle (10m, 45m, 3h, 2d…) est construite en
# regroupant les bougies d'une échelle téléchargée plus fine.
MINUTES_PAR_INTERVALLE = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}
INTERVALLES_DEFAUT = ["15m", "1h", "4h", "1d", "1w"]
UNITES = {"m": 1, "h": 60, "d": 1440, "w": 10080}

# ---------------------------------------------------------------------------
# Détection (valeurs de départ ; toutes se changent dans l'interface)
# ---------------------------------------------------------------------------
PERIODE_ATR = 14            # l'ATR sert d'unité : une figure se mesure en ATR
SENSIBILITE = 3.0           # une vague doit faire au moins 3 ATR pour compter
TOLERANCE = 15.0            # écart toléré entre deux sommets « égaux », en % de la hauteur
RANGE_LARGEUR = 4.0         # un range tient dans une bande de 4 ATR…
RANGE_DUREE = 30            # … pendant au moins 30 bougies
NIVEAU_TOUCHES = 3          # un support ou une résistance : au moins 3 contacts
PERIODE_RSI = 14
HORIZON = 20                # « que se passe-t-il N bougies après la figure ? »

# ---------------------------------------------------------------------------
# Téléchargement
# ---------------------------------------------------------------------------
JOURS_HISTORIQUE = 1461         # profondeur par défaut : 4 ans
REQUETES_PARALLELES = 6
BOUGIES_DIRECT = 1000           # bougies lues sur Binance pour l'analyse en direct
BOUGIES_CHAUFFE = 100           # bougies de plus au début, pour que l'ATR soit stable

FRAIS_PCT = 0.10                # par ordre, au comptant chez Binance


def minutes(intervalle: str) -> int:
    """'45m' -> 45, '4h' -> 240, '2d' -> 2880, '1w' -> 10080."""
    if intervalle in MINUTES_PAR_INTERVALLE:
        return MINUTES_PAR_INTERVALLE[intervalle]
    trouve = re.fullmatch(r"\s*(\d+)\s*([mhdw])\s*", str(intervalle))
    if not trouve or int(trouve.group(1)) == 0:
        raise ValueError(f"Échelle illisible : {intervalle!r}. Exemples : 1m, 45m, 2h, 1d, 2d, 1w.")
    return int(trouve.group(1)) * UNITES[trouve.group(2)]


def nom_intervalle(nombre_minutes: int) -> str:
    """240 -> '4h' : l'écriture la plus courte, dans l'unité la plus grande qui tombe juste."""
    for unite, valeur in sorted(UNITES.items(), key=lambda u: -u[1]):
        if nombre_minutes % valeur == 0:
            return f"{nombre_minutes // valeur}{unite}"
    return f"{nombre_minutes}m"


def normaliser(intervalle: str) -> str:
    """'60m' -> '1h', '7d' -> '1w' : un seul nom par durée."""
    return nom_intervalle(minutes(intervalle))


def duree(intervalle: str) -> pd.Timedelta:
    return pd.Timedelta(minutes=minutes(intervalle))


def trier_intervalles(intervalles) -> list[str]:
    """Valide, normalise et trie du plus court au plus long, sans doublon."""
    if isinstance(intervalles, str):
        intervalles = [i for i in re.split(r"[\s,;]+", intervalles) if i]
    uniques = list(dict.fromkeys(normaliser(i) for i in intervalles))
    return sorted(uniques, key=minutes)


def est_natif(intervalle: str) -> bool:
    return normaliser(intervalle) in MINUTES_PAR_INTERVALLE


def preparer_dossiers() -> None:
    for dossier in (DOSSIER_DONNEES, DOSSIER_RESULTATS):
        dossier.mkdir(parents=True, exist_ok=True)
