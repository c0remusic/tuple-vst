"""
Cale l'exposition sur une MESURE de la distribution tonale, pas à l'œil.

Constat qui a motivé l'outil. Le rendu de la façade mesurait une médiane de
luminance à 0,796, avec 84,5 % des pixels au-dessus de 0,60 et un tiers
au-dessus de 0,85. L'image était bimodale — une grosse masse claire plus les
écrans OLED à 0 — et presque rien dans les tons moyens. D'où l'impression de
platitude : sans médiane exploitable, pads, blocs et libellés n'ont pas de place
pour se séparer les uns des autres.

Juger une exposition à l'œil sur un écran non calibré ne marche pas, d'autant
qu'ici la transformation de vue est AgX, donc non linéaire : diviser la lumière
par deux ne divise pas la valeur affichée par deux. On mesure.

CIBLE
    médiane entre 0,42 et 0,56, et moins de 10 % des pixels au-dessus de 0,85.
    Une médiane plus basse noircit les blancs du boîtier, plus haute reproduit
    l'aplatissement constaté.

USAGE
    cd tools/blender
    blender --background --python-exit-code 1 --python tune_exposure.py
    blender --background --python-exit-code 1 --python tune_exposure.py -- --plastic
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

EXPOSURES = [-2.1, -2.7, -3.3, -3.9]
# MESURES DE LA VRAIE REFERENCE (e0e8c286-...png, 1672x941) :
#   mediane 0.619   p25 0.350   p75 0.753   p95 0.832   >0.85 = 3.5 %
# Ces chiffres remplacent deux cibles fausses successives : une heuristique
# generique (0.42-0.56), puis les mesures de tuple_front_product_render.png que
# j'avais pris pour la maquette sans l'ouvrir (mediane 0.799).
REF = {"median": 0.619, "p25": 0.350, "p75": 0.753, "over_85": 3.5}
TARGET = (0.58, 0.66)
SAMPLE_STEP = 40


def measure(path):
    """Médiane de luminance et part de hautes lumières d'un PNG.

    Échantillonnage régulier : lire 2 millions de pixels par variante
    coûterait plus que les rendus eux-mêmes.
    """
    img = bpy.data.images.load(path)
    try:
        w, h = img.size
        px = list(img.pixels)
        lum = []
        for i in range(0, w * h, SAMPLE_STEP):
            o = i * 4
            lum.append(0.2126 * px[o] + 0.7152 * px[o + 1] + 0.0722 * px[o + 2])
        if not lum:
            raise RuntimeError("aucun pixel échantillonné dans %s" % path)
        lum.sort()
        n = len(lum)
        return {
            "median": lum[n // 2],
            "p25": lum[n // 4],
            "p75": lum[3 * n // 4],
            "over_85": 100.0 * sum(1 for v in lum if v > 0.85) / n,
            "under_10": 100.0 * sum(1 for v in lum if v < 0.10) / n,
        }
    finally:
        bpy.data.images.remove(img)


def parse_args(argv):
    args = {"plastic": False, "samples": 90, "percent": 45}
    if "--" not in argv:
        return args
    rest = argv[argv.index("--") + 1:]
    i = 0
    while i < len(rest):
        if rest[i] == "--plastic":
            args["plastic"] = True; i += 1
        elif rest[i] == "--samples":
            args["samples"] = int(rest[i + 1]); i += 2
        elif rest[i] == "--percent":
            args["percent"] = int(rest[i + 1]); i += 2
        else:
            raise SystemExit("argument inconnu : %r" % rest[i])
    return args


def main():
    args = parse_args(sys.argv)
    out_dir = os.path.join(_HERE, "renders", "tune_exposure")
    log("Blender %s — calage de l'exposition sur mesure" % bpy.app.version_string)

    fp.build(plastic_only=args["plastic"])
    proto = fp.proto
    proto.CONFIG["render"]["output_prefix"] = "exp_"
    proto.configure_render(samples=args["samples"],
                           resolution_percent=args["percent"],
                           output_dir=out_dir)

    scene = bpy.context.scene
    rows = []
    for ev in EXPOSURES:
        scene.view_settings.exposure = ev
        if abs(scene.view_settings.exposure - ev) > 1e-6:
            raise RuntimeError("exposition %r non prise en compte" % ev)
        path = os.path.join(out_dir, "exp_%+05.1f" % ev)
        scene.render.filepath = path
        log("rendu exposition %+.1f EV ..." % ev)
        bpy.ops.render.render(write_still=True)
        png = path + ".png"
        if not os.path.exists(png):
            raise RuntimeError("exposition %+.1f : aucun fichier écrit" % ev)
        rows.append((ev, measure(png)))

    log("--- distribution tonale mesurée ---")
    log("  référence :  médiane %.3f  p25 %.3f  p75 %.3f  >0.85 %.1f %%"
        % (REF["median"], REF["p25"], REF["p75"], REF["over_85"]))
    log("  %6s  %7s  %6s  %6s  %8s  %9s  %s"
        % ("EV", "médiane", "p25", "p75", ">0.85 %", "écart p25", "cible"))
    best = None
    for ev, m in rows:
        inside = TARGET[0] <= m["median"] <= TARGET[1]
        log("  %+6.1f  %7.3f  %6.3f  %6.3f  %8.1f  %+9.3f  %s"
            % (ev, m["median"], m["p25"], m["p75"], m["over_85"],
               m["p25"] - REF["p25"], "OUI" if inside else "non"))
        if inside and (best is None or m["over_85"] < best[1]["over_85"]):
            best = (ev, m)

    if best is None:
        log("AUCUNE valeur balayée n'atteint la cible %.2f-%.2f : élargir "
            "EXPOSURES au lieu de choisir la moins mauvaise" % TARGET)
    else:
        log("RETENIR : %+.1f EV (médiane %.3f, %.1f %% au-dessus de 0.85)"
            % (best[0], best[1]["median"], best[1]["over_85"]))


if __name__ == "__main__":
    main()
