"""
Page « Statistiques » : sur tout l'historique téléchargé, que s'est-il passé
après chaque sorte de figure ? Comparé au hasard, sur chaque moitié de la
période, et avec une règle de trade fixe (voir `statistiques.py`).
"""

from __future__ import annotations

import os
import re

import customtkinter as ctk
import numpy as np
import pandas as pd

from .. import config, dessin, detection, donnees, rapport, statistiques
from . import composants as cp
from .composants import ZoneGraphique
from .theme import COULEURS, legende

REGROUPEMENTS = {"Figure": [], "Figure × échelle": ["Échelle"], "Figure × crypto": ["Crypto"]}
EXEMPLES_MIN = 30           # en dessous, le résultat dépend trop de quelques cas


class PageStats(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        r = app.reglages
        self.analyses = {}
        self.occurrences = pd.DataFrame()
        self.toutes = pd.DataFrame()
        self.parametres = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cp.titre_page(self, "Statistiques",
                      "Que fait le prix après chaque figure ? Pour chaque sorte de figure, sur tout "
                      "l'historique choisi : combien de fois le prix est allé dans le sens attendu, "
                      "comparé au hasard, et ce qu'aurait donné une règle de trade simple."
                      ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        gauche = ctk.CTkScrollableFrame(self, width=360, fg_color="transparent")
        gauche.grid(row=1, column=0, sticky="nsw", padx=(0, 12))

        carte, dedans = cp.section(gauche, "Cryptos")
        carte.pack(fill="x", pady=(0, 10))
        dispo = app.cryptos_disponibles()
        self.cases_cryptos = cp.ListeCases(dedans, dispo, r.get("stats_cryptos", dispo), colonnes=4)
        self.cases_cryptos.pack(fill="x")

        carte, dedans = cp.section(gauche, "Échelles", "Les échelles téléchargées, et d'autres à "
                                                       "construire (ex. 45m 2d).")
        carte.pack(fill="x", pady=(0, 10))
        echelles = app.intervalles_disponibles()
        self.cases_echelles = cp.ListeCases(dedans, echelles, r.get("stats_echelles", [
            e for e in ("1h", "4h", "1d") if e in echelles]), colonnes=5)
        self.cases_echelles.pack(fill="x")
        self.saisie_autres = cp.champ(dedans, "Autres échelles", r.get("stats_autres", ""), largeur=120,
                                      aide="ex. 45m 2d")

        carte, dedans = cp.section(gauche, "Figures")
        carte.pack(fill="x", pady=(0, 10))
        self.choix = cp.ChoixFigures(dedans, r.get("stats_types", list(detection.TOUS_LES_TYPES)))
        self.choix.pack(fill="x")

        carte, dedans = cp.section(gauche, "Mesure")
        carte.pack(fill="x", pady=(0, 10))
        self.saisie_horizon = cp.champ(dedans, "Juger après (bougies)", r.get("stats_horizon", config.HORIZON),
                                       largeur=64)
        self.saisie_frais = cp.champ(dedans, "Frais par ordre (%)", r.get("stats_frais", config.FRAIS_PCT),
                                     largeur=64)
        self.saisie_debut = cp.champ(dedans, "Début (AAAA-MM-JJ)", r.get("stats_debut", ""), largeur=110,
                                     aide="tout")
        self.saisie_fin = cp.champ(dedans, "Fin (AAAA-MM-JJ)", r.get("stats_fin", ""), largeur=110,
                                   aide="tout")
        cp.note(dedans, "Le trade : entrée à la clôture du signal, sortie à l'objectif, à l'invalidation "
                        "ou au bout de N bougies. Les frais sont payés deux fois.")

        carte, dedans = cp.section(gauche, "Réglages de la détection")
        carte.pack(fill="x", pady=(0, 10))
        self.reglages_detection = cp.ReglagesDetection(dedans, r.get("stats_reglages"))
        self.reglages_detection.pack(fill="x")

        ctk.CTkButton(gauche, text="Calculer", height=44, font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.lancer).pack(fill="x", pady=(4, 4))
        cp.note(gauche, "Quelques secondes par crypto et par échelle ; compter une minute pour 4 ans "
                        "en 1m.")

        # ======================== DROITE ========================
        droite = ctk.CTkFrame(self, fg_color=COULEURS["panneau"], corner_radius=10)
        droite.grid(row=1, column=1, sticky="nsew")
        droite.grid_columnconfigure(0, weight=1)
        droite.grid_rowconfigure(1, weight=1)
        entete = ctk.CTkFrame(droite, fg_color="transparent")
        entete.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        self.titre = ctk.CTkLabel(entete, text="Aucun calcul lancé.", anchor="w", justify="left",
                                  wraplength=700, font=ctk.CTkFont(size=13, weight="bold"))
        self.titre.pack(side="left", fill="x", expand=True)
        self.regroupement = ctk.StringVar(value=r.get("stats_regroupement", "Figure"))
        ctk.CTkSegmentedButton(entete, values=list(REGROUPEMENTS), variable=self.regroupement,
                               command=lambda _v: self._afficher()).pack(side="right")

        self.onglets = ctk.CTkTabview(droite, fg_color=COULEURS["panneau"])
        self.onglets.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        for nom in ("Résumé", "Graphique", "Occurrences"):
            self.onglets.add(nom)

        resume = self.onglets.tab("Résumé")
        self.tableau = cp.Tableau(resume, hauteur=16)
        self.tableau.pack(fill="both", expand=True)
        cp.note(resume, largeur=1000, texte=(
            "Repérées : figures terminées (confirmées, invalidées ou sans cassure) ; pour une figure "
            "neutre, le total des deux sens. Confirmées : celles qui ont cassé dans ce sens. Bon sens : "
            "part des cas où le prix, N bougies après le signal, est allé dans le sens attendu ; Hasard : "
            "la même chose pour n'importe quelle bougie du même historique ; Écart = Bon sens − Hasard, "
            "en points. Objectif / Invalidée : premier niveau touché dans les N bougies. Trade net : la "
            "règle de trade, frais déduits. Écart 1re / 2e moitié : l'écart sur chaque moitié de la "
            "période. Vert : meilleur que le hasard sur les deux moitiés et trade gagnant en moyenne. "
            f"Gris : moins de {EXEMPLES_MIN} exemples, résultat peu fiable.")).pack(fill="x", pady=(6, 4))
        boutons = ctk.CTkFrame(resume, fg_color="transparent")
        boutons.pack(fill="x")
        ctk.CTkButton(boutons, text="Exporter en Excel", width=150, command=self.exporter).pack(side="left")
        cp.bouton_discret(boutons, "Ouvrir le dossier des résultats",
                          lambda: os.startfile(config.DOSSIER_RESULTATS), largeur=200).pack(side="left", padx=8)

        self.graphique = ZoneGraphique(self.onglets.tab("Graphique"), taille=(8, 6), barre_outils=False,
                                       disposition="constrained")
        self.graphique.pack(fill="both", expand=True)

        occ = self.onglets.tab("Occurrences")
        self.tableau_occ = cp.Tableau(occ, hauteur=18, au_double_clic=self._ouvrir)
        self.tableau_occ.pack(fill="both", expand=True)
        self.note_occ = cp.note(occ, "", largeur=1000)

    # ==================================================================
    def echelles(self) -> list[str]:
        autres = [e for e in re.split(r"[\s,;]+", self.saisie_autres.get()) if e]
        return config.trier_intervalles(self.cases_echelles.cochees() + autres)

    def lancer(self):
        symboles = self.cases_cryptos.cochees()
        try:
            echelles = self.echelles()
            reglages = detection.Reglages(**self.reglages_detection.valeurs(), types=self.choix.cochees())
            reglages.verifier()
            debut, fin = cp.lire_date(self.saisie_debut), cp.lire_date(self.saisie_fin)
        except ValueError as erreur:
            self.app.statut(str(erreur), erreur=True)
            return
        if not symboles or not echelles or not reglages.types:
            self.app.statut("Coche au moins une crypto, une échelle et une figure.", erreur=True)
            return
        horizon = max(1, int(cp.lire_nombre(self.saisie_horizon, config.HORIZON)))
        frais = cp.lire_nombre(self.saisie_frais, config.FRAIS_PCT) / 100
        app = self.app
        travaux = [(s, e) for s in symboles for e in echelles]

        def travail():
            analyses, occurrences, toutes, absentes = {}, [], [], []
            for k, (symbole, echelle) in enumerate(travaux):
                app.progression(k / len(travaux), f"{symbole} {echelle} ({k + 1}/{len(travaux)})")
                try:
                    bougies, provenance = donnees.charger(symbole, echelle)
                except donnees.DonneesAbsentes:
                    absentes.append(f"{symbole} {echelle}")
                    continue
                if debut is not None:
                    bougies = bougies[bougies.index >= debut]
                if fin is not None:
                    bougies = bougies[bougies.index < fin + pd.Timedelta(days=1)]
                if len(bougies) < 100:
                    absentes.append(f"{symbole} {echelle}")
                    continue
                a = detection.analyser(bougies, reglages, symbole, echelle, provenance)
                analyses[(symbole, echelle)] = a
                occurrences.append(statistiques.evaluer(a, horizon, frais))
                toutes.append(statistiques.reperees(a))
            occ = pd.concat(occurrences, ignore_index=True) if occurrences else pd.DataFrame()
            tout = pd.concat(toutes, ignore_index=True) if toutes else pd.DataFrame()
            return analyses, occ, tout, absentes, (horizon, frais, reglages)

        app.executer(travail, apres=self._resultats, libelle="Statistiques")

    def _resultats(self, retour):
        self.analyses, self.occurrences, self.toutes, absentes, self.parametres = retour
        horizon, frais, _reglages = self.parametres
        if self.occurrences.empty:
            self.titre.configure(text="Aucune figure confirmée avec ces réglages.")
            self.tableau.remplir(pd.DataFrame())
            self.app.statut("Rien à mesurer." + (f" Absentes : {', '.join(absentes)}." if absentes else ""),
                            erreur=bool(absentes))
            return
        periode = (f"du {self.occurrences['Signal'].min():%d/%m/%Y} au "
                   f"{self.occurrences['Signal'].max():%d/%m/%Y}")
        self.titre.configure(text=(
            f"{cp.entier(len(self.occurrences))} figures confirmées, {periode} · {len(self.analyses)} "
            f"séries (crypto × échelle) · jugées après {horizon} bougies · frais "
            f"{cp.decimal(frais * 100, 2).rstrip('0').rstrip(',')} % par ordre"))
        self._afficher()
        message = "Statistiques calculées."
        if absentes:
            message += f" Sans données : {', '.join(absentes[:8])}" + ("…" if len(absentes) > 8 else ".")
        self.app.statut(message, erreur=False)

    # ==================================================================
    def _resume(self) -> pd.DataFrame:
        return statistiques.resumer(self.occurrences, self.toutes, REGROUPEMENTS[self.regroupement.get()])

    def _afficher(self):
        if self.occurrences.empty:
            return
        resume = self._resume()
        pourcents = {c: cp.pct_simple for c in ("Bon sens", "Hasard", "Objectif atteint", "Invalidée",
                                               "Trades gagnants")}
        ecarts = {c: cp.points for c in ("Écart", "Écart 1re moitié", "Écart 2e moitié")}
        variations = {c: (lambda v: cp.pct(v, 2)) for c in ("Variation moyenne", "Hasard moyen",
                                                             "Trade net moyen")}
        formats = {**pourcents, **ecarts, **variations,
                   **{c: cp.entier for c in ("Repérées", "Confirmées", "Évaluées")}}

        def couleur(ligne):
            if ligne["Évaluées"] < EXEMPLES_MIN:
                return "gris"
            if ligne["Écart 1re moitié"] > 0 and ligne["Écart 2e moitié"] > 0 and ligne["Trade net moyen"] > 0:
                return "vert"
            if ligne["Écart 1re moitié"] < 0 and ligne["Écart 2e moitié"] < 0:
                return "rouge"
            return None

        self.tableau.remplir(resume.drop(columns=["Famille"]), formats=formats, couleur=couleur,
                             gauche=("Figure", "Crypto", "Échelle"), garder_tri=True,
                             largeurs={"Figure": 230, "Sens": 46, "Crypto": 64, "Échelle": 64,
                                       "Repérées": 74, "Confirmées": 84, "Évaluées": 74,
                                       "Bon sens": 74, "Hasard": 66, "Écart": 80,
                                       "Variation moyenne": 90, "Hasard moyen": 90,
                                       "Objectif atteint": 86, "Invalidée": 76, "Trade net moyen": 96,
                                       "Trades gagnants": 90, "Écart 1re moitié": 104,
                                       "Écart 2e moitié": 104})
        self._graphique()
        occ = self.occurrences
        vue = occ[["Crypto", "Échelle", "Figure", "Sens", "Signal", "Prix", "Après N", "Issue",
                   "Trade net", "Moitié", "_k"]].copy()
        vue["Sens"] = vue["Sens"].map({1: "▲", -1: "▼"})
        vue = vue.sort_values("Signal", ascending=False)
        horizon = self.parametres[0]
        self.tableau_occ.remplir(
            vue, gauche=("Figure",),
            formats={"Signal": cp.date_courte, "Prix": cp.prix, "Après N": cp.pct, "Trade net": cp.pct},
            largeurs={"Crypto": 64, "Échelle": 64, "Figure": 230, "Sens": 46, "Signal": 118,
                      "Prix": 90, "Après N": 80, "Issue": 90, "Trade net": 80, "Moitié": 60},
            couleur=lambda l: "vert" if l["Après N"] > 0 else "rouge")
        texte = (f"{len(vue):,} figures. Après N : variation {horizon} bougies après le signal, dans le "
                 "sens attendu. Double-clic : la figure dans la page Graphique.").replace(",", " ")
        if len(vue) > self.tableau_occ.max_lignes:
            texte += f" Seules les {self.tableau_occ.max_lignes} plus récentes sont listées (l'export Excel les a toutes)."
        self.note_occ.configure(text=texte)

    def _graphique(self):
        """Écart au hasard de chaque figure, avec les deux moitiés."""
        resume = statistiques.resumer(self.occurrences, self.toutes)
        resume = resume[resume["Évaluées"] >= EXEMPLES_MIN].sort_values("Écart")
        fig = self.graphique.figure
        fig.clear()
        ax = fig.add_subplot()
        dessin.styliser(ax)
        if resume.empty:
            ax.text(0.5, 0.5, f"Aucune figure n'a au moins {EXEMPLES_MIN} exemples.", ha="center",
                    va="center", color=COULEURS["texte_doux"], transform=ax.transAxes)
            self.graphique.redessiner()
            return
        y = np.arange(len(resume))
        teintes = [COULEURS["vert"] if v > 0 else COULEURS["rouge"] for v in resume["Écart"]]
        ax.barh(y, resume["Écart"] * 100, color=teintes, alpha=0.75, height=0.6, label="Toute la période")
        ax.scatter(resume["Écart 1re moitié"] * 100, y, marker="|", s=90, color="white", label="1re moitié", zorder=3)
        ax.scatter(resume["Écart 2e moitié"] * 100, y, marker="|", s=90, color=COULEURS["orange"],
                   label="2e moitié", zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{f} ({n})" for f, n in zip(resume["Figure"], resume["Évaluées"])], fontsize=8)
        ax.axvline(0, color="#888888", lw=0.8)
        ax.set_xlabel("Écart au hasard (points de % de cas dans le bon sens)")
        ax.set_title(f"Mieux ou moins bien que le hasard ? (figures avec au moins {EXEMPLES_MIN} exemples)",
                     fontsize=10, loc="left")
        legende(ax, loc="lower right")
        self.graphique.redessiner()

    def _ouvrir(self, cle):
        ligne = self.tableau_occ.df.loc[cle]
        analyse = self.analyses.get((ligne["Crypto"], ligne["Échelle"]))
        if analyse is not None:
            self.app.ouvrir_analyse(analyse, int(ligne["_k"]))

    def exporter(self):
        if self.occurrences.empty:
            self.app.statut("Lance d'abord un calcul.", erreur=True)
            return
        horizon, frais, reglages = self.parametres
        feuilles = {"Par figure": statistiques.resumer(self.occurrences, self.toutes),
                    "Par figure et échelle": statistiques.resumer(self.occurrences, self.toutes, ["Échelle"]),
                    "Par figure et crypto": statistiques.resumer(self.occurrences, self.toutes, ["Crypto"]),
                    "Occurrences": self.occurrences.drop(columns=["_k"]).tail(1_000_000)}
        chemin = config.DOSSIER_RESULTATS / f"statistiques_{pd.Timestamp.now():%Y-%m-%d_%Hh%M%S}.xlsx"
        rapport.ecrire_excel(chemin, feuilles, [
            "Ce qui suit chaque figure",
            f"Jugé {horizon} bougies après le signal. Frais : {frais * 100:g} % par ordre.",
            f"Réglages : vagues de {reglages.sensibilite:g} ATR, tolérance {reglages.tolerance:g} %, "
            f"range {reglages.range_largeur:g} ATR sur {reglages.range_duree} bougies.",
            "Bon sens : part des cas où le prix est allé dans le sens attendu. Hasard : la même chose "
            "pour toutes les bougies du même historique. Écart : la différence, en points.",
            "Trade : entrée à la clôture du signal, sortie à l'objectif, à l'invalidation ou au bout "
            "de N bougies (au premier des trois ; l'invalidation l'emporte si les deux sont touchés "
            "dans la même bougie).",
        ])
        self.app.statut(f"Exporté : {chemin}")

    # ==================================================================
    def donnees_modifiees(self):
        dispo = self.app.cryptos_disponibles()
        coches = self.cases_cryptos.cochees()
        self.cases_cryptos.definir(dispo, coches + [c for c in dispo if c not in self.cases_cryptos.variables])
        echelles = self.app.intervalles_disponibles()
        self.cases_echelles.definir(echelles, self.cases_echelles.cochees())

    def reglages(self) -> dict:
        return {"stats_cryptos": self.cases_cryptos.cochees(), "stats_echelles": self.cases_echelles.cochees(),
                "stats_autres": self.saisie_autres.get().strip(), "stats_types": self.choix.cochees(),
                "stats_horizon": int(cp.lire_nombre(self.saisie_horizon, config.HORIZON)),
                "stats_frais": cp.lire_nombre(self.saisie_frais, config.FRAIS_PCT),
                "stats_debut": self.saisie_debut.get().strip(), "stats_fin": self.saisie_fin.get().strip(),
                "stats_reglages": self.reglages_detection.valeurs(),
                "stats_regroupement": self.regroupement.get()}
