"""Audit des closures Cycles, materiau par materiau.

Cycles plafonne a MAX_CLOSURE = 64 par shader COMPILE et abandonne les
suivantes SANS lever d'erreur — seulement un WARNING sur stderr, qui ne nomme
pas le materiau fautif. Ce script le nomme.

Il ne rend rien. Il construit la scene comme le rendu la construit, puis
compte pour chaque materiau les noeuds qui produisent des closures en SVM.

Le compte est une BORNE, pas la valeur exacte de Cycles : le poids reel d'un
Principled depend des entrees actives (une transmission a 0 n'emet pas sa
closure). Il sert a classer, pas a certifier. Le verdict se prend au rendu, en
regardant si le WARNING disparait.

    blender --background --python-exit-code 1 --python closure_audit.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bpy  # noqa: E402

import tuple_faceplate as fp  # noqa: E402


# Poids indicatifs. Le Principled est un uber-shader : en SVM il se developpe
# en une closure par composante active. Les valeurs viennent de la liste des
# composantes du Principled 5.2 (diffuse, subsurface, specular, transmission,
# coat, sheen, emission), pas d'une mesure.
PRINCIPLED_COMPONENTS = (
    ("Subsurface Weight", 1),
    ("Transmission Weight", 1),
    ("Coat Weight", 1),
    ("Sheen Weight", 1),
    ("Emission Strength", 1),
)


def _socket(node, name):
    for sock in node.inputs:
        if sock.name == name:
            return sock
    return None


def principled_weight(node):
    """Borne du nombre de closures d'un Principled, composantes actives seules."""
    n = 2  # diffuse + specular : toujours presents
    for name, cost in PRINCIPLED_COMPONENTS:
        sock = _socket(node, name)
        if sock is None or sock.is_linked:
            n += cost          # lie = valeur inconnue, on compte au pire
        elif sock.default_value > 0.0:
            n += cost
    return n


CLOSURE_NODES = {
    "ShaderNodeBsdfDiffuse": 1,
    "ShaderNodeBsdfGlossy": 1,
    "ShaderNodeBsdfAnisotropic": 1,
    "ShaderNodeBsdfGlass": 1,
    "ShaderNodeBsdfRefraction": 1,
    "ShaderNodeBsdfTranslucent": 1,
    "ShaderNodeBsdfTransparent": 1,
    "ShaderNodeBsdfSheen": 1,
    "ShaderNodeBsdfToon": 1,
    "ShaderNodeBsdfHair": 1,
    "ShaderNodeBsdfHairPrincipled": 1,
    "ShaderNodeEmission": 1,
    "ShaderNodeBackground": 1,
    "ShaderNodeVolumeScatter": 1,
    "ShaderNodeVolumeAbsorption": 1,
    "ShaderNodeVolumePrincipled": 2,
    "ShaderNodeSubsurfaceScattering": 1,
    "ShaderNodeHoldout": 1,
}


def count_closures(node_tree):
    total = 0
    detail = {}
    for node in node_tree.nodes:
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree is not None:
            sub, _ = count_closures(node.node_tree)
            total += sub
            detail["group:%s" % node.node_tree.name] = sub
            continue
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            w = principled_weight(node)
        else:
            w = CLOSURE_NODES.get(node.bl_idname, 0)
        if w:
            total += w
            detail[node.bl_idname] = detail.get(node.bl_idname, 0) + w
    return total, detail


def main():
    fp.build(plastic_only=False)

    # Un materiau ne compte que s'il est REELLEMENT assigne a un objet de la
    # scene : Cycles ne compile que ceux-la. Compter les orphelins de
    # bpy.data.materials gonflerait le classement avec du mort.
    used = {}
    for obj in bpy.context.scene.objects:
        for slot in getattr(obj, "material_slots", []):
            if slot.material is not None:
                used.setdefault(slot.material.name, slot.material)

    rows = []
    for name, mat in used.items():
        if not mat.use_nodes or mat.node_tree is None:
            rows.append((0, name, {}, 0))
            continue
        total, detail = count_closures(mat.node_tree)
        rows.append((total, name, detail, len(mat.node_tree.nodes)))

    rows.sort(reverse=True)

    print("")
    print("=== CLOSURE AUDIT — %d materiaux assignes a un objet ===" % len(rows))
    print("%-6s %-34s %-7s %s" % ("bound", "materiau", "noeuds", "detail"))
    for total, name, detail, nnodes in rows:
        flag = "  <<< AU-DESSUS DE 64" if total > 64 else ""
        print("%-6d %-34s %-7d %s%s"
              % (total, name, nnodes,
                 ", ".join("%s=%d" % kv for kv in sorted(detail.items())),
                 flag))

    print("")
    print("total materiaux assignes : %d" % len(rows))
    print("borne maximale rencontree : %d" % (rows[0][0] if rows else 0))

    # Le monde est compile comme un shader a part entiere.
    world = bpy.context.scene.world
    if world is not None and world.use_nodes:
        wtotal, wdetail = count_closures(world.node_tree)
        print("world '%s' : %d (%s)"
              % (world.name, wtotal, ", ".join("%s=%d" % kv for kv in sorted(wdetail.items()))))


if __name__ == "__main__":
    main()
