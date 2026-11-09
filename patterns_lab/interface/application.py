"""
Fenêtre principale : barre latérale, cinq pages, barre d'état.

Tout traitement long (téléchargement, analyse, recherche en direct,
statistiques) part dans un thread de travail via `executer()`, et seul le
thread graphique touche aux widgets : le thread de travail dépose ses messages
dans une file, que `_pomper` vide toutes les 80 ms. L'interface ne fige donc
jamais.
"""

from __future__ import annotations

import gc
import queue
import threading
import traceback

import customtkinter as ctk
import pandas as pd

from .. import config, donnees
from . import reglages, theme
from .page_catalogue import PageCatalogue
from .page_direct import PageDirect
from .page_donnees import PageDonnees
from .page_graphique import PageGraphique
from .page_stats import PageStats
from .theme import COULEURS

NAVIGATION = [
    ("donnees", "Données", "Télécharger l'historique"),
    ("graphique", "Graphique", "Les figures d'une crypto"),
    ("direct", "En ce moment", "Les figures qui se forment"),
    ("stats", "Statistiques", "Ce qui suit chaque figure"),
    ("catalogue", "Catalogue", "Toutes les figures expliquées"),
]


class Application(ctk.CTk):

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()
        config.preparer_dossiers()
        self.title("CryptoPatterns")
        self.geometry("1480x920")
        self.minsize(1240, 760)
        self.configure(fg_color=COULEURS["fond"])
        theme.configurer_tableaux()

        self.reglages = reglages.charger()
        self.file = queue.Queue()
        self.occupe = False
        self.arret = threading.Event()
        self._inventaire = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._barre_laterale()
        self.contenu = ctk.CTkFrame(self, fg_color="transparent")
        self.contenu.grid(row=0, column=1, sticky="nsew", padx=16, pady=(14, 6))
        self.contenu.grid_columnconfigure(0, weight=1)
        self.contenu.grid_rowconfigure(0, weight=1)
        self._barre_etat()

        self.pages = {
            "donnees": PageDonnees(self.contenu, self),
            "graphique": PageGraphique(self.contenu, self),
            "direct": PageDirect(self.contenu, self),
            "stats": PageStats(self.contenu, self),
            "catalogue": PageCatalogue(self.contenu, self),
        }
        self.page_active = None
        self.afficher("graphique" if not self.inventaire().empty else "donnees")
        self.after(80, self._pomper)
        self.protocol("WM_DELETE_WINDOW", self.fermer)

    # ==================================================================
    # STRUCTURE
    # ==================================================================
    def _barre_laterale(self):
        barre = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=COULEURS["panneau"])
        barre.grid(row=0, column=0, rowspan=2, sticky="nsew")
        barre.grid_propagate(False)
        ctk.CTkLabel(barre, text="Figures", font=ctk.CTkFont(size=24, weight="bold")
                     ).pack(pady=(26, 0), padx=20, anchor="w")
        ctk.CTkLabel(barre, text="chartistes · ranges · chandeliers", font=ctk.CTkFont(size=12),
                     text_color=COULEURS["texte_doux"]).pack(padx=20, anchor="w", pady=(0, 24))
        self.boutons = {}
        for cle, libelle, aide in NAVIGATION:
            bouton = ctk.CTkButton(barre, text=f"{libelle}\n{aide}", anchor="w", height=54,
                                   corner_radius=8, fg_color="transparent",
                                   hover_color=COULEURS["carte"], font=ctk.CTkFont(size=13),
                                   command=lambda c=cle: self.afficher(c))
            bouton.pack(fill="x", padx=12, pady=3)
            self.boutons[cle] = bouton
        ctk.CTkLabel(barre, justify="left", wraplength=190, font=ctk.CTkFont(size=11),
                     text_color=COULEURS["texte_doux"],
                     text=("Vert : figure haussière.\nRouge : baissière.\nBleu : neutre, c'est la "
                           "cassure qui décide.\n\nUne figure n'est datée qu'au moment où elle "
                           "devient visible sur le graphique : aucun regard vers le futur.")
                     ).pack(side="bottom", padx=20, pady=20, anchor="w")

    def _barre_etat(self):
        barre = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=COULEURS["panneau"])
        barre.grid(row=1, column=1, sticky="ew")
        self.texte_statut = ctk.CTkLabel(barre, text="Prêt.", anchor="w",
                                         text_color=COULEURS["texte_doux"])
        self.texte_statut.pack(side="left", padx=14, fill="x", expand=True)
        self.barre_progression = ctk.CTkProgressBar(barre, width=260)
        self.barre_progression.set(0)
        self.barre_progression.pack(side="right", padx=14)

    def afficher(self, cle: str):
        if self.page_active is not None:
            self.pages[self.page_active].grid_remove()
        self.page_active = cle
        self.pages[cle].grid(row=0, column=0, sticky="nsew")
        for c, bouton in self.boutons.items():
            bouton.configure(fg_color=COULEURS["accent"] if c == cle else "transparent")
        if hasattr(self.pages[cle], "au_affichage"):
            self.pages[cle].au_affichage()

    def ouvrir_analyse(self, analyse, selection=None):
        """Montre une analyse (venue de « En ce moment » ou des statistiques) dans la page Graphique."""
        self.afficher("graphique")
        self.pages["graphique"].montrer(analyse, selection)

    # ==================================================================
    # TÂCHES EN ARRIÈRE-PLAN
    # ==================================================================
    def executer(self, fonction, apres=None, libelle: str = "", silencieux: bool = False) -> bool:
        """
        Lance `fonction()` dans un thread ; `apres(resultat)` est ensuite appelé
        dans le thread graphique. Une seule tâche à la fois.
        """
        if self.occupe:
            if not silencieux:
                self.statut("Une tâche est déjà en cours, attends qu'elle se termine.", erreur=True)
            return False
        self.occupe = True
        self.statut(f"{libelle}…")
        self.barre_progression.set(0)
        # Les variables et polices Tk des widgets détruits doivent disparaître
        # ici, dans le thread graphique (sinon : « main thread is not in main loop »).
        gc.collect()

        def travail():
            try:
                resultat = fonction()
                self.file.put(("fini", apres, resultat))
            except Exception as erreur:                 # noqa: BLE001
                traceback.print_exc()
                self.file.put(("erreur", libelle, erreur))

        threading.Thread(target=travail, daemon=True).start()
        return True

    def progression(self, fraction: float, texte: str = ""):
        """Appelable depuis le thread de travail."""
        self.file.put(("progression", fraction, texte))

    def journal(self, texte: str):
        """Ligne pour le journal de la page Données ; appelable depuis le thread de travail."""
        self.file.put(("journal", texte, None))

    def statut(self, texte: str, erreur: bool = False):
        self.texte_statut.configure(text=texte,
                                    text_color=COULEURS["rouge"] if erreur else COULEURS["texte_doux"])

    def _pomper(self):
        try:
            while True:
                genre, a, b = self.file.get_nowait()
                if genre == "progression":
                    self.barre_progression.set(max(0.0, min(1.0, a)))
                    if b:
                        self.statut(b)
                elif genre == "journal":
                    self.pages["donnees"].ajouter_journal(a)
                elif genre == "fini":
                    self.occupe = False
                    self.barre_progression.set(1)
                    self.statut("Terminé.")
                    if a is not None:
                        try:
                            a(b)
                        except Exception as erreur:     # noqa: BLE001
                            traceback.print_exc()
                            self.statut(f"Affichage : échec — {erreur}", erreur=True)
                elif genre == "erreur":
                    self.occupe = False
                    self.barre_progression.set(0)
                    self.statut(f"{a} : échec — {b}", erreur=True)
        except queue.Empty:
            pass
        self.after(80, self._pomper)

    # ==================================================================
    # DONNÉES DISPONIBLES
    # ==================================================================
    def inventaire(self, rafraichir: bool = False) -> pd.DataFrame:
        if self._inventaire is None or rafraichir:
            self._inventaire = donnees.inventaire()
        return self._inventaire

    def cryptos_disponibles(self) -> list[str]:
        inv = self.inventaire()
        return sorted(inv["Symbole"].unique()) if not inv.empty else []

    def intervalles_disponibles(self, symbole: str | None = None) -> list[str]:
        inv = self.inventaire()
        if inv.empty:
            return []
        if symbole:
            inv = inv[inv["Symbole"] == symbole]
        return config.trier_intervalles(list(inv["Échelle"].unique()))

    def donnees_modifiees(self):
        """Après un téléchargement : chaque page met à jour ses listes."""
        self.inventaire(rafraichir=True)
        for page in self.pages.values():
            if hasattr(page, "donnees_modifiees"):
                page.donnees_modifiees()

    # ==================================================================
    def fermer(self):
        self.arret.set()
        for page in self.pages.values():
            if hasattr(page, "reglages"):
                try:
                    self.reglages.update(page.reglages())
                except Exception:                       # noqa: BLE001
                    traceback.print_exc()
        reglages.enregistrer(self.reglages)
        self.destroy()


def lancer():
    app = Application()
    app.state("zoomed")              # fenêtre agrandie sous Windows
    app.mainloop()
