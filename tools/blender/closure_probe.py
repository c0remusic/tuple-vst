"""Sonde : quelle composante de MAT_shell fait franchir le plafond de closures.

Cycles plafonne a 64 closures par shader compile et abandonne les suivantes
SANS lever d'erreur — un simple WARNING sur stderr, qui ne nomme pas le
coupable. `closure_audit.py` a montre qu'aucun graphe de materiau n'approche
64 en comptant les noeuds : le Principled se developpe donc en BEAUCOUP plus
de closures qu'il n'a de noeuds, et le comptage statique ne peut pas trancher.

Cette sonde tranche autrement : elle neutralise UNE composante a la fois et
regarde si le WARNING tombe. C'est la mesure, pas le modele, qui decide.

Ne rend pas d'image utile : resolution minimale, 1 sample. Le WARNING est
emis a la COMPILATION des shaders, avant le rendu proprement dit — inutile de
payer une image complete pour l'observer.

    blender --background --python-exit-code 1 --python closure_probe.py -- --mode nosss

Modes : base, novolume, nosss, notransmission, nocoat, nosheen, diffuse
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bpy  # noqa: E402

import tuple_faceplate as fp  # noqa: E402
import tuple_vst_proto as proto  # noqa: E402


MODES = ("base", "novolume", "nosss", "notransmission", "nocoat", "nosheen",
         "diffuse")


def parse_mode(argv):
    """Rend (mode, full). `full` bascule en qualite de rendu comparable a la
    reference : 1672x941 et les samples de la CONFIG, au lieu de la vignette
    a 1 sample qui suffit a observer le WARNING."""
    if "--" not in argv:
        return "base", False
    rest = argv[argv.index("--") + 1:]
    mode, full = "base", False
    i = 0
    while i < len(rest):
        if rest[i] == "--mode":
            if rest[i + 1] not in MODES:
                raise SystemExit("--mode attend %s, recu %r"
                                 % (" | ".join(MODES), rest[i + 1]))
            mode = rest[i + 1]; i += 2
        elif rest[i] == "--full":
            full = True; i += 1
        else:
            raise SystemExit("argument inconnu : %r" % rest[i])
    return mode, full


def find_principled(tree):
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            return node
    raise RuntimeError("aucun Principled dans MAT_shell — le materiau a change, "
                       "relire _shell() avant d'utiliser cette sonde")


def zero_socket(node, name):
    """Met un socket a zero. Echoue fort s'il n'existe pas.

    Un socket absent signifie que le nom a change dans cette version de
    Blender ; passer outre en silence rendrait la sonde muette et son verdict
    faux — elle conclurait 'sans effet' alors qu'elle n'a rien neutralise.
    """
    for sock in node.inputs:
        if sock.name == name:
            if sock.is_linked:
                for link in list(sock.links):
                    node.id_data.links.remove(link)
            sock.default_value = 0.0
            return
    raise RuntimeError("socket %r introuvable sur le Principled de MAT_shell" % name)


def main():
    mode, full = parse_mode(sys.argv)
    fp.build(plastic_only=False)

    mat = bpy.data.materials.get("MAT_shell")
    if mat is None or not mat.use_nodes:
        raise RuntimeError("MAT_shell introuvable ou sans nodes apres build()")
    tree = mat.node_tree
    bsdf = find_principled(tree)

    if mode == "base":
        pass
    elif mode == "novolume":
        out = None
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeOutputMaterial":
                out = node
                break
        if out is None:
            raise RuntimeError("pas de noeud Output dans MAT_shell")
        vol = out.inputs.get("Volume")
        if vol is None:
            raise RuntimeError("pas d'entree Volume sur l'Output de MAT_shell")
        n = len(vol.links)
        for link in list(vol.links):
            tree.links.remove(link)
        print("[probe] %d lien(s) Volume retire(s)" % n)
        if n == 0:
            raise RuntimeError(
                "aucun lien Volume a retirer — la sonde n'aurait rien "
                "neutralise, son verdict serait faux. Depuis le 2026-07-30 le "
                "volume est debranche par defaut : remettre SHELL_VOLUME = True "
                "dans tuple_faceplate.py pour rejouer cette comparaison.")
    elif mode == "nosss":
        zero_socket(bsdf, "Subsurface Weight")
    elif mode == "notransmission":
        zero_socket(bsdf, "Transmission Weight")
    elif mode == "nocoat":
        zero_socket(bsdf, "Coat Weight")
    elif mode == "nosheen":
        zero_socket(bsdf, "Sheen Weight")
    elif mode == "diffuse":
        diff = tree.nodes.new("ShaderNodeBsdfDiffuse")
        out = None
        for node in tree.nodes:
            if node.bl_idname == "ShaderNodeOutputMaterial":
                out = node
        for link in list(out.inputs["Surface"].links):
            tree.links.remove(link)
        tree.links.new(diff.outputs["BSDF"], out.inputs["Surface"])
        print("[probe] surface remplacee par un Diffuse nu")

    print("[probe] mode = %s, full = %s" % (mode, full))

    proto.CONFIG["render"]["output_prefix"] = "probe_%s_" % mode
    # En --full on rend a la taille EXACTE de la maquette : sans ca les
    # frequences ne sont pas comparables et detail_metrics mesure autre chose.
    proto.CONFIG["render"]["resolution"] = (1672, 941) if full else (167, 94)
    out_dir = os.path.join(_HERE, "renders", "closure_probe")
    proto.configure_render(samples=None if full else 1, resolution_percent=100,
                           output_dir=out_dir, engine="CYCLES")
    scene = bpy.context.scene
    scene.frame_start = scene.frame_end = 1
    suffix = "_full" if full else ""
    scene.render.filepath = os.path.join(out_dir, "probe_%s%s" % (mode, suffix))
    bpy.ops.render.render(write_still=True)
    print("[probe] rendu termine, mode = %s, full = %s" % (mode, full))


if __name__ == "__main__":
    main()
