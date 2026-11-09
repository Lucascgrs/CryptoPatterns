"""
Briques réutilisables de l'interface : sections, champs, tableau triable,
cases à cocher, choix des figures, réglages de la détection, zone de graphique.
"""

from __future__ import annotations

import gc
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from .. import config
from ..figures import CATALOGUE, FAMILLES, types_de
from .theme import COULEURS


# ===========================================================================
# MISE EN FORME DES NOMBRES
# ===========================================================================
def _vide(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NaT


def pct(v, decimales=1) -> str:
    return "-" if _vide(v) else f"{v * 100:+.{decimales}f} %".replace(".", ",")


def pct_simple(v, decimales=0) -> str:
    return "-" if _vide(v) else f"{v * 100:.{decimales}f} %".replace(".", ",")


def points(v, decimales=1) -> str:
    """Écart entre deux pourcentages, en points : +3,2 pts."""
    return "-" if _vide(v) else f"{v * 100:+.{decimales}f} pts".replace(".", ",")


def decimal(v, decimales=2) -> str:
    return "-" if _vide(v) else f"{v:.{decimales}f}".replace(".", ",")


def prix(v) -> str:
    if _vide(v) or not np.isfinite(v):
        return "-"
    return f"{v:,.6g}".replace(",", " ").replace(".", ",")


def entier(v) -> str:
    return "-" if _vide(v) else f"{int(v):,}".replace(",", " ")


def date_courte(v) -> str:
    return "-" if v is None or pd.isna(v) else f"{pd.Timestamp(v):%d/%m/%Y %H:%M}"


# ===========================================================================
# STRUCTURE
# ===========================================================================
def titre_page(parent, titre: str, sous_titre: str = ""):
    cadre = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(cadre, text=titre, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
    if sous_titre:
        ctk.CTkLabel(cadre, text=sous_titre, font=ctk.CTkFont(size=12), justify="left",
                     text_color=COULEURS["texte_doux"], wraplength=1100).pack(anchor="w", pady=(2, 0))
    return cadre


def section(parent, titre: str, aide: str = "", largeur_aide: int = 330):
    """Carte avec un titre ; renvoie (carte, intérieur)."""
    carte = ctk.CTkFrame(parent, fg_color=COULEURS["panneau"], corner_radius=10)
    ctk.CTkLabel(carte, text=titre, font=ctk.CTkFont(size=14, weight="bold")
                 ).pack(anchor="w", padx=14, pady=(10, 2))
    if aide:
        ctk.CTkLabel(carte, text=aide, font=ctk.CTkFont(size=11), justify="left",
                     text_color=COULEURS["texte_doux"], wraplength=largeur_aide
                     ).pack(anchor="w", padx=14, pady=(0, 4))
    interieur = ctk.CTkFrame(carte, fg_color="transparent")
    interieur.pack(fill="both", expand=True, padx=12, pady=(2, 12))
    return carte, interieur


def champ(parent, libelle: str, valeur="", largeur: int = 90, aide: str = ""):
    """Libellé + zone de saisie sur une ligne ; renvoie la zone de saisie."""
    ligne = ctk.CTkFrame(parent, fg_color="transparent")
    ligne.pack(fill="x", pady=3)
    ctk.CTkLabel(ligne, text=libelle, anchor="w").pack(side="left")
    saisie = ctk.CTkEntry(ligne, width=largeur, placeholder_text=aide, justify="right")
    saisie.pack(side="right")
    if valeur not in ("", None):
        saisie.insert(0, str(valeur).replace(".", ","))
    return saisie


def note(parent, texte: str, largeur: int = 330, emballer: bool = True):
    """Petit texte d'explication, grisé. `emballer=False` : à placer soi-même (grid)."""
    etiquette = ctk.CTkLabel(parent, text=texte, wraplength=largeur, justify="left", anchor="w",
                             text_color=COULEURS["texte_doux"], font=ctk.CTkFont(size=11))
    if emballer:
        etiquette.pack(fill="x")
    return etiquette


def bouton_discret(parent, texte, commande, largeur=110, danger=False):
    return ctk.CTkButton(parent, text=texte, width=largeur, height=26, fg_color=COULEURS["carte"],
                         hover_color=COULEURS["rouge"] if danger else COULEURS["neutre"],
                         command=commande)


def lire_nombre(saisie, defaut: float) -> float:
    try:
        return float(saisie.get().replace(",", ".").replace(" ", "").strip())
    except ValueError:
        return defaut


def ecrire(saisie, valeur) -> None:
    saisie.delete(0, "end")
    if valeur not in ("", None):
        saisie.insert(0, f"{valeur:g}".replace(".", ",") if isinstance(valeur, float) else str(valeur))


def lire_date(saisie):
    """'2025-01-31' -> Timestamp, '' -> None ; lève ValueError si illisible."""
    texte = saisie.get().strip()
    if not texte:
        return None
    try:
        return pd.Timestamp(texte)
    except ValueError:
        raise ValueError(f"Date illisible : {texte!r} (format attendu : AAAA-MM-JJ).") from None


# ===========================================================================
# TABLEAU TRIABLE
# ===========================================================================
class Tableau(ctk.CTkFrame):
    """
    Treeview alimenté par un DataFrame. Un clic sur un en-tête trie la colonne
    (un second clic inverse l'ordre). `formats` associe à une colonne une
    fonction d'affichage ; `couleur(ligne)` renvoie 'vert', 'rouge', 'gris' ou None.
    Les colonnes dont le nom commence par « _ » ne sont pas affichées.
    """

    def __init__(self, parent, hauteur=12, au_double_clic=None, au_choix=None):
        # Taille demandée fixe : sans cela, un tableau de quinze colonnes
        # imposerait sa largeur à toute la fenêtre.
        super().__init__(parent, fg_color="transparent", width=300, height=hauteur * 24 + 40)
        self.grid_propagate(False)
        self.arbre = ttk.Treeview(self, show="headings", height=hauteur, selectmode="browse")
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.arbre.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.arbre.xview)
        self.arbre.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.arbre.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.arbre.tag_configure("vert", foreground=COULEURS["vert"])
        self.arbre.tag_configure("rouge", foreground=COULEURS["rouge"])
        self.arbre.tag_configure("gris", foreground=COULEURS["texte_doux"])
        self.arbre.tag_configure("orange", foreground=COULEURS["orange"])
        self.df = None
        self.formats, self.couleur, self.largeurs, self.gauche = {}, None, {}, set()
        self._cles = []
        self.tri = (None, False)
        self.max_lignes = 3000
        self._silence = False
        if au_double_clic:
            self.arbre.bind("<Double-1>", lambda _e: self._rappel(au_double_clic))
        if au_choix:
            self.arbre.bind("<<TreeviewSelect>>", lambda _e: self._rappel(au_choix))

    def _rappel(self, fonction):
        if self._silence:
            return
        cle = self.selection()
        if cle is not None:
            fonction(cle)

    def remplir(self, df: pd.DataFrame, formats=None, couleur=None, largeurs=None,
                gauche=(), garder_tri=False):
        self.df = df
        self.formats = formats or {}
        self.couleur = couleur
        self.largeurs = largeurs or {}
        self.gauche = set(gauche)
        if not garder_tri:
            self.tri = (None, False)
        self._afficher()

    def _afficher(self):
        arbre = self.arbre
        arbre.delete(*arbre.get_children())
        df = self.df
        if df is None:
            arbre["columns"] = ()
            return
        colonne_tri, decroissant = self.tri
        if colonne_tri is not None and colonne_tri in df.columns:
            df = df.sort_values(colonne_tri, ascending=not decroissant, na_position="last",
                                kind="stable")
        colonnes = [str(c) for c in df.columns if not str(c).startswith("_")]
        arbre["columns"] = colonnes
        for c in colonnes:
            fleche = (" ▼" if decroissant else " ▲") if c == colonne_tri else ""
            arbre.heading(c, text=c + fleche, command=lambda c=c: self._trier(c))
            largeur = self.largeurs.get(c, max(70, min(170, 9 * len(c) + 16)))
            arbre.column(c, width=largeur, minwidth=40,
                         anchor="w" if c in self.gauche else "center", stretch=False)
        visibles = df.head(self.max_lignes)
        for position, (_cle, ligne) in enumerate(visibles.iterrows()):
            valeurs = [self.formats.get(c, _defaut)(ligne[c]) for c in colonnes]
            tags = ()
            if self.couleur is not None:
                teinte = self.couleur(ligne)
                tags = (teinte,) if teinte else ()
            arbre.insert("", "end", iid=str(position), values=valeurs, tags=tags)
        self._cles = list(visibles.index)

    def _trier(self, colonne):
        actuelle, decroissant = self.tri
        self.tri = (colonne, not decroissant if actuelle == colonne else True)
        self._afficher()

    def selection(self):
        choix = self.arbre.selection()
        if not choix:
            return None
        return self._cles[int(choix[0])]

    def cles_affichees(self) -> list:
        return list(self._cles)

    def choisir(self, cle, rappeler: bool = False):
        """Sélectionne la ligne dont l'index vaut `cle` et la fait défiler à l'écran."""
        if cle not in self._cles:
            self.arbre.selection_remove(self.arbre.selection())
            return
        iid = str(self._cles.index(cle))
        self._silence = not rappeler
        try:
            self.arbre.selection_set(iid)
            self.arbre.see(iid)
            self.update_idletasks()
        finally:
            self._silence = False


def _defaut(v):
    if isinstance(v, (float, np.floating)):
        return "-" if np.isnan(v) else f"{v:.4g}".replace(".", ",")
    if isinstance(v, pd.Timestamp):
        return date_courte(v)
    return str(v)


# ===========================================================================
# CASES À COCHER
# ===========================================================================
class ListeCases(ctk.CTkFrame):
    """Une case par élément, sur plusieurs colonnes, avec « Tout / Rien »."""

    def __init__(self, parent, elements=(), coches=(), colonnes=4, au_changement=None,
                 boutons=True, largeur=70):
        super().__init__(parent, fg_color="transparent")
        self.colonnes = colonnes
        self.largeur = largeur
        self.au_changement = au_changement
        self.variables: dict[str, ctk.BooleanVar] = {}
        self.grille = ctk.CTkFrame(self, fg_color="transparent")
        self.grille.pack(fill="x")
        if boutons:
            barre = ctk.CTkFrame(self, fg_color="transparent")
            barre.pack(fill="x", pady=(4, 0))
            for texte, valeur in (("Tout", True), ("Rien", False)):
                ctk.CTkButton(barre, text=texte, width=60, height=24, fg_color=COULEURS["carte"],
                              hover_color=COULEURS["neutre"],
                              command=lambda v=valeur: self.tout(v)).pack(side="left", padx=(0, 6))
        self.definir(elements, coches)

    def definir(self, elements, coches):
        for enfant in self.grille.winfo_children():
            enfant.destroy()
        self.variables = {}
        gc.collect()        # anciennes variables Tk libérées dans le thread graphique
        for k, element in enumerate(elements):
            variable = ctk.BooleanVar(value=element in coches)
            ctk.CTkCheckBox(self.grille, text=element, variable=variable, width=self.largeur,
                            checkbox_width=18, checkbox_height=18,
                            command=self._change).grid(row=k // self.colonnes,
                                                       column=k % self.colonnes,
                                                       sticky="w", padx=(0, 8), pady=2)
            self.variables[element] = variable

    def _change(self):
        if self.au_changement:
            self.au_changement()

    def tout(self, valeur: bool):
        for variable in self.variables.values():
            variable.set(valeur)
        self._change()

    def cochees(self) -> list[str]:
        return [e for e, v in self.variables.items() if v.get()]

    def cocher(self, elements):
        for e, v in self.variables.items():
            v.set(e in elements)


# ===========================================================================
# CHOIX DES FIGURES
# ===========================================================================
SANS_CHANDELIERS = [t for t in CATALOGUE if CATALOGUE[t].famille != "Chandeliers"]


class ChoixFigures(ctk.CTkFrame):
    """
    Les figures du catalogue, rangées par famille. La case de la famille coche
    ou décoche toute la famille ; le triangle déplie la liste de ses figures.
    """

    def __init__(self, parent, coches=None, au_changement=None, deplies=()):
        super().__init__(parent, fg_color="transparent")
        self.au_changement = au_changement
        coches = set(SANS_CHANDELIERS if coches is None else coches)
        self.variables: dict[str, ctk.BooleanVar] = {}
        self.familles: dict[str, ctk.BooleanVar] = {}
        self.contenus: dict[str, ctk.CTkFrame] = {}
        self.fleches: dict[str, ctk.CTkButton] = {}
        self.entetes: dict[str, ctk.CTkFrame] = {}
        police = ctk.CTkFont(weight="bold")
        for famille in FAMILLES:
            types = types_de(famille)
            entete = ctk.CTkFrame(self, fg_color="transparent")
            entete.pack(fill="x", pady=(4, 0))
            fleche = ctk.CTkButton(entete, text="▸", width=22, height=22, fg_color="transparent",
                                   hover_color=COULEURS["neutre"],
                                   command=lambda f=famille: self.deplier(f))
            fleche.pack(side="left")
            variable_famille = ctk.BooleanVar(value=all(t in coches for t in types))
            ctk.CTkCheckBox(entete, text=f"{famille} ({len(types)})", variable=variable_famille,
                            font=police, checkbox_width=18, checkbox_height=18,
                            command=lambda f=famille: self._famille(f)).pack(side="left", padx=(2, 0))
            contenu = ctk.CTkFrame(self, fg_color="transparent")
            for k, type_ in enumerate(types):
                variable = ctk.BooleanVar(value=type_ in coches)
                ctk.CTkCheckBox(contenu, text=CATALOGUE[type_].nom, variable=variable, width=160,
                                checkbox_width=16, checkbox_height=16, font=ctk.CTkFont(size=12),
                                command=lambda f=famille: self._type(f)
                                ).grid(row=k // 2, column=k % 2, sticky="w", padx=(26, 4), pady=1)
                self.variables[type_] = variable
            self.familles[famille] = variable_famille
            self.contenus[famille] = contenu
            self.fleches[famille] = fleche
            self.entetes[famille] = entete
        for famille in deplies:
            self.deplier(famille)

    def deplier(self, famille):
        contenu = self.contenus[famille]
        if contenu.winfo_manager():                 # déjà affiché : on replie
            contenu.pack_forget()
            self.fleches[famille].configure(text="▸")
            return
        contenu.pack(fill="x", after=self.entetes[famille])
        self.fleches[famille].configure(text="▾")

    def _famille(self, famille):
        valeur = self.familles[famille].get()
        for type_ in types_de(famille):
            self.variables[type_].set(valeur)
        self._change()

    def _type(self, famille):
        self.familles[famille].set(all(self.variables[t].get() for t in types_de(famille)))
        self._change()

    def _change(self):
        if self.au_changement:
            self.au_changement()

    def cochees(self) -> list[str]:
        return [t for t, v in self.variables.items() if v.get()]

    def cocher(self, types):
        types = set(types)
        for t, v in self.variables.items():
            v.set(t in types)
        for famille, variable in self.familles.items():
            variable.set(all(self.variables[t].get() for t in types_de(famille)))


# ===========================================================================
# RÉGLAGES DE LA DÉTECTION
# ===========================================================================
class ReglagesDetection(ctk.CTkFrame):
    """Les cinq réglages de la détection, avec leur explication."""

    CHAMPS = [
        ("sensibilite", "Taille des vagues (× ATR)", config.SENSIBILITE,
         "Un sommet ou un creux compte quand le prix s'en éloigne d'au moins autant. Plus bas : "
         "plus de petites figures ; plus haut : seulement les grandes."),
        ("tolerance", "Tolérance (%)", config.TOLERANCE,
         "Écart admis entre deux sommets « égaux », ou entre un pivot et sa droite, en % de la "
         "hauteur de la figure."),
        ("range_largeur", "Range : largeur (× ATR)", config.RANGE_LARGEUR, ""),
        ("range_duree", "Range : durée (bougies)", config.RANGE_DUREE,
         "Un range : toutes les clôtures tiennent dans cette largeur pendant au moins cette durée."),
        ("niveau_touches", "Support / résistance : contacts", config.NIVEAU_TOUCHES,
         "Nombre de sommets ou de creux au même niveau (à ½ ATR près) pour tracer un niveau."),
    ]

    def __init__(self, parent, valeurs: dict | None = None):
        super().__init__(parent, fg_color="transparent")
        valeurs = valeurs or {}
        self.saisies = {}
        for cle, libelle, defaut, aide in self.CHAMPS:
            self.saisies[cle] = champ(self, libelle, valeurs.get(cle, defaut), largeur=64)
            if aide:
                note(self, aide, largeur=320)

    def valeurs(self) -> dict:
        sortie = {}
        for cle, _libelle, defaut, _aide in self.CHAMPS:
            v = lire_nombre(self.saisies[cle], defaut)
            sortie[cle] = int(round(v)) if isinstance(defaut, int) else v
        return sortie

    def definir(self, valeurs: dict):
        for cle, saisie in self.saisies.items():
            if cle in valeurs:
                ecrire(saisie, valeurs[cle])


# ===========================================================================
# GRAPHIQUE
# ===========================================================================
class ZoneGraphique(ctk.CTkFrame):
    """Une figure matplotlib intégrée, avec la barre d'outils (zoom, déplacement)."""

    def __init__(self, parent, taille=(9, 4), barre_outils=True, disposition=None):
        super().__init__(parent, fg_color=COULEURS["fond"])
        self.figure = Figure(figsize=taille, dpi=100, facecolor=COULEURS["fond"], layout=disposition)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.barre = None
        if barre_outils:
            barre = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            barre.configure(background=COULEURS["panneau"])
            for enfant in barre.winfo_children():
                try:
                    enfant.configure(background=COULEURS["panneau"])
                except tk.TclError:
                    pass
            barre.update()
            barre.pack(side="bottom", fill="x")
            self.barre = barre
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def redessiner(self):
        self.canvas.draw_idle()
