"""
Récupération, stockage et lecture des chandeliers Binance.

Repris de `CryptoSupertrend/supertrend_lab/donnees.py` :

  1. **Stockage Parquet.** Une année en 1 minute fait 525 600 bougies : deux ans
     dépassent la limite d'Excel.
  2. **Mise à jour incrémentale qui n'efface jamais rien.** On ne télécharge que
     ce qui manque avant et après l'historique présent, puis on fusionne.
  3. **Requêtes en parallèle** (Binance plafonne à 1000 bougies par appel).

Ajouts propres à ce projet :

  - **N'importe quelle échelle.** Binance ne sert que 1m, 3m, 5m… 1w. Une échelle
    comme 10m, 45m, 3h ou 2d est construite en regroupant les bougies de la plus
    grande échelle téléchargée qui la divise (45m à partir de 15m, 2d à partir de
    1d). Seules les bougies complètes sont gardées.
  - **Lecture en direct** des dernières bougies, sans rien enregistrer.
  - **Import** des historiques de CryptoSupertrend, fusionnés sans rien effacer.

Seules les bougies **clôturées** comptent : la bougie en cours change encore.
"""

from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd
import requests

from . import config

URL_KLINES = "https://api.binance.com/api/v3/klines"
URL_PRIX = "https://api.binance.com/api/v3/ticker/price"
URL_COINGECKO = "https://api.coingecko.com/api/v3/coins/markets"
ENTETES = {"User-Agent": "CryptoPatterns/1.0"}

BOUGIES_PAR_REQUETE = 1000
COLONNES = ["Open", "High", "Low", "Close", "Volume"]
POIDS_ALERTE = 4800             # Binance : 6000 de « poids » par minute au maximum
REQUETES_DIRECT_MAX = 12        # échelle construite en direct : au plus 12 000 bougies de base


class PaireIndisponible(Exception):
    """La paire n'existe pas sur Binance (jeton absent, ou retiré de la cote)."""


class Interrompu(Exception):
    """Téléchargement arrêté à la demande."""


class DonneesAbsentes(Exception):
    """Aucun fichier téléchargé ne permet de construire l'échelle demandée."""


# ===========================================================================
# STOCKAGE
# ===========================================================================
def chemin(symbole: str, intervalle: str):
    return config.DOSSIER_DONNEES / f"{symbole}_{intervalle}.parquet"


def lire(symbole: str, intervalle: str) -> pd.DataFrame | None:
    """Historique OHLCV enregistré, indexé par l'heure d'OUVERTURE (UTC)."""
    fichier = chemin(symbole, intervalle)
    if not fichier.exists():
        return None
    return pd.read_parquet(fichier)


def inventaire() -> pd.DataFrame:
    """Une ligne par fichier téléchargé : symbole, échelle, bornes, nombre de bougies."""
    lignes = []
    if config.DOSSIER_DONNEES.is_dir():
        for fichier in sorted(config.DOSSIER_DONNEES.glob("*.parquet")):
            symbole, _, intervalle = fichier.stem.rpartition("_")
            if intervalle not in config.MINUTES_PAR_INTERVALLE:
                continue
            index = pd.read_parquet(fichier, columns=[]).index
            if len(index):
                lignes.append({"Symbole": symbole, "Échelle": intervalle,
                               "Début (UTC)": index.min(), "Fin (UTC)": index.max(),
                               "Bougies": len(index)})
    return pd.DataFrame(lignes)


def echelle_de_base(intervalle: str, disponibles) -> str | None:
    """
    L'échelle téléchargée à partir de laquelle construire `intervalle` : elle-même
    si elle est là, sinon la plus grande échelle disponible qui la divise.
    """
    cible = config.minutes(intervalle)
    candidates = [i for i in disponibles
                  if i in config.MINUTES_PAR_INTERVALLE
                  and cible % config.MINUTES_PAR_INTERVALLE[i] == 0]
    if not candidates:
        return None
    return max(candidates, key=lambda i: config.MINUTES_PAR_INTERVALLE[i])


def reechantillonner(df: pd.DataFrame, intervalle: str) -> pd.DataFrame:
    """
    Regroupe des bougies fines en bougies de `intervalle`. Les semaines
    commencent le lundi comme chez Binance, les autres échelles sont calées sur
    minuit UTC. La première et la dernière bougie ne sont gardées que si elles
    sont complètes.
    """
    if df.empty:
        return df
    pas = config.duree(intervalle)
    origine = pd.Timestamp("1970-01-05") if config.minutes(intervalle) % 10080 == 0 else "epoch"
    regles = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    groupes = df.resample(pas, origin=origine, label="left", closed="left")
    sortie = groupes.agg(regles).dropna(subset=["Open"])
    sortie = sortie[sortie.index >= df.index[0]]           # première bougie incomplète écartée
    if len(df) > 1:
        pas_base = df.index[-1] - df.index[-2]
        fin_donnees = df.index[-1] + pas_base
        sortie = sortie[sortie.index + pas <= fin_donnees]
    return sortie


_CACHE: dict = {}


def charger(symbole: str, intervalle: str) -> tuple[pd.DataFrame, str]:
    """
    Les bougies de `symbole` à l'échelle `intervalle`, depuis les fichiers
    téléchargés. Renvoie (bougies, provenance) ; la provenance dit si l'échelle a
    été construite à partir d'une autre (« construite à partir de 15m »).
    """
    intervalle = config.normaliser(intervalle)
    inv = inventaire()
    presentes = [] if inv.empty else list(inv.loc[inv["Symbole"] == symbole, "Échelle"])
    base = echelle_de_base(intervalle, presentes)
    if base is None:
        raise DonneesAbsentes(
            f"{symbole} {intervalle} : aucune échelle téléchargée ne permet de la construire "
            f"(il en faut une qui divise {intervalle} ; page Données).")
    fichier = chemin(symbole, base)
    cle = (symbole, intervalle, fichier.stat().st_mtime_ns)
    if cle not in _CACHE:
        brut = lire(symbole, base)
        df = brut if base == intervalle else reechantillonner(brut, intervalle)
        if len(_CACHE) > 12:
            _CACHE.clear()
        _CACHE[cle] = df
    provenance = "fichier téléchargé" if base == intervalle else f"construite à partir de {base}"
    return _CACHE[cle], provenance


def symboles_disponibles() -> list[str]:
    inv = inventaire()
    return sorted(inv["Symbole"].unique()) if not inv.empty else []


# ===========================================================================
# REQUÊTES BINANCE
# ===========================================================================
_SESSION = requests.Session()
_SESSION.headers.update(ENTETES)


def _en_ms(moment: pd.Timestamp) -> int:
    return int(pd.Timestamp(moment).value // 1_000_000)


def _requete(params: dict) -> list:
    """Un appel à /klines, avec reprise sur les limites de débit et le réseau."""
    for essai in range(6):
        try:
            reponse = _SESSION.get(URL_KLINES, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** essai)
            continue
        if reponse.status_code in (418, 429):
            time.sleep(int(reponse.headers.get("Retry-After", 30)))
            continue
        if reponse.status_code == 400:
            raise PaireIndisponible(reponse.json().get("msg", "paire inconnue"))
        if reponse.status_code >= 500:
            time.sleep(2 ** essai)
            continue
        reponse.raise_for_status()
        if int(reponse.headers.get("x-mbx-used-weight-1m", 0)) > POIDS_ALERTE:
            time.sleep(15)
        return reponse.json()
    raise ConnectionError(f"Binance ne répond pas ({params['symbol']} {params['interval']}).")


def _en_tableau(bougies: list) -> pd.DataFrame:
    if not bougies:
        return pd.DataFrame(columns=COLONNES, dtype=float)
    df = pd.DataFrame([b[:6] for b in bougies], columns=["Ouverture"] + COLONNES)
    df.index = pd.to_datetime(df.pop("Ouverture"), unit="ms")
    df.index.name = "Date"
    df = df.astype(float)
    return df[~df.index.duplicated(keep="last")].sort_index()


def premiere_bougie(symbole: str, intervalle: str, apres: pd.Timestamp) -> pd.Timestamp | None:
    """Première bougie disponible à partir de `apres` (évite des requêtes vides avant la cotation)."""
    lot = _requete({"symbol": symbole + config.DEVISE_COTATION, "interval": intervalle,
                    "startTime": _en_ms(apres), "limit": 1})
    return pd.to_datetime(lot[0][0], unit="ms") if lot else None


def telecharger_plage(symbole: str, intervalle: str, debut: pd.Timestamp,
                      fin: pd.Timestamp, progression=None, arret=None) -> pd.DataFrame:
    """
    Bougies dont l'ouverture tombe dans [debut, fin[, en tranches parallèles.
    `progression(faites, total)` après chaque requête ; `arret` (threading.Event)
    interrompt en levant `Interrompu`.
    """
    paire = symbole + config.DEVISE_COTATION
    pas = config.duree(intervalle) * BOUGIES_PAR_REQUETE
    tranches = []
    curseur = debut
    while curseur < fin:
        tranches.append((curseur, min(curseur + pas, fin)))
        curseur += pas
    if not tranches:
        return pd.DataFrame(columns=COLONNES, dtype=float)

    faites = 0
    verrou = Lock()

    def charger_tranche(tranche):
        nonlocal faites
        if arret is not None and arret.is_set():
            raise Interrompu()
        a, b = tranche
        lot = _requete({"symbol": paire, "interval": intervalle, "startTime": _en_ms(a),
                        "endTime": _en_ms(b) - 1, "limit": BOUGIES_PAR_REQUETE})
        with verrou:
            faites += 1
            if progression is not None:
                progression(faites, len(tranches))
        return lot

    with ThreadPoolExecutor(config.REQUETES_PARALLELES) as pool:
        lots = list(pool.map(charger_tranche, tranches))
    return _en_tableau([b for lot in lots for b in lot])


def maintenant_utc() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def bougies_direct(symbole: str, intervalle: str,
                   nombre: int = config.BOUGIES_DIRECT) -> tuple[pd.DataFrame, str]:
    """
    Les `nombre` dernières bougies **clôturées**, lues sur Binance sans rien
    enregistrer. Une échelle que Binance ne sert pas est construite à partir de
    la plus grande échelle native qui la divise (au plus 12 000 bougies de base).
    """
    intervalle = config.normaliser(intervalle)
    base = echelle_de_base(intervalle, config.MINUTES_PAR_INTERVALLE)
    facteur = config.minutes(intervalle) // config.MINUTES_PAR_INTERVALLE[base]
    voulues = min((nombre + 1) * facteur, REQUETES_DIRECT_MAX * BOUGIES_PAR_REQUETE)
    paire = symbole + config.DEVISE_COTATION
    lots, fin = [], None
    while voulues > 0:
        params = {"symbol": paire, "interval": base, "limit": min(voulues, BOUGIES_PAR_REQUETE)}
        if fin is not None:
            params["endTime"] = fin
        lot = _requete(params)
        if not lot:
            break
        lots.insert(0, lot)
        voulues -= len(lot)
        fin = lot[0][0] - 1
        if len(lot) < params["limit"]:
            break
    df = _en_tableau([b for lot in lots for b in lot])
    df = df[df.index + config.duree(base) <= maintenant_utc()]       # bougie en cours écartée
    if base != intervalle:
        df = reechantillonner(df, intervalle)
    provenance = "Binance en direct" + ("" if base == intervalle else f", construite à partir de {base}")
    return df.tail(nombre), provenance


# ===========================================================================
# MISE À JOUR DES FICHIERS
# ===========================================================================
def requetes_estimees(intervalle: str, jours: float) -> int:
    """Nombre d'appels à Binance pour `jours` d'historique (pour annoncer la durée)."""
    return int(jours * 1440 / config.MINUTES_PAR_INTERVALLE[intervalle] / BOUGIES_PAR_REQUETE) + 1


def _enregistrer(symbole: str, intervalle: str, df: pd.DataFrame) -> None:
    config.DOSSIER_DONNEES.mkdir(parents=True, exist_ok=True)
    df.to_parquet(chemin(symbole, intervalle))


def mettre_a_jour(symbole: str, intervalle: str, debut: pd.Timestamp,
                  progression=None, arret=None) -> str:
    """
    Complète le fichier de `symbole` / `intervalle` pour qu'il couvre
    [debut, maintenant]. Ce qui est déjà présent n'est ni retéléchargé ni
    supprimé, même si `debut` est plus récent que le début du fichier.
    """
    dt = config.duree(intervalle)
    maintenant = maintenant_utc()
    fin = (maintenant - dt).floor("min")

    existant = lire(symbole, intervalle)
    plages = []
    if existant is None or existant.empty:
        plages.append((debut, fin + dt))
    else:
        if debut < existant.index[0]:
            plages.append((debut, existant.index[0]))
        plages.append((existant.index[-1] + dt, fin + dt))

    nouveaux = []
    for a, b in plages:
        if a >= b:
            continue
        depart = premiere_bougie(symbole, intervalle, a)
        if depart is None or depart >= b:
            continue
        nouveaux.append(telecharger_plage(symbole, intervalle, depart, b, progression, arret))

    morceaux = [m for m in [existant, *nouveaux] if m is not None and not m.empty]
    if not morceaux:
        return f"{symbole} {intervalle} : aucune bougie disponible"
    df = pd.concat(morceaux)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df.index + dt <= maintenant]

    ajoutees = len(df) - (0 if existant is None else len(existant))
    if ajoutees or existant is None:
        _enregistrer(symbole, intervalle, df)
    return (f"{symbole:<6}{intervalle:>4} : {len(df):>9,} bougies "
            f"({df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d %H:%M} UTC), "
            f"{ajoutees:+,} nouvelles").replace(",", " ")


def importer_voisin(journal=print) -> int:
    """
    Copie les historiques de CryptoSupertrend (`../CryptoSupertrend/donnees`) en
    les fusionnant avec ceux d'ici : une bougie présente d'un seul côté est
    gardée, rien n'est effacé. Renvoie le nombre de fichiers ajoutés ou complétés.
    """
    source = config.DOSSIER_VOISIN
    if not source.is_dir():
        journal(f"Dossier introuvable : {source}")
        return 0
    modifies = 0
    for fichier in sorted(source.glob("*.parquet")):
        symbole, _, intervalle = fichier.stem.rpartition("_")
        if intervalle not in config.MINUTES_PAR_INTERVALLE:
            continue
        cible = chemin(symbole, intervalle)
        if not cible.exists():
            config.DOSSIER_DONNEES.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fichier, cible)
            journal(f"{symbole:<6}{intervalle:>4} : copié")
            modifies += 1
            continue
        ici, la_bas = pd.read_parquet(cible), pd.read_parquet(fichier)
        fusion = pd.concat([la_bas, ici])
        fusion = fusion[~fusion.index.duplicated(keep="last")].sort_index()
        if len(fusion) > len(ici):
            _enregistrer(symbole, intervalle, fusion)
            journal(f"{symbole:<6}{intervalle:>4} : {len(fusion) - len(ici):+,} bougies".replace(",", " "))
            modifies += 1
    journal(f"Import terminé : {modifies} fichier(s) ajouté(s) ou complété(s).")
    _CACHE.clear()
    return modifies


# ===========================================================================
# CLASSEMENT DU MARCHÉ
# ===========================================================================
def paires_binance() -> set[str]:
    """Symboles cotés en USDT sur Binance, ex. {'BTC', 'ETH', ...}."""
    reponse = _SESSION.get(URL_PRIX, timeout=30)
    reponse.raise_for_status()
    suffixe = config.DEVISE_COTATION
    return {p["symbol"][: -len(suffixe)] for p in reponse.json()
            if p["symbol"].endswith(suffixe)}


def top_cryptos(n: int) -> list[str]:
    """Les `n` plus grosses capitalisations (CoinGecko), hors stablecoins, cotées sur Binance."""
    import re

    reponse = _SESSION.get(URL_COINGECKO, timeout=30, params={
        "vs_currency": "usd", "order": "market_cap_desc",
        "per_page": min(n + 40, 250), "page": 1})
    reponse.raise_for_status()
    cotees = paires_binance()
    retenus = []
    for jeton in reponse.json():
        symbole = jeton["symbol"].upper()
        if symbole in config.STABLECOINS or re.match(config.MOTIF_STABLECOIN, symbole):
            continue
        if symbole in cotees and symbole not in retenus:
            retenus.append(symbole)
        if len(retenus) == n:
            break
    return retenus
