"""
Page « Graphique » : une crypto, une échelle au choix, et toutes les figures
repérées dessus.

À gauche, ce qu'on analyse (crypto, échelle, source, période), les figures à
chercher et les réglages. À droite, le graphique, la liste des figures et la
fiche de la figure sélectionnée. Cliquer une figure dans la liste ou sur le
graphique la sélectionne ; « Précédente / Suivante » les passe en revue.
"""

from __future__ import annotations

import os

import customtkinter as ctk
import numpy as np
import pandas as pd

from .. import config, detection, donnees, rapport
from ..figures import CONFIRMEE, EN_FORMATION, FAMILLES, INVALIDEE, SANS_CASSURE, nom_sens
from . import composants as cp
from .graphique import GraphiqueFigures
from .theme import COULEURS

SOURCES = ["Historique", "En direct"]
STATUTS = {"Tous les statuts": None, "Confirmées": {CONFIRMEE}, "En formation": {EN_FORMATION},
           "Invalidées": {INVALIDEE}, "Sans cassure": {SANS_CASSURE}}
EXEMPLES_ECHELLES = ["10m", "45m", "3h", "2d"]


def _mesure(v) -> str:
    """Un rapport (0,786) avec trois décimales, un prix ou une hauteur en clair."""
    if isinstance(v, (float, np.floating)):
        return cp.decimal(float(v), 3) if abs(v) < 10 else cp.prix(float(v))
    return str(v)


class PageGraphique(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        r = app.reglages
        self.analyse = None
        self.tableau_complet = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cp.titre_page(self, "Graphique",
                      "Choisis une crypto et une échelle (n'importe laquelle : 15m, 45m, 4h, 2d…), puis "
                      "« Analyser ». Clique une figure dans la liste ou sur le graphique pour la voir en "
                      "détail ; molette pour zoomer."
                      ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # ======================== COLONNE DE GAUCHE ========================
        gauche = ctk.CTkScrollableFrame(self, width=360, fg_color="transparent")
        gauche.grid(row=1, column=0, sticky="nsw", padx=(0, 12))

        carte, dedans = cp.section(gauche, "Marché")
        carte.pack(fill="x", pady=(0, 10))
        ligne = ctk.CTkFrame(dedans, fg_color="transparent")
        ligne.pack(fill="x", pady=2)
        ctk.CTkLabel(ligne, text="Crypto", width=70, anchor="w").pack(side="left")
        self.crypto = ctk.CTkComboBox(ligne, values=app.cryptos_disponibles() or config.CRYPTOS_DEFAUT,
                                      width=110, command=lambda _v: self._maj_echelles())
        self.crypto.pack(side="left")
        self.crypto.set(r.get("graphique_crypto", (app.cryptos_disponibles() or ["BTC"])[0]))
        ctk.CTkLabel(ligne, text="Échelle", width=56, anchor="e").pack(side="left", padx=(8, 4))
        self.echelle = ctk.CTkComboBox(ligne, values=["4h"], width=80)
        self.echelle.pack(side="left")
        self._maj_echelles()
        self.echelle.set(r.get("graphique_echelle", "4h"))
        cp.note(dedans, "Toute échelle peut être tapée : 45m, 3h, 2d… Elle est construite à partir "
                        "d'une échelle téléchargée qui la divise.")
        self.source = ctk.StringVar(value=r.get("graphique_source", SOURCES[0]))
        ctk.CTkSegmentedButton(dedans, values=SOURCES, variable=self.source,
                               command=lambda _v: self._maj_source()).pack(fill="x", pady=(8, 2))
        self.note_source = cp.note(dedans, "")
        self.saisie_bougies = cp.champ(dedans, "Bougies analysées (les dernières)",
                                       r.get("graphique_bougies", 5000), largeur=80, aide="toutes")
        self.saisie_debut = cp.champ(dedans, "À partir du (AAAA-MM-JJ)", r.get("graphique_debut", ""),
                                     largeur=110, aide="début")
        self.saisie_fin = cp.champ(dedans, "Jusqu'au (AAAA-MM-JJ)", r.get("graphique_fin", ""),
                                   largeur=110, aide="aujourd'hui")
        self._maj_source()

        carte, dedans = cp.section(gauche, "Figures à chercher",
                                   "Coche une famille entière, ou déplie-la (▸) pour choisir figure par "
                                   "figure. Les chandeliers sont nombreux : à cocher quand tu les veux.")
        carte.pack(fill="x", pady=(0, 10))
        self.choix = cp.ChoixFigures(dedans, r.get("graphique_types"))
        self.choix.pack(fill="x")

        carte, dedans = cp.section(gauche, "Réglages de la détection")
        carte.pack(fill="x", pady=(0, 10))
        self.reglages_detection = cp.ReglagesDetection(dedans, r.get("graphique_reglages"))
        self.reglages_detection.pack(fill="x")
        self.saisie_horizon = cp.champ(dedans, "Résultat jugé après (bougies)",
                                       r.get("graphique_horizon", config.HORIZON), largeur=64)
        cp.note(dedans, "La colonne « Après N » de la liste : la variation du prix N bougies après la "
                        "confirmation, comptée dans le sens attendu.")

        ctk.CTkButton(gauche, text="Analyser", height=44, font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.lancer).pack(fill="x", pady=(4, 12))

        # ======================== COLONNE DE DROITE ========================
        droite = ctk.CTkFrame(self, fg_color=COULEURS["panneau"], corner_radius=10)
        droite.grid(row=1, column=1, sticky="nsew")
        droite.grid_columnconfigure(0, weight=1)
        droite.grid_rowconfigure(1, weight=3)
        droite.grid_rowconfigure(2, weight=2)

        entete = ctk.CTkFrame(droite, fg_color="transparent")
        entete.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        self.titre = ctk.CTkLabel(entete, text="Aucune analyse.", anchor="w", justify="left",
                                  font=ctk.CTkFont(size=13, weight="bold"))
        self.titre.pack(side="left", fill="x", expand=True)
        self.options = {}
        for cle, texte, defaut in (("pivots", "Vagues", True), ("structure", "HH / HL", False),
                                   ("niveaux", "Supports / résistances", True),
                                   ("chandeliers", "Chandeliers", True)):
            variable = ctk.BooleanVar(value=r.get(f"graphique_{cle}", defaut))
            ctk.CTkCheckBox(entete, text=texte, variable=variable, checkbox_width=16, checkbox_height=16,
                            command=self._appliquer_options).pack(side="left", padx=(8, 0))
            self.options[cle] = variable
        self.panneau = ctk.StringVar(value=r.get("graphique_panneau", "Volume"))
        ctk.CTkOptionMenu(entete, values=["Volume", "RSI"], variable=self.panneau, width=90,
                          command=lambda _v: self._appliquer_options()).pack(side="left", padx=(10, 0))

        self.graphique = GraphiqueFigures(droite, au_choix=self._depuis_graphique)
        self.graphique.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 4))

        bas = ctk.CTkFrame(droite, fg_color="transparent")
        bas.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        bas.grid_columnconfigure(0, weight=3)
        bas.grid_columnconfigure(1, weight=2)
        bas.grid_rowconfigure(1, weight=1)

        filtres = ctk.CTkFrame(bas, fg_color="transparent")
        filtres.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.filtre_famille = ctk.StringVar(value="Toutes les familles")
        ctk.CTkOptionMenu(filtres, values=["Toutes les familles"] + FAMILLES, variable=self.filtre_famille,
                          width=180, command=lambda _v: self._filtrer()).pack(side="left")
        self.filtre_statut = ctk.StringVar(value="Tous les statuts")
        ctk.CTkOptionMenu(filtres, values=list(STATUTS), variable=self.filtre_statut, width=150,
                          command=lambda _v: self._filtrer()).pack(side="left", padx=6)
        self.compte = ctk.CTkLabel(filtres, text="", text_color=COULEURS["texte_doux"])
        self.compte.pack(side="left", padx=6)
        cp.bouton_discret(filtres, "Exporter (Excel)", self.exporter, largeur=120).pack(side="right")
        cp.bouton_discret(filtres, "Image", self.image, largeur=60).pack(side="right", padx=6)

        self.tableau = cp.Tableau(bas, hauteur=8, au_choix=self._depuis_liste)
        self.tableau.grid(row=1, column=0, sticky="nsew")

        fiche = ctk.CTkFrame(bas, fg_color=COULEURS["carte"], corner_radius=8)
        fiche.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0))
        fiche.grid_rowconfigure(1, weight=1)
        fiche.grid_columnconfigure(0, weight=1)
        navigation = ctk.CTkFrame(fiche, fg_color="transparent")
        navigation.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        cp.bouton_discret(navigation, "◀ Précédente", lambda: self._voisine(-1), largeur=100).pack(side="left")
        cp.bouton_discret(navigation, "Suivante ▶", lambda: self._voisine(1), largeur=100).pack(side="left", padx=6)
        self.texte = ctk.CTkTextbox(fiche, wrap="word", fg_color=COULEURS["carte"],
                                    font=ctk.CTkFont(size=12))
        self.texte.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self._fiche(None)

    # ==================================================================
    # CHOIX
    # ==================================================================
    def _maj_echelles(self):
        dispo = self.app.intervalles_disponibles(self.crypto.get().strip().upper())
        valeurs = dispo or list(config.INTERVALLES_DEFAUT)
        self.echelle.configure(values=valeurs + [e for e in EXEMPLES_ECHELLES if e not in valeurs])

    def _maj_source(self):
        direct = self.source.get() == "En direct"
        self.note_source.configure(text=(
            "Les 1000 dernières bougies terminées, lues sur Binance à l'instant. Rien n'est "
            "enregistré ; toute crypto cotée en USDT fonctionne." if direct else
            "Les bougies téléchargées (page Données). Les plus récentes d'abord : laisser vide pour "
            "tout l'historique, mais 4 ans en 1m prennent une minute."))
        etat = "disabled" if direct else "normal"
        for saisie in (self.saisie_bougies, self.saisie_debut, self.saisie_fin):
            saisie.configure(state=etat)

    def _reglages(self) -> detection.Reglages:
        r = detection.Reglages(**self.reglages_detection.valeurs(), types=self.choix.cochees())
        r.verifier()
        return r

    def horizon(self) -> int:
        return max(1, int(cp.lire_nombre(self.saisie_horizon, config.HORIZON)))

    # ==================================================================
    # ANALYSE
    # ==================================================================
    def lancer(self):
        symbole = self.crypto.get().strip().upper()
        try:
            intervalle = config.normaliser(self.echelle.get().strip())
            reglages = self._reglages()
            if not reglages.types:
                raise ValueError("Coche au moins une figure à chercher.")
            debut, fin = cp.lire_date(self.saisie_debut), cp.lire_date(self.saisie_fin)
        except ValueError as erreur:
            self.app.statut(str(erreur), erreur=True)
            return
        direct = self.source.get() == "En direct"
        nombre = int(cp.lire_nombre(self.saisie_bougies, 0))

        def travail():
            if direct:
                bougies, provenance = donnees.bougies_direct(symbole, intervalle)
            else:
                bougies, provenance = donnees.charger(symbole, intervalle)
                if debut is not None:
                    bougies = bougies[bougies.index >= debut]
                if fin is not None:
                    bougies = bougies[bougies.index < fin + pd.Timedelta(days=1)]
                if nombre > 0:
                    bougies = bougies.tail(nombre)
            if len(bougies) < 50:
                raise ValueError(f"seulement {len(bougies)} bougies sur cette période")
            return detection.analyser(bougies, reglages, symbole, intervalle, provenance)

        self.app.executer(travail, apres=self.montrer, libelle=f"Analyse de {symbole} {intervalle}")

    def montrer(self, analyse, selection=None):
        self.analyse = analyse
        self.crypto.set(analyse.symbole)
        self.echelle.set(analyse.intervalle)
        df = analyse.bougies
        self.titre.configure(text=(
            f"{analyse.symbole} {analyse.intervalle} · {len(df):,} bougies du {df.index[0]:%d/%m/%Y} "
            f"au {df.index[-1]:%d/%m/%Y %H:%M} UTC · {len(analyse.figures):,} figures").replace(",", " "))
        self.tableau_complet = analyse.tableau(self.horizon())
        self.graphique.options["horizon"] = self.horizon()
        self._appliquer_options(redessiner=False)
        vue = None
        if selection is not None:
            f = analyse.figures[selection]
            fin = (f.signal if f.signal is not None else f.fin) + self.horizon()
            marge = max(15, int(0.35 * (fin - f.debut)))
            vue = (f.debut - marge, min(len(df), fin + marge))
        self.graphique.afficher(analyse, vue=vue, selection=selection)
        self._filtrer(garder_selection=selection)
        if selection is not None:
            self._fiche(selection)
        self.app.statut(f"{len(analyse.figures)} figures repérées ({analyse.provenance}).")

    # ==================================================================
    # LISTE ET FILTRES
    # ==================================================================
    def _filtrer(self, garder_selection=None):
        t = self.tableau_complet
        if t is None or self.analyse is None:
            return
        if t.empty:
            self.tableau.remplir(pd.DataFrame({"": ["Aucune figure avec ces réglages."]}))
            self.graphique.definir_autorisees([])
            self.compte.configure(text="0 figure")
            return
        masque = np.ones(len(t), dtype=bool)
        famille = self.filtre_famille.get()
        if famille in FAMILLES:
            masque &= (t["Famille"] == famille).to_numpy()
        statuts = STATUTS[self.filtre_statut.get()]
        if statuts is not None:
            masque &= t["Statut"].isin(statuts).to_numpy()
        vue = t[masque].drop(columns=["Famille"])
        colonne_apres = f"Après {self.horizon()}"
        self.tableau.remplir(
            vue, garder_tri=True, gauche=("Figure",),
            formats={"Début": cp.date_courte, "Signal": cp.date_courte, "Prix": cp.prix,
                     "Objectif": cp.prix, "Invalidation": cp.prix, colonne_apres: cp.pct},
            largeurs={"Début": 118, "Signal": 118, "Figure": 210, "Sens": 46, "Statut": 96,
                      "Prix": 84, "Objectif": 84, "Invalidation": 90, colonne_apres: 76},
            couleur=lambda l: "gris" if l["Statut"] != CONFIRMEE else
            ("vert" if l["Sens"] == "▲" else "rouge" if l["Sens"] == "▼" else None))
        self.compte.configure(text=f"{int(masque.sum()):,} figures".replace(",", " "))
        self.graphique.definir_autorisees(vue.index.to_numpy())
        selection = garder_selection if garder_selection is not None else self.graphique.selection
        if selection is not None:
            self.tableau.choisir(selection)

    def _appliquer_options(self, redessiner=True):
        options = {cle: v.get() for cle, v in self.options.items()}
        options["panneau"] = self.panneau.get()
        if redessiner:
            self.graphique.definir_options(**options)
        else:
            self.graphique.options.update(options)

    def _depuis_liste(self, k):
        self.graphique.selectionner(k)
        self._fiche(k)

    def _depuis_graphique(self, k):
        self.tableau.choisir(k)
        self._fiche(k)

    def _voisine(self, pas):
        cles = self.tableau.cles_affichees()
        if not cles or self.analyse is None:
            return
        actuelle = self.graphique.selection
        if actuelle in cles:
            k = cles[max(0, min(len(cles) - 1, cles.index(actuelle) + pas))]
        else:
            k = cles[0] if pas > 0 else cles[-1]
        self.tableau.choisir(k)
        self._depuis_liste(k)

    # ==================================================================
    # FICHE DE LA FIGURE
    # ==================================================================
    def _fiche(self, k):
        self.texte.configure(state="normal")
        self.texte.delete("1.0", "end")
        if k is None or self.analyse is None:
            self.texte.insert("1.0", "Sélectionne une figure dans la liste ou sur le graphique : sa fiche "
                                     "s'affiche ici.\n\nLe catalogue (barre de gauche) montre le dessin type "
                                     "de chaque figure.")
            self.texte.configure(state="disabled")
            return
        a = self.analyse
        f = a.figures[k]
        c = a.bougies["Close"].to_numpy()
        m = f.modele
        lignes = [f"{f.nom_complet} — {f.statut}",
                  f"Sens attendu : {nom_sens(m.sens) if m.sens else 'selon la cassure'}"
                  + (f" ; cassure {'▲' if f.sens_cassure > 0 else '▼'}" if not m.sens and f.sens_cassure else ""),
                  f"Formée du {a.date(f.debut):%d/%m/%Y %H:%M} au {a.date(f.fin):%d/%m/%Y %H:%M} (UTC)",
                  f"Connue le {a.date(f.detection):%d/%m/%Y %H:%M}"]
        reference = c[f.signal] if f.signal is not None else c[-1]
        if f.signal is not None:
            lignes.append(f"Signal le {a.date(f.signal):%d/%m/%Y %H:%M}, à {cp.prix(c[f.signal])}")
        elif np.isfinite(f.niveau):
            lignes.append(f"Niveau à franchir : {cp.prix(f.niveau)} "
                          f"({cp.pct(f.niveau / c[-1] - 1)} du dernier prix)")
        for nom, niveau in (("Objectif", f.objectif), ("Invalidation", f.invalidation)):
            if np.isfinite(niveau):
                lignes.append(f"{nom} : {cp.prix(niveau)} ({cp.pct(niveau / reference - 1)})")
        h = self.horizon()
        if f.signal is not None and f.sens and f.signal + h < a.n:
            variation = f.sens * (c[f.signal + h] / c[f.signal] - 1)
            lignes.append(f"Après {h} bougies : {cp.pct(variation)} dans le sens attendu")
        details = {cle: v for cle, v in f.details.items()
                   if cle not in ("cassure", "fin du suivi", "ligne RSI", "invalidée le")}
        if details:
            lignes.append("Mesures : " + " ; ".join(f"{cle} {_mesure(v)}" for cle, v in details.items()))
        lignes += ["", m.description, "", "Comment elle est repérée : " + m.regle]
        if m.objectif:
            lignes += ["", m.objectif]
        self.texte.insert("1.0", "\n".join(lignes))
        self.texte.configure(state="disabled")

    # ==================================================================
    # EXPORTS
    # ==================================================================
    def exporter(self):
        if self.analyse is None or self.tableau_complet is None:
            self.app.statut("Lance d'abord une analyse.", erreur=True)
            return
        a = self.analyse
        t = self.tableau_complet.copy()
        t = t.rename(columns={f"Après {self.horizon()}": "Après N"})
        chemin = config.DOSSIER_RESULTATS / (f"figures_{a.symbole}_{a.intervalle}_"
                                             f"{pd.Timestamp.now():%Y-%m-%d_%Hh%M%S}.xlsx")
        compte = detection.compter(a).reset_index()
        rapport.ecrire_excel(chemin, {"Figures": t, "Par type": compte}, [
            f"Figures repérées sur {a.symbole} {a.intervalle} ({a.provenance})",
            f"Du {a.bougies.index[0]:%d/%m/%Y} au {a.bougies.index[-1]:%d/%m/%Y %H:%M} (UTC), "
            f"{len(a.bougies)} bougies.",
            f"Réglages : vagues de {a.reglages.sensibilite:g} ATR, tolérance {a.reglages.tolerance:g} %, "
            f"range {a.reglages.range_largeur:g} ATR sur {a.reglages.range_duree} bougies.",
            f"Après N : variation du prix {self.horizon()} bougies après le signal, dans le sens attendu.",
        ])
        self.app.statut(f"Exporté : {chemin}")

    def image(self):
        if self.analyse is None:
            self.app.statut("Lance d'abord une analyse.", erreur=True)
            return
        a = self.analyse
        chemin = config.DOSSIER_RESULTATS / (f"graphique_{a.symbole}_{a.intervalle}_"
                                             f"{pd.Timestamp.now():%Y-%m-%d_%Hh%M%S}.png")
        self.graphique.figure.savefig(chemin, facecolor=COULEURS["fond"])
        self.app.statut(f"Image enregistrée : {chemin}")
        try:
            os.startfile(chemin)
        except OSError:
            pass

    # ==================================================================
    def au_affichage(self):
        dispo = self.app.cryptos_disponibles()
        if dispo:
            self.crypto.configure(values=dispo)
        self._maj_echelles()

    def donnees_modifiees(self):
        self.au_affichage()

    def reglages(self) -> dict:
        return {"graphique_crypto": self.crypto.get().strip().upper(),
                "graphique_echelle": self.echelle.get().strip(),
                "graphique_source": self.source.get(),
                "graphique_bougies": int(cp.lire_nombre(self.saisie_bougies, 0)) or "",
                "graphique_debut": self.saisie_debut.get().strip(),
                "graphique_fin": self.saisie_fin.get().strip(),
                "graphique_types": self.choix.cochees(),
                "graphique_reglages": self.reglages_detection.valeurs(),
                "graphique_horizon": self.horizon(),
                "graphique_panneau": self.panneau.get(),
                **{f"graphique_{cle}": v.get() for cle, v in self.options.items()}}
