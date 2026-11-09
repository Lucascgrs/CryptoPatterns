"""
Apparence de l'interface : palette, tableaux.

Même palette que CryptoSupertrend et Crypto Lab, pour que les applications se
ressemblent.
"""

from __future__ import annotations

from tkinter import ttk

COULEURS = {
    "fond":         "#1a1a1a",
    "panneau":      "#242424",
    "carte":        "#2b2b2b",
    "accent":       "#1f6aa5",
    "accent_clair": "#2e86c1",
    "vert":         "#2ecc71",
    "rouge":        "#e74c3c",
    "orange":       "#f39c12",
    "texte":        "#e6e6e6",
    "texte_doux":   "#9aa0a6",
    "axe":          "#1e1e1e",
    "neutre":       "#3a3a3a",
}

POLICE = "Segoe UI"


def configurer_tableaux() -> None:
    """Accorde les tableaux ttk (Treeview) au thème sombre de CustomTkinter."""
    style = ttk.Style()
    style.theme_use("default")
    style.configure("Treeview", background=COULEURS["carte"], foreground=COULEURS["texte"],
                    fieldbackground=COULEURS["carte"], rowheight=24, borderwidth=0,
                    font=(POLICE, 10))
    style.configure("Treeview.Heading", background=COULEURS["accent"], foreground="white",
                    relief="flat", font=(POLICE + " Semibold", 10))
    style.map("Treeview", background=[("selected", COULEURS["accent_clair"])])
    style.map("Treeview.Heading", background=[("active", COULEURS["accent_clair"])])
    style.configure("Vertical.TScrollbar", background=COULEURS["neutre"],
                    troughcolor=COULEURS["panneau"], borderwidth=0, arrowsize=12)
    style.configure("Horizontal.TScrollbar", background=COULEURS["neutre"],
                    troughcolor=COULEURS["panneau"], borderwidth=0, arrowsize=12)


def legende(ax, **kwargs):
    return ax.legend(facecolor=COULEURS["carte"], labelcolor="white", edgecolor="#555555",
                     fontsize=8, **kwargs)
