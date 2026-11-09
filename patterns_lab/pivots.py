"""
Les sommets et les creux (« pivots »), base de toutes les figures chartistes.

**Méthode du zigzag.** On suit le prix vague par vague. Pendant une hausse, on
retient le plus haut atteint ; dès que le prix redescend de `sensibilité × ATR`
sous ce plus haut, celui-ci devient un **sommet**, et l'on suit la baisse. On
fait de même à la baisse pour les **creux**. Sommets et creux alternent donc
toujours, et chaque vague fait au moins `sensibilité` ATR : les petites
oscillations sont ignorées. Plus la sensibilité est basse, plus on trouve de
pivots, donc de petites figures.

**Aucun regard vers le futur.** Un sommet n'est connu qu'au moment où le prix
est assez redescendu : c'est sa bougie de **confirmation**, toujours postérieure
au sommet lui-même. Les figures ne sont datées qu'à partir de la confirmation de
leur dernier pivot. Le dernier extrême, pas encore confirmé, est gardé à part
(« provisoire ») : il sert aux figures en cours de formation.

**Structure de marché.** Chaque sommet est comparé au précédent (HH : sommet
plus haut, LH : sommet plus bas), chaque creux aussi (HL : creux plus haut,
LL : creux plus bas). HH + HL = tendance haussière, LH + LL = baissière.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .indicateurs import njit

SOMMET, CREUX = 1, -1


@njit(cache=True)
def _zigzag(haut, bas, seuil):
    n = len(haut)
    indices = np.empty(n, dtype=np.int64)
    prix = np.empty(n)
    types = np.empty(n, dtype=np.int8)
    confirmations = np.empty(n, dtype=np.int64)
    k = 0
    if n == 0:
        return indices[:0], prix[:0], types[:0], confirmations[:0], -1, 0
    sens = 0
    i_haut = 0
    i_bas = 0
    extreme = 0
    for i in range(1, n):
        if sens == 0:
            # Départ : on attend le premier mouvement d'au moins un seuil.
            if haut[i] >= haut[i_haut]:
                i_haut = i
            if bas[i] <= bas[i_bas]:
                i_bas = i
            if haut[i_haut] - bas[i_bas] >= seuil[i]:
                if i_bas < i_haut:
                    indices[k] = i_bas
                    prix[k] = bas[i_bas]
                    types[k] = -1
                    confirmations[k] = i
                    k += 1
                    sens = 1
                    extreme = i_haut
                else:
                    indices[k] = i_haut
                    prix[k] = haut[i_haut]
                    types[k] = 1
                    confirmations[k] = i
                    k += 1
                    sens = -1
                    extreme = i_bas
            continue
        if sens == 1:
            # Vague montante : le retournement se juge sur le plus haut déjà
            # atteint, avant de mettre ce plus haut à jour avec la bougie.
            if bas[i] <= haut[extreme] - seuil[extreme]:
                indices[k] = extreme
                prix[k] = haut[extreme]
                types[k] = 1
                confirmations[k] = i
                k += 1
                sens = -1
                extreme = i
            elif haut[i] > haut[extreme]:
                extreme = i
        else:
            if haut[i] >= bas[extreme] + seuil[extreme]:
                indices[k] = extreme
                prix[k] = bas[extreme]
                types[k] = -1
                confirmations[k] = i
                k += 1
                sens = 1
                extreme = i
            elif bas[i] < bas[extreme]:
                extreme = i
    return indices[:k], prix[:k], types[:k], confirmations[:k], extreme, sens


@dataclass
class Pivots:
    """Sommets et creux alternés. `confirme` = bougie de confirmation (−1 : provisoire)."""
    i: np.ndarray
    prix: np.ndarray
    type: np.ndarray
    confirme: np.ndarray

    def __len__(self):
        return len(self.i)

    @property
    def provisoire(self) -> bool:
        """Le dernier pivot est-il l'extrême en cours, pas encore confirmé ?"""
        return len(self.i) > 0 and self.confirme[-1] < 0

    def confirmes(self) -> "Pivots":
        if self.provisoire:
            return Pivots(self.i[:-1], self.prix[:-1], self.type[:-1], self.confirme[:-1])
        return self


def zigzag(haut: np.ndarray, bas: np.ndarray, atr: np.ndarray, sensibilite: float) -> Pivots:
    """
    Pivots du zigzag, seuil = `sensibilite` × ATR (l'ATR de la bougie de
    l'extrême). Le dernier extrême, non confirmé, est ajouté en provisoire.
    """
    seuil = np.asarray(atr, dtype=float) * float(sensibilite)
    indices, prix, types, conf, extreme, sens = _zigzag(
        np.asarray(haut, dtype=float), np.asarray(bas, dtype=float), seuil)
    if sens != 0 and extreme > (indices[-1] if len(indices) else -1):
        prix_ext = haut[extreme] if sens == 1 else bas[extreme]
        indices = np.append(indices, extreme)
        prix = np.append(prix, prix_ext)
        types = np.append(types, np.int8(sens))
        conf = np.append(conf, -1)
    return Pivots(indices.astype(np.int64), prix.astype(float), types.astype(np.int8),
                  conf.astype(np.int64))


def structure(pivots: Pivots) -> list[str]:
    """HH / LH pour les sommets, HL / LL pour les creux ; '' pour le premier de chaque sorte."""
    etiquettes = []
    dernier = {SOMMET: None, CREUX: None}
    for prix, sorte in zip(pivots.prix, pivots.type):
        sorte = int(sorte)
        precedent = dernier[sorte]
        if precedent is None:
            etiquettes.append("")
        elif sorte == SOMMET:
            etiquettes.append("HH" if prix > precedent else "LH")
        else:
            etiquettes.append("HL" if prix > precedent else "LL")
        dernier[sorte] = prix
    return etiquettes
