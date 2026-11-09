"""
CryptoPatterns — ligne de commande. L'interface graphique : python Dashboard.py

    python main.py telecharger                       # 10 cryptos, 15m à 1w, 4 ans
    python main.py telecharger BTC ETH --intervalles 1h,4h,1d --tout
    python main.py importer                          # reprend les historiques de CryptoSupertrend
    python main.py inventaire
    python main.py analyser BTC 4h                   # les figures des 5000 dernières bougies + une image
    python main.py analyser ETH 45m --bougies 2000 --chandeliers
    python main.py analyser SOL 1h --direct          # les 1000 dernières bougies, lues sur Binance
    python main.py direct --intervalles 15m,1h,4h,1d # ce qui se forme en ce moment
    python main.py stats BTC --intervalles 1h,4h,1d --horizon 20 --excel
    python main.py catalogue                         # toutes les figures reconnues

Réglages de la détection (toutes les commandes qui détectent) :
    --sensibilite 3   taille minimale d'une vague, en ATR
    --tolerance 15    écart admis entre sommets « égaux », en % de la hauteur
    --figures double_sommet,triangle_ascendant   ou des familles : Retournements,Harmoniques
    --chandeliers     ajoute les figures de chandeliers (nombreuses)
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from patterns_lab import config, dessin, detection, donnees, rapport, statistiques
from patterns_lab.figures import CATALOGUE, CONFIRMEE, EN_FORMATION, FAMILLES, nom_sens, types_de


def _pct(v, decimales=1) -> str:
    return "-" if pd.isna(v) else f"{v * 100:+.{decimales}f} %".replace(".", ",")


def _prix(v) -> str:
    return "-" if pd.isna(v) or not np.isfinite(v) else f"{v:,.6g}".replace(",", " ").replace(".", ",")


def _reglages(arguments) -> detection.Reglages:
    if arguments.figures:
        types = []
        for nom in arguments.figures.split(","):
            nom = nom.strip()
            if nom in CATALOGUE:
                types.append(nom)
            elif nom in FAMILLES:
                types += types_de(nom)
            else:
                sys.exit(f"Figure ou famille inconnue : {nom!r} (python main.py catalogue).")
    else:
        types = [t for t in CATALOGUE if CATALOGUE[t].famille != "Chandeliers"]
    if arguments.chandeliers:
        types += [t for t in types_de("Chandeliers") if t not in types]
    r = detection.Reglages(sensibilite=arguments.sensibilite, tolerance=arguments.tolerance,
                           range_largeur=arguments.range_largeur, range_duree=arguments.range_duree,
                           types=types)
    try:
        r.verifier()
    except ValueError as erreur:
        sys.exit(str(erreur))
    return r


def _intervalles(texte) -> list[str]:
    try:
        return config.trier_intervalles(texte)
    except ValueError as erreur:
        sys.exit(str(erreur))


# ===========================================================================
# COMMANDES
# ===========================================================================
def cmd_telecharger(arguments):
    symboles = (donnees.top_cryptos(arguments.top) if arguments.top
                else [s.upper() for s in arguments.symboles] or list(config.CRYPTOS_DEFAUT))
    intervalles = [i for i in _intervalles(arguments.intervalles) if config.est_natif(i)]
    debut_analyse = (config.DEBUT_BINANCE if arguments.tout
                     else donnees.maintenant_utc().normalize() - pd.Timedelta(days=arguments.jours))
    print(f"Téléchargement de {len(symboles)} cryptos × {len(intervalles)} échelles depuis le "
          f"{debut_analyse:%Y-%m-%d} : {', '.join(symboles)}")

    def afficher(faites, total):
        if total > 3:
            print(f"\r    {faites}/{total} requêtes", end="", flush=True)

    for symbole in symboles:
        for intervalle in intervalles:
            debut = debut_analyse - config.BOUGIES_CHAUFFE * config.duree(intervalle)
            try:
                ligne = donnees.mettre_a_jour(symbole, intervalle, debut, afficher)
                print(f"\r{ligne}")
            except donnees.PaireIndisponible as erreur:
                print(f"\r{symbole} : absente de Binance ({erreur}), ignorée.")
                break


def cmd_importer(_arguments):
    config.preparer_dossiers()
    donnees.importer_voisin()


def cmd_inventaire(_arguments):
    inv = donnees.inventaire()
    if inv.empty:
        print("Rien de téléchargé : python main.py telecharger")
        return
    print(inv.to_string(index=False))


def _charger(arguments) -> detection.Analyse:
    symbole = arguments.symbole.upper()
    intervalle = _intervalles(arguments.intervalle)[0]
    try:
        if arguments.direct:
            bougies, provenance = donnees.bougies_direct(symbole, intervalle)
        else:
            bougies, provenance = donnees.charger(symbole, intervalle)
            if arguments.debut:
                bougies = bougies[bougies.index >= pd.Timestamp(arguments.debut)]
            if arguments.fin:
                bougies = bougies[bougies.index < pd.Timestamp(arguments.fin) + pd.Timedelta(days=1)]
            if arguments.bougies:
                bougies = bougies.tail(arguments.bougies)
    except (donnees.DonneesAbsentes, donnees.PaireIndisponible) as erreur:
        sys.exit(str(erreur))
    if len(bougies) < 50:
        sys.exit(f"Seulement {len(bougies)} bougies : pas assez pour chercher des figures.")
    return detection.analyser(bougies, _reglages(arguments), symbole, intervalle, provenance)


def cmd_analyser(arguments):
    a = _charger(arguments)
    df = a.bougies
    print(f"{a.symbole} {a.intervalle} ({a.provenance}) : {len(df)} bougies du {df.index[0]:%d/%m/%Y} "
          f"au {df.index[-1]:%d/%m/%Y %H:%M} UTC, {len(a.figures)} figures.\n")
    compte = detection.compter(a)
    if not compte.empty:
        print(compte.to_string(), "\n")
    tableau = a.tableau(arguments.horizon)
    if not tableau.empty:
        dernieres = tableau.tail(arguments.lignes).drop(columns=["Famille"])
        for c in ("Prix", "Objectif", "Invalidation"):
            dernieres[c] = dernieres[c].map(_prix)
        dernieres[f"Après {arguments.horizon}"] = dernieres[f"Après {arguments.horizon}"].map(_pct)
        print(f"Les {len(dernieres)} dernières :")
        print(dernieres.to_string(index=False))
    config.preparer_dossiers()
    chemin = config.DOSSIER_RESULTATS / f"graphique_{a.symbole}_{a.intervalle}_{pd.Timestamp.now():%Y-%m-%d_%Hh%M%S}.png"
    dessin.image(a, chemin, max(0, a.n - 300), a.n, horizon=arguments.horizon)
    print(f"\nImage des 300 dernières bougies : {chemin}")


def cmd_direct(arguments):
    symboles = [s.upper() for s in arguments.symboles] or list(config.CRYPTOS_DEFAUT)
    reglages = _reglages(arguments)
    lignes = []
    for symbole in symboles:
        for intervalle in _intervalles(arguments.intervalles):
            try:
                bougies, _provenance = donnees.bougies_direct(symbole, intervalle)
            except donnees.PaireIndisponible:
                print(f"{symbole} : absente de Binance, ignorée.")
                break
            a = detection.analyser(bougies, reglages, symbole, intervalle)
            c = a.bougies["Close"].to_numpy()
            for f in a.figures:
                recente = f.statut == CONFIRMEE and f.signal is not None and a.n - 1 - f.signal <= arguments.recentes
                if not recente and f.statut != EN_FORMATION:
                    continue
                lignes.append({"Crypto": symbole, "Échelle": intervalle, "Figure": f.nom_complet,
                               "Sens": {1: "▲", -1: "▼"}.get(f.sens, "?"), "Statut": f.statut,
                               "Il y a": "en cours" if not recente else f"{a.n - 1 - f.signal} bg",
                               "Prix": _prix(c[-1]),
                               "Niveau": _prix(f.niveau) if f.statut == EN_FORMATION else "-",
                               "Objectif": _prix(f.objectif), "Invalidation": _prix(f.invalidation)})
    if not lignes:
        print("Aucune figure récente ou en formation.")
        return
    print(pd.DataFrame(lignes).sort_values(["Statut", "Crypto"]).to_string(index=False))


def cmd_stats(arguments):
    symboles = [s.upper() for s in arguments.symboles] or donnees.symboles_disponibles()
    if not symboles:
        sys.exit("Rien de téléchargé : python main.py telecharger")
    reglages = _reglages(arguments)
    frais = arguments.frais / 100
    occurrences, toutes = [], []
    for symbole in symboles:
        for intervalle in _intervalles(arguments.intervalles):
            try:
                bougies, _provenance = donnees.charger(symbole, intervalle)
            except donnees.DonneesAbsentes as erreur:
                print(erreur)
                continue
            print(f"{symbole} {intervalle} : {len(bougies)} bougies…", flush=True)
            a = detection.analyser(bougies, reglages, symbole, intervalle)
            occurrences.append(statistiques.evaluer(a, arguments.horizon, frais))
            toutes.append(statistiques.reperees(a))
    if not occurrences:
        sys.exit("Aucune série à mesurer.")
    occ = pd.concat(occurrences, ignore_index=True)
    tout = pd.concat(toutes, ignore_index=True)
    resume = statistiques.resumer(occ, tout)
    vue = resume.drop(columns=["Famille", "Hasard moyen", "Repérées"]).copy()
    for c in ("Bon sens", "Hasard", "Objectif atteint", "Invalidée", "Trades gagnants"):
        vue[c] = vue[c].map(lambda v: "-" if pd.isna(v) else f"{v * 100:.0f} %")
    for c in ("Écart", "Écart 1re moitié", "Écart 2e moitié"):
        vue[c] = vue[c].map(lambda v: "-" if pd.isna(v) else f"{v * 100:+.1f}".replace(".", ","))
    for c in ("Variation moyenne", "Trade net moyen"):
        vue[c] = vue[c].map(lambda v: _pct(v, 2))
    pd.set_option("display.width", 250)
    print(f"\nJugé {arguments.horizon} bougies après le signal ; écarts au hasard en points.\n")
    print(vue.to_string(index=False))
    if arguments.excel:
        config.preparer_dossiers()
        chemin = config.DOSSIER_RESULTATS / f"statistiques_{pd.Timestamp.now():%Y-%m-%d_%Hh%M%S}.xlsx"
        rapport.ecrire_excel(chemin, {"Par figure": resume,
                                      "Par figure et échelle": statistiques.resumer(occ, tout, ["Échelle"]),
                                      "Occurrences": occ.drop(columns=["_k"])},
                             ["Ce qui suit chaque figure", f"Jugé {arguments.horizon} bougies après le signal."])
        print(f"\nExcel : {chemin}")


def cmd_catalogue(_arguments):
    for famille in FAMILLES:
        print(f"\n{famille}")
        for type_ in types_de(famille):
            m = CATALOGUE[type_]
            print(f"  {type_:<26}{m.nom:<28}{nom_sens(m.sens) if m.sens else 'selon la cassure'}")


# ===========================================================================
def main(argv=None):
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(description="Figures chartistes, ranges et chandeliers sur les cryptos.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sous = p.add_subparsers(dest="commande", required=True)

    def detection_args(q):
        q.add_argument("--sensibilite", type=float, default=config.SENSIBILITE)
        q.add_argument("--tolerance", type=float, default=config.TOLERANCE)
        q.add_argument("--range-largeur", type=float, default=config.RANGE_LARGEUR)
        q.add_argument("--range-duree", type=int, default=config.RANGE_DUREE)
        q.add_argument("--figures", default="", help="types ou familles, séparés par des virgules")
        q.add_argument("--chandeliers", action="store_true", help="ajoute les figures de chandeliers")

    q = sous.add_parser("telecharger", help="télécharger ou compléter l'historique")
    q.add_argument("symboles", nargs="*")
    q.add_argument("--intervalles", default=",".join(config.INTERVALLES_DEFAUT))
    q.add_argument("--jours", type=int, default=config.JOURS_HISTORIQUE)
    q.add_argument("--tout", action="store_true", help="depuis l'ouverture de Binance (2017)")
    q.add_argument("--top", type=int, default=0, help="les N plus grosses capitalisations")
    q.set_defaults(fonction=cmd_telecharger)

    q = sous.add_parser("importer", help="reprendre les historiques de CryptoSupertrend")
    q.set_defaults(fonction=cmd_importer)

    q = sous.add_parser("inventaire", help="ce qui est déjà téléchargé")
    q.set_defaults(fonction=cmd_inventaire)

    q = sous.add_parser("analyser", help="les figures d'une crypto à une échelle")
    q.add_argument("symbole")
    q.add_argument("intervalle")
    q.add_argument("--bougies", type=int, default=5000, help="les N dernières (0 = toutes)")
    q.add_argument("--debut", default="")
    q.add_argument("--fin", default="")
    q.add_argument("--direct", action="store_true", help="lire les 1000 dernières bougies sur Binance")
    q.add_argument("--horizon", type=int, default=config.HORIZON)
    q.add_argument("--lignes", type=int, default=25, help="figures listées")
    detection_args(q)
    q.set_defaults(fonction=cmd_analyser)

    q = sous.add_parser("direct", help="les figures qui se confirment ou se forment en ce moment")
    q.add_argument("symboles", nargs="*")
    q.add_argument("--intervalles", default="15m,1h,4h,1d")
    q.add_argument("--recentes", type=int, default=3, help="confirmées depuis au plus N bougies")
    detection_args(q)
    q.set_defaults(fonction=cmd_direct)

    q = sous.add_parser("stats", help="ce qui suit chaque figure, comparé au hasard")
    q.add_argument("symboles", nargs="*")
    q.add_argument("--intervalles", default="1h,4h,1d")
    q.add_argument("--horizon", type=int, default=config.HORIZON)
    q.add_argument("--frais", type=float, default=config.FRAIS_PCT, help="en %% par ordre")
    q.add_argument("--excel", action="store_true")
    detection_args(q)
    q.set_defaults(fonction=cmd_stats)

    q = sous.add_parser("catalogue", help="les figures reconnues")
    q.set_defaults(fonction=cmd_catalogue)

    arguments = p.parse_args(argv)
    arguments.fonction(arguments)


if __name__ == "__main__":
    main()
