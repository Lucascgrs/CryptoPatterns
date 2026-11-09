"""
Exports Excel lisibles : un onglet par tableau, en-têtes figés, pourcentages
affichés comme tels, dégradé rouge / vert sur les écarts et les gains.

Convention : dans les tableaux, les pourcentages sont des fractions (0,55) ;
les colonnes listées dans `pourcentages` sont affichées « 55,0 % » par Excel.
"""

from __future__ import annotations

import pandas as pd
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

# Colonnes en pourcentage, dans tous les tableaux du projet.
POURCENTAGES = {"Bon sens", "Hasard", "Écart", "Variation moyenne", "Hasard moyen",
                "Objectif atteint", "Invalidée", "Trade net moyen", "Trades gagnants",
                "Écart 1re moitié", "Écart 2e moitié", "Après N", "Hasard bon sens",
                "Trade brut", "Trade net"}
# Colonnes colorées : rouge en dessous de zéro, vert au-dessus.
COLOREES = {"Écart", "Variation moyenne", "Trade net moyen", "Écart 1re moitié",
            "Écart 2e moitié", "Après N", "Trade net"}


def ecrire_excel(chemin, feuilles: dict[str, pd.DataFrame], lisez_moi: list[str] | None = None) -> None:
    with pd.ExcelWriter(chemin, engine="openpyxl") as classeur:
        if lisez_moi:
            pd.DataFrame({"": lisez_moi}).to_excel(classeur, sheet_name="Lisez-moi",
                                                    index=False, header=False)
            feuille = classeur.sheets["Lisez-moi"]
            feuille.column_dimensions["A"].width = 120
            feuille["A1"].font = Font(bold=True, size=13)
            for cellule in feuille["A"]:
                cellule.alignment = Alignment(wrap_text=True, vertical="top")
        for nom, df in feuilles.items():
            nom = nom[:31]
            df = df.copy()
            for c in df.columns:
                if pd.api.types.is_bool_dtype(df[c]):
                    df[c] = df[c].map({True: "oui", False: "non"})
            df.to_excel(classeur, sheet_name=nom, index=False)
            _mettre_en_forme(classeur.sheets[nom], df)


def _mettre_en_forme(feuille, df: pd.DataFrame) -> None:
    feuille.freeze_panes = "B2"
    n = len(df) + 1
    for j, nom in enumerate(df.columns, start=1):
        lettre = get_column_letter(j)
        serie = df[nom]
        nom = str(nom)
        largeur = max([len(nom)] + [len(str(v)) for v in serie.head(200)])
        feuille.column_dimensions[lettre].width = min(max(largeur, 8) + 2, 45)
        feuille[f"{lettre}1"].alignment = Alignment(wrap_text=True, vertical="center")
        feuille[f"{lettre}1"].font = Font(bold=True)
        if nom in POURCENTAGES:
            for (cellule,) in feuille[f"{lettre}2:{lettre}{n}"]:
                cellule.number_format = "0.0%"
        elif pd.api.types.is_datetime64_any_dtype(serie):
            feuille.column_dimensions[lettre].width = 18
            for (cellule,) in feuille[f"{lettre}2:{lettre}{n}"]:
                cellule.number_format = "yyyy-mm-dd hh:mm"
        if nom in COLOREES and n > 2:
            feuille.conditional_formatting.add(
                f"{lettre}2:{lettre}{n}",
                ColorScaleRule(start_type="min", start_color="F8696B", mid_type="num", mid_value=0,
                               mid_color="FFFFFF", end_type="max", end_color="63BE7B"))
    feuille.row_dimensions[1].height = 32
