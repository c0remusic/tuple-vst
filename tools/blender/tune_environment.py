"""Balaie force d'environnement x exposition, et MESURE le gradient gauche-droite.

Pourquoi ce script plutot que `tune_exposure.py` seul. Depuis le branchement de
l'HDRI, aucune exposition ne cale a la fois la mediane et les hautes lumieres :
a -3,3 EV la mediane tombe juste (0,613 contre 0,619) mais 20,9 % des pixels
passent au-dessus de 0,85 contre 3,5 % sur la maquette. La mesure PAR ZONE dit
pourquoi — ce n'est pas un probleme de niveau mais de REPARTITION :

    colonne 0 (gauche)  mediane +0,27 / +0,26 / +0,17 contre la maquette
    colonne 5 (droite)  mediane -0,04 / -0,10 / -0,18

La maquette a son point le plus clair au CENTRE, le rendu l'a a GAUCHE. L'HDRI
est place en haut a gauche (rotation 122 deg) et vient s'ajouter a LIGHT_key,
deja a gauche. Sa force est le suspect direct : le commentaire du code raisonne
pour 0,30 et la valeur posee est 0,95.

L'exposition ne peut pas corriger un gradient — elle deplace toute la
distribution du meme cote. D'ou le balayage croise.

ATTENTION a ce que ce script NE mesure PAS. Un gradient n'est pas un defaut en
soi : `02_relief_3d_system.md` IMPOSE une source unique en haut a gauche, donc
un degrade vers le bas-droite est VOULU. L'objectif n'est pas de l'annuler mais
de le ramener a l'amplitude de la maquette. Egaliser les luminances par cellule
a deja supprime le modele une fois.

    blender --background --python-exit-code 1 --python tune_environment.py
    blender --background --python-exit-code 1 --python tune_environment.py -- --samples 60 --percent 40
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

STRENGTHS = [0.15, 0.30, 0.60, 0.95]
EXPOSURES = [-3.3, -3.9]

# Mesures de la VRAIE reference e0e8c286-...png (1672x941).
REF = {"median": 0.619, "p25": 0.350, "p75": 0.753, "over_85": 3.5}
# Amplitude du gradient horizontal de la maquette : mediane de la bande gauche
# moins mediane de la bande droite, sur le tiers gauche et le tiers droit.
# Releve sur la reference, pas suppose.
REF_GRADIENT = None          # calcule au demarrage sur la reference elle-meme

REFERENCE_PNG = r"C:\Users\LEETJ\Downloads\e0e8c286-0105-4e45-8ebe-8893a31789db.png"

SAMPLE_STEP = 17


def _luma_rows(path):
    """Rend (largeur, hauteur, liste de luminances lignes x colonnes).

    Passe par bpy.data.images : ce script tourne dans Blender, ou numpy n'est
    pas garanti. Les outils autonomes de Tuple_3D (numpy + PIL) restent la
    reference pour l'analyse fine ; ici on veut juste piloter le balayage.
    """
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        px = list(img.pixels)
        rows = []
        for y in range(0, h, 4):
            line = []
            for x in range(0, w, 4):
                o = (y * w + x) * 4
                line.append(0.2126 * px[o] + 0.7152 * px[o + 1] + 0.0722 * px[o + 2])
            rows.append(line)
        return w, h, rows
    finally:
        bpy.data.images.remove(img)


def _median(values):
    s = sorted(values)
    return s[len(s) // 2]


def measure(path):
    w, h, rows = _luma_rows(path)
    flat = [v for line in rows for v in line]
    if not flat:
        raise RuntimeError("aucun pixel echantillonne dans %s" % path)
    flat.sort()
    n = len(flat)

    ncols = len(rows[0])
    third = ncols // 3
    left = [v for line in rows for v in line[:third]]
    right = [v for line in rows for v in line[-third:]]

    return {
        "median": flat[n // 2],
        "p25": flat[n // 4],
        "p75": flat[3 * n // 4],
        "over_85": 100.0 * sum(1 for v in flat if v > 0.85) / n,
        "gradient": _median(left) - _median(right),
    }


def parse_args(argv):
    args = {"samples": 60, "percent": 40}
    if "--" not in argv:
        return args
    rest = argv[argv.index("--") + 1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--samples":
            args["samples"] = int(rest[i + 1]); i += 2
        elif rest[i] == "--percent":
            args["percent"] = int(rest[i + 1]); i += 2
        else:
            raise SystemExit("argument inconnu : %r" % rest[i])
    return args


def background_node():
    world = bpy.context.scene.world
    if world is None or not world.use_nodes:
        raise RuntimeError("pas de world a nodes — l'environnement n'a pas ete "
                           "construit, le balayage n'aurait aucun sens")
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        raise RuntimeError("pas de noeud Background dans le world")
    # Un balayage sur un world qui ne porte PAS l'HDRI mesurerait le vide en
    # silence. On exige la presence du noeud d'environnement.
    if not any(n.bl_idname == "ShaderNodeTexEnvironment" for n in world.node_tree.nodes):
        raise RuntimeError("aucun ShaderNodeTexEnvironment dans le world : "
                           "l'HDRI n'est pas branche, ce balayage ne mesurerait "
                           "que la couleur unie")
    return bg


def main():
    args = parse_args(sys.argv)
    out_dir = os.path.join(_HERE, "renders", "tune_environment")
    log("Blender %s — balayage environnement x exposition" % bpy.app.version_string)

    if not os.path.exists(REFERENCE_PNG):
        raise RuntimeError("maquette de reference introuvable : %s" % REFERENCE_PNG)
    ref_measure = measure(REFERENCE_PNG)
    log("reference : mediane %.3f  p25 %.3f  p75 %.3f  >0.85 %.1f %%  gradient %+.3f"
        % (ref_measure["median"], ref_measure["p25"], ref_measure["p75"],
           ref_measure["over_85"], ref_measure["gradient"]))

    fp.build(plastic_only=False)
    proto = fp.proto
    proto.CONFIG["render"]["output_prefix"] = "env_"
    proto.CONFIG["render"]["resolution"] = (1672, 941)
    proto.configure_render(samples=args["samples"],
                           resolution_percent=args["percent"],
                           output_dir=out_dir)

    bg = background_node()
    scene = bpy.context.scene
    rows = []
    for strength in STRENGTHS:
        for ev in EXPOSURES:
            bg.inputs["Strength"].default_value = strength
            scene.view_settings.exposure = ev
            if abs(bg.inputs["Strength"].default_value - strength) > 1e-6:
                raise RuntimeError("force %r non prise en compte" % strength)
            if abs(scene.view_settings.exposure - ev) > 1e-6:
                raise RuntimeError("exposition %r non prise en compte" % ev)
            path = os.path.join(out_dir, "env_%04.2f_ev%+05.1f" % (strength, ev))
            scene.render.filepath = path
            log("rendu HDRI %.2f / %+.1f EV ..." % (strength, ev))
            bpy.ops.render.render(write_still=True)
            png = path + ".png"
            if not os.path.exists(png):
                raise RuntimeError("HDRI %.2f / %+.1f : aucun fichier ecrit"
                                   % (strength, ev))
            rows.append((strength, ev, measure(png)))

    log("--- resultats ---")
    log("  %6s %6s  %7s  %6s  %6s  %8s  %9s"
        % ("HDRI", "EV", "mediane", "p25", "p75", ">0.85 %", "gradient"))
    log("  %6s %6s  %7.3f  %6.3f  %6.3f  %8.1f  %+9.3f"
        % ("ref", "-", ref_measure["median"], ref_measure["p25"],
           ref_measure["p75"], ref_measure["over_85"], ref_measure["gradient"]))
    for strength, ev, m in rows:
        log("  %6.2f %+6.1f  %7.3f  %6.3f  %6.3f  %8.1f  %+9.3f"
            % (strength, ev, m["median"], m["p25"], m["p75"], m["over_85"],
               m["gradient"]))

    log("")
    log("Lecture : `gradient` = mediane du tiers gauche moins mediane du tiers "
        "droit. Le comparer a celui de la reference, PAS le ramener a zero — "
        "la spec impose une source en haut a gauche, donc un degrade est voulu.")


if __name__ == "__main__":
    main()
