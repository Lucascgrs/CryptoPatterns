"""
Page « En ce moment » : quelles figures viennent de se confirmer, ou sont en
train de se former, sur plusieurs cryptos et plusieurs échelles à la fois ?

Les dernières bougies terminées sont lues sur Binance à l'instant (rien n'est
enregistré). Un double-clic ouvre la figure dans la page Graphique.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
import numpy as np
import pandas as pd

from .. import config, detection, donnees
from ..figures import CONFIRMEE, EN_FORMATION
from . import composants as cp
from .theme import COULEURS

ECHELLES_DEFAUT = ["15m", "1h", "4h", "1d"]


class PageDirect(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        r = app.reglages
        self.analyses = {}
        self._minuterie = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cp.titre_page(self, "En ce moment",
                      "Les figures qui viennent de se confirmer ou qui se forment, lues sur Binance à "
                      "l'instant, pour toutes les cryptos et échelles choisies. Seules les bougies "
                      "terminées comptent. Double-clic sur une ligne : la figure dans la page Graphique."
                      ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        gauche = ctk.CTkScrollableFrame(self, width=360, fg_color="transparent")
        gauche.grid(row=1, column=0, sticky="nsw", padx=(0, 12))

        carte, dedans = cp.section(gauche, "Cryptos", "Symboles séparés par des espaces.")
        carte.pack(fill="x", pady=(0, 10))
        self.saisie_cryptos = ctk.CTkTextbox(dedans, height=56, wrap="word")
        self.saisie_cryptos.pack(fill="x")
        self.saisie_cryptos.insert("1.0", " ".join(r.get("direct_cryptos", config.CRYPTOS_DEFAUT)))
        boutons = ctk.CTkFrame(dedans, fg_color="transparent")
        boutons.pack(fill="x", pady=(6, 0))
        cp.bouton_discret(boutons, "Téléchargées", self._telechargees, largeur=100).pack(side="left")
        cp.bouton_discret(boutons, "Top 10", lambda: self._top(10), largeur=70).pack(side="left", padx=6)
        cp.bouton_discret(boutons, "Top 20", lambda: self._top(20), largeur=70).pack(side="left")

        carte, dedans = cp.section(gauche, "Échelles")
        carte.pack(fill="x", pady=(0, 10))
        self.cases_echelles = cp.ListeCases(dedans, list(config.MINUTES_PAR_INTERVALLE),
                                            r.get("direct_echelles", ECHELLES_DEFAUT), colonnes=5)
        self.cases_echelles.pack(fill="x")
        self.saisie_autres = cp.champ(dedans, "Autres échelles", r.get("direct_autres", ""), largeur=120,
                                      aide="ex. 45m 2d")

        carte, dedans = cp.section(gauche, "Figures à chercher")
        carte.pack(fill="x", pady=(0, 10))
        self.choix = cp.ChoixFigures(dedans, r.get("direct_types"))
        self.choix.pack(fill="x")

        carte, dedans = cp.section(gauche, "Lesquelles montrer")
        carte.pack(fill="x", pady=(0, 10))
        self.saisie_recentes = cp.champ(dedans, "Confirmées depuis au plus (bougies)",
                                        r.get("direct_recentes", 3), largeur=56)
        self.formation = ctk.BooleanVar(value=r.get("direct_formation", True))
        ctk.CTkCheckBox(dedans, text="Montrer aussi celles en formation", variable=self.formation,
                        checkbox_width=18, checkbox_height=18).pack(anchor="w", pady=(4, 0))
        cp.note(dedans, "En formation : la figure est dessinée mais le prix n'a pas encore franchi le "
                        "niveau qui la confirme (colonne « Niveau » ; « Écart » = chemin qui reste).")

        carte, dedans = cp.section(gauche, "Réglages de la détection")
        carte.pack(fill="x", pady=(0, 10))
        self.reglages_detection = cp.ReglagesDetection(dedans, r.get("direct_reglages"))
        self.reglages_detection.pack(fill="x")

        ctk.CTkButton(gauche, text="Chercher maintenant", height=44,
                      font=ctk.CTkFont(size=15, weight="bold"), command=self.chercher
                      ).pack(fill="x", pady=(4, 6))
        ligne = ctk.CTkFrame(gauche, fg_color="transparent")
        ligne.pack(fill="x", pady=(0, 12))
        self.auto = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ligne, text="Recommencer toutes les", variable=self.auto, command=self._programmer,
                        checkbox_width=18, checkbox_height=18).pack(side="left")
        self.saisie_minutes = ctk.CTkEntry(ligne, width=46, justify="right")
        self.saisie_minutes.insert(0, str(r.get("direct_minutes", 15)))
        self.saisie_minutes.pack(side="left", padx=4)
        ctk.CTkLabel(ligne, text="minutes").pack(side="left")

        droite = ctk.CTkFrame(self, fg_color=COULEURS["panneau"], corner_radius=10)
        droite.grid(row=1, column=1, sticky="nsew")
        droite.grid_columnconfigure(0, weight=1)
        droite.grid_rowconfigure(1, weight=1)
        self.titre = ctk.CTkLabel(droite, text="Aucune recherche pour l'instant.", anchor="w",
                                  font=ctk.CTkFont(size=13, weight="bold"))
        self.titre.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        self.tableau = cp.Tableau(droite, hauteur=20, au_double_clic=self._ouvrir)
        self.tableau.grid(row=1, column=0, sticky="nsew", padx=10)
        cp.note(droite, "Il y a : nombre de bougies depuis la confirmation. Niveau : le prix à franchir "
                        "pour confirmer une figure en formation ; Écart : ce qu'il reste à parcourir. "
                        "Objectif et invalidation : voir le catalogue. Dates en UTC.",
                largeur=900, emballer=False).grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 10))

    # ==================================================================
    def cryptos(self) -> list[str]:
        texte = self.saisie_cryptos.get("1.0", "end").upper()
        return list(dict.fromkeys(s for s in re.split(r"[\s,;]+", texte) if s))

    def _definir_cryptos(self, symboles):
        self.saisie_cryptos.delete("1.0", "end")
        self.saisie_cryptos.insert("1.0", " ".join(symboles))

    def _telechargees(self):
        dispo = self.app.cryptos_disponibles()
        if dispo:
            self._definir_cryptos(dispo)

    def _top(self, n):
        self.app.executer(lambda: donnees.top_cryptos(n), apres=self._definir_cryptos,
                          libelle=f"Classement CoinGecko (Top {n})")

    def echelles(self) -> list[str]:
        autres = [e for e in re.split(r"[\s,;]+", self.saisie_autres.get()) if e]
        return config.trier_intervalles(self.cases_echelles.cochees() + autres)

    # ==================================================================
    def chercher(self, automatique: bool = False):
        symboles = self.cryptos()
        try:
            echelles = self.echelles()
            reglages = detection.Reglages(**self.reglages_detection.valeurs(), types=self.choix.cochees())
            reglages.verifier()
        except ValueError as erreur:
            self.app.statut(str(erreur), erreur=True)
            return
        if not symboles or not echelles or not reglages.types:
            self.app.statut("Choisis au moins une crypto, une échelle et une figure.", erreur=True)
            return
        recentes = int(cp.lire_nombre(self.saisie_recentes, 3))
        formation = self.formation.get()
        app = self.app
        travaux = [(s, e) for s in symboles for e in echelles]

        def un(travail):
            symbole, echelle = travail
            try:
                bougies, provenance = donnees.bougies_direct(symbole, echelle)
            except donnees.PaireIndisponible:
                return travail, None, "absente de Binance"
            if len(bougies) < 50:
                return travail, None, "trop peu de bougies"
            return travail, detection.analyser(bougies, reglages, symbole, echelle, provenance), ""

        def travail():
            analyses, absentes = {}, []
            with ThreadPoolExecutor(config.REQUETES_PARALLELES) as pool:
                for k, (cle, analyse, raison) in enumerate(pool.map(un, travaux)):
                    app.progression((k + 1) / len(travaux), f"{cle[0]} {cle[1]} ({k + 1}/{len(travaux)})")
                    if analyse is None:
                        absentes.append(f"{cle[0]} {cle[1]} ({raison})")
                    else:
                        analyses[cle] = analyse
            return analyses, absentes, self._lignes(analyses, recentes, formation)

        lance = app.executer(travail, apres=self._resultats, libelle="Recherche en direct",
                             silencieux=automatique)
        if not lance and automatique:
            self._programmer()            # occupé : on réessaiera au prochain tour

    @staticmethod
    def _lignes(analyses, recentes, formation) -> pd.DataFrame:
        lignes = []
        for (symbole, echelle), a in analyses.items():
            c = a.bougies["Close"].to_numpy()
            dernier = a.n - 1
            for k, f in enumerate(a.figures):
                if f.statut == CONFIRMEE and f.signal is not None and dernier - f.signal <= recentes:
                    il_y_a = dernier - f.signal
                elif f.statut == EN_FORMATION and formation:
                    il_y_a = np.nan
                else:
                    continue
                ecart = f.niveau / c[-1] - 1 if f.statut == EN_FORMATION and np.isfinite(f.niveau) else np.nan
                lignes.append({
                    "Crypto": symbole, "Échelle": echelle, "Figure": f.nom_complet,
                    "Sens": {1: "▲", -1: "▼"}.get(f.sens, "?"), "Statut": f.statut,
                    "Il y a": il_y_a, "Date": a.date(f.signal if f.signal is not None else f.fin),
                    "Prix": float(c[-1]), "Niveau": f.niveau if f.statut == EN_FORMATION else np.nan,
                    "Écart": ecart, "Objectif": f.objectif, "Invalidation": f.invalidation,
                    "_cle": (symbole, echelle), "_k": k,
                })
        df = pd.DataFrame(lignes)
        if not df.empty:
            df = df.sort_values(["Statut", "Il y a", "Crypto"], na_position="last").reset_index(drop=True)
        return df

    def _resultats(self, retour):
        self.analyses, absentes, lignes = retour
        moment = pd.Timestamp.now()
        nb = 0 if lignes.empty else len(lignes)
        self.titre.configure(text=f"Recherche de {moment:%H:%M} (heure locale) · {len(self.analyses)} "
                                  f"graphiques · {nb} figures")
        if lignes.empty:
            self.tableau.remplir(pd.DataFrame({"": ["Aucune figure récente ou en formation."]}))
        else:
            self.tableau.remplir(
                lignes, gauche=("Figure",),
                formats={"Il y a": lambda v: "en cours" if pd.isna(v) else f"{int(v)} bg",
                         "Date": cp.date_courte, "Prix": cp.prix, "Niveau": cp.prix, "Écart": cp.pct,
                         "Objectif": cp.prix, "Invalidation": cp.prix},
                largeurs={"Crypto": 70, "Échelle": 64, "Figure": 220, "Sens": 46, "Statut": 96,
                          "Il y a": 70, "Date": 118, "Prix": 90, "Niveau": 90, "Écart": 76,
                          "Objectif": 90, "Invalidation": 90},
                couleur=lambda l: "gris" if l["Statut"] != CONFIRMEE else
                ("vert" if l["Sens"] == "▲" else "rouge" if l["Sens"] == "▼" else None))
        message = f"Recherche terminée : {nb} figures."
        if absentes:
            message += f" Ignorées : {', '.join(absentes[:6])}" + ("…" if len(absentes) > 6 else ".")
        self.app.statut(message)
        self._programmer()

    def _ouvrir(self, cle):
        df = self.tableau.df
        if df is None or "_cle" not in df.columns:
            return
        ligne = df.loc[cle]
        analyse = self.analyses.get(ligne["_cle"])
        if analyse is not None:
            self.app.ouvrir_analyse(analyse, int(ligne["_k"]))

    def _programmer(self):
        if self._minuterie is not None:
            self.after_cancel(self._minuterie)
            self._minuterie = None
        if self.auto.get():
            minutes = max(1.0, cp.lire_nombre(self.saisie_minutes, 15))
            self._minuterie = self.after(int(minutes * 60_000), lambda: self.chercher(automatique=True))

    # ==================================================================
    def reglages(self) -> dict:
        return {"direct_cryptos": self.cryptos(), "direct_echelles": self.cases_echelles.cochees(),
                "direct_autres": self.saisie_autres.get().strip(), "direct_types": self.choix.cochees(),
                "direct_recentes": int(cp.lire_nombre(self.saisie_recentes, 3)),
                "direct_formation": self.formation.get(),
                "direct_reglages": self.reglages_detection.valeurs(),
                "direct_minutes": cp.lire_nombre(self.saisie_minutes, 15)}
