"""
Les figures chartistes, reconnues à partir des pivots du zigzag.

  - Retournements : double et triple sommet/creux, tête-épaules (et inversée).
  - Figures à deux droites : triangles, biseaux, élargissement, canaux,
    rectangle. Une droite passe par les sommets, l'autre par les creux ; leur
    pente et leur écart décident du nom.
  - Tasse avec anse (et inversée).

Toutes suivent le même cycle de vie :

  1. la figure est **connue** à la confirmation de son dernier pivot ;
  2. on attend la **cassure** : la première clôture au-delà du niveau qui la
     confirme (ligne de cou, droite du triangle…) ;
  3. si le prix franchit d'abord le niveau d'**invalidation**, la figure est
     invalidée ; s'il ne se passe rien dans le délai, elle reste « sans cassure ».

La bougie de signal est la plus tardive des deux : cassure et connaissance de la
figure. On n'agit jamais sur une information qu'on n'avait pas encore.

Les figures en miroir (tête-épaules inversée, tasse inversée) sont cherchées
avec le même code, sur le graphique retourné (prix changés de signe).
"""

from __future__ import annotations

import numpy as np

from .figures import CONFIRMEE, EN_FORMATION, INVALIDEE, SANS_CASSURE, Figure
from .pivots import SOMMET, Pivots

ATTENTE_MIN = 10               # délai minimal (en bougies) laissé à la cassure


class Marche:
    """Les tableaux d'un historique, pour ne pas les repasser partout."""

    def __init__(self, ouverture, haut, bas, cloture, atr):
        self.o = ouverture
        self.h = haut
        self.b = bas
        self.c = cloture
        self.atr = atr
        self.n = len(cloture)

    def retourne(self) -> "Marche":
        """Le graphique la tête en bas : les sommets deviennent des creux."""
        return Marche(-self.o, -self.b, -self.h, -self.c, self.atr)


def retourner_pivots(pv: Pivots) -> Pivots:
    return Pivots(pv.i, -pv.prix, (-pv.type).astype(np.int8), pv.confirme)


def retourner_figure(f: Figure, type_: str) -> Figure:
    """Remet à l'endroit une figure trouvée sur le graphique retourné."""
    f.type = type_
    f.points = [(i, -p) for i, p in f.points]
    f.lignes = [(i0, -p0, i1, -p1) for i0, p0, i1, p1 in f.lignes]
    f.etiquettes = [(i, -p, t) for i, p, t in f.etiquettes]
    if f.zone is not None:
        i0, i1, bas, haut = f.zone
        f.zone = (i0, i1, -haut, -bas)
    f.niveau, f.objectif, f.invalidation = -f.niveau, -f.objectif, -f.invalidation
    f.sens_cassure = -f.sens_cassure
    return f


# ===========================================================================
# CASSURE ET INVALIDATION
# ===========================================================================
def _suivre(m: Marche, figure: Figure, depart: int, limite: int,
            haut_ligne, bas_ligne, sens_attendu: int, inval_haut=np.inf, inval_bas=-np.inf):
    """
    Cherche, de `depart` à `limite` inclus, la première clôture au-dessus de
    `haut_ligne(i)` ou au-dessous de `bas_ligne(i)` (fonctions vectorisées, ou
    None si ce côté ne compte pas).

    `sens_attendu` : +1 seule la sortie par le haut confirme, −1 par le bas,
    0 les deux. Une sortie du mauvais côté invalide la figure, tout comme un
    plus haut au-dessus de `inval_haut` ou un plus bas sous `inval_bas`.
    Remplit statut, signal et sens_cassure de la figure.
    """
    fin = min(limite, m.n - 1)
    if depart > fin:
        figure.statut = EN_FORMATION
        return
    i = np.arange(depart, fin + 1)
    c = m.c[depart:fin + 1]
    vers_haut = c > haut_ligne(i) if haut_ligne is not None else np.zeros(len(i), bool)
    vers_bas = c < bas_ligne(i) if bas_ligne is not None else np.zeros(len(i), bool)
    rate = (m.h[depart:fin + 1] > inval_haut) | (m.b[depart:fin + 1] < inval_bas)
    if sens_attendu > 0:
        bonne, mauvaise = vers_haut, vers_bas | rate
    elif sens_attendu < 0:
        bonne, mauvaise = vers_bas, vers_haut | rate
    else:
        bonne, mauvaise = vers_haut | vers_bas, rate
    k_bonne = int(np.argmax(bonne)) if bonne.any() else None
    k_mauvaise = int(np.argmax(mauvaise)) if mauvaise.any() else None
    if k_mauvaise is not None and (k_bonne is None or k_mauvaise < k_bonne):
        figure.statut = INVALIDEE
        figure.details["fin du suivi"] = depart + k_mauvaise
        return
    if k_bonne is None:
        figure.statut = EN_FORMATION if limite >= m.n - 1 else SANS_CASSURE
        figure.details["fin du suivi"] = fin
        return
    cassure = depart + k_bonne
    figure.sens_cassure = 1 if vers_haut[k_bonne] else -1
    figure.statut = CONFIRMEE
    figure.signal = max(cassure, figure.detection)
    figure.details["cassure"] = cassure
    figure.details["fin du suivi"] = cassure


def _horizontale(niveau: float):
    return lambda i: np.full(len(i), niveau)


def _droite(i0, p0, i1, p1):
    pente = (p1 - p0) / (i1 - i0) if i1 != i0 else 0.0
    return lambda i: p0 + pente * (np.asarray(i, dtype=float) - i0)


# ===========================================================================
# DOUBLE ET TRIPLE SOMMET / CREUX
# ===========================================================================
def doubles_et_triples(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """
    Double sommet (S C S), double creux (C S C), triple sommet (S C S C S) et
    triple creux. `tolerance` : écart admis entre les extrêmes, en fraction de
    la hauteur de la figure.

    Un double inclus dans un triple n'est repris que s'il s'était confirmé : en
    temps réel, on l'aurait vu se déclencher avant que le triple n'existe, et
    l'effacer après coup embellirait les statistiques.
    """
    figures, pris = [], set()
    n = len(pv)
    for taille, type_s, type_c in ((5, "triple_sommet", "triple_creux"),
                                   (3, "double_sommet", "double_creux")):
        for k in range(1, n - taille + 1):
            ks = list(range(k, k + taille))
            dans_un_triple = any(j in pris for j in ks[::2])
            sorte = int(pv.type[k])
            s = 1 if sorte == SOMMET else -1
            extremes = s * pv.prix[ks[::2]]           # « à l'endroit » : les extrêmes sont des sommets
            milieux = s * pv.prix[ks[1::2]]
            cou = milieux.min()
            hauteur = extremes.min() - cou
            if hauteur <= 0 or extremes.max() - extremes.min() > tolerance * hauteur:
                continue
            if s * pv.prix[k - 1] >= cou:             # le prix montait vers le premier sommet
                continue
            provisoire = pv.confirme[ks[-1]] < 0
            premier, dernier = int(pv.i[k]), int(pv.i[ks[-1]])
            f = Figure(
                type=type_s if s == 1 else type_c, debut=premier, fin=dernier,
                detection=m.n - 1 if provisoire else int(pv.confirme[ks[-1]]),
                points=[(int(pv.i[j]), float(pv.prix[j])) for j in [k - 1] + ks],
                niveau=float(s * cou), objectif=float(s * (cou - hauteur)),
                invalidation=float(s * extremes.max()))
            f.details.update({"hauteur": float(hauteur),
                              "écart des extrêmes (% hauteur)": float(
                                  100 * (extremes.max() - extremes.min()) / hauteur)})
            noms = ("S1", "S2", "S3") if s == 1 else ("C1", "C2", "C3")
            f.etiquettes = [(int(pv.i[j]), float(pv.prix[j]), noms[e]) for e, j in enumerate(ks[::2])]
            if provisoire:
                f.statut = EN_FORMATION
                f.details["dernier pivot"] = "pas encore confirmé"
                bout = m.n - 1
            else:
                limite = dernier + max(dernier - premier, ATTENTE_MIN)
                if s == 1:
                    _suivre(m, f, dernier + 1, limite, None, _horizontale(f.niveau), -1,
                            inval_haut=f.invalidation)
                else:
                    _suivre(m, f, dernier + 1, limite, _horizontale(f.niveau), None, 1,
                            inval_bas=f.invalidation)
                bout = int(f.details["fin du suivi"]) if "fin du suivi" in f.details else m.n - 1
            if dans_un_triple and f.statut != CONFIRMEE:
                continue
            f.lignes = [(premier, f.niveau, bout, f.niveau)]
            f.etiquettes.append((premier, f.niveau, "cou"))
            figures.append(f)
            if taille == 5:
                pris.update(ks)
    return figures


# ===========================================================================
# TÊTE-ÉPAULES
# ===========================================================================
def tete_epaules(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """Tête-épaules sur le graphique, puis tête-épaules inversée sur le graphique retourné."""
    figures = _tete_epaules(m, pv, tolerance)
    for f in _tete_epaules(m.retourne(), retourner_pivots(pv), tolerance):
        figures.append(retourner_figure(f, "tete_epaules_inverse"))
    return figures


def _tete_epaules(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """
    Six pivots : creux d'avant, épaule gauche, creux, tête, creux, épaule droite.
    La ligne de cou relie les deux creux qui encadrent la tête.
    """
    figures = []
    for k in range(0, len(pv) - 5):
        if pv.type[k + 1] != SOMMET:
            continue
        ks = list(range(k, k + 6))
        avant, g, c1, tete, c2, d = pv.prix[ks]
        x = pv.i[ks].astype(float)
        cou = _droite(x[2], c1, x[4], c2)
        hauteur = tete - float(cou(x[3]))
        if hauteur <= 0:
            continue
        if tete - max(g, d) < 0.1 * hauteur:                      # la tête dépasse les épaules
            continue
        if abs(g - d) > 2 * tolerance * hauteur:                  # épaules à peu près égales
            continue
        if abs(c1 - c2) > 0.5 * hauteur:                          # ligne de cou peu penchée
            continue
        if g <= cou(x[1]) or d <= cou(x[5]):                      # épaules au-dessus du cou
            continue
        if not (1 / 3 <= (x[5] - x[3]) / (x[3] - x[1]) <= 3):     # épaules de durées comparables
            continue
        if avant >= min(c1, c2):                                  # le prix montait avant
            continue
        provisoire = pv.confirme[k + 5] < 0
        debut, fin = int(x[1]), int(x[5])
        f = Figure(type="tete_epaules", debut=debut, fin=fin,
                   detection=m.n - 1 if provisoire else int(pv.confirme[k + 5]),
                   points=[(int(a), float(b)) for a, b in zip(x, pv.prix[ks])],
                   invalidation=float(d))
        f.details.update({"hauteur": float(hauteur)})
        f.etiquettes = [(debut, float(g), "ÉG"), (int(x[3]), float(tete), "Tête"), (fin, float(d), "ÉD")]
        if provisoire:
            f.statut = EN_FORMATION
            f.details["dernier pivot"] = "pas encore confirmé"
            bout = m.n - 1
        else:
            limite = fin + max((fin - debut) // 2, ATTENTE_MIN)
            _suivre(m, f, fin + 1, limite, None, cou, -1, inval_haut=float(d))
            bout = int(f.details.get("fin du suivi", m.n - 1))
        f.niveau = float(cou(bout))
        f.objectif = f.niveau - hauteur
        f.lignes = [(debut, float(cou(debut)), bout, f.niveau)]
        figures.append(f)
    return figures


# ===========================================================================
# FIGURES À DEUX DROITES
# ===========================================================================
PLAT = 0.25          # une droite est « plate » si elle bouge de moins de 25 % de la hauteur
RESSERREMENT = 0.30  # triangle, biseau : l'écart se réduit d'au moins 30 %


def _ajuster(x, y):
    """
    Droite des moindres carrés : (pente, ordonnée à l'origine). Calcul direct
    sur 2 à 4 points, bien plus rapide que np.polyfit appelé des milliers de fois.
    """
    x, y = x.tolist(), y.tolist()
    origine = x[0]
    x = [v - origine for v in x]                 # centré : pas de perte de précision
    n = len(x)
    sx, sy = sum(x), sum(y)
    sxx = sum(v * v for v in x)
    sxy = sum(a * b for a, b in zip(x, y))
    denominateur = n * sxx - sx * sx
    pente = (n * sxy - sx * sy) / denominateur if denominateur else 0.0
    return pente, (sy - pente * sx) / n - pente * origine


def _classer(pente_h, pente_b, h0, h1, duree):
    """Nom de la figure d'après les deux pentes et l'écart au début (h0) et à la fin (h1)."""
    du, dl = pente_h * duree / h0, pente_b * duree / h0         # déplacement, en hauteurs
    plat_h, plat_b = abs(du) <= PLAT, abs(dl) <= PLAT
    if h1 <= h0 * (1 - RESSERREMENT):
        if plat_h and dl > PLAT:
            return "triangle_ascendant"
        if plat_b and du < -PLAT:
            return "triangle_descendant"
        if du < -PLAT and dl > PLAT:
            return "triangle_symetrique"
        if du > PLAT and dl > du:
            return "biseau_ascendant"
        if dl < -PLAT and du < dl:
            return "biseau_descendant"
        return None
    if h1 >= h0 * (1 + RESSERREMENT):
        return "elargissement" if du > PLAT and dl < -PLAT else None
    if plat_h and plat_b:
        return "rectangle"
    if du > PLAT and dl > PLAT:
        return "canal_ascendant"
    if du < -PLAT and dl < -PLAT:
        return "canal_descendant"
    return None


PIVOTS_MIN, PIVOTS_MAX = 5, 8


def deux_droites(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """
    Fenêtres de 5 à 8 pivots confirmés consécutifs, comme on les verrait se
    former en direct : dès que 5 pivots dessinent une figure, elle existe. Si
    elle n'a ni cassé ni échoué quand le pivot suivant est confirmé et que ce
    pivot la prolonge, elle grandit d'un pivot (jusqu'à 8). Sinon elle est
    gardée telle quelle. On repart ensuite de son dernier pivot : les figures
    ne se chevauchent pas.

    Prendre d'emblée la plus longue fenêtre serait plus simple, mais une petite
    figure qui a cassé (à tort) puis s'est fondue dans une plus grande
    disparaîtrait des statistiques, alors qu'en direct on l'aurait vue.
    """
    pv = pv.confirmes()
    figures = []
    k, n = 0, len(pv)
    while k <= n - PIVOTS_MIN:
        f, taille = None, PIVOTS_MIN
        while f is None and taille <= PIVOTS_MAX and k + taille <= n:
            f = _fenetre(m, pv, k, taille, tolerance)
            if f is None:
                taille += 1
        if f is None:
            k += 1
            continue
        while taille < PIVOTS_MAX and k + taille < n:
            pivot_suivant = int(pv.confirme[k + taille])
            if f.statut != EN_FORMATION and int(f.details.get("fin du suivi", m.n)) <= pivot_suivant:
                break                               # la figure a cassé ou échoué avant
            plus_grande = _fenetre(m, pv, k, taille + 1, tolerance)
            if plus_grande is None:
                break
            f, taille = plus_grande, taille + 1
        figures.append(f)
        k += taille - 1
    return figures


def _fenetre(m: Marche, pv: Pivots, k: int, taille: int, tolerance: float) -> Figure | None:
    ks = np.arange(k, k + taille)
    xi = pv.i[ks].astype(float)
    py = pv.prix[ks]
    sommets = pv.type[ks] == SOMMET
    if sommets.sum() < 2 or (~sommets).sum() < 2:
        return None
    pente_h, ord_h = _ajuster(xi[sommets], py[sommets])
    pente_b, ord_b = _ajuster(xi[~sommets], py[~sommets])
    x0, x1 = xi[0], xi[-1]
    duree = x1 - x0
    if duree < 4:
        return None

    def haut(i):
        return ord_h + pente_h * np.asarray(i, dtype=float)

    def bas(i):
        return ord_b + pente_b * np.asarray(i, dtype=float)

    h0, h1 = haut(x0) - bas(x0), haut(x1) - bas(x1)
    if h0 <= 0 or h1 <= 0:
        return None
    # Chaque pivot touche sa droite, à la tolérance près.
    marge = tolerance * max(h0, h1)
    ecart = np.where(sommets, np.abs(py - haut(xi)), np.abs(py - bas(xi)))
    if ecart.max() > marge:
        return None
    # Aucune clôture nettement hors des droites entre le premier et le dernier pivot.
    i = np.arange(int(x0), int(x1) + 1)
    c = m.c[int(x0):int(x1) + 1]
    if (c > haut(i) + marge).any() or (c < bas(i) - marge).any():
        return None
    type_ = _classer(pente_h, pente_b, h0, h1, duree)
    if type_ is None:
        return None

    debut, fin = int(x0), int(x1)
    f = Figure(type=type_, debut=debut, fin=fin, detection=int(pv.confirme[ks[-1]]),
               points=[(int(a), float(b)) for a, b in zip(xi, py)])
    f.details.update({"hauteur": float(h0), "pivots": int(taille)})
    limite = fin + max(int(duree), ATTENTE_MIN)
    if pente_h != pente_b:
        croisement = (ord_b - ord_h) / (pente_h - pente_b)        # pointe du triangle
        if croisement > fin:
            limite = min(limite, int(croisement))
    sens = f.modele.sens
    _suivre(m, f, fin + 1, limite, haut, bas, sens)
    bout = int(f.details.get("fin du suivi", m.n - 1))
    f.lignes = [(debut, float(haut(debut)), bout, float(haut(bout))),
                (debut, float(bas(debut)), bout, float(bas(bout)))]
    if f.statut == CONFIRMEE:
        cassure = int(f.details["cassure"])
        f.objectif = float(m.c[cassure]) + f.sens_cassure * h0
        f.niveau = float(haut(cassure)) if f.sens_cassure > 0 else float(bas(cassure))
        f.invalidation = float(bas(cassure)) if f.sens_cassure > 0 else float(haut(cassure))
    else:
        cote = sens if sens else 1
        f.niveau = float(haut(bout)) if cote > 0 else float(bas(bout))
        f.invalidation = float(bas(bout)) if cote > 0 else float(haut(bout))
        f.objectif = f.niveau + cote * h0
    return f


# ===========================================================================
# TASSE AVEC ANSE
# ===========================================================================
def tasses(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """Tasse avec anse, puis tasse inversée sur le graphique retourné."""
    figures = _tasses(m, pv, tolerance)
    for f in _tasses(m.retourne(), retourner_pivots(pv), tolerance):
        figures.append(retourner_figure(f, "tasse_inversee"))
    return figures


def _tasses(m: Marche, pv: Pivots, tolerance: float) -> list[Figure]:
    """
    Tasse : sommet (bord gauche) → creux (fond) → première bougie qui revient au
    niveau du bord (bord droit). Fond arrondi exigé. L'anse est le petit repli
    qui suit ; la cassure est la première clôture au-dessus du plus haut du bord.
    """
    figures = []
    pc = pv.confirmes()
    precedente = None               # (cassure, signal) de la dernière tasse confirmée
    for k in range(len(pc) - 1):
        if pc.type[k] != SOMMET:
            continue
        g, fond = int(pc.i[k]), int(pc.i[k + 1])
        bord, creux = float(pc.prix[k]), float(pc.prix[k + 1])
        profondeur = bord - creux
        retour = m.h[fond + 1:] >= bord - tolerance * profondeur
        if not retour.any():
            continue
        droite = fond + 1 + int(np.argmax(retour))
        largeur = droite - g
        if largeur < 10:
            continue
        # Fond arrondi : au moins 40 % des clôtures dans le tiers bas.
        if np.mean(m.c[g:droite + 1] <= creux + profondeur / 3) < 0.40:
            continue
        # Anse : au moins 3 bougies sous le bord, repli de moins de la moitié de
        # la profondeur, au plus la moitié de la durée de la tasse.
        plafond = max(bord, float(m.h[droite]))
        plancher = plafond - 0.5 * profondeur
        limite = droite + max(largeur // 2, 3)
        cassure, bas_anse, rate = None, float(m.b[droite]), False
        for j in range(droite + 1, min(limite, m.n - 1) + 1):
            if m.c[j] > plafond:
                if j - droite >= 3:
                    cassure = j
                else:
                    rate = True                     # repart sans anse
                break
            if m.b[j] < plancher:
                rate = True
                break
            bas_anse = min(bas_anse, float(m.b[j]))
            plafond = max(plafond, float(m.h[j]))
        if rate or (cassure is None and limite < m.n - 1):
            continue
        detection = max(int(pc.confirme[k + 1]), droite)
        # Pas de tasse dans une tasse déjà confirmée au moment où celle-ci apparaît.
        # (Juger sur une cassure postérieure serait regarder le futur.)
        if precedente is not None and g < precedente[0] and precedente[1] <= detection:
            continue
        pas = max(1, largeur // 40)
        contour = [(j, float(m.c[j])) for j in range(g, droite, pas)] + [(droite, float(m.c[droite]))]
        f = Figure(type="tasse_anse", debut=g, fin=droite, detection=detection, points=contour,
                   niveau=float(plafond), invalidation=bas_anse,
                   objectif=float(plafond + profondeur))
        f.details.update({"profondeur": float(profondeur)})
        f.etiquettes = [(g, bord, "bord"), (fond, creux, "fond")]
        if cassure is not None:
            f.statut = CONFIRMEE
            f.sens_cassure = 1
            f.signal = max(cassure, detection)
            f.details["cassure"] = cassure
            bout = cassure
        else:
            f.statut = EN_FORMATION
            bout = m.n - 1
        f.lignes = [(g, float(plafond), bout, float(plafond))]
        if bout > droite:
            f.zone = (droite, bout, bas_anse, float(plafond))
        figures.append(f)
        if cassure is not None:
            precedente = (cassure, f.signal)
    return figures
