"""
Le graphique interactif de la page « Graphique ».

    en haut   les bougies, les figures repérées, les vagues du zigzag, les
              supports et résistances ;
    en bas    le volume ou le RSI (avec les droites des divergences).

Navigation :
  - molette : zoom autour du curseur ;
  - barre d'outils : loupe (zoom sur un rectangle), croix (déplacer), maison
    (vue de départ) ;
  - clic sur une figure : elle est sélectionnée (mise en évidence, objectif et
    invalidation tracés) et la liste se place dessus.

Seule la fenêtre visible est dessinée, et redessinée après chaque zoom ou
déplacement : un historique de deux millions de bougies reste fluide. Les
bougies sont regroupées quand il y en a trop pour la largeur de l'écran.
"""

from __future__ import annotations

import math

import numpy as np
from matplotlib.ticker import AutoLocator, MaxNLocator

from .. import config, dessin
from .composants import ZoneGraphique
from .theme import COULEURS

FIGURES_MAX = 300           # figures dessinées à la fois (hors sélection)
CHANDELIERS_MAX = 250       # marqueurs de chandeliers à la fois
ETIQUETTES_MAX = 25         # au-delà, seules les figures sélectionnées ont leurs étiquettes


class GraphiqueFigures(ZoneGraphique):

    def __init__(self, parent, au_choix=None):
        super().__init__(parent, taille=(7, 4.6), disposition="constrained")
        self.figure.get_layout_engine().set(h_pad=0.02, hspace=0.0)
        grille = self.figure.add_gridspec(2, 1, height_ratios=[4.2, 1])
        self.ax = self.figure.add_subplot(grille[0])
        self.ax_bas = self.figure.add_subplot(grille[1], sharex=self.ax)
        for ax in (self.ax, self.ax_bas):
            dessin.styliser(ax)
            ax.set_autoscale_on(False)
        self.ax.tick_params(labelbottom=False)
        self.au_choix = au_choix
        self.analyse = None
        self.selection = None
        self.autorisees = None          # indices des figures à montrer (filtre de la liste)
        self.options = {"pivots": True, "structure": False, "niveaux": True, "chandeliers": True,
                        "panneau": "Volume", "horizon": config.HORIZON}
        self._artistes = []
        self._dessinees = []
        self._prevu = None
        self.message = self.ax.text(0.5, 0.5, "", transform=self.ax.transAxes, ha="center",
                                    va="center", color=COULEURS["texte_doux"], fontsize=11)
        self.note = self.ax.text(0.995, 0.01, "", transform=self.ax.transAxes, ha="right",
                                 va="bottom", color=COULEURS["texte_doux"], fontsize=8, zorder=10)
        # Branché une seule fois : on ne vide jamais les axes avec clear(), qui
        # effacerait aussi cet abonnement.
        self.ax.callbacks.connect("xlim_changed", self._planifier)
        self.canvas.mpl_connect("scroll_event", self._molette)
        self.canvas.mpl_connect("button_press_event", self._clic)
        self.ax.format_coord = self._coordonnees
        self.vider("Choisis une crypto et une échelle, puis « Analyser ».")

    # ==================================================================
    def vider(self, message: str = ""):
        self.analyse = None
        self.selection = None
        self._effacer()
        self.message.set_text(message)
        self.note.set_text("")
        self.ax.set_title("")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax_bas.set_yticks([])
        self.redessiner()

    def _effacer(self):
        for artiste in self._artistes:
            try:
                artiste.remove()
            except (ValueError, NotImplementedError):
                pass
        self._artistes = []
        self._dessinees = []

    def afficher(self, analyse, vue=None, selection=None):
        """Nouvelle analyse ; `vue` = (i0, i1), sinon les 300 dernières bougies."""
        self.analyse = analyse
        self.selection = selection
        self.autorisees = None          # le filtre de la liste sera redonné pour cette analyse
        df = analyse.bougies
        self.o, self.h, self.b, self.c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
        self.volume = df["Volume"].to_numpy(dtype=float)
        self.n = len(self.c)
        self.debuts = np.array([f.debut for f in analyse.figures], dtype=np.int64)
        self.bouts = np.array([f.signal if f.signal is not None else
                               int(f.details.get("fin du suivi", f.fin)) for f in analyse.figures],
                              dtype=np.int64)
        self.est_bougie = np.array([f.famille == "Chandeliers" for f in analyse.figures], dtype=bool)
        self.message.set_text("")
        self.ax.yaxis.set_major_locator(AutoLocator())
        dessin.format_dates(self.ax_bas, df.index, config.minutes(analyse.intervalle))
        if vue is None:
            vue = (max(0, self.n - 300), self.n)
        self.ax.set_xlim(vue[0] - 0.5, vue[1] + 3)
        self._redessiner()
        if self.barre is not None:
            self.barre.update()             # la « maison » ramène à cette vue

    def definir_autorisees(self, indices):
        self.autorisees = None if indices is None else np.asarray(sorted(indices), dtype=np.int64)
        self._planifier()

    def definir_options(self, **options):
        self.options.update(options)
        self._planifier()

    # ==================================================================
    def selectionner(self, k, cadrer: bool = True):
        if self.analyse is None:
            return
        self.selection = k
        if k is None or not cadrer:
            self._redessiner()
            return
        f = self.analyse.figures[k]
        fin = max(int(self.bouts[k]), f.fin) + (self.options["horizon"] if f.signal is not None else 5)
        largeur = fin - f.debut
        marge = max(15, int(0.35 * largeur))
        self.ax.set_xlim(f.debut - marge, min(self.n + 5, fin + marge))
        self._redessiner()

    def _planifier(self, _ax=None):
        if self.analyse is not None and self._prevu is None:
            self._prevu = self.after(60, self._redessiner)

    def _bougies_max(self) -> int:
        largeur = self.canvas.get_tk_widget().winfo_width()
        return max(120, min(dessin.BOUGIES_MAX, largeur // 3 if largeur > 50 else dessin.BOUGIES_MAX))

    def _redessiner(self):
        self._prevu = None
        a = self.analyse
        if a is None:
            return
        self._effacer()
        x0, x1 = self.ax.get_xlim()
        i0, i1 = max(0, int(math.floor(x0))), min(self.n, int(math.ceil(x1)) + 1)
        if i1 - i0 < 2:
            return
        ax = self.ax
        art = self._artistes
        art += dessin.tracer_bougies(ax, self.o, self.h, self.b, self.c, i0, i1, self._bougies_max())
        if self.options["pivots"]:
            art += dessin.tracer_pivots(ax, a, i0, i1, structure=self.options["structure"])
        if self.options["niveaux"]:
            art += dessin.tracer_niveaux(ax, a, i0, i1)

        visibles = (self.debuts <= i1) & (self.bouts >= i0)
        if self.autorisees is not None:
            masque = np.zeros(len(visibles), dtype=bool)
            masque[self.autorisees] = True
            visibles &= masque
        bougies = np.flatnonzero(visibles & self.est_bougie)
        autres = np.flatnonzero(visibles & ~self.est_bougie)
        cache = []
        if not self.options["chandeliers"]:
            bougies = bougies[:0]
        elif len(bougies) > CHANDELIERS_MAX:
            cache.append(f"{len(bougies)} chandeliers")
            bougies = bougies[:0]
        if len(autres) > FIGURES_MAX:
            cache.append(f"{len(autres) - FIGURES_MAX} figures")
            autres = autres[-FIGURES_MAX:]
        etiquettes = len(autres) + len(bougies) <= ETIQUETTES_MAX
        for k in list(autres) + list(bougies):
            if k != self.selection:
                art += dessin.tracer_figure(ax, a.figures[k], self.c, etiquettes=etiquettes,
                                            horizon=self.options["horizon"])
        self._dessinees = [int(k) for k in list(autres) + list(bougies)]
        bas, haut = float(self.b[i0:i1].min()), float(self.h[i0:i1].max())
        if self.selection is not None and 0 <= self.selection < len(a.figures):
            f = a.figures[self.selection]
            art += dessin.tracer_figure(ax, f, self.c, mise_en_avant=True, horizon=self.options["horizon"])
            if f.debut <= i1 and self.bouts[self.selection] >= i0:
                for niveau in (f.objectif, f.invalidation):
                    if np.isfinite(niveau):
                        bas, haut = min(bas, niveau), max(haut, niveau)
        self.note.set_text(("Masqués (zoome pour les voir) : " + ", ".join(cache)) if cache else "")
        marge = (haut - bas) * 0.05 or haut * 0.01
        ax.set_ylim(bas - marge, haut + marge)
        self._panneau_bas(i0, i1)
        titre = f"{a.symbole} {a.intervalle}"
        if a.provenance:
            titre += f"  ·  {a.provenance}"
        ax.set_title(titre, fontsize=10, loc="left", color=COULEURS["texte"])
        self.redessiner()

    def _panneau_bas(self, i0, i1):
        ax = self.ax_bas
        art = self._artistes
        if self.options["panneau"] == "RSI":
            pas = max(1, (i1 - i0) // 1500)
            x = np.arange(i0, i1, pas)
            art += ax.plot(x, self.analyse.rsi[i0:i1:pas], color="#c39bd3", lw=0.9)
            for niveau in (30, 70):
                art.append(ax.axhline(niveau, color="#666666", lw=0.6, ls="--"))
            for k in self._dessinees + ([self.selection] if self.selection is not None else []):
                f = self.analyse.figures[k]
                if "ligne RSI" in f.details:
                    a0, r0, a1, r1 = f.details["ligne RSI"]
                    art += ax.plot([a0, a1], [r0, r1], color=dessin.couleur_sens(f.sens),
                                   lw=2 if k == self.selection else 1.1)
            ax.set_ylim(0, 100)
            ax.set_yticks([30, 70])
            ax.set_ylabel("RSI", fontsize=8)
        else:
            x, bo, _, _, bc, paquet = dessin.regrouper(self.o, self.h, self.b, self.c, i0, i1,
                                                       self._bougies_max())
            if not len(x):
                return
            g0 = (i0 // paquet) * paquet
            vol = np.add.reduceat(self.volume[g0:i1], np.arange(len(x)) * paquet)
            teintes = np.where(bc >= bo, dessin.COULEURS["bougie_haut"], dessin.COULEURS["bougie_bas"])
            art.append(ax.bar(x, vol, width=0.7 * paquet, color=teintes, alpha=0.7))
            ax.set_ylim(0, float(vol.max()) * 1.1 or 1)
            ax.yaxis.set_major_locator(MaxNLocator(3))
            ax.set_ylabel("Volume", fontsize=8)

    # ==================================================================
    def _molette(self, evenement):
        if self.analyse is None or evenement.xdata is None:
            return
        if evenement.inaxes not in (self.ax, self.ax_bas):
            return
        facteur = 0.8 if evenement.button == "up" else 1.25
        x0, x1 = self.ax.get_xlim()
        x = evenement.xdata
        n0, n1 = x - (x - x0) * facteur, x + (x1 - x) * facteur
        if n1 - n0 < 12:
            return
        self.ax.set_xlim(max(n0, -50), min(n1, self.n + 50))

    def _clic(self, evenement):
        if (self.analyse is None or evenement.button != 1 or evenement.inaxes is not self.ax
                or evenement.xdata is None or (self.barre is not None and self.barre.mode)):
            return
        x, y = evenement.xdata, evenement.ydata
        bas, haut = self.ax.get_ylim()
        x0, x1 = self.ax.get_xlim()
        meilleur, score_min = None, np.inf
        for k in self._dessinees:
            f = self.analyse.figures[k]
            if not (f.debut - 1 <= x <= self.bouts[k] + 1):
                continue
            prix = [p for _, p in f.points] + [p for l in f.lignes for p in (l[1], l[3])]
            if f.zone is not None:
                prix += [f.zone[2], f.zone[3]]
            if not prix:
                continue
            p0, p1 = min(prix), max(prix)
            distance = 0.0 if p0 <= y <= p1 else min(abs(y - p0), abs(y - p1))
            score = distance / (haut - bas) + 0.02 * (self.bouts[k] - f.debut) / (x1 - x0)
            if score < score_min:
                meilleur, score_min = k, score
        if meilleur is not None and score_min < 0.08:
            self.selection = meilleur
            self._redessiner()
            if self.au_choix:
                self.au_choix(meilleur)

    def _coordonnees(self, x, y):
        if self.analyse is None:
            return ""
        i = int(round(x))
        if 0 <= i < self.n:
            return f"{self.analyse.date(i):%d/%m/%Y %H:%M} UTC   prix {y:,.6g}".replace(",", " ")
        return f"prix {y:,.6g}".replace(",", " ")
