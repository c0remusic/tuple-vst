"""
TUPLE VST — prototype 3D du boîtier translucide + knob aluminium brossé.

Cible vérifiée : Blender 5.3.0 Alpha (hash 4fe17ef6be5d).
Les points d'API ci-dessous ont été SONDÉS sur cette build, pas supposés :
  - Principled BSDF utilise le nommage 4.x+ : "Transmission Weight",
    "Emission Color", "Emission Strength", "Specular IOR Level", "Coat Weight".
  - `Action.fcurves` N'EXISTE PLUS. Les fcurves se lisent via
    action.layers[].strips[].channelbags[].fcurves  (cf. iter_fcurves).
  - `Mesh.use_auto_smooth` a disparu : le lissage passe par les arêtes vives
    au niveau data (cf. smooth_by_angle).
  - `Material.use_nodes` est déprécié (retrait annoncé en 6.0) et vaut déjà
    True à la création : on n'y touche pas.
  - L'introspection `bl_rna` de scene.render.engine ne liste que BLENDER_EEVEE
    sur cette build, mais l'affectation "CYCLES" fonctionne. On n'interroge
    donc pas l'enum, on affecte directement.

USAGE

TOUJOURS passer `--python-exit-code 1`. Mesuré sur cette build : une exception
Python non rattrapée fait sortir Blender avec le code 0 — un script appelant ne
verrait donc JAMAIS l'échec, seule la trace dans le log le révèle. Avec ce flag,
l'exception devient un code de sortie 1.

    # 1. construire la scène seulement (vérification qu'elle s'exécute)
    blender --background --python-exit-code 1 --python tuple_vst_proto.py

    # 2. rendu de la frame 1
    blender --background --python-exit-code 1 --python tuple_vst_proto.py -- --render-frame 1

    # 3. toute la séquence 24 frames (sprite sheet)
    blender --background --python-exit-code 1 --python tuple_vst_proto.py -- --render-anim

    # 4. aperçu rapide EEVEE (samples et résolution réduits)
    blender --background --python-exit-code 1 --python tuple_vst_proto.py -- --render-frame 1 --engine eevee --samples 32 --percent 50

    # 5. sauvegarder le .blend pour ouvrir dans l'UI
    blender --background --python-exit-code 1 --python tuple_vst_proto.py -- --save-blend proto.blend

EXTENSION (pads, boutons, écrans LCD)
    build_knob() est paramétré et renvoie un dict {root, rotor, cap, collar}.
    Dupliquer une entrée de CONFIG["knobs"] suffit pour ajouter un knob.
    Pour des pads : réutiliser create_box() + mat_brushed_aluminium() /
    mat_indicator() et parenter au même schéma root/rotor.
"""

import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Vector

# ---------------------------------------------------------------------------
# CONFIG — tout ce qui se règle sans toucher au code
# Unités : mètres (1.0 = 1 m). Le boîtier fait 300 x 180 x 22 mm.
# ---------------------------------------------------------------------------

MM = 0.001

CONFIG = {
    "enclosure": {
        "size": (300 * MM, 180 * MM, 22 * MM),
        "bevel_width": 1.4 * MM,
        "bevel_segments": 3,
        "tint": (0.90, 0.93, 0.95, 1.0),
        "roughness": 0.055,
        "ior": 1.46,
    },
    "pcb": {
        "size": (278 * MM, 158 * MM, 1.6 * MM),
        "z_offset": 4.5 * MM,          # au-dessus de la face basse du boîtier
        "color": (0.035, 0.185, 0.075, 1.0),
        "chip_count": 16,
        "chip_seed": 7,                # graine fixe => scène reproductible
    },
    "knobs": [
        {
            "name": "hero",
            # x, y sur le boîtier ; z est calculé sur la face haute
            "xy": (0.0, 30 * MM),
            "radius": 12 * MM,
            "height": 14 * MM,
            "segments": 96,
            "collar_color": (0.05, 0.28, 0.85, 1.0),
            "collar_emission": 0.8,
            "indicator_color": (0.62, 0.86, 1.0, 1.0),
            "indicator_strength": 14.0,
        },
    ],
    "animation": {
        "frame_start": 1,
        "frame_end": 24,
        "angle_start_deg": -135.0,
        "angle_end_deg": 135.0,
    },
    "camera": {
        "focal_mm": 85.0,
        "sensor_mm": 36.0,
        "fstop": 3.5,
        "distance": 260 * MM,
        "azimuth_deg": -58.0,
        "elevation_deg": 32.0,
    },
    "lighting": {
        # (nom, position, taille m, puissance W)
        "key":  {"loc": (-300 * MM, -280 * MM, 400 * MM), "size": 500 * MM, "power": 150.0,
                 "color": (1.0, 0.98, 0.95)},
        "fill": {"loc": (450 * MM, -200 * MM, 180 * MM), "size": 900 * MM, "power": 45.0,
                 "color": (0.92, 0.95, 1.0)},
        "rim":  {"loc": (150 * MM, 450 * MM, 300 * MM), "size": 350 * MM, "power": 200.0,
                 "color": (0.88, 0.94, 1.0)},
        "backdrop_grey": 0.19,
        "world_grey": 0.045,
    },
    "render": {
        "samples": 256,
        "resolution": (1920, 1080),
        "resolution_percent": 100,
        "output_subdir": os.path.join("renders", "knob_rotation"),
        "output_prefix": "knob_",
    },
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Utilitaires bas niveau
# ---------------------------------------------------------------------------

def log(msg):
    print("[tuple-proto] %s" % msg)
    sys.stdout.flush()


def clear_scene():
    """Vide la scène et purge les datablocks orphelins.

    On n'utilise PAS wm.read_factory_settings : cela réinitialiserait aussi
    les préférences, dont l'activation de l'add-on Cycles.
    """
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    # sinon get_collection rendrait des références mortes au run suivant
    _COLLECTIONS.clear()

    # purge des datablocks sans utilisateur, en plusieurs passes
    # (retirer un matériau peut libérer une texture, etc.)
    pools = (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
             bpy.data.cameras, bpy.data.actions, bpy.data.node_groups,
             bpy.data.images, bpy.data.textures)
    for _ in range(4):
        removed = 0
        for pool in pools:
            for db in list(pool):
                if db.users == 0:
                    pool.remove(db)
                    removed += 1
        if removed == 0:
            break

    log("scène vidée (%d objets restants)" % len(bpy.data.objects))


_COLLECTIONS = {}


def get_collection(name):
    """Collection nommée, créée à la demande sous la collection de scène.

    Convention du projet : une collection par famille de pièces, pour pouvoir
    isoler/masquer une famille sans toucher aux autres.
    """
    coll = _COLLECTIONS.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
        _COLLECTIONS[name] = coll
    return coll


def link(ob, collection="MISC"):
    get_collection(collection).objects.link(ob)
    return ob


def set_input(node, candidates, value):
    """Affecte une entrée de node en essayant plusieurs noms possibles.

    Les sockets du Principled BSDF ont été renommés en 4.0 (et peuvent encore
    bouger). Plutôt que de deviner, on essaie une liste et on échoue FORT si
    aucun nom ne correspond — pas de fallback silencieux.
    """
    if isinstance(candidates, str):
        candidates = [candidates]
    for name in candidates:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return socket
    raise RuntimeError(
        "aucune entrée %r sur le node %r. Entrées disponibles : %s"
        % (candidates, node.bl_idname, [i.name for i in node.inputs])
    )


def new_material(name):
    """Crée un matériau à nodes et renvoie (mat, nodes, links, bsdf).

    `use_nodes` est déjà True à la création sur cette build et son accès est
    déprécié : on ne l'affecte pas.
    """
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    if nt is None:
        raise RuntimeError("matériau %r sans node_tree" % name)
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("Principled BSDF absent du matériau %r" % name)
    return mat, nt.nodes, nt.links, bsdf


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


def create_box(name, size, location=(0.0, 0.0, 0.0), collection="MISC"):
    """Boîte aux dimensions EXACTES, sans passer par l'échelle objet.

    Construite en bmesh : aucune dépendance au contexte, donc fiable en
    --background. L'échelle objet reste à 1, ce qui garde les modificateurs
    Bevel uniformes.
    """
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    return link(ob, collection)


def create_cylinder(name, radius, height, segments=64, location=(0.0, 0.0, 0.0),
                    collection="MISC"):
    """Cylindre centré sur son axe Z, dimensions exactes (radius1/radius2).

    bmesh.ops.create_cone attend radius1/radius2 sur cette build (sondé).
    """
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=height,
    )
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    return link(ob, collection)


def create_plane(name, size, location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0),
                 collection="MISC"):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    ob.rotation_euler = rotation
    return link(ob, collection)


def smooth_by_angle(ob, angle_deg=30.0):
    """Lissage par angle au niveau data.

    `Mesh.use_auto_smooth` n'existe plus depuis 4.1 : on met toutes les faces
    en smooth et on marque vives les arêtes dont l'angle dièdre dépasse le
    seuil. Depuis 4.1 le moteur respecte directement ces arêtes vives.
    """
    me = ob.data
    for poly in me.polygons:
        poly.use_smooth = True

    threshold = math.radians(angle_deg)
    bm = bmesh.new()
    bm.from_mesh(me)
    for edge in bm.edges:
        # short-circuit volontaire : calc_face_angle lève si != 2 faces
        edge.smooth = (len(edge.link_faces) == 2
                       and edge.calc_face_angle() <= threshold)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


def add_bevel(ob, width, segments=3, angle_deg=30.0, name="bevel"):
    mod = ob.modifiers.new(name, "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle_deg)
    mod.miter_outer = "MITER_ARC"
    mod.harden_normals = False
    return mod


def iter_fcurves(action):
    """Itère les fcurves d'une action, compatible actions à slots.

    IMPORTANT : sur Blender 5.3, `Action.fcurves` n'existe plus
    (AttributeError vérifié). Le chemin réel est
    action.layers[].strips[].channelbags[].fcurves. On garde le chemin legacy
    en premier au cas où le script tourne sur une build plus ancienne.
    """
    if action is None:
        return
    if hasattr(action, "fcurves"):
        for fcurve in action.fcurves:
            yield fcurve
        return
    for layer in action.layers:
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                for fcurve in bag.fcurves:
                    yield fcurve


# ---------------------------------------------------------------------------
# Matériaux
# ---------------------------------------------------------------------------

def mat_translucent_shell():
    """Polycarbonate / verre translucide : transmission forte, IOR ~1.46."""
    cfg = CONFIG["enclosure"]
    mat, nodes, links, bsdf = new_material("MAT_shell_translucent")

    set_input(bsdf, "Base Color", cfg["tint"])
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", cfg["roughness"])
    set_input(bsdf, "IOR", cfg["ior"])
    set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.5)
    set_input(bsdf, ["Coat Weight", "Clearcoat"], 0.0)

    # micro-relief très faible : évite le rendu "verre CG parfait"
    coord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    bump = nodes.new("ShaderNodeBump")
    noise.inputs["Scale"].default_value = 240.0
    noise.inputs["Detail"].default_value = 2.0
    bump.inputs["Strength"].default_value = 0.03
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    mat.use_backface_culling = False
    return mat


def mat_pcb_green():
    """Vernis épargne vert, mat, légèrement granuleux."""
    cfg = CONFIG["pcb"]
    mat, nodes, links, bsdf = new_material("MAT_pcb_green")

    set_input(bsdf, "Base Color", cfg["color"])
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", 0.38)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.45)

    coord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    bump = nodes.new("ShaderNodeBump")
    noise.inputs["Scale"].default_value = 420.0
    noise.inputs["Detail"].default_value = 3.0
    bump.inputs["Strength"].default_value = 0.12
    links.new(coord.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_chip_black():
    """Boîtier de composant : plastique noir, semi-mat."""
    mat, _nodes, _links, bsdf = new_material("MAT_chip_black")
    set_input(bsdf, "Base Color", (0.018, 0.018, 0.020, 1.0))
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", 0.42)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.5)
    return mat


def mat_brushed_aluminium():
    """Aluminium brossé circulaire.

    Deux mécanismes complémentaires :
      - anisotropie du Principled + node Tangent en mode RADIAL/Z, qui étire
        le reflet spéculaire dans le sens du brossage ;
      - relief procédural : Wave en anneaux (rainures concentriques) puis
        Noise fin par-dessus, chaînés via deux nodes Bump.
    """
    mat, nodes, links, bsdf = new_material("MAT_alu_brushed")

    set_input(bsdf, "Base Color", (0.86, 0.87, 0.89, 1.0))
    set_input(bsdf, "Metallic", 1.0)
    set_input(bsdf, "Roughness", 0.15)
    set_input(bsdf, "Anisotropic", 0.85)
    set_input(bsdf, "Anisotropic Rotation", 0.0)

    tangent = nodes.new("ShaderNodeTangent")
    tangent.direction_type = "RADIAL"
    tangent.axis = "Z"
    links.new(tangent.outputs["Tangent"], bsdf.inputs["Tangent"])

    coord = nodes.new("ShaderNodeTexCoord")

    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.rings_direction = "Z"
    wave.wave_profile = "SIN"
    wave.inputs["Scale"].default_value = 90.0
    wave.inputs["Distortion"].default_value = 22.0
    wave.inputs["Detail"].default_value = 4.0
    wave.inputs["Detail Scale"].default_value = 3.0

    bump_rings = nodes.new("ShaderNodeBump")
    bump_rings.inputs["Strength"].default_value = 0.14

    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 900.0
    grain.inputs["Detail"].default_value = 2.0

    bump_grain = nodes.new("ShaderNodeBump")
    bump_grain.inputs["Strength"].default_value = 0.05

    links.new(coord.outputs["Object"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], bump_rings.inputs["Height"])
    links.new(coord.outputs["Object"], grain.inputs["Vector"])
    links.new(grain.outputs["Fac"], bump_grain.inputs["Height"])
    links.new(bump_rings.outputs["Normal"], bump_grain.inputs["Normal"])
    links.new(bump_grain.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_indicator(name, color, strength):
    """Témoin de position lumineux."""
    mat, _nodes, _links, bsdf = new_material(name)
    set_input(bsdf, "Base Color", (0.02, 0.02, 0.02, 1.0))
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", 0.3)
    set_input(bsdf, ["Emission Color", "Emission"], color)
    set_input(bsdf, "Emission Strength", strength)
    return mat


def mat_accent_collar(name, color, emission):
    """Collerette anodisée bleue, légèrement émissive pour la faire ressortir."""
    mat, _nodes, _links, bsdf = new_material(name)
    set_input(bsdf, "Base Color", color)
    set_input(bsdf, "Metallic", 0.85)
    set_input(bsdf, "Roughness", 0.28)
    set_input(bsdf, ["Emission Color", "Emission"], color)
    set_input(bsdf, "Emission Strength", emission)
    return mat


def mat_backdrop():
    grey = CONFIG["lighting"]["backdrop_grey"]
    mat, _nodes, _links, bsdf = new_material("MAT_backdrop")
    set_input(bsdf, "Base Color", (grey, grey, grey, 1.0))
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "Roughness", 0.55)
    return mat


# ---------------------------------------------------------------------------
# Géométrie — boîtier + PCB
# ---------------------------------------------------------------------------

def build_enclosure():
    """Dalle translucide posée sur le sol (face basse à z = 0).

    Choix assumé : dalle PLEINE, PCB noyé dedans (façon résine/encapsulation)
    plutôt que coque creuse + Solidify. C'est ce qui donne le look "PCB sous
    plastique" avec le moins de géométrie. Pour une vraie coque : ajouter un
    modificateur SOLIDIFY et retirer la face haute.

    Ombrage à plat volontaire : sur du verre, les 3 segments du bevel lisent
    comme un chanfrein usiné. Passer harden_normals à True demanderait un
    ombrage lisse et rendrait les grandes faces planes incorrectes.
    """
    cfg = CONFIG["enclosure"]
    sx, sy, sz = cfg["size"]
    ob = create_box("SHELL_body", (sx, sy, sz), location=(0.0, 0.0, sz / 2.0),
                    collection="SHELL")
    add_bevel(ob, cfg["bevel_width"], cfg["bevel_segments"])
    assign(ob, mat_translucent_shell())
    log("boîtier : %.0f x %.0f x %.0f mm, bevel %.1f mm x%d"
        % (sx / MM, sy / MM, sz / MM, cfg["bevel_width"] / MM, cfg["bevel_segments"]))
    return ob


def build_pcb():
    """PCB verte + puces noires, visible à travers le boîtier.

    Placement des puces : pseudo-aléatoire à graine FIXE (CONFIG.pcb.chip_seed)
    pour que la scène soit reproductible d'un run à l'autre.
    """
    cfg = CONFIG["pcb"]
    px, py, pz = cfg["size"]
    z = cfg["z_offset"] + pz / 2.0

    pcb = create_box("PCB_board", (px, py, pz), location=(0.0, 0.0, z),
                     collection="PCB")
    assign(pcb, mat_pcb_green())

    chip_mat = mat_chip_black()
    rng = random.Random(cfg["chip_seed"])

    # zone à éviter : l'empreinte des knobs, pour ne pas coller une puce
    # juste sous le knob héros
    keepout = []
    for knob in CONFIG["knobs"]:
        kx, ky = knob["xy"]
        keepout.append((kx, ky, knob["radius"] * 2.2))

    chips = []
    attempts = 0
    while len(chips) < cfg["chip_count"] and attempts < cfg["chip_count"] * 40:
        attempts += 1
        cw = rng.uniform(6 * MM, 22 * MM)
        cd = rng.uniform(4 * MM, 14 * MM)
        ch = rng.uniform(1.5 * MM, 3.0 * MM)
        cx = rng.uniform(-px / 2 + cw, px / 2 - cw)
        cy = rng.uniform(-py / 2 + cd, py / 2 - cd)

        if any(math.hypot(cx - kx, cy - ky) < r for kx, ky, r in keepout):
            continue

        # coordonnées LOCALES par rapport au centre de la PCB : on ne touche
        # pas à matrix_parent_inverse, qui exigerait un matrix_world à jour
        # (cf. note dans build_knob).
        chip = create_box("PCB_chip_%02d" % len(chips), (cw, cd, ch),
                          location=(cx, cy, pz / 2.0 + ch / 2.0),
                          collection="PCB")
        chip.rotation_euler.z = rng.choice((0.0, math.pi / 2.0))
        chip.parent = pcb
        assign(chip, chip_mat)
        chips.append(chip)

    log("PCB : %.0f x %.0f mm, %d puces (graine %d, %d tirages)"
        % (px / MM, py / MM, len(chips), cfg["chip_seed"], attempts))
    return pcb, chips


# ---------------------------------------------------------------------------
# Géométrie — knob (dupliquable)
# ---------------------------------------------------------------------------

def build_knob(spec, base_z, alu_mat=None):
    """Construit un knob et renvoie ses parties.

    Hiérarchie, pensée pour que l'animation ne fasse tourner QUE ce qui doit
    tourner :

        KNOB_<name>_root      (Empty, statique, positionné sur le boîtier)
          |- KNOB_<name>_collar   collerette accent, STATIQUE
          `- KNOB_<name>_rotor    (Empty, c'est lui qu'on anime en Z)
               |- KNOB_<name>_cap        cylindre alu brossé
               `- KNOB_<name>_indicator  témoin lumineux

    Renvoie {"root", "rotor", "cap", "collar", "indicator"}.
    Pour un pad ou un bouton : réutiliser ce schéma en remplaçant le cylindre
    par create_box() et en n'animant pas le rotor.

    ATTENTION — les enfants sont créés en coordonnées LOCALES et
    `matrix_parent_inverse` est laissé à l'identité. La tentation est d'écrire
    l'enfant en coordonnées monde puis de compenser avec
    `matrix_parent_inverse = parent.matrix_world.inverted()` : ça NE MARCHE PAS
    ici, parce que `matrix_world` du parent vaut encore l'identité tant que le
    depsgraph n'a pas été réévalué. L'inverse ne compense alors rien et
    l'enfant se retrouve décalé de la position du parent (collerette flottant
    à 30 mm du knob, constaté au rendu).
    """
    name = spec["name"]
    kx, ky = spec["xy"]
    radius = spec["radius"]
    height = spec["height"]
    segments = spec["segments"]

    if alu_mat is None:
        alu_mat = mat_brushed_aluminium()

    root = bpy.data.objects.new("KNOB_%s_root" % name, None)
    root.location = (kx, ky, base_z)
    root.empty_display_size = radius
    link(root, "KNOBS")

    rotor = bpy.data.objects.new("KNOB_%s_rotor" % name, None)
    rotor.empty_display_size = radius * 0.5
    link(rotor, "KNOBS")
    rotor.parent = root

    # Toutes les positions ci-dessous sont LOCALES au parent : l'origine
    # (0, 0, 0) est déjà sur la face haute du boîtier, à l'aplomb du knob.

    # collerette accent : disque un peu plus large, à la base, statique
    collar_h = 2.5 * MM
    collar = create_cylinder("KNOB_%s_collar" % name, radius * 1.10, collar_h,
                             segments=segments, location=(0.0, 0.0, collar_h / 2.0),
                             collection="KNOBS")
    smooth_by_angle(collar, 30.0)
    assign(collar, mat_accent_collar("MAT_collar_%s" % name,
                                     spec["collar_color"], spec["collar_emission"]))
    collar.parent = root

    # corps du knob
    cap = create_cylinder("KNOB_%s_cap" % name, radius, height,
                          segments=segments,
                          location=(0.0, 0.0, collar_h + height / 2.0),
                          collection="KNOBS")
    smooth_by_angle(cap, 30.0)
    add_bevel(cap, 0.9 * MM, segments=4)
    assign(cap, alu_mat)
    cap.parent = rotor

    # témoin de position sur le dessus, orienté vers +Y (= 0°)
    ind_len = radius * 0.62
    ind = create_box(
        "KNOB_%s_indicator" % name,
        (1.4 * MM, ind_len, 0.7 * MM),
        location=(0.0, radius - ind_len / 2.0 - 1.2 * MM,
                  collar_h + height + 0.2 * MM),
        collection="KNOBS",
    )
    assign(ind, mat_indicator("MAT_indicator_%s" % name,
                              spec["indicator_color"], spec["indicator_strength"]))
    ind.parent = rotor

    cap_top = base_z + collar_h + height          # coordonnée MONDE, pour la visée

    log("knob %r : r=%.1f mm h=%.1f mm, sommet z=%.1f mm"
        % (name, radius / MM, height / MM, cap_top / MM))

    return {"root": root, "rotor": rotor, "cap": cap,
            "collar": collar, "indicator": ind,
            "top_z": cap_top, "height": height, "radius": radius}


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def animate_knob_rotation(rotor, frame_start=None, frame_end=None,
                          angle_start_deg=None, angle_end_deg=None):
    """Rotation Z linéaire du rotor, deux clés, interpolation LINEAR.

    L'accès aux fcurves passe par iter_fcurves : `Action.fcurves` n'existe
    plus sur Blender 5.3. Sans passer par les channelbags, l'interpolation
    resterait en BEZIER et la sprite sheet aurait un ease-in/out parasite.
    """
    cfg = CONFIG["animation"]
    frame_start = cfg["frame_start"] if frame_start is None else frame_start
    frame_end = cfg["frame_end"] if frame_end is None else frame_end
    a0 = cfg["angle_start_deg"] if angle_start_deg is None else angle_start_deg
    a1 = cfg["angle_end_deg"] if angle_end_deg is None else angle_end_deg

    rotor.rotation_mode = "XYZ"

    rotor.rotation_euler.z = math.radians(a0)
    rotor.keyframe_insert("rotation_euler", index=2, frame=frame_start)
    rotor.rotation_euler.z = math.radians(a1)
    rotor.keyframe_insert("rotation_euler", index=2, frame=frame_end)

    action = rotor.animation_data.action if rotor.animation_data else None
    if action is None:
        raise RuntimeError("aucune action créée sur %r" % rotor.name)

    keys = 0
    for fcurve in iter_fcurves(action):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "LINEAR"
            keys += 1
        fcurve.update()
    if keys == 0:
        raise RuntimeError(
            "aucune keyframe atteinte via iter_fcurves : le chemin d'accès "
            "aux fcurves a changé, l'interpolation LINEAR n'est pas garantie"
        )

    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)

    span = frame_end - frame_start
    log("animation : %.0f deg -> %.0f deg sur frames %d-%d (%d clés LINEAR, %.2f deg/frame)"
        % (a0, a1, frame_start, frame_end, keys,
           (a1 - a0) / span if span else 0.0))
    return action


# ---------------------------------------------------------------------------
# Éclairage + fond
# ---------------------------------------------------------------------------

def build_studio_lighting(aim):
    """Trois points AREA (key / fill / rim) + fond gris neutre.

    Les lampes sont orientées par contrainte TRACK_TO vers l'empty de visée :
    plus fiable qu'un calcul d'euler à la main, et il suffit de bouger `aim`
    pour recadrer tout l'éclairage.
    """
    cfg = CONFIG["lighting"]
    lights = {}

    for role in ("key", "fill", "rim"):
        spec = cfg[role]
        data = bpy.data.lights.new("LIGHT_%s" % role, type="AREA")
        data.shape = "SQUARE"
        data.size = spec["size"]
        data.energy = spec["power"]
        data.color = spec["color"]
        ob = bpy.data.objects.new("LIGHT_%s" % role, data)
        ob.location = spec["loc"]
        link(ob, "LIGHTS")
        con = ob.constraints.new("TRACK_TO")
        con.target = aim
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        lights[role] = ob

    # fond : sol + paroi arrière
    backdrop = mat_backdrop()
    floor = create_plane("BACKDROP_floor", 4.0, location=(0.0, 0.0, 0.0),
                         collection="BACKDROP")
    assign(floor, backdrop)
    wall = create_plane("BACKDROP_wall", 4.0, location=(0.0, 1.2, 0.0),
                        rotation=(math.radians(90.0), 0.0, 0.0),
                        collection="BACKDROP")
    assign(wall, backdrop)

    # ciel très sombre : les AREA font tout le travail
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        g = cfg["world_grey"]
        bg.inputs["Color"].default_value = (g, g, g, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    log("éclairage : key %.0fW / fill %.0fW / rim %.0fW, fond gris %.2f"
        % (cfg["key"]["power"], cfg["fill"]["power"], cfg["rim"]["power"],
           cfg["backdrop_grey"]))
    return lights, (floor, wall)


# ---------------------------------------------------------------------------
# Caméra
# ---------------------------------------------------------------------------

def build_hero_camera(aim):
    """Hero shot 85 mm f/3.5, mise au point sur l'empty de visée.

    Position calculée en coordonnées sphériques autour de `aim`, orientation
    déléguée à une contrainte TRACK_TO (pas de quaternion à la main).
    """
    cfg = CONFIG["camera"]
    data = bpy.data.cameras.new("CAM_hero")
    data.lens = cfg["focal_mm"]
    data.sensor_width = cfg["sensor_mm"]
    data.dof.use_dof = True
    data.dof.focus_object = aim
    data.dof.aperture_fstop = cfg["fstop"]

    d = cfg["distance"]
    az = math.radians(cfg["azimuth_deg"])
    el = math.radians(cfg["elevation_deg"])
    target = aim.location
    loc = Vector((
        target.x + d * math.cos(el) * math.sin(az),
        target.y - d * math.cos(el) * math.cos(az),
        target.z + d * math.sin(el),
    ))

    cam = bpy.data.objects.new("CAM_hero", data)
    cam.location = loc
    link(cam, "CAMERA")
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.context.scene.camera = cam

    report_dof(cfg, d)
    log("caméra : %.0f mm f/%.1f à %.0f mm (azimut %.0f deg, élévation %.0f deg)"
        % (cfg["focal_mm"], cfg["fstop"], d / MM,
           cfg["azimuth_deg"], cfg["elevation_deg"]))
    return cam


def report_dof(cfg, distance_m):
    """Profondeur de champ effective — utile car f/3.5 au 85 mm de près est
    extrêmement mince, et ça se voit tout de suite au rendu."""
    f = cfg["focal_mm"]
    n = cfg["fstop"]
    s = distance_m / MM                      # distance en mm
    coc = 0.030                              # cercle de confusion, plein format
    if s <= f:
        log("DOF : distance <= focale, calcul non pertinent")
        return None
    m = f / (s - f)                           # grandissement
    dof_mm = 2.0 * n * coc * (m + 1.0) / (m * m)
    frame_w = cfg["sensor_mm"] / f * s
    log("DOF : grandissement %.3f, zone nette ~%.2f mm, largeur de champ %.0f mm"
        % (m, dof_mm, frame_w))
    return dof_mm


# ---------------------------------------------------------------------------
# Configuration du rendu
# ---------------------------------------------------------------------------

def pick_gpu(preferred=("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")):
    """Active le meilleur backend GPU Cycles disponible. Renvoie (backend, noms).

    NE PAS filtrer sur l'enum `compute_device_type` : sur cette build, cet enum
    est VIDE via bl_rna, même après `refresh_devices()`. Itérer dessus revient à
    ne tester aucun backend et à conclure « pas de GPU » alors qu'une RTX 2060
    est présente et vue par OptiX comme par CUDA (mesuré). On tente donc chaque
    backend DIRECTEMENT et on laisse l'affectation échouer si la plateforme ne
    le connaît pas — le TypeError renvoyé liste au passage l'enum réel, qui vaut
    ('NONE', 'CUDA', 'OPTIX', 'HIP', 'ONEAPI') sous Windows.

    OptiX passe avant CUDA : sur une carte RTX il exploite les cœurs RT.
    """
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None:
        log("GPU : add-on cycles introuvable dans les préférences")
        return None, []
    prefs = addon.preferences

    if hasattr(prefs, "refresh_devices"):
        try:
            prefs.refresh_devices()
        except Exception as exc:                       # noqa: BLE001 - journalisé
            log("GPU : refresh_devices a échoué (%s)" % exc)

    for backend in preferred:
        try:
            prefs.compute_device_type = backend
        except (TypeError, AttributeError):
            continue                                   # backend inconnu ici
        if prefs.compute_device_type != backend:
            continue
        try:
            devices = list(prefs.get_devices_for_type(backend))
        except Exception as exc:                       # noqa: BLE001 - journalisé
            log("GPU : énumération %s impossible (%s)" % (backend, exc))
            continue

        usable = [d for d in devices if d.type == backend]
        if not usable:
            continue

        for dev in devices:
            dev.use = (dev.type == backend)
        names = [d.name for d in usable]
        log("GPU : %s actif -> %s" % (backend, names))
        return backend, names

    log("GPU : aucun backend utilisable, rendu en CPU")
    return None, []


def configure_units():
    """Unités de scène en MILLIMÈTRES.

    Purement un réglage d'affichage : la géométrie est construite en mètres
    (unité interne de Blender) via la constante MM. Ce réglage fait que l'UI et
    les champs numériques se lisent en mm, ce qui est la convention du projet.
    """
    unit = bpy.context.scene.unit_settings
    unit.system = "METRIC"
    unit.scale_length = 1.0
    unit.length_unit = "MILLIMETERS"
    log("unités : métrique, longueurs en millimètres")


def configure_render(samples=None, resolution_percent=None, output_dir=None,
                     engine="CYCLES"):
    """Moteur + échantillonnage + sortie.

    `engine` vaut CYCLES (rendu final photoréaliste) ou BLENDER_EEVEE (aperçu
    rapide). Les réglages propres à Cycles ne sont appliqués que pour Cycles.
    """
    cfg = CONFIG["render"]
    scene = bpy.context.scene

    # L'introspection bl_rna de render.engine ne liste que BLENDER_EEVEE sur
    # cette build alpha, alors que l'affectation CYCLES fonctionne : on
    # affecte sans consulter l'enum, puis on VÉRIFIE la relecture.
    scene.render.engine = engine
    if scene.render.engine != engine:
        raise RuntimeError("impossible de passer le moteur en %s (valeur : %r). "
                           "L'add-on correspondant est-il activé ?"
                           % (engine, scene.render.engine))

    if engine == "CYCLES":
        backend, gpu_names = pick_gpu()
        scene.cycles.device = "GPU" if backend else "CPU"

        scene.cycles.samples = cfg["samples"] if samples is None else samples
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.use_denoising = True
        for denoiser in ("OPENIMAGEDENOISE", "OPTIX"):
            try:
                scene.cycles.denoiser = denoiser
                break
            except (TypeError, AttributeError):
                continue

        # transmission : sans assez de rebonds, la dalle translucide rend noire
        scene.cycles.max_bounces = 16
        scene.cycles.transmission_bounces = 12
        scene.cycles.transparent_max_bounces = 16
        scene.cycles.caustics_refractive = True
        scene.cycles.blur_glossy = 0.5
        # Sans rebonds de volume, le shader de volume du polycarbonate ne rend
        # rien du tout : la laitance disparait en silence.
        if hasattr(scene.cycles, "volume_bounces"):
            scene.cycles.volume_bounces = 4
        if hasattr(scene.cycles, "volume_step_rate"):
            scene.cycles.volume_step_rate = 0.5
    else:
        backend, gpu_names = None, []
        eevee = scene.eevee
        if hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = cfg["samples"] if samples is None else samples

    rx, ry = cfg["resolution"]
    scene.render.resolution_x = rx
    scene.render.resolution_y = ry
    scene.render.resolution_percentage = (cfg["resolution_percent"]
                                          if resolution_percent is None
                                          else resolution_percent)
    scene.render.film_transparent = False

    img = scene.render.image_settings
    img.file_format = "PNG"
    img.color_mode = "RGBA"
    img.color_depth = "8"
    img.compression = 15

    out = output_dir or os.path.join(SCRIPT_DIR, cfg["output_subdir"])
    os.makedirs(out, exist_ok=True)
    scene.render.filepath = os.path.join(out, cfg["output_prefix"])
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True

    if engine == "CYCLES":
        log("rendu : CYCLES/%s%s, %d samples, denoise=%s, %dx%d @%d%%, "
            "rebonds max/transmission/volume = %d/%d/%d"
            % (scene.cycles.device,
               (" (%s)" % ", ".join(gpu_names)) if gpu_names else "",
               scene.cycles.samples, scene.cycles.use_denoising,
               rx, ry, scene.render.resolution_percentage,
               scene.cycles.max_bounces, scene.cycles.transmission_bounces,
               getattr(scene.cycles, "volume_bounces", -1)))
    else:
        log("rendu : %s (aperçu), %dx%d @%d%%"
            % (engine, rx, ry, scene.render.resolution_percentage))
    log("sortie : %s%s####.png" % (out + os.sep, cfg["output_prefix"]))
    return out


# ---------------------------------------------------------------------------
# Assemblage
# ---------------------------------------------------------------------------

def build_scene():
    clear_scene()

    shell = build_enclosure()
    pcb, chips = build_pcb()

    shell_top = CONFIG["enclosure"]["size"][2]
    alu = mat_brushed_aluminium()          # partagé par tous les knobs
    knobs = [build_knob(spec, shell_top, alu_mat=alu) for spec in CONFIG["knobs"]]

    hero = knobs[0]

    # empty de visée : cible commune caméra / lampes / mise au point
    aim = bpy.data.objects.new("AIM_hero", None)
    aim.location = (hero["root"].location.x, hero["root"].location.y, hero["top_z"])
    aim.empty_display_size = 0.01
    link(aim, "CAMERA")

    build_studio_lighting(aim)
    build_hero_camera(aim)
    animate_knob_rotation(hero["rotor"])

    # force la réévaluation du depsgraph : sans ça les matrix_world restent à
    # l'identité pour tout ce qui a été créé dans ce run, ce qui fausserait
    # toute vérification ou tout code ajouté ensuite.
    bpy.context.view_layer.update()
    verify_knob_alignment(knobs)

    return {"shell": shell, "pcb": pcb, "chips": chips,
            "knobs": knobs, "aim": aim}


def verify_knob_alignment(knobs, tol=1e-6):
    """Vérifie que capuchon et collerette sont bien concentriques au root.

    Ce contrôle existe parce que le bug inverse est SILENCIEUX au build : un
    mauvais `matrix_parent_inverse` ne lève aucune erreur, il déplace juste la
    pièce, et ça ne se voit qu'au rendu. Ici, ça échoue tout de suite.
    """
    for knob in knobs:
        root = knob["root"].matrix_world.translation
        for part in ("cap", "collar"):
            pos = knob[part].matrix_world.translation
            dxy = math.hypot(pos.x - root.x, pos.y - root.y)
            if dxy > tol:
                raise RuntimeError(
                    "%s décalé de %.3f mm de l'axe du knob (attendu 0) — "
                    "vérifier le parentage / matrix_parent_inverse"
                    % (knob[part].name, dxy / MM))

        # hauteur portée par le knob lui-même, pas relue dans CONFIG :
        # indexer CONFIG serait faux dès le deuxième knob.
        top = knob["cap"].matrix_world.translation.z + knob["height"] / 2.0
        if abs(top - knob["top_z"]) > tol:
            raise RuntimeError(
                "sommet réel du knob %s = %.3f mm, annoncé %.3f mm : la cible "
                "de visée / mise au point serait fausse"
                % (knob["cap"].name, top / MM, knob["top_z"] / MM))
    log("vérification : %d knob(s) concentrique(s), sommets conformes" % len(knobs))


def parse_args(argv):
    """Arguments passés après `--` sur la ligne de commande Blender."""
    args = {"render_frame": None, "render_anim": False, "samples": None,
            "percent": None, "save_blend": None, "engine": "CYCLES"}
    if "--" not in argv:
        return args
    rest = argv[argv.index("--") + 1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--render-frame":
            args["render_frame"] = int(rest[i + 1]); i += 2
        elif tok == "--render-anim":
            args["render_anim"] = True; i += 1
        elif tok == "--samples":
            args["samples"] = int(rest[i + 1]); i += 2
        elif tok == "--percent":
            args["percent"] = int(rest[i + 1]); i += 2
        elif tok == "--save-blend":
            args["save_blend"] = rest[i + 1]; i += 2
        elif tok == "--engine":
            name = rest[i + 1].upper()
            mapping = {"CYCLES": "CYCLES", "EEVEE": "BLENDER_EEVEE",
                       "BLENDER_EEVEE": "BLENDER_EEVEE"}
            if name not in mapping:
                raise SystemExit("--engine attend cycles ou eevee, recu %r" % rest[i + 1])
            args["engine"] = mapping[name]; i += 2
        else:
            raise SystemExit("argument inconnu : %r" % tok)
    return args


def main():
    args = parse_args(sys.argv)
    log("Blender %s" % bpy.app.version_string)

    configure_units()
    scene_data = build_scene()
    configure_render(samples=args["samples"], resolution_percent=args["percent"],
                     engine=args["engine"])

    log("objets dans la scène : %d" % len(bpy.data.objects))

    if args["save_blend"]:
        path = args["save_blend"]
        if not os.path.isabs(path):
            path = os.path.join(SCRIPT_DIR, path)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        log(".blend écrit : %s" % path)

    if args["render_anim"]:
        log("rendu de la séquence %d-%d..."
            % (bpy.context.scene.frame_start, bpy.context.scene.frame_end))
        bpy.ops.render.render(animation=True, write_still=True)
        log("séquence terminée")
    elif args["render_frame"] is not None:
        frame = args["render_frame"]
        bpy.context.scene.frame_set(frame)
        base = bpy.context.scene.render.filepath
        bpy.context.scene.render.filepath = "%s%04d" % (base, frame)
        log("rendu de la frame %d..." % frame)
        bpy.ops.render.render(write_still=True)
        written = bpy.context.scene.render.filepath + ".png"
        log("frame %d écrite : %s (existe=%s)"
            % (frame, written, os.path.exists(written)))
        bpy.context.scene.render.filepath = base
    else:
        log("scène construite, aucun rendu demandé "
            "(ajouter -- --render-frame 1 ou -- --render-anim)")

    return scene_data


if __name__ == "__main__":
    main()
