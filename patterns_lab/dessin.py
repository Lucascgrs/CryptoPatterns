"""
Le dessin des bougies et des figures sur un axe matplotlib.

Sert à l'interface (graphique interactif) et à la ligne de commande (images
PNG). L'axe horizontal est la **position** de la bougie (0, 1, 2…) et non sa
date : pas de trous les jours sans données, et les figures se dessinent
directement avec leurs indices. Les dates sont écrites sous l'axe.

Quand la vue contient trop de bougies pour les voir (plus de ~600), elles sont
regroupées : une bougie affichée en résume plusieurs (ouverture de la première,
plus haut, plus bas, clôture de la dernière). En zoomant, on retrouve les
bougies une à une.
"""

from __future__ import annotations

import math

import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

COULEURS = {
    "fond": "#1a1a1a",
    "axe": "#1e1e1e",
    "texte": "#e6e6e6",
    "texte_doux": "#9aa0a6",
    "bougie_haut": "#3f9e83",
    "bougie_bas": "#b4554d",
    "hausse": "#4ade80",
    "baisse": "#f87171",
    "neutre": "#60a5fa",
    "range": "#60a5fa",
    "pivot": "#8a8f98",
    "support": "#4ade80",
    "resistance": "#f87171",
    "les_deux": "#f4b942",
    "objectif": "#4ade80",
    "invalidation": "#f39c12",
    "selection": "#ffd54f",
}

BOUGIES_MAX = 600


def couleur_sens(sens: int) -> str:
    return COULEURS["hausse"] if sens > 0 else COULEURS["baisse"] if sens < 0 else COULEURS["neutre"]


def styliser(ax) -> None:
    ax.set_facecolor(COULEURS["axe"])
    ax.tick_params(colors="#bbbbbb", labelsize=8)
    for bordure in ax.spines.values():
        bordure.set_color("#555555")
    ax.title.set_color("white")
    ax.xaxis.label.set_color("#bbbbbb")
    ax.yaxis.label.set_color("#bbbbbb")
    ax.grid(alpha=0.12, color="#888888")


def format_dates(ax, index, intervalle_minutes: int) -> None:
    """Graduations horizontales : la date de la bougie à chaque position."""
    if intervalle_minutes < 1440:
        motif = "%d/%m %H:%M"
    elif intervalle_minutes < 10080 * 4:
        motif = "%d/%m/%Y"
    else:
        motif = "%m/%Y"
    n = len(index)

    def texte(x, _pos):
        i = int(round(x))
        if i < 0 or i >= n:
            return ""
        return index[i].strftime(motif)

    ax.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(texte))


# ===========================================================================
# BOUGIES
# ===========================================================================
def regrouper(o, h, b, c, i0: int, i1: int, maximum: int = BOUGIES_MAX):
    """
    Bougies de [i0, i1[ regroupées par paquets pour en afficher au plus
    `maximum`. Les paquets sont alignés sur des multiples de leur taille : en
    faisant défiler, une bougie regroupée ne change pas.
    Renvoie (x, o, h, b, c, taille du paquet).
    """
    i0, i1 = max(0, int(i0)), min(len(c), int(i1))
    if i1 <= i0:
        vide = np.array([])
        return vide, vide, vide, vide, vide, 1
    paquet = max(1, math.ceil((i1 - i0) / maximum))
    g0 = (i0 // paquet) * paquet
    debuts = np.arange(g0, i1, paquet)
    rel = debuts - g0
    fins = np.minimum(debuts + paquet, i1) - 1
    ho = o[debuts]
    hh = np.maximum.reduceat(h[g0:i1], rel)
    hb = np.minimum.reduceat(b[g0:i1], rel)
    hc = c[fins]
    x = debuts + (paquet - 1) / 2
    return x, ho, hh, hb, hc, paquet


def tracer_bougies(ax, o, h, b, c, i0, i1, maximum: int = BOUGIES_MAX) -> list:
    x, bo, bh, bb, bc, paquet = regrouper(o, h, b, c, i0, i1, maximum)
    if not len(x):
        return []
    largeur = 0.7 * paquet
    monte = bc >= bo
    teintes = np.where(monte, COULEURS["bougie_haut"], COULEURS["bougie_bas"])
    meches = LineCollection([((xi, lo), (xi, hi)) for xi, lo, hi in zip(x, bb, bh)],
                            colors=teintes, linewidths=0.8, zorder=2)
    corps = PolyCollection(
        [((xi - largeur / 2, a), (xi + largeur / 2, a), (xi + largeur / 2, z), (xi - largeur / 2, z))
         for xi, a, z in zip(x, bo, bc)],
        facecolors=teintes, edgecolors=teintes, linewidths=0.6, zorder=3)
    ax.add_collection(meches)
    ax.add_collection(corps)
    return [meches, corps]


# ===========================================================================
# FIGURES
# ===========================================================================
def tracer_figure(ax, f, cloture, mise_en_avant: bool = False, etiquettes: bool = False,
                  horizon: int = 20) -> list:
    """Dessine une figure ; renvoie les objets créés (pour pouvoir les effacer)."""
    artistes = []
    teinte = couleur_sens(f.sens)
    epaisseur = 2.4 if mise_en_avant else 1.0
    opacite = 1.0 if mise_en_avant else 0.55
    z = 6 if mise_en_avant else 4

    if f.famille == "Chandeliers":
        i0, i1, bas, haut = f.zone
        x = (i0 + i1) / 2
        ecart = (haut - bas) * 0.15 + 1e-12
        if f.sens > 0:
            artistes += ax.plot([x], [bas - ecart], marker="^", color=teinte, ms=7 if mise_en_avant else 5,
                                ls="none", zorder=z)
            y, va = bas - 2.2 * ecart, "top"
        else:
            artistes += ax.plot([x], [haut + ecart], marker="v", color=teinte, ms=7 if mise_en_avant else 5,
                                ls="none", zorder=z)
            y, va = haut + 2.2 * ecart, "bottom"
        if mise_en_avant:
            artistes.append(ax.add_patch(Rectangle((i0 - 0.45, bas), i1 - i0 + 0.9, haut - bas, fill=False,
                                                   ec=COULEURS["selection"], lw=1.2, zorder=z)))
        if etiquettes or mise_en_avant:
            artistes.append(ax.text(x, y, f.modele.court, color=teinte, fontsize=7, ha="center", va=va,
                                    zorder=z, clip_on=True))
        return artistes

    if f.zone is not None:
        i0, i1, bas, haut = f.zone
        artistes.append(ax.add_patch(Rectangle(
            (i0 - 0.5, bas), i1 - i0 + 1, haut - bas, facecolor=COULEURS["range"] if f.type == "range"
            else teinte, alpha=0.18 if mise_en_avant else 0.07, edgecolor=teinte,
            lw=1.2 if mise_en_avant else 0.6, zorder=1)))
    # Figures à deux droites : hors sélection, les droites suffisent (le trajet
    # entre les pivots doublerait la ligne du zigzag).
    if f.points and (mise_en_avant or not f.lignes or f.famille not in ("Triangles et biseaux",
                                                                         "Canaux et ranges")):
        xs, ys = zip(*f.points)
        artistes += ax.plot(xs, ys, color=teinte, lw=epaisseur, alpha=opacite, zorder=z,
                            solid_joinstyle="round")
    for i0, p0, i1, p1 in f.lignes:
        artistes += ax.plot([i0, i1], [p0, p1], color=teinte, lw=epaisseur * 0.8, alpha=opacite,
                            ls="--" if f.famille in ("Retournements", "Harmoniques") else "-", zorder=z)
    if etiquettes or mise_en_avant:
        for i, p, texte in f.etiquettes:
            artistes.append(ax.text(i, p, f" {texte}", color=teinte, fontsize=7.5 if mise_en_avant else 6.5,
                                    ha="left", va="bottom", zorder=z + 1, clip_on=True))
    if f.signal is not None:
        artistes += ax.plot([f.signal], [cloture[f.signal]], marker="o", ms=6 if mise_en_avant else 4,
                            color=teinte, mec="white" if mise_en_avant else teinte, mew=0.8, ls="none",
                            zorder=z + 1)
    if mise_en_avant:
        depart = f.signal if f.signal is not None else f.fin
        fin = depart + max(horizon, 5)
        for niveau, cle, texte in ((f.objectif, "objectif", "objectif"),
                                   (f.invalidation, "invalidation", "invalidation")):
            if niveau is not None and np.isfinite(niveau):
                artistes += ax.plot([depart, fin], [niveau, niveau], color=COULEURS[cle], lw=1.1, ls=":",
                                    zorder=z)
                artistes.append(ax.text(fin, niveau, f" {texte}", color=COULEURS[cle], fontsize=7,
                                        va="center", zorder=z, clip_on=True))
    return artistes


def tracer_pivots(ax, analyse, i0, i1, structure: bool = False) -> list:
    pv = analyse.pivots
    if not len(pv):
        return []
    a = max(0, int(np.searchsorted(pv.i, i0)) - 1)
    z = min(len(pv), int(np.searchsorted(pv.i, i1)) + 1)
    artistes = ax.plot(pv.i[a:z], pv.prix[a:z], color=COULEURS["pivot"], lw=0.8, alpha=0.7,
                       ls="-", zorder=3)
    if structure and z - a <= 120:
        for k in range(a, z):
            texte = analyse.structure[k]
            if not texte:
                continue
            haut = pv.type[k] > 0
            artistes.append(ax.text(pv.i[k], pv.prix[k], texte, fontsize=6.5, ha="center",
                                    va="bottom" if haut else "top", clip_on=True, zorder=5,
                                    color=COULEURS["hausse"] if texte in ("HH", "HL") else COULEURS["baisse"]))
    return artistes


def tracer_niveaux(ax, analyse, i0, i1) -> list:
    """Chaque niveau, du premier au dernier contact (prolongé d'un quart), plus épais s'il est souvent touché."""
    artistes = []
    for niveau in analyse.niveaux:
        etendue = niveau.fin - niveau.debut
        fin = niveau.fin + max(etendue // 4, 10)
        if fin < i0 or niveau.debut > i1:
            continue
        cle = {"support": "support", "résistance": "resistance"}.get(niveau.role, "les_deux")
        contacts = len(niveau.touches)
        artistes += ax.plot([niveau.debut, fin], [niveau.prix, niveau.prix], color=COULEURS[cle],
                            lw=0.8 + 0.25 * min(contacts - 2, 4), alpha=min(0.75, 0.3 + 0.1 * contacts),
                            ls="-", zorder=2, solid_capstyle="butt")
        artistes += ax.plot([t for t, _, _ in niveau.touches], [niveau.prix] * contacts, ls="none",
                            marker="|", ms=6, color=COULEURS[cle], alpha=0.8, zorder=2)
    return artistes


def figures_visibles(analyse, i0, i1, types=None, statuts=None):
    """Indices des figures qui chevauchent [i0, i1] (début ≤ i1 et fin du suivi ≥ i0)."""
    resultat = []
    for k, f in enumerate(analyse.figures):
        if f.debut > i1:
            break
        bout = f.signal if f.signal is not None else f.fin
        if bout < i0:
            continue
        if types is not None and f.type not in types:
            continue
        if statuts is not None and f.statut not in statuts:
            continue
        resultat.append(k)
    return resultat


# ===========================================================================
# IMAGE COMPLÈTE (ligne de commande)
# ===========================================================================
def image(analyse, chemin, i0=None, i1=None, selection=None, horizon: int = 20,
          pivots: bool = True, niveaux: bool = True, chandeliers: bool = True) -> None:
    """Enregistre un PNG : bougies, figures de la fenêtre, volume."""
    from matplotlib.figure import Figure as FigureMpl

    from . import config

    df = analyse.bougies
    o, h, b, c = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    n = len(c)
    i0 = max(0, n - 400) if i0 is None else max(0, int(i0))
    i1 = n if i1 is None else min(n, int(i1))
    fig = FigureMpl(figsize=(14, 7.5), dpi=110, facecolor=COULEURS["fond"])
    grille = fig.add_gridspec(2, 1, height_ratios=[5, 1], hspace=0.04)
    ax = fig.add_subplot(grille[0])
    ax_vol = fig.add_subplot(grille[1], sharex=ax)
    for a in (ax, ax_vol):
        styliser(a)
    tracer_bougies(ax, o, h, b, c, i0, i1)
    if pivots:
        tracer_pivots(ax, analyse, i0, i1, structure=True)
    if niveaux:
        tracer_niveaux(ax, analyse, i0, i1)
    visibles = figures_visibles(analyse, i0, i1)
    peu = len(visibles) <= 40
    for k in visibles:
        f = analyse.figures[k]
        if f.famille == "Chandeliers" and not chandeliers:
            continue
        tracer_figure(ax, f, c, mise_en_avant=(k == selection), etiquettes=peu, horizon=horizon)
    x, _, _, _, _, paquet = regrouper(o, h, b, c, i0, i1)
    volume = df["Volume"].to_numpy()
    vol = np.add.reduceat(volume[(i0 // paquet) * paquet:i1], np.arange(0, len(x)) * paquet) \
        if len(x) else np.array([])
    ax_vol.bar(x, vol, width=0.7 * paquet, color=COULEURS["pivot"], alpha=0.6)
    bas, haut = b[i0:i1].min(), h[i0:i1].max()
    marge = (haut - bas) * 0.06
    ax.set_ylim(bas - marge, haut + marge)
    ax.set_xlim(i0 - 1, i1 + 1)
    format_dates(ax_vol, df.index, config.minutes(analyse.intervalle) if analyse.intervalle else 60)
    ax.tick_params(labelbottom=False)
    ax.set_title(f"{analyse.symbole} {analyse.intervalle} — {len(visibles)} figures dans la vue",
                 fontsize=10, loc="left")
    ax_vol.set_ylabel("Volume", fontsize=8)
    fig.savefig(chemin, facecolor=COULEURS["fond"], bbox_inches="tight")
