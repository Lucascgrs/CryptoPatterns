"""
Le dessin type de chaque figure, pour la page Catalogue.

Coordonnées sur une grille de 0 à 10. Chaque schéma peut avoir :
  trace       le trajet du prix (ligne brisée)
  lignes      droites (ligne de cou, bords d'un triangle…)
  etiquettes  (x, y, texte)
  cassure     (x, y) : là où la figure se confirme
  zone        (x0, x1, bas, haut) : le range
  rsi         le trajet du RSI, dessiné dans la bande du bas (divergences)
  bougies     [(ouverture, haut, bas, clôture)] : figures de chandeliers
Les figures baissières sont le plus souvent le miroir des haussières.
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Rectangle


def _miroir(schema: dict, etiquettes: dict | None = None) -> dict:
    """La même figure, tête en bas (y → 10 − y)."""
    sortie = {}
    for cle, valeur in schema.items():
        if cle == "trace":
            sortie[cle] = [(x, 10 - y) for x, y in valeur]
        elif cle == "lignes":
            sortie[cle] = [((a, 10 - b), (c, 10 - d)) for (a, b), (c, d) in valeur]
        elif cle == "etiquettes":
            sortie[cle] = [(x, 10 - y, (etiquettes or {}).get(t, t)) for x, y, t in valeur]
        elif cle == "cassure":
            sortie[cle] = (valeur[0], 10 - valeur[1])
        elif cle == "zone":
            x0, x1, bas, haut = valeur
            sortie[cle] = (x0, x1, 10 - haut, 10 - bas)
        else:
            sortie[cle] = valeur
    return sortie


def _tasse() -> dict:
    x = np.linspace(0.5, 7, 40)
    y = 3 + 5 * ((x - 3.75) / 3.25) ** 4
    trace = list(zip(x, y)) + [(7.6, 7.0), (8.2, 7.4), (8.6, 6.9), (9.3, 8.7), (10, 9.6)]
    return {"trace": trace, "lignes": [((0.5, 8), (9.1, 8))],
            "etiquettes": [(0.5, 8, "bord"), (3.75, 3, "fond"), (8.1, 6.6, "anse")], "cassure": (9.05, 8)}


SCHEMAS: dict[str, dict] = {
    "double_sommet": {
        "trace": [(0, 1.5), (2, 7.5), (3.7, 4.5), (5.5, 7.6), (7.5, 3.5), (9.5, 1.8)],
        "lignes": [((1.5, 4.5), (8.5, 4.5))],
        "etiquettes": [(2, 7.5, "S1"), (5.5, 7.6, "S2"), (8.6, 4.5, "cou")], "cassure": (7.0, 4.5)},
    "triple_sommet": {
        "trace": [(0, 1.5), (1.6, 7.5), (3, 4.5), (4.6, 7.6), (6, 4.6), (7.6, 7.5), (9, 3.5), (10, 2)],
        "lignes": [((1.2, 4.5), (9.4, 4.5))],
        "etiquettes": [(1.6, 7.5, "S1"), (4.6, 7.6, "S2"), (7.6, 7.5, "S3")], "cassure": (8.55, 4.5)},
    "tete_epaules": {
        "trace": [(0, 1.5), (1.5, 6), (3, 4.2), (5, 8.5), (7, 4.4), (8.5, 6), (10, 2)],
        "lignes": [((2.3, 4.15), (9.8, 4.5))],
        "etiquettes": [(1.5, 6, "ÉG"), (5, 8.5, "Tête"), (8.5, 6, "ÉD")], "cassure": (9.18, 4.44)},
    "triangle_ascendant": {
        "trace": [(0, 1.5), (1.5, 7.5), (3, 3.5), (4.5, 7.5), (6, 5), (7.3, 7.5), (8.2, 6.3), (9.2, 8.6),
                  (10, 9.6)],
        "lignes": [((1.5, 7.5), (9, 7.5)), ((3, 3.5), (8.6, 6.9))], "cassure": (8.75, 7.5)},
    "triangle_symetrique": {
        "trace": [(0, 5), (1, 8.5), (2.5, 2), (4, 7.3), (5.5, 3.3), (7, 6.2), (8.2, 4.5), (9.3, 7.1),
                  (10, 8.4)],
        "lignes": [((1, 8.5), (9.2, 5.4)), ((2.5, 2), (9.2, 4.9))], "cassure": (8.75, 5.6)},
    "biseau_ascendant": {
        "trace": [(0, 1), (1.5, 4.5), (3, 3), (4.5, 6.2), (6, 5.2), (7.3, 7.3), (8.3, 6.6), (9.2, 5),
                  (10, 3.5)],
        "lignes": [((1.5, 4.5), (8.8, 7.9)), ((3, 3), (8.8, 7.1))], "cassure": (8.7, 6.1)},
    "elargissement": {
        "trace": [(0, 5), (1.5, 6.2), (2.8, 4), (4.3, 7.2), (5.8, 3), (7.3, 8.2), (8.8, 2), (10, 0.8)],
        "lignes": [((1.5, 6.2), (8, 8.7)), ((2.8, 4), (9.3, 1.6))], "cassure": (8.6, 2.2)},
    "canal_ascendant": {
        "trace": [(0, 1), (1.5, 4), (2.5, 2.5), (4, 5.5), (5, 4), (6.5, 7), (7.5, 5.5), (8.6, 7.6),
                  (9.3, 9.2), (10, 9.9)],
        "lignes": [((1.5, 4), (9.2, 8.6)), ((0, 1), (9.2, 6.5))], "cassure": (9.1, 8.6)},
    "rectangle": {
        "trace": [(0, 2), (1.2, 7), (2.5, 3.5), (4, 7), (5.5, 3.5), (7, 7), (8.3, 3.5), (9.6, 7.3),
                  (10, 8.6)],
        "lignes": [((1.2, 7), (9.6, 7)), ((2.5, 3.5), (9.6, 3.5))], "cassure": (9.5, 7)},
    "range": {
        "trace": [(0, 1), (1, 4.5), (1.8, 5.8), (2.6, 4.3), (3.4, 5.6), (4.2, 4.4), (5, 5.7), (5.8, 4.2),
                  (6.6, 5.5), (7.4, 4.4), (8.2, 5.8), (9, 5.2), (9.6, 7), (10, 8.5)],
        "zone": (1, 9.1, 4.1, 5.9), "cassure": (9.25, 5.9)},
    "drapeau_haussier": {
        "trace": [(0, 1), (2.5, 7.5), (3.1, 6.6), (3.8, 7.1), (4.5, 6.1), (5.2, 6.6), (5.9, 5.7),
                  (7, 8.2), (8.5, 9.8)],
        "lignes": [((2.5, 7.5), (6.5, 6.2)), ((3.1, 6.6), (6.5, 5.5))],
        "etiquettes": [(0.6, 2.5, "mât")], "cassure": (6.3, 6.6)},
    "fanion_haussier": {
        "trace": [(0, 1), (2.5, 7.5), (3.1, 6.2), (3.7, 7.2), (4.3, 6.5), (4.9, 7.0), (5.4, 6.7),
                  (6.5, 8.6), (8, 9.8)],
        "lignes": [((2.5, 7.5), (5.8, 6.9)), ((3.1, 6.2), (5.8, 6.85))],
        "etiquettes": [(0.6, 2.5, "mât")], "cassure": (5.75, 7.0)},
    "tasse_anse": _tasse(),
    "gartley_haussier": {
        "trace": [(0, 1), (2, 8), (3.5, 3.67), (5, 6.5), (7, 2.5), (8.5, 5.5)],
        "lignes": [((0, 1), (3.5, 3.67)), ((3.5, 3.67), (7, 2.5)), ((2, 8), (5, 6.5))],
        "etiquettes": [(0, 1, "X"), (2, 8, "A"), (3.5, 3.67, "B"), (5, 6.5, "C"), (7, 2.5, "D")],
        "cassure": (7, 2.5)},
    "chauve_souris_haussiere": {
        "trace": [(0, 1), (2, 8), (3.5, 5.2), (5, 7), (7.2, 1.8), (8.5, 5)],
        "lignes": [((0, 1), (3.5, 5.2)), ((3.5, 5.2), (7.2, 1.8)), ((2, 8), (5, 7))],
        "etiquettes": [(0, 1, "X"), (2, 8, "A"), (3.5, 5.2, "B"), (5, 7, "C"), (7.2, 1.8, "D")],
        "cassure": (7.2, 1.8)},
    "papillon_haussier": {
        "trace": [(0, 2.5), (2, 8), (3.5, 3.7), (5, 6.5), (7.2, 1.0), (8.5, 4.5)],
        "lignes": [((0, 2.5), (3.5, 3.7)), ((3.5, 3.7), (7.2, 1.0)), ((2, 8), (5, 6.5))],
        "etiquettes": [(0, 2.5, "X"), (2, 8, "A"), (3.5, 3.7, "B"), (5, 6.5, "C"), (7.2, 1.0, "D")],
        "cassure": (7.2, 1.0)},
    "crabe_haussier": {
        "trace": [(0, 3.5), (2, 8), (3.5, 5.2), (5, 7), (7.5, 0.7), (8.7, 4)],
        "lignes": [((0, 3.5), (3.5, 5.2)), ((3.5, 5.2), (7.5, 0.7)), ((2, 8), (5, 7))],
        "etiquettes": [(0, 3.5, "X"), (2, 8, "A"), (3.5, 5.2, "B"), (5, 7, "C"), (7.5, 0.7, "D")],
        "cassure": (7.5, 0.7)},
    "abcd_haussier": {
        "trace": [(0.5, 8), (3, 4), (4.8, 6.8), (7.3, 2.8), (8.8, 5.5)],
        "lignes": [((0.5, 8), (3, 4)), ((4.8, 6.8), (7.3, 2.8))],
        "etiquettes": [(0.5, 8, "A"), (3, 4, "B"), (4.8, 6.8, "C"), (7.3, 2.8, "D")], "cassure": (7.3, 2.8)},
    "divergence_haussiere": {
        "trace": [(0, 9.5), (2.5, 5.5), (4, 7.6), (6.5, 4.6), (8, 7.2), (9.5, 8.6)],
        "lignes": [((2.5, 5.5), (6.5, 4.6))],
        "rsi": [(0, 2.6), (2.5, 0.4), (4, 1.8), (6.5, 1.0), (8, 2.2), (9.5, 2.6)],
        "lignes_rsi": [((2.5, 0.4), (6.5, 1.0))], "cassure": (7.0, 5.8)},
    "divergence_baissiere": {
        "trace": [(0, 4.5), (2.5, 8.2), (4, 6), (6.5, 9.2), (8, 6.2), (9.5, 5)],
        "lignes": [((2.5, 8.2), (6.5, 9.2))],
        "rsi": [(0, 0.6), (2.5, 2.6), (4, 1.3), (6.5, 2.0), (8, 0.9), (9.5, 0.5)],
        "lignes_rsi": [((2.5, 2.6), (6.5, 2.0))], "cassure": (7.0, 8.0)},
}

_CREUX = {"S1": "C1", "S2": "C2", "S3": "C3", "ÉG": "ÉG", "Tête": "Tête", "ÉD": "ÉD", "bord": "bord",
          "fond": "sommet", "anse": "anse"}
for _haut, _bas in (("double_sommet", "double_creux"), ("triple_sommet", "triple_creux"),
                    ("tete_epaules", "tete_epaules_inverse"), ("triangle_ascendant", "triangle_descendant"),
                    ("biseau_ascendant", "biseau_descendant"), ("canal_ascendant", "canal_descendant"),
                    ("drapeau_haussier", "drapeau_baissier"), ("fanion_haussier", "fanion_baissier"),
                    ("tasse_anse", "tasse_inversee"), ("gartley_haussier", "gartley_baissier"),
                    ("chauve_souris_haussiere", "chauve_souris_baissiere"),
                    ("papillon_haussier", "papillon_baissier"), ("crabe_haussier", "crabe_baissier"),
                    ("abcd_haussier", "abcd_baissier")):
    SCHEMAS[_bas] = _miroir(SCHEMAS[_haut], _CREUX)

# ---------------------------------------------------------------- chandeliers
_BAISSE = [(8.6, 8.9, 7.9, 8.1), (8.1, 8.3, 7.2, 7.4), (7.4, 7.6, 6.5, 6.7), (6.7, 6.9, 5.8, 6.0)]
_HAUSSE = [(1.4, 2.1, 1.1, 1.9), (1.9, 2.8, 1.7, 2.6), (2.6, 3.5, 2.4, 3.3), (3.3, 4.2, 3.1, 4.0)]
_BOUGIES = {
    "doji_apres_hausse": (_HAUSSE, [(4.0, 4.8, 3.4, 4.02)]),
    "doji_apres_baisse": (_BAISSE, [(6.0, 6.6, 5.2, 5.98)]),
    "marteau": (_BAISSE, [(5.7, 5.95, 4.0, 5.9)]),
    "pendu": (_HAUSSE, [(4.25, 4.45, 2.8, 4.4)]),
    "marteau_inverse": (_BAISSE, [(5.85, 7.6, 5.75, 6.0)]),
    "etoile_filante": (_HAUSSE, [(4.2, 5.9, 3.98, 4.05)]),
    "avalement_haussier": (_BAISSE, [(6.0, 6.1, 5.4, 5.5), (5.4, 6.6, 5.3, 6.5)]),
    "avalement_baissier": (_HAUSSE, [(4.0, 4.6, 3.9, 4.5), (4.6, 4.7, 3.6, 3.7)]),
    "harami_haussier": (_BAISSE, [(6.0, 6.1, 4.2, 4.3), (4.6, 5.2, 4.5, 5.0)]),
    "harami_baissier": (_HAUSSE, [(4.0, 5.8, 3.9, 5.7), (5.4, 5.5, 4.8, 4.9)]),
    "etoile_du_matin": (_BAISSE, [(6.0, 6.1, 4.6, 4.7), (4.5, 4.8, 4.1, 4.55), (4.6, 6.0, 4.5, 5.8)]),
    "etoile_du_soir": (_HAUSSE, [(4.0, 5.5, 3.9, 5.4), (5.55, 5.9, 5.3, 5.6), (5.5, 5.6, 4.0, 4.2)]),
    "trois_soldats": (_BAISSE[2:], [(5.0, 6.0, 4.9, 5.9), (5.6, 6.9, 5.5, 6.8), (6.5, 7.8, 6.4, 7.7)]),
    "trois_corbeaux": (_HAUSSE[2:], [(5.0, 5.1, 4.0, 4.1), (4.4, 4.5, 3.2, 3.3), (3.6, 3.7, 2.4, 2.5)]),
    "penetrante": (_BAISSE, [(6.0, 6.1, 4.4, 4.5), (4.4, 5.6, 4.3, 5.5)]),
    "nuage_noir": (_HAUSSE, [(4.0, 5.6, 3.9, 5.5), (5.6, 5.7, 4.4, 4.5)]),
    "pince_haut": (_HAUSSE, [(4.0, 5.2, 3.9, 5.0), (5.0, 5.2, 4.1, 4.2)]),
    "pince_bas": (_BAISSE, [(6.0, 6.1, 4.8, 5.0), (5.0, 6.0, 4.8, 5.9)]),
    "marubozu_haussier": ([(4.8, 5.3, 4.5, 5.0), (5.0, 5.4, 4.7, 4.9)], [(4.9, 8.05, 4.85, 8.0)]),
    "marubozu_baissier": ([(5.2, 5.5, 4.7, 5.0), (5.0, 5.3, 4.6, 5.1)], [(5.1, 5.15, 1.95, 2.0)]),
}
for _type, (_contexte, _figure) in _BOUGIES.items():
    SCHEMAS[_type] = {"bougies": _contexte + _figure, "figure_depuis": len(_contexte)}


def dessiner(ax, type_: str, couleur: str, couleurs_bougies=("#3f9e83", "#b4554d")) -> None:
    """Dessine le schéma de `type_` sur un axe vide."""
    s = SCHEMAS.get(type_)
    if s is None:
        return
    if "bougies" in s:
        for k, (o, h, b, c) in enumerate(s["bougies"]):
            teinte = couleurs_bougies[0] if c >= o else couleurs_bougies[1]
            ax.plot([k, k], [b, h], color=teinte, lw=1.4, zorder=2)
            ax.add_patch(Rectangle(
                (k - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.04), color=teinte, zorder=3))
        debut = s["figure_depuis"]
        fin = len(s["bougies"]) - 1
        bas = min(b for _, _, b, _ in s["bougies"][debut:])
        haut = max(h for _, h, _, _ in s["bougies"][debut:])
        ax.add_patch(Rectangle(
            (debut - 0.5, bas - 0.2), fin - debut + 1, haut - bas + 0.4, fill=False, ec=couleur, lw=1.4,
            ls="--", zorder=4))
        ax.set_xlim(-1, len(s["bougies"]) + 0.5)
        ax.set_ylim(0.5, 9.5)
        return
    if "zone" in s:
        x0, x1, bas, haut = s["zone"]
        ax.add_patch(Rectangle((x0, bas), x1 - x0, haut - bas,
                                                               color=couleur, alpha=0.15, zorder=1))
    xs, ys = zip(*s["trace"])
    ax.plot(xs, ys, color="#e6e6e6", lw=1.8, zorder=3)
    for (a, b), (c, d) in s.get("lignes", []):
        ax.plot([a, c], [b, d], color=couleur, lw=1.6, ls="--", zorder=2)
    for x, y, texte in s.get("etiquettes", []):
        # Sous un creux du trajet, au-dessus d'un sommet.
        voisins = [py for px, py in s["trace"] if abs(px - x) < 2.5 and px != x]
        creux = bool(voisins) and all(py > y for py in voisins)
        ax.text(x, y - 0.35 if creux else y + 0.35, texte, color=couleur, fontsize=10, ha="center",
                va="top" if creux else "bottom", zorder=4)
    if "cassure" in s:
        ax.plot(*s["cassure"], marker="o", ms=9, color=couleur, mec="white", zorder=5)
    if "rsi" in s:
        ax.axhline(3.3, color="#555555", lw=0.8)
        xs, ys = zip(*s["rsi"])
        ax.plot(xs, ys, color="#c39bd3", lw=1.5, zorder=3)
        for (a, b), (c, d) in s.get("lignes_rsi", []):
            ax.plot([a, c], [b, d], color=couleur, lw=1.6, ls="--", zorder=2)
        ax.text(0, 3.0, "RSI", color="#c39bd3", fontsize=9, va="top")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.2, 10.8)
