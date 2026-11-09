"""
Page « Données » : choisir les cryptos, les échelles et la profondeur, puis
télécharger (ou compléter) l'historique Binance. Les historiques de
CryptoSupertrend peuvent être importés plutôt que retéléchargés.
"""

from __future__ import annotations

import re

import customtkinter as ctk
import pandas as pd

from .. import config, donnees
from . import composants as cp
from .theme import COULEURS

PROFONDEURS = {"90 jours": 90, "1 an": 365, "2 ans": 730, "4 ans": 1461, "Tout": None}
REQUETES_PAR_SECONDE = 5          # mesuré : ~6 requêtes en parallèle, ~0,5 s chacune


class PageDonnees(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        r = app.reglages
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cp.titre_page(self, "Données",
                      "Historique des bougies Binance (paires en USDT), téléchargé une fois pour toutes. "
                      "Relancer complète ce qui manque, avant comme après : rien de ce qui est déjà "
                      "téléchargé n'est effacé. Les autres échelles (10m, 45m, 3h, 2d…) se construisent "
                      "ensuite à partir de celles-ci.").grid(row=0, column=0, columnspan=2,
                                                              sticky="w", pady=(0, 12))

        gauche = ctk.CTkScrollableFrame(self, width=430, fg_color="transparent")
        gauche.grid(row=1, column=0, sticky="nsw", padx=(0, 14))

        carte, dedans = cp.section(gauche, "Cryptos",
                                   "Symboles séparés par des espaces. Les stablecoins sont inutiles.")
        carte.pack(fill="x", pady=(0, 10))
        self.saisie_cryptos = ctk.CTkTextbox(dedans, height=64, wrap="word")
        self.saisie_cryptos.pack(fill="x")
        self.saisie_cryptos.insert("1.0", " ".join(r.get("cryptos", config.CRYPTOS_DEFAUT)))
        boutons = ctk.CTkFrame(dedans, fg_color="transparent")
        boutons.pack(fill="x", pady=(6, 0))
        for texte, commande in (("Liste par défaut", self._liste_defaut),
                                ("Top 10 du moment", lambda: self._top(10)),
                                ("Top 20 du moment", lambda: self._top(20))):
            cp.bouton_discret(boutons, texte, commande, largeur=120).pack(side="left", padx=(0, 6))

        carte, dedans = cp.section(gauche, "Échelles",
                                   "Durée d'une bougie. Pour les figures, 15m à 1w suffisent ; 1m et "
                                   "5m sont lourds (2 millions de bougies pour 4 ans en 1m).")
        carte.pack(fill="x", pady=(0, 10))
        self.cases_echelles = cp.ListeCases(dedans, list(config.MINUTES_PAR_INTERVALLE),
                                            r.get("echelles_telechargement", config.INTERVALLES_DEFAUT),
                                            colonnes=5, au_changement=self._estimer)
        self.cases_echelles.pack(fill="x")

        carte, dedans = cp.section(gauche, "Profondeur",
                                   "Jusqu'où remonter dans le passé. « Tout » : depuis l'ouverture "
                                   "de Binance (août 2017), ou la cotation de la crypto.")
        carte.pack(fill="x", pady=(0, 10))
        self.profondeur = ctk.StringVar(value=r.get("profondeur", "4 ans"))
        if self.profondeur.get() not in PROFONDEURS:
            self.profondeur.set("4 ans")
        ctk.CTkSegmentedButton(dedans, values=list(PROFONDEURS), variable=self.profondeur,
                               command=lambda _v: self._estimer()).pack(fill="x")
        self.estimation = ctk.CTkLabel(dedans, text="", justify="left", anchor="w", wraplength=380,
                                       text_color=COULEURS["texte_doux"])
        self.estimation.pack(fill="x", pady=(6, 0))

        actions = ctk.CTkFrame(gauche, fg_color="transparent")
        actions.pack(fill="x", pady=(4, 0))
        self.bouton = ctk.CTkButton(actions, text="Télécharger / mettre à jour", height=40,
                                    font=ctk.CTkFont(size=14, weight="bold"), command=self.telecharger)
        self.bouton.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(actions, text="Arrêter", width=90, height=40, fg_color=COULEURS["carte"],
                      hover_color=COULEURS["rouge"], command=self.arreter).pack(side="left", padx=(8, 0))

        if config.DOSSIER_VOISIN.is_dir():
            carte, dedans = cp.section(gauche, "Déjà téléchargé ailleurs ?",
                                       "CryptoSupertrend a ses propres historiques. Les importer les "
                                       "copie ici et les fusionne avec ceux d'ici, sans rien effacer.")
            carte.pack(fill="x", pady=(10, 0))
            ctk.CTkButton(dedans, text="Importer depuis CryptoSupertrend", height=32,
                          fg_color=COULEURS["carte"], hover_color=COULEURS["neutre"],
                          command=self.importer).pack(fill="x")

        droite = ctk.CTkFrame(self, fg_color="transparent")
        droite.grid(row=1, column=1, sticky="nsew")
        droite.grid_columnconfigure(0, weight=1)
        droite.grid_rowconfigure(0, weight=3)
        droite.grid_rowconfigure(1, weight=2)

        carte, dedans = cp.section(droite, "Déjà téléchargé",
                                   "Date de la première bougie de chaque échelle.")
        carte.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.tableau = cp.Tableau(dedans, hauteur=12)
        self.tableau.pack(fill="both", expand=True)

        carte, dedans = cp.section(droite, "Journal")
        carte.grid(row=1, column=0, sticky="nsew")
        self.zone_journal = ctk.CTkTextbox(dedans, font=ctk.CTkFont(family="Consolas", size=12),
                                           fg_color=COULEURS["carte"])
        self.zone_journal.pack(fill="both", expand=True)
        self.zone_journal.configure(state="disabled")

        self._estimer()
        self.afficher_inventaire()

    # ------------------------------------------------------------------
    def cryptos(self) -> list[str]:
        texte = self.saisie_cryptos.get("1.0", "end").upper()
        return list(dict.fromkeys(s for s in re.split(r"[\s,;]+", texte) if s))

    def _definir_cryptos(self, symboles):
        self.saisie_cryptos.delete("1.0", "end")
        self.saisie_cryptos.insert("1.0", " ".join(symboles))
        self._estimer()

    def _liste_defaut(self):
        self._definir_cryptos(config.CRYPTOS_DEFAUT)

    def _top(self, n):
        self.app.executer(lambda: donnees.top_cryptos(n), apres=self._definir_cryptos,
                          libelle=f"Classement CoinGecko (Top {n})")

    def _jours(self) -> float:
        jours = PROFONDEURS[self.profondeur.get()]
        if jours is None:
            jours = (donnees.maintenant_utc() - config.DEBUT_BINANCE).days
        return jours

    def _estimer(self):
        jours = self._jours()
        echelles = self.cases_echelles.cochees()
        requetes = sum(donnees.requetes_estimees(i, jours) for i in echelles) * len(self.cryptos())
        minutes = requetes / REQUETES_PAR_SECONDE / 60
        duree = f"{minutes:.0f} min" if minutes >= 1 else "moins d'une minute"
        nombre = f"{requetes:,}".replace(",", " ")
        self.estimation.configure(
            text=f"Au plus {nombre} requêtes, environ {duree} la première fois. "
                 "Ensuite, seules les bougies manquantes sont téléchargées.")

    def ajouter_journal(self, texte: str):
        self.zone_journal.configure(state="normal")
        self.zone_journal.insert("end", texte + "\n")
        self.zone_journal.see("end")
        self.zone_journal.configure(state="disabled")

    def afficher_inventaire(self):
        inv = self.app.inventaire()
        if inv.empty:
            self.tableau.remplir(pd.DataFrame({"": ["Rien de téléchargé pour l'instant."]}))
            return
        echelles = config.trier_intervalles(list(inv["Échelle"].unique()))
        debuts = inv.pivot(index="Symbole", columns="Échelle", values="Début (UTC)")[echelles]
        tableau = debuts.apply(lambda c: c.map(lambda d: "" if pd.isna(d) else f"{d:%Y-%m-%d}"))
        tableau.insert(0, "Crypto", tableau.index)
        tableau["À jour au (UTC)"] = inv.groupby("Symbole")["Fin (UTC)"].min().map(
            lambda d: f"{d:%d/%m %H:%M}")
        self.tableau.remplir(tableau.reset_index(drop=True), largeurs={c: 92 for c in echelles},
                             gauche=("Crypto",))

    # ------------------------------------------------------------------
    def telecharger(self):
        symboles = self.cryptos()
        echelles = config.trier_intervalles(self.cases_echelles.cochees())
        if not symboles or not echelles:
            self.app.statut("Choisis au moins une crypto et une échelle.", erreur=True)
            return
        tout = PROFONDEURS[self.profondeur.get()] is None
        jours = self._jours()
        app = self.app
        app.arret.clear()

        def travail():
            debut_analyse = (config.DEBUT_BINANCE if tout else
                             donnees.maintenant_utc().normalize() - pd.Timedelta(days=jours))
            total = len(symboles) * len(echelles)
            app.journal(f"Téléchargement : {len(symboles)} cryptos × {len(echelles)} échelles "
                        f"depuis le {debut_analyse:%Y-%m-%d}")
            for k, symbole in enumerate(symboles):
                for j, intervalle in enumerate(echelles):
                    fait = k * len(echelles) + j
                    debut = debut_analyse - config.BOUGIES_CHAUFFE * config.duree(intervalle)

                    def suivre(n, total_requetes, fait=fait, s=symbole, i=intervalle):
                        app.progression((fait + n / total_requetes) / total,
                                        f"{s} {i} : {n}/{total_requetes} requêtes")

                    app.progression(fait / total, f"{symbole} {intervalle}…")
                    try:
                        app.journal(donnees.mettre_a_jour(symbole, intervalle, debut, suivre, app.arret))
                    except donnees.PaireIndisponible as erreur:
                        app.journal(f"{symbole} : absente de Binance ({erreur}), ignorée.")
                        break
                    except donnees.Interrompu:
                        app.journal("Arrêté. Les échelles terminées sont enregistrées.")
                        return "arrêté"
                    except Exception as erreur:                     # noqa: BLE001
                        app.journal(f"{symbole} {intervalle} : échec ({erreur}). Arrêt.")
                        return "échec"
            app.journal("Terminé.")
            return "fini"

        app.executer(travail, apres=self._fin, libelle="Téléchargement")

    def importer(self):
        app = self.app

        def travail():
            donnees.importer_voisin(journal=app.journal)
            return "fini"

        app.executer(travail, apres=self._fin, libelle="Import depuis CryptoSupertrend")

    def arreter(self):
        self.app.arret.set()

    def _fin(self, resultat):
        self.app.donnees_modifiees()
        if resultat != "fini":
            self.app.statut(f"Téléchargement {resultat} : voir le journal.", erreur=resultat == "échec")

    def donnees_modifiees(self):
        self.afficher_inventaire()

    def reglages(self) -> dict:
        return {"cryptos": self.cryptos(), "echelles_telechargement": self.cases_echelles.cochees(),
                "profondeur": self.profondeur.get()}
