"""
Mémoire de l'interface entre deux lancements : les derniers réglages de chaque
page, dans `donnees/interface.json` (jamais versionné).
"""

from __future__ import annotations

import json

from .. import config

FICHIER_REGLAGES = config.DOSSIER_DONNEES / "interface.json"


def charger() -> dict:
    try:
        return json.loads(FICHIER_REGLAGES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def enregistrer(reglages: dict) -> None:
    FICHIER_REGLAGES.parent.mkdir(parents=True, exist_ok=True)
    FICHIER_REGLAGES.write_text(json.dumps(reglages, ensure_ascii=False, indent=2), encoding="utf-8")
