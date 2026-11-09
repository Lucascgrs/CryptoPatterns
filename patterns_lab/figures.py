"""
Le catalogue des figures, et la fiche d'une figure repérée.

Chaque type de figure a un sens attendu :
  +1  haussier : on s'attend à une hausse après la confirmation ;
  −1  baissier ;
   0  neutre : la direction est celle de la cassure (triangle symétrique,
      rectangle, canal, range…).

Une figure repérée (`Figure`) garde tout ce qu'il faut pour la dessiner (points,
droites, zone, étiquettes) et pour la juger après coup : la bougie où elle est
connue (`detection`), celle où elle est confirmée (`signal`), l'objectif et le
niveau d'invalidation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Statuts
CONFIRMEE = "confirmée"
EN_FORMATION = "en formation"
INVALIDEE = "invalidée"
SANS_CASSURE = "sans cassure"

FAMILLES = ["Retournements", "Triangles et biseaux", "Canaux et ranges", "Continuations",
            "Harmoniques", "Divergences", "Chandeliers"]


@dataclass(frozen=True)
class Modele:
    nom: str
    famille: str
    sens: int
    court: str              # abréviation sur le graphique
    description: str        # ce que c'est, ce qu'on en attend
    regle: str              # comment le programme la reconnaît
    objectif: str = ""      # comment l'objectif et l'invalidation sont fixés


_OBJ_HAUTEUR = ("Objectif : la hauteur de la figure, reportée depuis la cassure. "
                "Invalidation : le bord opposé de la figure au moment de la cassure.")
_OBJ_HARMO = ("Objectif : retour de 61,8 % de la jambe AD. Invalidation : D dépassé de "
              "23,6 % de la jambe AD.")
_OBJ_BOUGIE = ("Pas d'objectif chiffré. Invalidation : l'extrême de la figure (le plus bas "
               "pour une figure haussière, le plus haut pour une baissière).")

_HARMO = ("Cinq pivots X, A, B, C, D dont les rapports suivent des proportions de "
          "Fibonacci (tolérance ± 5 %). ")

CATALOGUE: dict[str, Modele] = {
    # ------------------------------------------------------------------ retournements
    "double_sommet": Modele(
        "Double sommet", "Retournements", -1, "M",
        "Le prix bute deux fois sur le même plafond, avec un creux entre les deux : la hausse "
        "s'essouffle. La figure se confirme quand le prix clôture sous ce creux (la « ligne de cou »).",
        "Trois pivots sommet – creux – sommet ; les deux sommets ne diffèrent pas de plus de la "
        "tolérance (en % de la hauteur) ; le prix montait avant le premier sommet (le creux "
        "précédent est plus bas que la ligne de cou).",
        "Objectif : la hauteur (sommets − ligne de cou), reportée sous la ligne de cou. "
        "Invalidation : le plus haut des deux sommets."),
    "double_creux": Modele(
        "Double creux", "Retournements", +1, "W",
        "Le prix rebondit deux fois sur le même plancher : la baisse s'essouffle. Confirmé quand "
        "le prix clôture au-dessus du sommet intermédiaire.",
        "Creux – sommet – creux, creux au même niveau (tolérance), prix en baisse avant.",
        "Objectif : la hauteur reportée au-dessus de la ligne de cou. Invalidation : le plus bas "
        "des deux creux."),
    "triple_sommet": Modele(
        "Triple sommet", "Retournements", -1, "3S",
        "Trois tentatives échouent sous le même plafond. Confirmé sous le plus bas des deux creux.",
        "Cinq pivots S – C – S – C – S ; les trois sommets dans la tolérance ; prix en hausse avant.",
        "Objectif : la hauteur reportée sous la ligne de cou. Invalidation : le plus haut sommet."),
    "triple_creux": Modele(
        "Triple creux", "Retournements", +1, "3C",
        "Trois rebonds sur le même plancher. Confirmé au-dessus du plus haut des deux sommets.",
        "Cinq pivots C – S – C – S – C ; les trois creux dans la tolérance ; prix en baisse avant.",
        "Objectif : la hauteur reportée au-dessus de la ligne de cou. Invalidation : le plus bas creux."),
    "tete_epaules": Modele(
        "Tête-épaules", "Retournements", -1, "ETE",
        "Un sommet (la tête) encadré de deux sommets plus bas et à peu près égaux (les épaules). "
        "La ligne de cou relie les deux creux ; sa cassure annonce la fin de la hausse.",
        "Six pivots C – S – C – S – C – S ; la tête dépasse les deux épaules ; épaules proches "
        "(deux fois la tolérance) ; durées des épaules dans un rapport de 1 à 3 au plus ; prix en "
        "hausse avant.",
        "Objectif : la distance tête – ligne de cou, reportée depuis la cassure. Invalidation : "
        "l'épaule droite."),
    "tete_epaules_inverse": Modele(
        "Tête-épaules inversée", "Retournements", +1, "ETEi",
        "Le miroir du tête-épaules, en bas d'une baisse : un creux plus profond entre deux creux "
        "moins profonds. Confirmé au-dessus de la ligne de cou.",
        "Six pivots S – C – S – C – S – C, mêmes conditions à l'envers.",
        "Objectif : la distance tête – ligne de cou au-dessus de la cassure. Invalidation : "
        "l'épaule droite."),
    # ------------------------------------------------------------------ triangles et biseaux
    "triangle_ascendant": Modele(
        "Triangle ascendant", "Triangles et biseaux", +1, "TA",
        "Un plafond horizontal et des creux de plus en plus hauts : les acheteurs poussent. On "
        "attend une sortie par le haut.",
        "Au moins cinq pivots ; droite des sommets plate, droite des creux montante ; l'écart se "
        "resserre d'au moins 30 % ; chaque pivot à moins de la tolérance de sa droite ; aucune "
        "clôture nettement hors des droites.", _OBJ_HAUTEUR),
    "triangle_descendant": Modele(
        "Triangle descendant", "Triangles et biseaux", -1, "TD",
        "Un plancher horizontal et des sommets de plus en plus bas : les vendeurs pressent. On "
        "attend une sortie par le bas.",
        "Comme le triangle ascendant, droite des creux plate et droite des sommets descendante.",
        _OBJ_HAUTEUR),
    "triangle_symetrique": Modele(
        "Triangle symétrique", "Triangles et biseaux", 0, "TS",
        "Sommets de plus en plus bas et creux de plus en plus hauts : le marché hésite. La "
        "direction est celle de la cassure.",
        "Droite des sommets descendante, droite des creux montante, écart resserré d'au moins 30 %.",
        _OBJ_HAUTEUR),
    "biseau_ascendant": Modele(
        "Biseau ascendant", "Triangles et biseaux", -1, "BA",
        "Les deux droites montent mais se resserrent : la hausse ralentit. Sortie attendue par le bas.",
        "Deux droites montantes, celle des creux plus pentue, écart resserré d'au moins 30 %.",
        _OBJ_HAUTEUR),
    "biseau_descendant": Modele(
        "Biseau descendant", "Triangles et biseaux", +1, "BD",
        "Les deux droites descendent en se resserrant : la baisse s'épuise. Sortie attendue par le haut.",
        "Deux droites descendantes, celle des sommets plus pentue, écart resserré d'au moins 30 %.",
        _OBJ_HAUTEUR),
    "elargissement": Modele(
        "Élargissement", "Triangles et biseaux", 0, "EL",
        "Sommets de plus en plus hauts et creux de plus en plus bas (« mégaphone ») : marché "
        "nerveux. La direction est celle de la cassure.",
        "Droite des sommets montante, droite des creux descendante, écart élargi d'au moins 30 %.",
        _OBJ_HAUTEUR),
    # ------------------------------------------------------------------ canaux et ranges
    "canal_ascendant": Modele(
        "Canal ascendant", "Canaux et ranges", 0, "CA",
        "Le prix monte entre deux droites parallèles. La sortie du canal, d'un côté ou de "
        "l'autre, est le signal.",
        "Au moins cinq pivots ; deux droites montantes d'écart à peu près constant (± 30 %).",
        _OBJ_HAUTEUR),
    "canal_descendant": Modele(
        "Canal descendant", "Canaux et ranges", 0, "CD",
        "Le prix descend entre deux droites parallèles. La sortie du canal est le signal.",
        "Deux droites descendantes d'écart à peu près constant.", _OBJ_HAUTEUR),
    "rectangle": Modele(
        "Rectangle", "Canaux et ranges", 0, "R",
        "Le prix rebondit entre un plancher et un plafond horizontaux, touchés plusieurs fois. "
        "La direction est celle de la cassure.",
        "Au moins cinq pivots ; deux droites plates d'écart constant.", _OBJ_HAUTEUR),
    "range": Modele(
        "Range", "Canaux et ranges", 0, "RG",
        "Une période de calme : toutes les clôtures tiennent dans une bande étroite. La sortie "
        "de la bande donne la direction.",
        "Au moins N bougies (réglage « durée ») dont toutes les clôtures tiennent dans une bande "
        "de L × ATR (réglage « largeur »). La cassure est la première clôture hors de la bande.",
        "Objectif : la largeur de la bande, reportée depuis la cassure. Invalidation : le bord "
        "opposé."),
    # ------------------------------------------------------------------ continuations
    "drapeau_haussier": Modele(
        "Drapeau haussier", "Continuations", +1, "DH",
        "Une montée brutale (le mât), puis une courte pause qui redescend légèrement entre deux "
        "parallèles (le drapeau). La hausse reprend à la sortie par le haut.",
        "Mât : hausse d'au moins 5 ATR à plus de 0,5 ATR par bougie. Drapeau : 3 bougies au moins, "
        "deux fois la durée du mât au plus, recul de moins de la moitié du mât, droites "
        "descendantes ou plates. Cassure : clôture au-dessus de la droite haute.",
        "Objectif : la hauteur du mât, reportée depuis la cassure. Invalidation : le plus bas du "
        "drapeau."),
    "drapeau_baissier": Modele(
        "Drapeau baissier", "Continuations", -1, "DB",
        "Une chute brutale, puis une courte remontée entre deux parallèles. La baisse reprend à "
        "la sortie par le bas.",
        "Le miroir du drapeau haussier.",
        "Objectif : la hauteur du mât sous la cassure. Invalidation : le plus haut du drapeau."),
    "fanion_haussier": Modele(
        "Fanion haussier", "Continuations", +1, "FH",
        "Comme le drapeau, mais la pause forme un petit triangle qui se resserre.",
        "Mât comme pour le drapeau ; pause en petit triangle (droites qui convergent).",
        "Objectif : la hauteur du mât. Invalidation : le plus bas du fanion."),
    "fanion_baissier": Modele(
        "Fanion baissier", "Continuations", -1, "FB",
        "Chute brutale suivie d'un petit triangle ; la baisse reprend par le bas.",
        "Le miroir du fanion haussier.",
        "Objectif : la hauteur du mât sous la cassure. Invalidation : le plus haut du fanion."),
    "tasse_anse": Modele(
        "Tasse avec anse", "Continuations", +1, "TAA",
        "Un creux arrondi (la tasse) qui revient au niveau de départ, puis un petit repli (l'anse). "
        "La hausse reprend au-dessus du bord de la tasse.",
        "Sommet – creux – retour au niveau du sommet (tolérance) ; fond arrondi (au moins 40 % du "
        "temps dans le tiers bas de la tasse) ; anse : repli de moins de la moitié de la "
        "profondeur, plus courte que la moitié de la tasse ; cassure au-dessus du bord.",
        "Objectif : la profondeur de la tasse au-dessus du bord. Invalidation : le plus bas de l'anse."),
    "tasse_inversee": Modele(
        "Tasse inversée", "Continuations", -1, "TI",
        "Le miroir de la tasse avec anse : un dôme arrondi, une petite remontée, puis la baisse "
        "reprend sous le bord.",
        "Mêmes conditions à l'envers.",
        "Objectif : la hauteur du dôme sous le bord. Invalidation : le plus haut de l'anse."),
    # ------------------------------------------------------------------ harmoniques
    "gartley_haussier": Modele(
        "Gartley haussier", "Harmoniques", +1, "Ga",
        "Figure en M dont le dernier point D marque un retournement à la hausse.",
        _HARMO + "B = 61,8 % de XA ; C = 38,2 à 88,6 % de AB ; CD = 127 à 161,8 % de BC ; "
        "D = 78,6 % de XA.", _OBJ_HARMO),
    "gartley_baissier": Modele(
        "Gartley baissier", "Harmoniques", -1, "Ga",
        "Figure en W dont le point D marque un retournement à la baisse.",
        _HARMO + "Mêmes rapports que le Gartley haussier, à l'envers.", _OBJ_HARMO),
    "chauve_souris_haussiere": Modele(
        "Chauve-souris haussière", "Harmoniques", +1, "Bat",
        "Proche du Gartley, avec un point D plus profond (88,6 % de XA).",
        _HARMO + "B = 38,2 à 50 % de XA ; C = 38,2 à 88,6 % de AB ; CD = 161,8 à 261,8 % de BC ; "
        "D = 88,6 % de XA.", _OBJ_HARMO),
    "chauve_souris_baissiere": Modele(
        "Chauve-souris baissière", "Harmoniques", -1, "Bat",
        "La chauve-souris à l'envers.", _HARMO + "Mêmes rapports, à l'envers.", _OBJ_HARMO),
    "papillon_haussier": Modele(
        "Papillon haussier", "Harmoniques", +1, "Pap",
        "Le point D dépasse X : retournement attendu au-delà du départ de la figure.",
        _HARMO + "B = 78,6 % de XA ; C = 38,2 à 88,6 % de AB ; CD = 161,8 à 224 % de BC ; "
        "D = 127 à 161,8 % de XA.", _OBJ_HARMO),
    "papillon_baissier": Modele(
        "Papillon baissier", "Harmoniques", -1, "Pap",
        "Le papillon à l'envers.", _HARMO + "Mêmes rapports, à l'envers.", _OBJ_HARMO),
    "crabe_haussier": Modele(
        "Crabe haussier", "Harmoniques", +1, "Cr",
        "Le plus étiré des harmoniques : D descend à 161,8 % de XA.",
        _HARMO + "B = 38,2 à 61,8 % de XA ; C = 38,2 à 88,6 % de AB ; CD = 224 à 361,8 % de BC ; "
        "D = 161,8 % de XA.", _OBJ_HARMO),
    "crabe_baissier": Modele(
        "Crabe baissier", "Harmoniques", -1, "Cr",
        "Le crabe à l'envers.", _HARMO + "Mêmes rapports, à l'envers.", _OBJ_HARMO),
    "abcd_haussier": Modele(
        "AB=CD haussier", "Harmoniques", +1, "ABCD",
        "Deux jambes de baisse de même longueur (AB et CD) séparées par un rebond : la seconde "
        "s'arrête là où la première s'était arrêtée.",
        "Quatre pivots A, B, C, D ; C = 38,2 à 88,6 % de AB ; CD = AB à ± 10 %.", _OBJ_HARMO),
    "abcd_baissier": Modele(
        "AB=CD baissier", "Harmoniques", -1, "ABCD",
        "Deux jambes de hausse de même longueur, séparées par un repli.",
        "Quatre pivots A, B, C, D ; C = 38,2 à 88,6 % de AB ; CD = AB à ± 10 %.", _OBJ_HARMO),
    # ------------------------------------------------------------------ divergences
    "divergence_haussiere": Modele(
        "Divergence haussière", "Divergences", +1, "Div+",
        "Le prix fait un creux plus bas, mais le RSI un creux plus haut : la baisse perd de sa force.",
        "Deux creux consécutifs du zigzag : prix plus bas, RSI(14) plus haut, premier RSI sous 50 ; "
        "connue à la confirmation du second creux.",
        "Objectif : le sommet entre les deux creux. Invalidation : le second creux."),
    "divergence_baissiere": Modele(
        "Divergence baissière", "Divergences", -1, "Div-",
        "Le prix fait un sommet plus haut, mais le RSI un sommet plus bas : la hausse perd de sa force.",
        "Deux sommets consécutifs : prix plus haut, RSI(14) plus bas, premier RSI au-dessus de 50.",
        "Objectif : le creux entre les deux sommets. Invalidation : le second sommet."),
    # ------------------------------------------------------------------ chandeliers
    "doji_apres_hausse": Modele(
        "Doji après hausse", "Chandeliers", -1, "Dj",
        "Ouverture et clôture presque égales : indécision. Après une hausse, il annonce un "
        "possible retournement à la baisse.",
        "Corps ≤ 10 % de l'amplitude, amplitude ≥ 0,5 ATR, prix en hausse sur les 5 bougies "
        "précédentes.", _OBJ_BOUGIE),
    "doji_apres_baisse": Modele(
        "Doji après baisse", "Chandeliers", +1, "Dj",
        "Indécision après une baisse : possible retournement à la hausse.",
        "Corps ≤ 10 % de l'amplitude, amplitude ≥ 0,5 ATR, prix en baisse avant.", _OBJ_BOUGIE),
    "marteau": Modele(
        "Marteau", "Chandeliers", +1, "Ma",
        "Petit corps en haut, longue mèche basse, après une baisse : les vendeurs ont poussé, les "
        "acheteurs ont tout repris.",
        "Mèche basse ≥ 2 corps, mèche haute ≤ 10 % de l'amplitude, corps ≥ 5 % de l'amplitude, "
        "amplitude ≥ 0,7 ATR, prix en baisse avant.", _OBJ_BOUGIE),
    "pendu": Modele(
        "Pendu", "Chandeliers", -1, "Pe",
        "La forme du marteau, mais après une hausse : signe de fatigue.",
        "Mêmes proportions que le marteau, prix en hausse avant.", _OBJ_BOUGIE),
    "marteau_inverse": Modele(
        "Marteau inversé", "Chandeliers", +1, "Mi",
        "Petit corps en bas, longue mèche haute, après une baisse.",
        "Mèche haute ≥ 2 corps, mèche basse ≤ 10 % de l'amplitude, prix en baisse avant.", _OBJ_BOUGIE),
    "etoile_filante": Modele(
        "Étoile filante", "Chandeliers", -1, "EF",
        "Petit corps en bas, longue mèche haute, après une hausse : le prix a été rejeté vers le bas.",
        "Mèche haute ≥ 2 corps, mèche basse ≤ 10 % de l'amplitude, prix en hausse avant.", _OBJ_BOUGIE),
    "avalement_haussier": Modele(
        "Avalement haussier", "Chandeliers", +1, "AvH",
        "Une bougie verte dont le corps englobe celui de la bougie rouge précédente, après une baisse.",
        "Bougie rouge puis verte ; le corps vert couvre le corps rouge et fait au moins la moitié "
        "du corps moyen ; prix en baisse avant.", _OBJ_BOUGIE),
    "avalement_baissier": Modele(
        "Avalement baissier", "Chandeliers", -1, "AvB",
        "Une bougie rouge qui englobe la verte précédente, après une hausse.",
        "Le miroir de l'avalement haussier.", _OBJ_BOUGIE),
    "harami_haussier": Modele(
        "Harami haussier", "Chandeliers", +1, "HaH",
        "Une grande bougie rouge, puis une petite verte logée dans son corps : la baisse marque "
        "une pause.",
        "Grand corps rouge (≥ corps moyen) puis corps vert ≤ 60 % du précédent, contenu dedans ; "
        "prix en baisse avant.", _OBJ_BOUGIE),
    "harami_baissier": Modele(
        "Harami baissier", "Chandeliers", -1, "HaB",
        "Une grande bougie verte, puis une petite rouge logée dans son corps.",
        "Le miroir du harami haussier.", _OBJ_BOUGIE),
    "etoile_du_matin": Modele(
        "Étoile du matin", "Chandeliers", +1, "EM",
        "Grande rouge, petite bougie d'hésitation, puis grande verte qui remonte au-delà du "
        "milieu de la rouge.",
        "Trois bougies ; corps du milieu ≤ 30 % du premier ; la troisième clôture au-dessus du "
        "milieu du premier corps ; prix en baisse avant.", _OBJ_BOUGIE),
    "etoile_du_soir": Modele(
        "Étoile du soir", "Chandeliers", -1, "ES",
        "Grande verte, petite bougie d'hésitation, puis grande rouge.",
        "Le miroir de l'étoile du matin.", _OBJ_BOUGIE),
    "trois_soldats": Modele(
        "Trois soldats blancs", "Chandeliers", +1, "3SB",
        "Trois grandes bougies vertes d'affilée, chacune clôturant plus haut.",
        "Trois corps verts ≥ 60 % du corps moyen ; chacun ouvre dans le corps précédent et "
        "clôture plus haut ; petites mèches hautes.", _OBJ_BOUGIE),
    "trois_corbeaux": Modele(
        "Trois corbeaux noirs", "Chandeliers", -1, "3CN",
        "Trois grandes bougies rouges d'affilée, chacune clôturant plus bas.",
        "Le miroir des trois soldats blancs.", _OBJ_BOUGIE),
    "penetrante": Modele(
        "Pénétrante", "Chandeliers", +1, "Pen",
        "Après une grande rouge, une verte qui remonte au-delà du milieu de son corps sans "
        "l'englober.",
        "Grande rouge puis verte qui ouvre au plus à sa clôture et clôture entre son milieu et son "
        "ouverture ; prix en baisse avant.", _OBJ_BOUGIE),
    "nuage_noir": Modele(
        "Couverture en nuage noir", "Chandeliers", -1, "NN",
        "Après une grande verte, une rouge qui redescend sous le milieu de son corps.",
        "Le miroir de la pénétrante.", _OBJ_BOUGIE),
    "pince_haut": Modele(
        "Pince haute", "Chandeliers", -1, "PH",
        "Deux bougies au même plus haut (une verte puis une rouge) après une hausse : le plafond "
        "tient.",
        "Plus hauts égaux à 0,05 ATR près ; verte puis rouge ; prix en hausse avant.", _OBJ_BOUGIE),
    "pince_bas": Modele(
        "Pince basse", "Chandeliers", +1, "PB",
        "Deux bougies au même plus bas (une rouge puis une verte) après une baisse : le plancher "
        "tient.",
        "Plus bas égaux à 0,05 ATR près ; rouge puis verte ; prix en baisse avant.", _OBJ_BOUGIE),
    "marubozu_haussier": Modele(
        "Marubozu haussier", "Chandeliers", +1, "MbH",
        "Une grande bougie verte presque sans mèche : les acheteurs ont dominé du début à la fin.",
        "Corps ≥ 90 % de l'amplitude et ≥ 1,5 corps moyen.", _OBJ_BOUGIE),
    "marubozu_baissier": Modele(
        "Marubozu baissier", "Chandeliers", -1, "MbB",
        "Une grande bougie rouge presque sans mèche.",
        "Corps ≥ 90 % de l'amplitude et ≥ 1,5 corps moyen.", _OBJ_BOUGIE),
}


def types_de(famille: str) -> list[str]:
    return [t for t, m in CATALOGUE.items() if m.famille == famille]


def nom_sens(sens: int) -> str:
    return {1: "▲ hausse", -1: "▼ baisse"}.get(int(sens), "selon la cassure")


@dataclass
class Figure:
    """Une figure repérée sur un historique. Indices = positions des bougies."""
    type: str
    debut: int
    fin: int
    detection: int                      # 1re bougie où la figure est connue
    points: list                        # [(i, prix)] : le tracé principal
    lignes: list = field(default_factory=list)          # [(i0, p0, i1, p1)]
    zone: tuple | None = None                           # (i0, i1, bas, haut)
    etiquettes: list = field(default_factory=list)      # [(i, prix, texte)]
    niveau: float = np.nan              # niveau à franchir pour confirmer
    signal: int | None = None           # bougie de confirmation (on agit à sa clôture)
    sens_cassure: int = 0               # direction de la cassure (figures neutres)
    objectif: float = np.nan
    invalidation: float = np.nan
    statut: str = EN_FORMATION
    details: dict = field(default_factory=dict)

    @property
    def modele(self) -> Modele:
        return CATALOGUE[self.type]

    @property
    def nom(self) -> str:
        return self.modele.nom

    @property
    def famille(self) -> str:
        return self.modele.famille

    @property
    def sens(self) -> int:
        """Sens attendu ; pour une figure neutre, celui de sa cassure (0 tant qu'elle n'a pas cassé)."""
        return self.modele.sens or self.sens_cassure

    @property
    def nom_complet(self) -> str:
        """Le nom, précisé par le sens de la cassure pour les figures neutres."""
        if self.modele.sens == 0 and self.sens_cassure:
            return f"{self.nom} (cassure {'▲' if self.sens_cassure > 0 else '▼'})"
        return self.nom
