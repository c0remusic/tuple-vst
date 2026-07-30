"""Rend la carte SANS la coque, pour savoir a qui imputer son illisibilite.

La planche de comparaison montre que la bande haute du rendu donne des
rectangles gris flous la ou la maquette montre des puces avec pattes, des
connecteurs et de la serigraphie. Deux causes possibles, et elles appellent des
correctifs opposes :

  A. la coque diffuse trop        -> agir sur la matiere ou la distance
  B. la carte elle-meme est pauvre -> agir sur les composants et leurs albedos

Les distinguer coute un rendu : on retire la coque et on regarde ce qu'il y a
dessous. Si la carte nue est deja pauvre, la matiere est hors de cause et
toucher a la transmission ne ferait que degrader la coque pour rien.

    blender --background --python-exit-code 1 --python pcb_probe.py

Ecrit renders/pcb_probe/pcb_nue.png, a la resolution de la maquette.
"""

import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import importlib                                                   # noqa: E402
import tuple_faceplate as fp                                       # noqa: E402
fp = importlib.reload(fp)

log = fp.log


def main():
    fp.build(plastic_only=False)

    hidden = 0
    for obj in bpy.context.scene.objects:
        for slot in getattr(obj, "material_slots", []):
            if slot.material is not None and slot.material.name == "MAT_shell":
                obj.hide_render = True
                hidden += 1
                break

    # Un probe qui ne cache rien rendrait une image identique au rendu normal et
    # se lirait comme « la coque n'y est pour rien » — conclusion inverse de la
    # verite. On exige d'avoir effectivement cache quelque chose.
    if hidden == 0:
        raise RuntimeError("aucun objet portant MAT_shell — rien n'a ete cache, "
                           "le probe ne discriminerait rien")
    log("coque masquee : %d objet(s)" % hidden)

    proto = fp.proto
    out_dir = os.path.join(_HERE, "renders", "pcb_probe")
    proto.CONFIG["render"]["output_prefix"] = "pcb_"
    proto.CONFIG["render"]["resolution"] = (1672, 941)
    proto.configure_render(output_dir=out_dir)
    scene = bpy.context.scene
    scene.frame_start = scene.frame_end = 1
    scene.render.filepath = os.path.join(out_dir, "pcb_nue")
    bpy.ops.render.render(write_still=True)
    written = scene.render.filepath + ".png"
    log("ecrit : %s (existe=%s)" % (written, os.path.exists(written)))


if __name__ == "__main__":
    main()
