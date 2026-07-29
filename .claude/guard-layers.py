#!/usr/bin/env python
"""Garde de frontiere de couches — tuple-vst.

La seule regle de structure du projet : rien sous source/domain/ ni
source/app/ n'inclut un en-tete JUCE. C'est ce qui permet au binaire de test de
demarrer en une seconde, sans hote audio.

Une consigne dans CLAUDE.md est une requete ; un hook PreToolUse est une
garantie. Ce script est la garantie.

Hook PreToolUse sur Edit|Write, lit le payload sur stdin. Sortie 2 = bloque.

Note d'implementation : ni jq (absent de la machine de dev — une premiere
version basee dessus etait INERTE), ni wrapper bash avec heredoc (Python lisait
le payload comme son propre script). Appel direct, stdin libre.
"""

import json
import re
import sys

JUCE_INCLUDE = re.compile(r'#\s*include\s*[<"][^>"]*juce', re.IGNORECASE)
GUARDED = ("/source/domain/", "/source/app/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        # On le DIT plutot que de laisser passer en silence : un garde muet est
        # une fausse assurance. Bloquer toute edition sur un payload illisible
        # couterait plus cher que le risque couvert — on avertit et on passe.
        print(f"guard-layers: payload illisible ({exc}), garde INACTIVE.",
              file=sys.stderr)
        return 0

    tool_input = payload.get("tool_input") or {}

    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    normalised = file_path.replace("\\", "/")
    if not any(marker in normalised for marker in GUARDED):
        return 0

    candidate = tool_input.get("content") or tool_input.get("new_string") or ""
    if not candidate or not JUCE_INCLUDE.search(candidate):
        return 0

    print(
        "guard-layers: BLOQUE — un en-tete JUCE dans une couche interne.\n"
        f"\n  fichier : {file_path}\n\n"
        "source/domain/ et source/app/ ne compilent pas contre JUCE. C'est la\n"
        "regle qui garde la boucle de test a une seconde et rend la logique\n"
        "metier testable sans hote audio (CLAUDE.md, \"Les trois couches\").\n\n"
        "Si ce code a besoin de JUCE, il appartient a source/plugin/.\n"
        "Verification : grep -ri \"juce\" source/domain/ source/app/",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
