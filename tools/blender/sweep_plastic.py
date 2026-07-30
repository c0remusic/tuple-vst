"""
Balayages paramétriques sur le polycarbonate de la coque.

POURQUOI DES BALAYAGES ET PAS DES RÉGLAGES
    Trois réglages à l'estime sur ce matériau, deux se sont révélés faux :
      - la densité volumique à 340 « produisait une laitance dépendante de
        l'épaisseur » : le témoin à densité 0 a montré que la laitance existe
        sans aucun volume, et que 340 ne fait que noyer les composants internes ;
      - la lisibilité des libellés a été attribuée à l'encre, au relief puis à
        l'exposition avant qu'une mesure ne montre que le matériau était
        identique à celui d'un libellé parfaitement net.
    Sur un matériau translucide l'effet dépend de produits (densité × épaisseur,
    rugosité × transmission) et l'intuition est mauvaise. On mesure.

MÉTHODE
    Une SEULE construction de scène, puis un rendu par valeur. Reconstruire
    coûterait un booléen et un Solidify par variante, et rien ne garantirait que
    les variantes soient comparables.

    Chaque balayage inclut une valeur TÉMOIN à zéro : elle mesure ce que le
    paramètre apporte réellement. Sans elle, impossible de distinguer « mal
    réglé » de « sans effet ».

USAGE
    cd tools/blender
    blender --background --python-exit-code 1 --python sweep_plastic.py -- --param volume
    blender --background --python-exit-code 1 --python sweep_plastic.py -- --param roughness
    blender --background --python-exit-code 1 --python sweep_plastic.py -- --param backlight
    ... --samples 160 --percent 100      pour une passe finale
"""

import bpy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import importlib                                                   # noqa: E402
import tuple_faceplate as fp                                       # noqa: E402
fp = importlib.reload(fp)

log = fp.log


# ---------------------------------------------------------------------------
# Accès aux paramètres — par TYPE de node, jamais par nom
# ---------------------------------------------------------------------------

def _shell_node(bl_idname):
    """Le node unique de ce type dans le matériau de coque.

    Recherché par type : les noms de nodes sont localisés et peuvent être
    suffixés, le type est stable. Échoue si le compte n'est pas de 1, ce qui
    signifierait que le shader a changé et que le balayage ne mesure plus ce
    qu'il croit mesurer.
    """
    shell = fp.m_shell()
    found = [n for n in shell.node_tree.nodes if n.bl_idname == bl_idname]
    if len(found) != 1:
        raise RuntimeError("%d node(s) %s dans %r, attendu 1 — shader modifié"
                           % (len(found), bl_idname, shell.name))
    return found[0]


def set_volume(value):
    """Densité du Volume Scatter."""
    _shell_node("ShaderNodeVolumeScatter").inputs["Density"].default_value = value


def set_roughness(value):
    """Rugosité UNIFORME, en écrasant les deux bornes du MapRange.

    Le shader module normalement la rugosité par un bruit entre deux bornes.
    Pour un balayage on aplatit cette irrégularité : mesurer une plage pendant
    qu'on balaie son centre ne dirait rien de net.
    Indices numériques : MapRange expose des noms d'entrée dupliqués selon son
    type de données, la position est le seul accès non ambigu (3 = To Min,
    4 = To Max).
    """
    mr = _shell_node("ShaderNodeMapRange")
    mr.inputs[3].default_value = value
    mr.inputs[4].default_value = value


def set_backlight(value):
    """Puissance de la lampe arrière, en watts."""
    ob = bpy.data.objects.get("LIGHT_back")
    if ob is None:
        raise RuntimeError("LIGHT_back absente : le balayage ne mesurerait rien")
    ob.data.energy = value


def set_toplight(value):
    """Puissance de la lampe haute, en watts.

    Suspecte du halo central residuel : son image miroir sur un panneau plan
    face camera retombe au milieu du cadre. Le brief demande des
    « restrained specular highlights ».
    """
    ob = bpy.data.objects.get("LIGHT_top")
    if ob is None:
        raise RuntimeError("LIGHT_top absente : le balayage ne mesurerait rien")
    ob.data.energy = value


SWEEPS = {
    "toplight":  (set_toplight,  [0.0, 3.0, 9.0, 18.0], "lampe haute (W)"),
    "volume":    (set_volume,    [0.0, 40.0, 120.0, 340.0], "densité de diffusion"),
    "roughness": (set_roughness, [0.04, 0.14, 0.26, 0.40], "rugosité de surface"),
    "backlight": (set_backlight, [0.0, 10.0, 34.0, 70.0], "lampe arrière (W)"),
}

# Ce qu'on neutralise pendant chaque balayage, pour isoler la variable.
NEUTRALISE = {
    "toplight": [(set_volume, 0.0)],
    "roughness": [(set_volume, 0.0), (set_toplight, 3.0)],
    "backlight": [(set_volume, 0.0)],
    "volume": [],
}


def parse_args(argv):
    args = {"samples": 110, "percent": 60, "param": "volume"}
    if "--" not in argv:
        return args
    rest = argv[argv.index("--") + 1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--samples":
            args["samples"] = int(rest[i + 1]); i += 2
        elif rest[i] == "--percent":
            args["percent"] = int(rest[i + 1]); i += 2
        elif rest[i] == "--param":
            args["param"] = rest[i + 1]; i += 2
        else:
            raise SystemExit("argument inconnu : %r" % rest[i])
    if args["param"] not in SWEEPS:
        raise SystemExit("--param attend %s, reçu %r"
                         % ("/".join(SWEEPS), args["param"]))
    return args


def main():
    args = parse_args(sys.argv)
    param = args["param"]
    setter, values, label = SWEEPS[param]
    out_dir = os.path.join(_HERE, "renders", "sweep_" + param)

    log("Blender %s — balayage : %s" % (bpy.app.version_string, label))

    fp.build(plastic_only=True)
    proto = fp.proto
    proto.CONFIG["render"]["output_prefix"] = param + "_"
    proto.configure_render(samples=args["samples"],
                           resolution_percent=args["percent"],
                           output_dir=out_dir)

    for neutral_setter, neutral_value in NEUTRALISE[param]:
        neutral_setter(neutral_value)
        log("neutralisé pour isoler la variable : %s = %s"
            % (neutral_setter.__name__, neutral_value))

    scene = bpy.context.scene
    written = []
    for value in values:
        setter(value)
        path = os.path.join(out_dir, "%s_%05d" % (param, int(round(value * 100))))
        scene.render.filepath = path
        log("rendu %s = %.3f ..." % (param, value))
        bpy.ops.render.render(write_still=True)
        png = path + ".png"
        if not os.path.exists(png):
            raise RuntimeError("%s = %.3f : aucun fichier écrit" % (param, value))
        written.append((value, png, os.path.getsize(png)))

    log("--- balayage %s terminé ---" % param)
    for value, png, size in written:
        log("  %-10s %8.3f  ->  %s  (%d octets)"
            % (param, value, os.path.basename(png), size))
    if len({size for _v, _p, size in written}) < len(written):
        log("ATTENTION : deux rendus de taille identique — vérifier que le "
            "paramètre agit réellement avant d'interpréter quoi que ce soit")


if __name__ == "__main__":
    main()
