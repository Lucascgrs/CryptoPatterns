"""
Page « Catalogue » : chaque figure, son dessin type, ce qu'elle annonce et la
règle exacte avec laquelle le programme la reconnaît.
"""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from .. import dessin
from ..figures import CATALOGUE, FAMILLES, nom_sens, types_de
from . import composants as cp
from . import schemas
from .composants import ZoneGraphique
from .theme import COULEURS


class PageCatalogue(ctk.CTkFrame):

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cp.titre_page(self, "Catalogue",
                      f"Les {len(CATALOGUE)} figures que le programme sait reconnaître, avec leur dessin "
                      "type et la règle exacte qu'il applique."
                      ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        cadre = ctk.CTkFrame(self, fg_color=COULEURS["panneau"], corner_radius=10, width=300)
        cadre.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
        cadre.grid_propagate(False)
        cadre.grid_rowconfigure(0, weight=1)
        cadre.grid_columnconfigure(0, weight=1)
        self.arbre = ttk.Treeview(cadre, show="tree", selectmode="browse")
        self.arbre.column("#0", width=270)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=self.arbre.yview)
        self.arbre.configure(yscrollcommand=defilement.set)
        self.arbre.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        defilement.grid(row=0, column=1, sticky="ns", pady=8)
        for famille in FAMILLES:
            self.arbre.insert("", "end", iid=f"famille:{famille}", text=famille, open=True)
            for type_ in types_de(famille):
                self.arbre.insert(f"famille:{famille}", "end", iid=type_, text=CATALOGUE[type_].nom)
        self.arbre.bind("<<TreeviewSelect>>", lambda _e: self._choisir())

        droite = ctk.CTkFrame(self, fg_color=COULEURS["panneau"], corner_radius=10)
        droite.grid(row=1, column=1, sticky="nsew")
        droite.grid_columnconfigure(0, weight=1)
        droite.grid_rowconfigure(1, weight=1)
        self.titre = ctk.CTkLabel(droite, text="", anchor="w", font=ctk.CTkFont(size=20, weight="bold"))
        self.titre.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        self.dessin = ZoneGraphique(droite, taille=(7, 3.6), barre_outils=False, disposition="constrained")
        self.dessin.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.texte = ctk.CTkTextbox(droite, wrap="word", height=230, fg_color=COULEURS["carte"],
                                    font=ctk.CTkFont(size=13))
        self.texte.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.arbre.selection_set("double_sommet")

    def _choisir(self):
        choix = self.arbre.selection()
        if not choix or choix[0].startswith("famille:"):
            return
        type_ = choix[0]
        m = CATALOGUE[type_]
        teinte = dessin.couleur_sens(m.sens)
        self.titre.configure(text=f"{m.nom}  ·  {m.famille}", text_color=teinte)
        fig = self.dessin.figure
        fig.clear()
        ax = fig.add_subplot()
        dessin.styliser(ax)
        ax.grid(False)
        ax.set_xticks([])
        ax.set_yticks([])
        schemas.dessiner(ax, type_, teinte)
        self.dessin.redessiner()
        sens = nom_sens(m.sens) if m.sens else "celui de la cassure (figure neutre)"
        lignes = [f"Sens attendu : {sens}", "", m.description, "",
                  "Comment le programme la reconnaît", m.regle]
        if m.objectif:
            lignes += ["", m.objectif]
        lignes += ["", "Sur le dessin : le point marque la confirmation (la bougie de signal)."
                   if "bougies" not in schemas.SCHEMAS.get(type_, {}) else
                   "Sur le dessin : la figure est encadrée, après les bougies qui donnent la tendance."]
        self.texte.configure(state="normal")
        self.texte.delete("1.0", "end")
        self.texte.insert("1.0", "\n".join(lignes))
        self.texte.configure(state="disabled")
