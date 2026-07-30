"""
TUPLE VST — façade complète en 3D, construite depuis la maquette de référence.

PRINCIPE DE COTATION
    Toutes les positions vivent dans LAYOUT en PIXELS de l'image de référence
    (1672 x 941), origine en HAUT À GAUCHE, axe Y vers le BAS — exactement comme
    on lit la maquette. Une seule constante, PX, convertit en mètres Blender.

    C'est volontaire : la sortie finale est une fenêtre 2D, donc la grandeur qui
    compte est la taille à l'écran, pas une cote physique. Re-mesurer la maquette
    et corriger un nombre ici suffit ; aucune arithmétique à refaire.

    px_to_world() fait la conversion et le retournement de Y. Ne jamais écrire de
    coordonnée monde en dur ailleurs.

DÉPENDANCE
    Réutilise les primitives éprouvées de tuple_vst_proto.py, dans le même
    dossier (create_box, create_cylinder, smooth_by_angle, set_input,
    configure_render, pick_gpu, iter_fcurves...). Pas de copie : un seul endroit
    à corriger.

CIBLE VÉRIFIÉE
    Blender 5.2.0 LTS et 5.3.0 alpha. Voir l'en-tête de tuple_vst_proto.py pour
    les pièges d'API (Action.fcurves absent, enums bl_rna vides, code de sortie 0
    sur exception).

USAGE
    cd tools/blender
    blender --background --python-exit-code 1 --python tuple_faceplate.py
    blender --background --python-exit-code 1 --python tuple_faceplate.py -- --render
    blender --background --python-exit-code 1 --python tuple_faceplate.py -- --render --engine eevee --samples 32
    blender --background --python-exit-code 1 --python tuple_faceplate.py -- --save-blend faceplate.blend

MATIÈRE DU BOÎTIER — valeurs ÉTABLIES PAR BALAYAGE, pas à l'estime
    Trois passes de réglage à l'estime sur ce plastique ont produit trois
    conclusions fausses. Les balayages de `sweep_plastic.py` ont tranché :

    1. La « laitance » n'était PAS un effet de matière. C'était la lampe haute
       vue en réflexion spéculaire au centre du panneau, plus la lampe ARRIÈRE
       vue directement en transmission à travers la coque — un émetteur
       rectangulaire lumineux derrière un panneau transmissif se voit purement
       et simplement. `LIGHT_back` porte donc `visible_transmission = False`.
    2. La densité volumique est MARGINALE à 1,2 mm de paroi : environ 5 % de
       diffusion. Elle ne produit pas la laitance ; à 340 elle noyait juste les
       composants internes.
    3. C'est la RUGOSITÉ de surface qui produit la laitance, et uniformément.
       0,04 donne du verre optique, 0,40 efface l'intérieur, 0,26 donne le
       boîtier translucide façon Game Boy.

    Règle qui en découle : sur ce matériau, ne rien régler au jugement. Passer
    par `sweep_plastic.py`, avec sa valeur témoin à zéro qui distingue
    « mal réglé » de « sans effet ».

PILE DE MODIFICATEURS DU BOÎTIER — l'ordre est significatif
    BOOLEAN (creuse les puits) -> SOLIDIFY (rend la coque creuse) -> BEVEL
    (adoucit les arêtes issues de la découpe) -> WEIGHTED NORMAL.
    Inverser BOOLEAN et BEVEL laisse les puits à angle vif. Retirer SOLIDIFY
    ramène une dalle pleine, et avec elle le voile vert de la PCB diffusé sur
    toute la façade.

ÉCARTS ASSUMÉS PAR RAPPORT À LA MAQUETTE
  - Les composants internes du boîtier sont suggérés par des puces posées sur une
    PCB, pas reproduits pastille par pastille.
  - Le clavier du panneau droit compte 24 touches ; la maquette en montre un
    nombre voisin, non compté précisément.
  - La timeline porte une graduation par mesure, alignee sur les six blocs. La
    maquette montre en plus une rangee de temps 1-2-3-4 que le brief ne demande
    pas : la remplir reviendrait a inventer du texte.
  - La rangee INVERSION (Root / 1st / 2nd / 3rd) vient du BRIEF. La maquette
    affiche son libellé mais masque ses boutons derriere le panneau PROGRESSION ;
    le brief fait foi, donc cette bande descend de 22 px pour les degager.

TOUT LE TEXTE VIENT DU BRIEF
    Les onze libellés d'accords allumes sont exactement ceux qu'il cite : C, Dm,
    Em, F, G, Am, Cmaj7, Dm7, Fmaj7, G7, Am9. Les contenus d'ecran que le brief
    ne specifie pas ne sont pas inventes : ils se deduisent de lui, ou ils
    disparaissent.
"""

import bpy
import bmesh
import math
import os
import random
import sys

# --- import des primitives du prototype (même dossier) ---------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import importlib                                                   # noqa: E402
import tuple_vst_proto as proto                                    # noqa: E402

# Dans une session Blender qui RESTE OUVERTE, `import` rend le module déjà
# charge : toute modification de tuple_vst_proto.py serait ignoree en silence,
# et on debuggerait le comportement d'une version qui n'est plus sur le disque.
# Piège vérifié le 2026-07-30 : volume_bounces restait a 0 en session vivante
# alors que le correctif etait bien dans le fichier. A noter que
# inspect.getsource() ne revele PAS le probleme, puisqu'il lit le disque et non
# le code charge.
proto = importlib.reload(proto)

log = proto.log
create_box = proto.create_box
create_cylinder = proto.create_cylinder
create_plane = proto.create_plane
smooth_by_angle = proto.smooth_by_angle
add_bevel = proto.add_bevel
set_input = proto.set_input
new_material = proto.new_material
assign = proto.assign
link = proto.link


# ===========================================================================
# Système de coordonnées
# ===========================================================================

REF_W, REF_H = 1672.0, 941.0      # taille de l'image de référence, en pixels
PX = 0.0002                        # 1 px = 0.2 mm  =>  façade 334.4 x 188.2 mm

FACE_Z = 0.0                       # plan de la façade (z = 0)
CUT_MARGIN = 8.0                   # débord des cutters devant la façade, en px
WALL = 6.0                         # épaisseur de paroi de la coque, en px (1.2 mm)
RIM = 2.4                          # largeur du filet de famille autour d'un pad, en px
ENGRAVE = 1.4                      # profondeur de gravure des libellés, en px (0.28 mm)
CORNER_R = 17.0                    # rayon des coins du boîtier, en px (3.4 mm)
BODY_D = 60.0                      # épaisseur du boîtier, en px (12 mm)
# 26 px (5,2 mm) ne montrait aucune épaisseur, alors que le brief demande une
# très légère plongée « to reveal the thickness of the chassis ».


def px_to_world(x_px, y_px):
    """(x, y) en pixels de la maquette -> (x, y) en mètres, centré sur l'origine.

    L'axe Y de l'image descend, celui de Blender monte : on retourne Y ici et
    NULLE PART AILLEURS.
    """
    return ((x_px - REF_W / 2.0) * PX, (REF_H / 2.0 - y_px) * PX)


def rect(x0, y0, x1, y1):
    """Rectangle en pixels -> (centre_x, centre_y, largeur, hauteur) en mètres."""
    cx, cy = px_to_world((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    return cx, cy, abs(x1 - x0) * PX, abs(y1 - y0) * PX


def p(v):
    """Longueur en pixels de référence -> mètres."""
    return v * PX


# ===========================================================================
# LAYOUT — relevé sur la maquette, en pixels. Seule source de vérité.
# ===========================================================================

LAYOUT = {
    "faceplate": (28, 16, 1644, 920),
    "screw_r": 9,
    "screws": [(68, 46), (1610, 46), (68, 880), (1610, 880)],

    "wordmark": (100, 56, "TUPLE VST", 27),

    "btn_voice_leading": (1188, 54, 1327, 93, "VOICE LEADING", "amber"),
    "btn_preset":        (1347, 54, 1500, 93, "PRESET · 01 INIT", "pale"),
    "midi_led":          (1553, 76, 5),
    "midi_label":        (1536, 56, "MIDI", 11),

    "oled_key":  (78, 104, 380, 158),
    "oled_char": (78, 202, 380, 288),

    "lbl_character": (82, 180, "CHARACTER", 14),
    "lbl_octave":    (82, 389, "OCTAVE", 14),
    "lbl_voicing":   (82, 468, "VOICING", 14),
    "lbl_inversion": (82, 595, "INVERSION", 14),
    "lbl_pads":      (428, 120, "PAD MATRIX  ·  C MAJOR", 15),
    "lbl_prog":      (105, 664, "PROGRESSION", 15),

    # encodeurs : centre + rayon
    "knobs": [(120, 337, 33), (227, 337, 33), (331, 337, 33)],

    # rangées de boutons : (y0, y1, [(x0, x1, libellé, état)])
    "octave": (411, 456, [
        (82, 131, "-2", "pale"), (143, 192, "-1", "pale"), (204, 253, "0", "lit"),
        (265, 314, "+1", "pale"), (326, 375, "+2", "pale"),
    ]),
    "voicing_1": (490, 534, [
        (76, 178, "Close", "pale"), (180, 282, "Open", "pale"), (284, 386, "Drop", "pale"),
    ]),
    "voicing_2": (541, 585, [
        (76, 178, "Rootless", "pale"), (180, 282, "Quartal", "pale"),
        (284, 386, "Two-Hand", "pale"),
    ]),
    # Le brief impose Root / 1st / 2nd / 3rd. La maquette de référence affiche le
    # libellé INVERSION mais masque ses boutons derriere le panneau PROGRESSION ;
    # le brief fait foi, donc cette bande descend de 22 px pour les degager
    # (voir lbl_prog, oled_status, transport, timeline, blocks_y).
    "inversion": (610, 648, [
        (78, 150, "Root", "lit"), (156, 228, "1st", "pale"),
        (234, 306, "2nd", "pale"), (312, 384, "3rd", "pale"),
    ]),

    # matrice de pads
    "pads": {
        "col_centers": [464, 561, 658, 754, 847, 940, 1034, 1126],
        "header_y": 163,
        "row0_top": 181,
        "row_pitch": 55,
        "rows": 8,
        "pad_w": 88,
        "pad_h": 50,
        "degrees": ["I", "II", "III", "IV", "V", "VI", "VII", "Borrowed"],
        # une famille harmonique = une couleur
        "colors": ["cyan", "blue", "green", "yellow", "amber", "coral", "violet", "lavender"],
        # libellés allumés, par colonne : {index_de_rangée: texte}
        "lit": [
            {0: "C", 1: "Cmaj7"},
            {0: "Dm", 1: "Dm7"},
            {0: "Em"},
            {0: "F", 2: "Fmaj7"},
            {0: "G", 3: "G7"},
            {0: "Am", 2: "Am9"},
            {},
            {},
        ],
    },

    "oled_monitor": (1200, 112, 1596, 425),
    "oled_movement": (1200, 440, 1596, 622),
    "piano": (1210, 337, 1560, 418),
    "piano_keys": 24,

    "oled_status": (258, 658, 880, 712),

    "transport": (664, 700, [
        (928, 1058, "PLAY", "pale"), (1068, 1205, "CAPTURE", "pale"),
        (1218, 1358, "CLEAR", "pale"), (1378, 1552, "EXPORT MIDI", "amber"),
    ]),

    "timeline": (150, 722, 1505, 776),
    "timeline_bars": 6,
    "playhead_x": 525,

    # blocs d'accords : (x0, x1, accord, sous-titre, vélocité, teinte, état)
    "blocks_y": (790, 872),
    "blocks": [
        (90, 352, "Cmaj7", "close - root", "v96", "cyan", "pale"),
        (378, 640, "Am9", "close - root", "v83", "coral", "hot"),
        (666, 862, "Dm7", "forced", "v104", "amber", "warm"),
        (888, 1050, "G7", "rootless", "v110", "orange", "pale"),
        (1063, 1288, "Fmaj9", "open - 1st", "v84", "lime", "pale"),
        (1300, 1552, "E♭", "borrowed", "v92", "violet", "pale"),
    ],
}

# familles harmoniques : RGB linéaire approximé depuis la maquette
def srgb(r, g, b):
    """Couleur d'ECRAN (0-255, sRGB) -> couleur LINEAIRE pour Blender.

    Indispensable : les entrees Base Color de Cycles sont lineaires. Injecter
    directement les valeurs sRGB de la spec eclaircit tout d'environ 30 %, ce
    qui est exactement l'ecart mesure entre mon rendu et la maquette
    (p25 a 0.715 contre 0.519, six fois trop de hautes lumieres).
    """
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(r), lin(g), lin(b))


# PALETTE DE LA SPEC — docs/06_visual_spec.md, namespace TupleColours.
# Ne pas retoucher ces valeurs sans mettre la spec a jour d'abord.
SPEC = {
    "chassis":    srgb(232, 228, 220),   # polycarbonate mat ivoire chaud
    "panel":      srgb(220, 216, 207),
    "control":    srgb(207, 202, 193),
    "text":       srgb(42, 40, 37),
    "muted_text": srgb(105, 101, 94),
    "oled":       srgb(4, 9, 12),
}

# Les sept familles harmoniques de la spec. `lavender` n'y figure PAS : la
# maquette montre huit colonnes pour sept couleurs, donc Borrowed recoit un
# violet désaturé, seule valeur de ce fichier absente de la spec.
FAMILY = {
    "cyan":     srgb(71, 213, 232),
    "blue":     srgb(90, 166, 245),
    "green":    srgb(113, 185, 109),
    "yellow":   srgb(227, 196, 85),
    "amber":    srgb(238, 171, 57),
    "coral":    srgb(239, 105, 99),
    "violet":   srgb(181, 116, 211),
    "lavender": srgb(198, 152, 214),     # hors spec, voir note ci-dessus
    "lime":     srgb(150, 200, 90),
    "orange":   srgb(238, 140, 57),
}

OLED_CYAN = (0.10, 0.72, 0.92)

# profondeurs, en px de référence — un seul endroit pour toute la topographie
D = {
    "well": 3.0,        # creux d'un puits
    "oled": 4.0,        # écran en retrait
    "button": 2.6,      # bouton en saillie
    "pad": 3.2,
    "text": 0.6,        # décollement du texte, évite le z-fighting
    "screw": 1.6,
    "block": 3.0,
}


# ===========================================================================
# Matériaux
# ===========================================================================

_MATS = {}


def mat(name, factory):
    """Cache de matériaux : un datablock par nom, réutilisé partout.

    Le cache Python ne suffit PAS en session ouverte. `importlib.reload` le
    remet à zéro à chaque exécution, `factory` rappelle alors
    bpy.data.materials.new(name), et Blender suffixe silencieusement :
    MAT_ink, MAT_ink.001, .002, .003... Mesuré le 2026-07-30 après six cycles
    dans la même session — quatre copies de MAT_ink, quatre de MAT_screen_text.
    Le danger n'est pas la mémoire : c'est qu'un débogage par nom modifie un
    orphelin au lieu du matériau réellement utilisé, ce qui est arrivé.
    On interroge donc bpy.data AVANT de créer.
    """
    m = _MATS.get(name)
    if m is None:
        m = bpy.data.materials.get(name) or factory(name)
        _MATS[name] = m
    return m


def _shell(name):
    """Polycarbonate translucide dépoli, avec volume — le « gameboy transparent ».

    Six mécanismes, un par point de la spécification matière. Voir la note en
    tête de fichier. Rien ici n'est décoratif : retirer le volume rend la
    laitance indépendante de l'épaisseur, retirer le bruit de rugosité rend le
    plastique parfaitement moulé.
    """
    m, nodes, links, bsdf = new_material(name)
    c = SPEC["chassis"]
    set_input(bsdf, "Base Color", (c[0], c[1], c[2], 1.0))
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, "IOR", 1.585)                       # polycarbonate
    set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)

    coord = nodes.new("ShaderNodeTexCoord")

    # -- variations d'épaisseur : basse fréquence, relief très faible --------
    n_thick = nodes.new("ShaderNodeTexNoise")
    n_thick.inputs["Scale"].default_value = 6.0
    n_thick.inputs["Detail"].default_value = 2.0
    bump_thick = nodes.new("ShaderNodeBump")
    # « texture : grain tres leger, jamais decoratif ou bruite » (06_visual_spec)
    bump_thick.inputs["Strength"].default_value = 0.018
    links.new(coord.outputs["Object"], n_thick.inputs["Vector"])
    links.new(n_thick.outputs["Fac"], bump_thick.inputs["Height"])

    # -- micro-rayures : bruit ÉTIRÉ, donc directionnel ---------------------
    map_scr = nodes.new("ShaderNodeMapping")
    map_scr.inputs["Scale"].default_value = (260.0, 4.0, 1.0)
    n_scr = nodes.new("ShaderNodeTexNoise")
    n_scr.inputs["Scale"].default_value = 220.0
    n_scr.inputs["Detail"].default_value = 6.0
    n_scr.inputs["Roughness"].default_value = 0.75
    bump_scr = nodes.new("ShaderNodeBump")
    bump_scr.inputs["Strength"].default_value = 0.008
    links.new(coord.outputs["Object"], map_scr.inputs["Vector"])
    links.new(map_scr.outputs["Vector"], n_scr.inputs["Vector"])
    links.new(n_scr.outputs["Fac"], bump_scr.inputs["Height"])
    links.new(bump_thick.outputs["Normal"], bump_scr.inputs["Normal"])
    links.new(bump_scr.outputs["Normal"], bsdf.inputs["Normal"])

    # -- rugosité IRRÉGULIÈRE, remappée entre deux bornes -------------------
    # MapRange expose des noms d'entrée dupliqués selon son type de données :
    # on indexe par position, seul accès non ambigu.
    n_rough = nodes.new("ShaderNodeTexNoise")
    n_rough.inputs["Scale"].default_value = 18.0
    n_rough.inputs["Detail"].default_value = 3.0
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs[1].default_value = 0.30      # From Min
    mr.inputs[2].default_value = 0.70      # From Max
    # VALEUR MESUREE (balayage 0.04 / 0.14 / 0.26 / 0.40, lampe haute fixee a
    # 3 W et volume neutralisé). C'est la rugosite qui produit la laitance du
    # polycarbonate, et elle la produit UNIFORMEMENT — a la difference d'un
    # reflet de lampe, qui forme un halo. A 0.04 le plastique devient du verre
    # optique et laisse voir la PCB comme sous une vitre ; a 0.40 les composants
    # internes s'effacent. 0.26 donne le boitier translucide attendu.
    mr.inputs[3].default_value = 0.20      # To Min
    mr.inputs[4].default_value = 0.32      # To Max
    links.new(n_rough.outputs["Fac"], mr.inputs[0])
    links.new(coord.outputs["Object"], n_rough.inputs["Vector"])

    # -- tranche plus brillante : rugosité abaissée aux angles rasants ------
    lw = nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    m_scale = nodes.new("ShaderNodeMath")
    m_scale.operation = "MULTIPLY"
    m_scale.inputs[1].default_value = 0.15
    m_sub = nodes.new("ShaderNodeMath")
    m_sub.operation = "SUBTRACT"
    m_sub.use_clamp = True
    links.new(lw.outputs["Facing"], m_scale.inputs[0])
    links.new(mr.outputs[0], m_sub.inputs[0])
    links.new(m_scale.outputs[0], m_sub.inputs[1])
    links.new(m_sub.outputs[0], bsdf.inputs["Roughness"])

    # -- laiteux : VRAI volume, la diffusion dépend de l'épaisseur ----------
    # Densités élevées assumées : la paroi ne fait que 1,2 mm, une densité
    # faible n'y produirait aucune profondeur optique mesurable.
    absorb = nodes.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (0.86, 0.91, 0.88, 1.0)
    absorb.inputs["Density"].default_value = 25.0
    scatter = nodes.new("ShaderNodeVolumeScatter")
    scatter.inputs["Color"].default_value = (0.93, 0.96, 0.94, 1.0)
    # A RETENIR : sur une paroi de 1,2 mm, ce volume est MARGINAL. Profondeur
    # optique = densité x épaisseur = 40 x 0.0012 = 0.048, soit environ 5 % de
    # diffusion. Le balayage 0/40/120/340 l'a montre : la laitance existait
    # déjà a densité 0, et 340 ne faisait que noyer les composants internes.
    # On garde le volume parce qu'il est physiquement juste et qu'il comptera
    # si la paroi s'epaissit ou sur la tranche, ou le trajet est plus long —
    # mais il ne faut PAS compter sur lui pour la laitance de la face.
    scatter.inputs["Density"].default_value = 40.0
    scatter.inputs["Anisotropy"].default_value = 0.25
    add = nodes.new("ShaderNodeAddShader")
    links.new(absorb.outputs["Volume"], add.inputs[0])
    links.new(scatter.outputs["Volume"], add.inputs[1])
    output = nodes.get("Material Output")
    if output is None:
        raise RuntimeError("pas de Material Output dans %r" % name)
    links.new(add.outputs[0], output.inputs["Volume"])

    m.use_backface_culling = False
    return m


def m_backing():
    """Diffuseur interne opaque, gris clair neutre.

    Sur la maquette de référence, la PCB verte n'apparait PAS derriere toute la
    façade : elle se voit dans une bande haute et le long des bords, tandis que
    le fond des zones de commande est neutre et clair. C'est aussi ainsi que
    sont faits les vrais boitiers translucides — une plaque de fond opaque
    imprimee, avec des fenetres la ou l'on veut voir l'interieur.

    Sans cette plaque, la PCB baigne toute la surface de vert et les panneaux
    d'interface reposent sur du circuit imprime, ce que la maquette ne montre
    nulle part.
    """
    def build(name):
        m, _n, _l, bsdf = new_material(name)
        set_input(bsdf, "Base Color", (0.74, 0.745, 0.72, 1.0))
        set_input(bsdf, "Roughness", 0.62)
        # Translucide et non opaque : un diffuseur reel laisse passer un peu de
        # lumiere, on devine donc la PCB derriere au lieu d'avoir un carton
        # colle. Son bord se fond au lieu de trancher.
        set_input(bsdf, ["Transmission Weight", "Transmission"], 0.42)
        set_input(bsdf, "IOR", 1.5)
        return m
    return mat("MAT_backing", build)


def m_trim():
    """Jonc de finition inférieur, en PLASTIQUE.

    Décision du 2026-07-30 : le boîtier reste intégralement plastique pour
    l'instant. Le « thin metallic lower edge » du brief reste atteignable, la
    géométrie est identique — seul ce matériau change.
    """
    return mat("MAT_trim", lambda n: _plastic(n, (0.19, 0.20, 0.20), 0.14))


def _oled(name):
    """Écran OLED éteint : noir profond, très peu réfléchissant."""
    m, _n, _l, bsdf = new_material(name)
    o = SPEC["oled"]
    set_input(bsdf, "Base Color", (o[0], o[1], o[2], 1.0))
    set_input(bsdf, "Roughness", 0.30)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.34)
    return m


def _emit(name, color, strength):
    m, _n, _l, bsdf = new_material(name)
    set_input(bsdf, "Base Color", (0.01, 0.01, 0.01, 1.0))
    set_input(bsdf, "Roughness", 0.4)
    set_input(bsdf, ["Emission Color", "Emission"], (color[0], color[1], color[2], 1.0))
    set_input(bsdf, "Emission Strength", strength)
    return m


def _plastic(name, color, roughness=0.42, metallic=0.0):
    m, _n, _l, bsdf = new_material(name)
    set_input(bsdf, "Base Color", (color[0], color[1], color[2], 1.0))
    set_input(bsdf, "Metallic", metallic)
    set_input(bsdf, "Roughness", roughness)
    return m


def _silicone(name, color, glow=0.0):
    """Silicone translucide laiteux des pads. `glow` allume par l'intérieur."""
    m, _n, _l, bsdf = new_material(name)
    set_input(bsdf, "Base Color", (color[0], color[1], color[2], 1.0))
    set_input(bsdf, "Roughness", 0.48)
    # 0.32 de subsurface délavait les teintes jusqu'au blanc sous cet éclairage
    set_input(bsdf, ["Subsurface Weight", "Subsurface"], 0.16)
    set_input(bsdf, "Subsurface Scale", 0.004)
    if glow > 0.0:
        set_input(bsdf, ["Emission Color", "Emission"], (color[0], color[1], color[2], 1.0))
        set_input(bsdf, "Emission Strength", glow)
    return m


def m_shell():      return mat("MAT_shell", _shell)
def m_oled():       return mat("MAT_oled", _oled)
def m_metal():      return mat("MAT_metal", lambda n: _plastic(n, (0.62, 0.65, 0.63), 0.24, 1.0))
def m_pcb():        return mat("MAT_pcb", lambda n: _plastic(n, (0.05, 0.20, 0.10), 0.40))
def m_chip():       return mat("MAT_chip", lambda n: _plastic(n, (0.02, 0.02, 0.02), 0.44))
def m_copper():     return mat("MAT_copper", lambda n: _plastic(n, (0.72, 0.42, 0.16), 0.30, 0.9))
def m_solder():     return mat("MAT_solder", lambda n: _plastic(n, (0.68, 0.70, 0.72), 0.24, 0.8))
def m_knob():       return mat("MAT_knob", lambda n: _plastic(n, (0.015, 0.017, 0.016), 0.34))
def m_knob_line():  return mat("MAT_knob_line", lambda n: _plastic(n, (0.86, 0.88, 0.86), 0.22, 0.7))
def m_well():
    # Un puits est une CAVITE : niveau -2 dans la spec de profondeur, donc plus
    # sombre que le contrôle qu'il accueille, sinon le relief ne se lit pas.
    ctrl = SPEC["control"]
    return mat("MAT_well", lambda n: _plastic(n, tuple(c * 0.62 for c in ctrl), 0.56))
def m_btn_pale():   return mat("MAT_btn_pale", lambda n: _plastic(n, SPEC["control"], 0.40))
def m_btn_lit():    return mat("MAT_btn_lit", lambda n: _plastic(n, SPEC["panel"], 0.28))
def m_btn_amber():  return mat("MAT_btn_amber", lambda n: _emit(n, FAMILY["amber"], 2.6))
def m_key_white():  return mat("MAT_key_white", lambda n: _plastic(n, (0.68, 0.69, 0.67), 0.32))
def m_key_black():  return mat("MAT_key_black", lambda n: _plastic(n, (0.03, 0.033, 0.031), 0.30))
def m_key_lit():    return mat("MAT_key_lit", lambda n: _emit(n, (0.20, 0.50, 0.88), 3.0))
def m_ink():        return mat("MAT_ink", lambda n: _plastic(n, SPEC["text"], 0.44))
def m_ink_light():  return mat("MAT_ink_light", lambda n: _plastic(n, (0.97, 0.96, 0.93), 0.36))
def m_screen_text():return mat("MAT_screen_text", lambda n: _emit(n, OLED_CYAN, 5.0))


def m_pad_body(name, lit):
    """Corps du pad : silicone translucide PALE (brief), à peine teinté.

    C'est le filet qui porte la famille, pas le corps — voir m_pad_rim. Un pad
    allumé reçoit l'émission ICI, dans le volume translucide : c'est ce qui
    produit le « glow from within » plutôt qu'une simple teinte de surface.
    """
    key = "MAT_pad_%s_%s" % (name, "lit" if lit else "off")
    color = FAMILY[name]
    if lit:
        # 4.5 ressortait a 1.7 effectif après -1.4 EV : teinte, pas rayonnant.
        # Calibre CONTRE l'exposition, pas dans l'absolu.
        # « éléments actifs : lumiere interne plutot qu'un halo externe massif »
        # (06_visual_spec). 16 produisait un halo qui debordait sur les voisins.
        soft = tuple(0.42 + c * 0.46 for c in color)
        return mat(key, lambda n: _silicone(n, soft, glow=4.0))
    # Base = SPEC["control"], teintee par la famille. Les pads doivent lire
    # GRIS MOYEN comme sur la maquette, pas blanc : ils occupaient le haut de la
    # gamme et ecrasaient le premier quartile.
    ctrl = SPEC["control"]
    # Coefficient descendu de 0.88 a 0.66 : dans la maquette un QUART de
    # l'image est sous 0.52, ce qui n'est possible que si les pads lisent
    # franchement gris. A 0.88 ils restaient dans le haut de la gamme.
    pale = tuple(ctrl[i] * (0.66 + 0.30 * color[i]) for i in range(3))
    return mat(key, lambda n: _silicone(n, pale, glow=0.0))


def m_pad_rim(name, lit):
    """Filet périphérique : la couleur de famille, à pleine saturation.

    Un filet fin saturé se distingue là où un aplat clair se confond. C'est ce
    qui rend les huit colonnes lisibles d'un coup d'œil.
    """
    key = "MAT_rim_%s_%s" % (name, "lit" if lit else "off")
    color = FAMILY[name]
    if lit:
        return mat(key, lambda n: _emit(n, color, 3.0))
    return mat(key, lambda n: _plastic(n, color, 0.34))


def m_block(tint, state):
    key = "MAT_block_%s_%s" % (tint, state)
    color = FAMILY[tint]
    if state == "hot":
        return mat(key, lambda n: _emit(n, color, 2.2))
    if state == "warm":
        return mat(key, lambda n: _emit(n, color, 1.7))
    return mat(key, lambda n: _plastic(n, SPEC["control"], 0.42))


BTN_MAT = {"pale": m_btn_pale, "lit": m_btn_lit, "amber": m_btn_amber}


# ===========================================================================
# Texte
# ===========================================================================

def text(body, x_px, y_px, size_px, material, coll, align="LEFT",
         z=None, extrude=None, name=None, stroke=0.0):
    """Objet texte posé sur la façade, coordonnées en pixels de la maquette.

    `y_px` est la ligne de base. L'alignement horizontal est délégué à Blender
    (align_x) : recentrer à la main obligerait à mesurer chaque chaîne.
    """
    curve = bpy.data.curves.new(name or ("TXT_" + body[:18]), type="FONT")
    curve.body = body
    curve.size = p(size_px)
    curve.align_x = align
    curve.align_y = "CENTER"
    # Une courbe d'épaisseur nulle est éclairée des DEUX faces par Cycles : les
    # libellés sortaient gris au lieu de noirs. On les rend solides par défaut.
    curve.extrude = p(1.1) if extrude is None else extrude
    # `offset` gonfle le contour du glyphe, donc épaissit le trait sans toucher
    # a la taille de la fonte ni a la mise en page. Seul levier disponible :
    # TextCurve n'a pas de propriete `bold`, et aucune fonte bold n'est chargee.
    if stroke:
        curve.offset = stroke
    ob = bpy.data.objects.new(name or ("TXT_" + body[:18]), curve)
    wx, wy = px_to_world(x_px, y_px)
    ob.location = (wx, wy, FACE_Z + (p(D["text"]) if z is None else z))
    link(ob, coll)
    assign(ob, material)
    return ob


_PENDING_PLAQUE = []

PLAQUE_PAD = 1.5        # marge de la plaque autour du texte, en px
PLAQUE_SINK = 0.6       # enfoncement de la plaque sous la surface, en px
INK_RELIEF = 1.8        # relief de l'encre au-dessus de la façade, en px


def m_plaque():
    """Champ sérigraphié : opaque, SANS transmission.

    C'est là tout l'intérêt — cette plaque arrête le rétroéclairage sous le
    libellé, exactement comme une encre de sérigraphie opaque sur du plastique
    translucide. Sans elle, la coque brille derrière le texte et le lave.
    """
    # 0.745 la rendait invisible mais annulait son benefice : elle remplacait
    # le retroeclairage par une surface aussi claire. Valeur intermediaire.
    return mat("MAT_plaque", lambda n: _plastic(n, SPEC["panel"], 0.34))


def printed_text(body, x_px, y_px, size_px, coll, align="LEFT", name=None):
    """Libellé sérigraphié en relief sur une plaque opaque.

    À réserver aux libellés posés sur le polycarbonate rétroéclairé. Sur une
    surface déjà opaque (bouton, bloc d'accord, écran) une encre à plat suffit.

    La plaque n'est pas créée ici : son encombrement dépend du texte rendu, qui
    n'est connu qu'après mise à jour du depsgraph. Voir finalize_plaques().
    """
    nm = name or ("PRT_" + body[:16])
    # Trait proportionnel a la taille : ~2,2 % du corps. Un offset absolu
    # deformerait les petits libellés et laisserait les gros trop fins.
    ob = text(body, x_px, y_px, size_px, m_ink(), coll, align=align,
              z=p(INK_RELIEF), extrude=p(INK_RELIEF * 0.55), name=nm,
              stroke=p(size_px) * 0.024)
    _PENDING_PLAQUE.append((ob, coll))
    return ob


def finalize_plaques():
    """Pose une plaque opaque sous chaque libellé sérigraphié, en UNE passe.

    L'encombrement réel du texte se lit dans `dimensions`, qui n'a de valeur
    qu'après réévaluation du depsgraph — d'où la passe unique.
    """
    if not _PENDING_PLAQUE:
        raise RuntimeError("aucun libellé sérigraphié : printed_text n'a jamais "
                           "été appelé, les libellés se laveraient sur la coque "
                           "rétroéclairée")
    bpy.context.view_layer.update()
    made = 0
    plaque_mat = m_plaque()
    for ob, coll in list(_PENDING_PLAQUE):
        dim = ob.dimensions
        if dim.x <= 0.0 or dim.y <= 0.0:
            raise RuntimeError(
                "le libellé %r n'a pas d'encombrement (%.4f x %.4f) : sa plaque "
                "serait vide et il se laverait" % (ob.name, dim.x, dim.y))
        pad = p(PLAQUE_PAD)
        w, h = dim.x + pad * 2.0, dim.y + pad * 2.0
        loc = ob.matrix_world.translation
        # centrée sur le texte : align_x peut être LEFT, CENTER ou RIGHT, donc
        # on part de l'encombrement rendu et non du point d'ancrage.
        cx = loc.x + (dim.x / 2.0 if ob.data.align_x == "LEFT"
                      else -dim.x / 2.0 if ob.data.align_x == "RIGHT" else 0.0)
        # DEVANT la paroi, pas dedans. Noyée sous la surface, sa valeur sombre
        # était diffusée par les 0,2 mm de polycarbonate laiteux à diffusion
        # volumique qui la couvraient : elle perdait son effet en même temps que
        # son liseré. Établi par témoin le 2026-07-30 — l'encre passée en rouge
        # émissif ressortait en taches diffuses, pas en texte net, alors que le
        # texte des écrans OLED restait parfaitement défini.
        # Très fine et serrée pour limiter le liseré, qui reste le prix à payer.
        plate_ob = create_box("PLAQUE_" + ob.name, (w, h, p(0.35)),
                              location=(cx, loc.y, FACE_Z + p(0.30)),
                              collection=coll)
        assign(plate_ob, plaque_mat)
        made += 1
    _PENDING_PLAQUE.clear()
    log("sérigraphie : %d libellés en relief sur plaque opaque" % made)
    return made


def centered_text(body, x0, y0, x1, y1, size_px, material, coll, z=None):
    return text(body, (x0 + x1) / 2.0, (y0 + y1) / 2.0, size_px, material, coll,
                align="CENTER", z=z)


# ===========================================================================
# Éléments composés
# ===========================================================================

def create_rounded_box(name, size, radius_px, corner_segments=12,
                       location=(0.0, 0.0, 0.0), collection="MISC"):
    """Prisme a section rectangulaire aux coins arrondis.

    Le rayon vit dans la GEOMETRIE, pas dans un modificateur Bevel : le bevel du
    boitier doit rester petit pour ne pas arrondir les arêtes des puits, alors
    que la silhouette demande un rayon franc. Les deux besoins sont
    incompatibles dans un seul modificateur.
    """
    sx, sy, sz = size
    r = min(p(radius_px), sx * 0.49, sy * 0.49)
    hx, hy = sx / 2.0 - r, sy / 2.0 - r

    profile = []
    for ccx, ccy, a0 in ((hx, hy, 0.0), (-hx, hy, 90.0),
                         (-hx, -hy, 180.0), (hx, -hy, 270.0)):
        for i in range(corner_segments + 1):
            a = math.radians(a0 + 90.0 * i / corner_segments)
            profile.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))

    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    top = [bm.verts.new((x, y, sz / 2.0)) for x, y in profile]
    face = bm.faces.new(top)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, -sz), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

    ob = bpy.data.objects.new(name, me)
    ob.location = location
    return link(ob, collection)


def plate(name, x0, y0, x1, y1, depth_px, material, coll, z_top=None, bevel=None):
    """Dalle rectangulaire alignée sur la façade.

    `z_top` est la cote de sa face SUPÉRIEURE. Négatif = en retrait (puits,
    écran) ; positif = en saillie (bouton, pad).
    """
    cx, cy, w, h = rect(x0, y0, x1, y1)
    d = p(depth_px)
    top = FACE_Z if z_top is None else z_top
    ob = create_box(name, (w, h, d), location=(cx, cy, top - d / 2.0),
                    collection=coll)
    if bevel:
        add_bevel(ob, p(bevel), segments=3)
    assign(ob, material)
    return ob


def cutter(name, x0, y0, x1, y1, depth_px):
    """Volume soustrait au boîtier pour ouvrir un puits.

    Il DÉBORDE devant la façade (CUT_MARGIN) : un cutter affleurant produirait
    des faces coplanaires, que le solveur booléen rend en artefacts.
    Ces objets ne sont jamais rendus, seulement consommés par le modificateur.
    """
    cx, cy, w, h = rect(x0, y0, x1, y1)
    total = p(depth_px) + p(CUT_MARGIN)
    ob = create_box("CUT_" + name, (w, h, total),
                    location=(cx, cy, FACE_Z + p(CUT_MARGIN) - total / 2.0),
                    collection="CUTTERS")
    ob.hide_render = True
    ob.display_type = "WIRE"
    return ob


def well(name, x0, y0, x1, y1, coll):
    """Puits creusé : le boîtier est réellement percé, puis le fond est posé."""
    cutter(name, x0, y0, x1, y1, D["well"])
    return plate(name, x0, y0, x1, y1, 1.6, m_well(), coll,
                 z_top=-p(D["well"]), bevel=0.8)


def oled(name, x0, y0, x1, y1, coll):
    cutter(name, x0, y0, x1, y1, D["oled"])
    return plate(name, x0, y0, x1, y1, 1.6, m_oled(), coll,
                 z_top=-p(D["oled"]), bevel=0.5)


def button(name, x0, y0, x1, y1, label, state, coll, label_size=11):
    ob = plate(name, x0, y0, x1, y1, D["button"], BTN_MAT[state](), coll,
               z_top=p(D["button"]), bevel=1.0)
    if label:
        # De l'encre sombre sur une surface émissive ambre est illisible :
        # ces boutons-là prennent une encre claire.
        ink = m_ink_light() if state == "amber" else m_ink()
        centered_text(label, x0, y0, x1, y1, label_size, ink, coll,
                      z=p(D["button"] + D["text"]))
    return ob


# ===========================================================================
# Construction, section par section
# ===========================================================================

def build_body():
    """Boîtier translucide + PCB interne + vis."""
    x0, y0, x1, y1 = LAYOUT["faceplate"]
    cx, cy, w, h = rect(x0, y0, x1, y1)
    depth = p(BODY_D)

    body = create_rounded_box("BODY_shell", (w, h, depth), CORNER_R,
                              location=(cx, cy, FACE_Z - depth / 2.0),
                              collection="BODY")
    smooth_by_angle(body, 24.0)
    assign(body, m_shell())

    # Pile de modificateurs, dans cet ordre exactement :
    #   BOOLEAN d'abord (creuse les puits), BEVEL ensuite (adoucit les arêtes
    #   NOUVELLEMENT créées par la découpe, d'où « shallow carved wells »),
    #   WEIGHTED NORMAL en dernier pour tenir l'ombrage sur les angles.
    # Inverser boolean et bevel laisse les puits à angle vif.
    cutters = proto.get_collection("CUTTERS")
    cutters.hide_render = True
    boolean = body.modifiers.new("wells", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.operand_type = "COLLECTION"
    boolean.collection = cutters
    boolean.solver = "EXACT"

    # SOLIDIFY sur un volume fermé le rend CREUX : il ajoute une surface
    # intérieure décalée vers l'intérieur (offset -1), donc les cotes
    # extérieures ne bougent pas. Placé APRÈS le booléen, il donne aussi des
    # parois minces aux puits qu'on vient de creuser.
    sol = body.modifiers.new("hollow", "SOLIDIFY")
    sol.thickness = p(WALL)
    sol.offset = -1.0
    sol.use_even_offset = True
    sol.use_rim = True

    # Pas de booléen de gravure ici : voir la note en tête de fichier. Les
    # libellés sont sérigraphiés en relief sur une plaque opaque.
    add_bevel(body, p(1.6), segments=2, angle_deg=40.0, name="edges")
    wn = body.modifiers.new("weighted_normals", "WEIGHTED_NORMAL")
    wn.keep_sharp = True

    # PCB visible au travers, dans le tiers bas du volume
    pcb = create_box("BODY_pcb", (w * 0.965, h * 0.955, p(1.6)),
                     location=(cx, cy, FACE_Z - depth * 0.68), collection="BODY")
    assign(pcb, m_pcb())

    # Pistes de cuivre : le brief demande « copper, solder mask and distinct
    # components », pas un rectangle vert uni.
    rng = random.Random(11)
    copper = m_copper()
    traces = 0
    pcb_z = FACE_Z - depth * 0.68
    for i in range(34):
        horizontal = rng.random() < 0.55
        length = rng.uniform(60, 320) * PX
        tx = rng.uniform(x0 + 70, x1 - 70)
        ty = rng.uniform(y0 + 50, y1 - 50)
        wx, wy = px_to_world(tx, ty)
        size = ((length, p(1.6), p(0.25)) if horizontal
                else (p(1.6), length, p(0.25)))
        tr = create_box("PCB_trace_%02d" % i, size,
                        location=(wx, wy, pcb_z + p(0.9)), collection="BODY")
        assign(tr, copper)
        traces += 1

    solder = m_solder()
    for i in range(60):
        px_ = rng.uniform(x0 + 60, x1 - 60)
        py_ = rng.uniform(y0 + 40, y1 - 40)
        wx, wy = px_to_world(px_, py_)
        pad_ = create_cylinder("PCB_solder_%02d" % i, p(2.2), p(0.6), segments=12,
                               location=(wx, wy, pcb_z + p(1.1)), collection="BODY")
        assign(pad_, solder)

    chip_mat = m_chip()
    chips = 0
    for i in range(46):
        cw = rng.uniform(14, 62) * PX
        cd = rng.uniform(10, 30) * PX
        ch = rng.uniform(2.5, 5.0) * PX
        px_ = rng.uniform(x0 + 60, x1 - 60)
        # Deux tiers des puces dans la bande haute : c'est la seule zone ou le
        # diffuseur ne les masque pas, donc la seule ou elles servent a quelque
        # chose. Les repartir uniformement en cache les deux tiers.
        if i % 3 != 0:
            py_ = rng.uniform(y0 + 34, y0 + 112)
        else:
            py_ = rng.uniform(y0 + 40, y1 - 40)
        wx, wy = px_to_world(px_, py_)
        chip = create_box("BODY_chip_%02d" % i, (cw, cd, ch),
                          location=(wx, wy, pcb_z + p(0.8) + ch / 2.0),
                          collection="BODY")
        chip.rotation_euler.z = rng.choice((0.0, math.pi / 2.0))
        assign(chip, chip_mat)
        chips += 1

    # liseré métallique inférieur
    # Liseré métallique : sur la face AVANT le long du bord bas, pas sous la
    # coque. Placé dessous il était rigoureusement invisible en élévation
    # frontale à 6 degrés de plongée, alors que le brief le demande visible.
    strip_y0, strip_y1 = y1 - 13.0, y1 - 5.0
    ecx, ecy, ew, eh = rect(x0 + CORNER_R, strip_y0, x1 - CORNER_R, strip_y1)
    edge = create_box("BODY_metal_edge", (ew, eh, p(2.2)),
                      location=(ecx, ecy, FACE_Z + p(0.6)), collection="BODY")
    add_bevel(edge, p(0.7), segments=3)
    assign(edge, m_trim())

    # Diffuseur interne : laisse la PCB visible en bande haute et en bordure,
    # opaque partout ailleurs. Les marges sont en px de la maquette, comme tout
    # le reste du layout.
    bx0, by0, bx1, by1 = x0 + 28, y0 + 118, x1 - 28, y1 - 28
    bcx, bcy, bw, bh = rect(bx0, by0, bx1, by1)
    backing = create_box("BODY_backing", (bw, bh, p(1.2)),
                         location=(bcx, bcy, FACE_Z - p(WALL) - p(2.4)),
                         collection="BODY")
    add_bevel(backing, p(2.0), segments=3)
    assign(backing, m_backing())
    log("diffuseur interne : %.0f x %.0f mm, PCB visible en bande haute de "
        "%d px et en bordure de %d px" % (bw * 1000, bh * 1000, 118, 28))

    r = p(LAYOUT["screw_r"])
    metal = m_metal()
    for i, (sx, sy) in enumerate(LAYOUT["screws"]):
        wx, wy = px_to_world(sx, sy)
        s = create_cylinder("BODY_screw_%d" % i, r, p(D["screw"]), segments=32,
                            location=(wx, wy, FACE_Z - p(D["screw"]) / 2.0),
                            collection="BODY")
        smooth_by_angle(s, 30.0)
        assign(s, metal)

    log("boîtier : %.1f x %.1f x %.1f mm, paroi %.1f mm"
        % (w * 1000, h * 1000, depth * 1000, p(WALL) * 1000))
    log("interne : %d puces, %d pistes de cuivre, 60 pastilles, liseré métallique"
        % (chips, traces))
    return body


def build_header():
    x, y, body, size = LAYOUT["wordmark"]
    printed_text(body, x, y + size * 0.5, size, "HEADER", align="LEFT",
                  name="TXT_wordmark")

    for key in ("btn_voice_leading", "btn_preset"):
        x0, y0, x1, y1, label, state = LAYOUT[key]
        button("BTN_" + key, x0, y0, x1, y1, label, state, "HEADER", label_size=12)

    lx, ly, lbody, lsize = LAYOUT["midi_label"]
    printed_text(lbody, lx, ly + lsize * 0.5, lsize, "HEADER", name="TXT_midi")
    mx, my, mr = LAYOUT["midi_led"]
    wx, wy = px_to_world(mx, my)
    led = create_cylinder("LED_midi", p(mr), p(2.0), segments=24,
                          location=(wx, wy, FACE_Z + p(1.0)), collection="HEADER")
    smooth_by_angle(led, 30.0)
    assign(led, mat("MAT_led_midi", lambda n: _emit(n, FAMILY["yellow"], 16.0)))
    log("bandeau : wordmark, 2 boutons, LED MIDI")


def build_left_panel():
    for key in ("lbl_character", "lbl_octave", "lbl_voicing", "lbl_inversion"):
        x, y, body, size = LAYOUT[key]
        printed_text(body, x, y + size * 0.5, size, "LEFT", name="TXT_" + key)

    oled("OLED_key", *LAYOUT["oled_key"], coll="LEFT")
    kx0, ky0, kx1, ky1 = LAYOUT["oled_key"]
    text("KEY  C   —   SCALE  MAJOR", kx0 + 18, (ky0 + ky1) / 2.0, 17,
         m_screen_text(), "LEFT", z=-p(D["oled"] - D["text"]), name="TXT_key_scale")

    oled("OLED_character", *LAYOUT["oled_char"], coll="LEFT")
    cx0, cy0, cx1, cy1 = LAYOUT["oled_char"]
    for i, (name_, value) in enumerate((("DENSITY", "58%"), ("TENSION", "32%"),
                                        ("MOVEMENT", "61%"))):
        row_y = cy0 + 20 + i * 23
        text(name_, cx0 + 18, row_y, 13, m_screen_text(), "LEFT",
             z=-p(D["oled"] - D["text"]), name="TXT_char_%s" % name_)
        text(value, cx0 + 130, row_y, 13, m_screen_text(), "LEFT",
             z=-p(D["oled"] - D["text"]), name="TXT_charval_%s" % name_)

    # encodeurs : corps noir mat + trait indicateur métallique
    body_mat, line_mat = m_knob(), m_knob_line()
    for i, (kx, ky, kr) in enumerate(LAYOUT["knobs"]):
        wx, wy = px_to_world(kx, ky)
        h = p(20.0)
        knob = create_cylinder("KNOB_%d" % i, p(kr), h, segments=72,
                               location=(wx, wy, FACE_Z + h / 2.0), collection="LEFT")
        smooth_by_angle(knob, 30.0)
        add_bevel(knob, p(2.2), segments=4)
        assign(knob, body_mat)
        line = create_box("KNOB_%d_line" % i, (p(2.6), p(kr * 0.74), p(1.2)),
                          location=(wx, wy + p(kr * 0.30), FACE_Z + h + p(0.4)),
                          collection="LEFT")
        assign(line, line_mat)

    rows = ("octave", "voicing_1", "voicing_2", "inversion")
    count = 0
    for key in rows:
        y0, y1, items = LAYOUT[key]
        for x0, x1, label, state in items:
            button("BTN_%s_%s" % (key, label), x0, y0, x1, y1, label, state, "LEFT")
            count += 1
    log("panneau gauche : 2 écrans, 3 encodeurs, %d boutons (%s)"
        % (count, ", ".join(rows)))


def build_pad_matrix():
    cfg = LAYOUT["pads"]
    x, y, body, size = LAYOUT["lbl_pads"]
    printed_text(body, x, y + size * 0.5, size, "PADS", name="TXT_pad_matrix")

    pw, ph = cfg["pad_w"], cfg["pad_h"]
    # puits d'accueil de la matrice entière
    left = cfg["col_centers"][0] - pw / 2.0 - 12
    right = cfg["col_centers"][-1] + pw / 2.0 + 12
    top = cfg["row0_top"] - 10
    bottom = cfg["row0_top"] + cfg["rows"] * cfg["row_pitch"] + 4
    well("WELL_pads", left, top, right, bottom, "PADS")

    ink = m_ink()
    total = lit_total = 0
    for c, cx in enumerate(cfg["col_centers"]):
        family = cfg["colors"][c]
        printed_text(cfg["degrees"][c], cx, cfg["header_y"], 14, "PADS",
                      align="CENTER", name="TXT_deg_%d" % c)

        for r in range(cfg["rows"]):
            y0 = cfg["row0_top"] + r * cfg["row_pitch"]
            label = cfg["lit"][c].get(r)
            is_lit = label is not None
            # Filet : dalle légèrement plus large, dont seule la bordure
            # dépasse sous le corps du pad — c'est ce qui lit comme un contour.
            plate("RIM_%d_%d" % (c, r), cx - pw / 2.0 - RIM, y0 - RIM,
                  cx + pw / 2.0 + RIM, y0 + ph + RIM, D["pad"],
                  m_pad_rim(family, is_lit), "PADS",
                  z_top=p(D["pad"] - 0.55), bevel=1.0)
            pad = plate("PAD_%d_%d" % (c, r), cx - pw / 2.0, y0,
                        cx + pw / 2.0, y0 + ph, D["pad"] + 0.55,
                        m_pad_body(family, is_lit), "PADS",
                        z_top=p(D["pad"]), bevel=2.0)
            total += 1
            if is_lit:
                centered_text(label, cx - pw / 2.0, y0, cx + pw / 2.0, y0 + ph,
                              15, ink, "PADS", z=p(D["pad"] + D["text"]))
                lit_total += 1
    rims = len([o for o in bpy.data.objects if o.name.startswith("RIM_")])
    if rims != total:
        raise RuntimeError(
            "%d filets pour %d pads : chaque pad doit porter le contour de sa "
            "famille" % (rims, total))
    log("matrice : %d colonnes x %d rangées = %d pads (+%d filets de famille), "
        "%d allumés" % (len(cfg["col_centers"]), cfg["rows"], total, rims, lit_total))


def build_right_panel():
    oled("OLED_monitor", *LAYOUT["oled_monitor"], coll="RIGHT")
    x0, y0, x1, y1 = LAYOUT["oled_monitor"]
    zt = -p(D["oled"] - D["text"])
    scr = m_screen_text()

    # Le brief demande l'accord, sa FONCTION, les notes et le voicing.
    # "v1.9" figurait sur la maquette mais pas dans le brief : retire.
    text("Am9", x0 + 40, y0 + 60, 52, scr, "RIGHT", z=zt, name="TXT_chord_big")
    text("VI  -  SUBMEDIANT", x1 - 40, y0 + 52, 16, scr, "RIGHT", align="RIGHT",
         z=zt, name="TXT_function")
    text("NOTES", x0 + 40, y0 + 114, 17, scr, "RIGHT", z=zt, name="TXT_notes_lbl")
    text("VOICING", x0 + 40, y0 + 156, 17, scr, "RIGHT", z=zt, name="TXT_voicing_lbl")
    for i, n in enumerate(("A", "C", "E", "G", "B")):
        text(n, x0 + 172 + i * 36, y0 + 114, 17, scr, "RIGHT", align="CENTER",
             z=zt, name="TXT_note_%d" % i)
        text(n, x0 + 172 + i * 36, y0 + 156, 17, scr, "RIGHT", align="CENTER",
             z=zt, name="TXT_vnote_%d" % i)
    for i, d in enumerate(("9", "13", "5", "b7", "3")):
        text(d, x0 + 172 + i * 36, y0 + 180, 15, scr, "RIGHT", align="CENTER",
             z=zt, name="TXT_deg2_%d" % i)

    build_piano()

    oled("OLED_movement", *LAYOUT["oled_movement"], coll="RIGHT")
    mx0, my0, mx1, my1 = LAYOUT["oled_movement"]
    text("VOICE MOVEMENT", mx0 + 36, my0 + 28, 19, scr, "RIGHT", z=zt,
         name="TXT_movement")
    cols = (("FROM", 36), ("TO", 166), ("INT", 268), ("DIR", 336))
    for label, dx in cols:
        text(label, mx0 + dx, my0 + 58, 14, scr, "RIGHT", z=zt,
             name="TXT_mv_h_%s" % label)
    # Am9 (A C E G B) vers Dm7 (D F A C) : conduite de voix reelle, pas des
    # intervalles pris au hasard.
    rows = (("A3", "A3", "0"), ("C4", "C4", "0"), ("E4", "F4", "+1"),
            ("G4", "A4", "+2"), ("B4", "C5", "+1"))
    for i, (src, dst, itv) in enumerate(rows):
        ry = my0 + 88 + i * 27
        for value, dx in ((src, 36), ("→", 116), (dst, 166), (itv, 268), ("↑", 336)):
            text(value, mx0 + dx, ry, 15, scr, "RIGHT", z=zt,
                 name="TXT_mv_%d_%d" % (i, dx))
    log("panneau droit : 2 écrans, clavier, tableau de conduite des voix")


def build_piano():
    """Clavier compact. Les touches noires suivent le motif chromatique réel."""
    x0, y0, x1, y1 = LAYOUT["piano"]
    n_white = LAYOUT["piano_keys"]
    kw = (x1 - x0) / float(n_white)
    black_after = {0, 1, 3, 4, 5}                  # C,D,F,G,A dans l'octave
    lit_white = {2, 4, 7, 9, 11, 14, 16}

    white, black = m_key_white(), m_key_black()
    lit = m_key_lit()
    for i in range(n_white):
        kx0 = x0 + i * kw
        plate("KEY_w_%02d" % i, kx0 + 0.6, y0, kx0 + kw - 0.6, y1, 3.0,
              lit if i in lit_white else white, "RIGHT", z_top=p(1.0))
    made = 0
    for i in range(n_white - 1):
        if i % 7 not in black_after:
            continue
        kx = x0 + (i + 1) * kw
        plate("KEY_b_%02d" % i, kx - kw * 0.30, y0, kx + kw * 0.30,
              y0 + (y1 - y0) * 0.60, 4.4, black, "RIGHT", z_top=p(2.4))
        made += 1
    log("clavier : %d touches blanches, %d noires, %d allumées"
        % (n_white, made, len(lit_white)))


def build_progression():
    x, y, body, size = LAYOUT["lbl_prog"]
    printed_text(body, x, y + size * 0.5, size, "PROG", name="TXT_progression")

    oled("OLED_status", *LAYOUT["oled_status"], coll="PROG")
    sx0, sy0, sx1, sy1 = LAYOUT["oled_status"]
    zt = -p(D["oled"] - D["text"])
    scr = m_screen_text()
    # Le brief ne specifie aucun contenu ici : on s'en tient a ce qu'il permet
    # de deduire (six blocs, Am9 est le bloc allume donc le selectionne).
    fields = (("SELECTED", "Am9", 30), ("CHORDS", "6", 232),
              ("VOICING", "ROOTLESS", 372))
    for label, value, dx in fields:
        text(label, sx0 + dx, sy0 + 22, 12, scr, "PROG", z=zt,
             name="TXT_st_l_%s" % label)
        text(value, sx0 + dx, sy0 + 48, 20, scr, "PROG", z=zt,
             name="TXT_st_v_%s" % label)

    ty0, ty1, items = LAYOUT["transport"]
    for x0, x1, label, state in items:
        button("BTN_tr_%s" % label, x0, ty0, x1, ty1, label, state, "PROG",
               label_size=13)

    build_timeline()

    by0, by1 = LAYOUT["blocks_y"]
    ink = m_ink()
    for i, (x0, x1, chord, sub, vel, tint, state) in enumerate(LAYOUT["blocks"]):
        plate("BLOCK_%d" % i, x0, by0, x1, by1, D["block"],
              m_block(tint, state), "PROG", z_top=p(D["block"]), bevel=1.6)
        # liseré d'accent en haut du bloc, comme sur la maquette
        plate("BLOCK_%d_accent" % i, x0, by0, x1, by0 + 4,
              D["block"] + 0.6, mat("MAT_accent_%s" % tint,
                                    lambda n, t=tint: _emit(n, FAMILY[t], 2.4)),
              "PROG", z_top=p(D["block"] + 0.5))
        zb = p(D["block"] + D["text"])
        text(chord, x0 + 22, by0 + 30, 24, ink, "PROG", z=zb,
             name="TXT_blk_%d" % i)
        text(sub, x0 + 22, by1 - 22, 13, ink, "PROG", z=zb,
             name="TXT_blksub_%d" % i)
        text(vel, x1 - 22, by1 - 22, 13, ink, "PROG", align="RIGHT", z=zb,
             name="TXT_blkvel_%d" % i)
    log("progression : écran d'état, 4 boutons, timeline, %d blocs d'accords"
        % len(LAYOUT["blocks"]))


def build_timeline():
    x0, y0, x1, y1 = LAYOUT["timeline"]
    bars = LAYOUT["timeline_bars"]
    oled("OLED_timeline", x0, y0, x1, y1, "PROG")
    zt = -p(D["oled"] - D["text"])
    scr = m_screen_text()
    ink = m_ink()

    printed_text("BAR", x0 - 46, y0 + 26, 13, "PROG", name="TXT_bar")

    # Une graduation par mesure, alignee sur les six blocs d'accords. La maquette
    # montre en plus une rangee de temps 1-2-3-4 que le brief ne demande pas :
    # la remplir reviendrait a inventer du texte.
    bar_w = (x1 - x0) / float(bars)
    for b in range(bars):
        bx = x0 + b * bar_w
        text(str(b + 1), bx + 14, y0 + 26, 17, scr, "PROG", z=zt,
             name="TXT_tl_bar_%d" % b)
        plate("TIMELINE_tick_%d" % b, bx, y0 + 4, bx + 1.5, y1 - 4,
              D["oled"] + 0.8, scr, "PROG", z_top=-p(D["oled"] - 0.6))

    ph = LAYOUT["playhead_x"]
    plate("TIMELINE_playhead", ph - 2, y0 - 6, ph + 2, y1, D["oled"] + 2.0,
          mat("MAT_playhead", lambda n: _emit(n, FAMILY["yellow"], 8.0)),
          "PROG", z_top=-p(D["oled"] - 1.0))
    log("timeline : %d graduations de mesure, tête de lecture à x=%d px" % (bars, ph))


# ===========================================================================
# Éclairage, caméra, rendu
# ===========================================================================

def build_lighting():
    """Studio produit : deux grandes Area rectangulaires + une lumière haute
    dédiée aux reflets du plastique, plus un cyclo gris chaud."""
    fx0, fy0, fx1, fy1 = LAYOUT["faceplate"]
    _cx, _cy, fw, fh = rect(fx0, fy0, fx1, fy1)

    aim = bpy.data.objects.new("AIM_face", None)
    aim.location = (0.0, 0.0, FACE_Z)
    aim.empty_display_size = p(20)
    link(aim, "CAMERA")

    # Puissances : la première passe à 220/90/160 W a cramé l'image entière.
    # Ces valeurs-ci sont celles qui tiennent l'exposition à cette distance
    # (~0,27 m d'une façade de 32 cm) ; à re-mesurer si la caméra recule.
    specs = (
        # Sources ELOIGNEES et LARGES : a 0.38 m d'une façade de 32 cm, la
        # decroissance en carre de la distance creait un degrade marque entre le
        # haut-centre et les bords. Les quatre libellés qui restaient laves
        # (TUPLE VST, PAD MATRIX, PROGRESSION, MIDI) tombaient tous dans les
        # zones claires : ce n'etait pas l'encre, c'etait l'uniformite.
        # Distance x1.76 => puissance x3.1 pour une exposition equivalente.
        # 02_relief_3d_system.md impose une source unique HAUT-GAUCHE :
        # « reflet sur le bord superieur et gauche, ombre sur le bord inferieur
        # et droit ». Ma clé etait a gauche mais EN DESSOUS, donc les reliefs
        # s'ombraient a l'envers de la spec.
        ("key",  (-fw * 0.95, fh * 0.85, fw * 2.10), fw * 1.90, 74.0, (1.0, 0.97, 0.93)),
        ("fill", (fw * 1.05, -fh * 0.25, fw * 1.70), fw * 2.10, 34.0, (0.94, 0.96, 1.0)),
        # VALEUR MESUREE (balayage 0 / 3 / 9 / 18 W). A 9 W son image miroir
        # formait au centre de la façade un halo blanc que j'ai pris trois
        # passes de suite pour de la laitance de matiere. A 0 le panneau devient
        # une vitre sans aucun modele. 3 W donne le voile de surface attendu
        # sans ecraser l'interieur.
        ("top",  (0.0, fh * 0.30, fw * 1.35), fw * 1.05, 3.0, (0.97, 0.98, 1.0)),
        # Lampe ARRIÈRE, derrière le boîtier et tournée vers la caméra : elle
        # traverse la coque et révèle la PCB et les composants. Sans elle
        # l'intérieur reste noir, le pourtour lit comme un cadre sombre — ce
        # que le prompt négatif refuse — et les libellés posés sur du vide se
        # lavent. C'est la lumière qui manquait, pas un réglage d'exposition.
        ("back", (0.0, fh * 0.10, -fw * 0.70), fw * 1.30, 34.0, (1.0, 0.98, 0.94)),
    )
    for name, loc, size, power, color in specs:
        data = bpy.data.lights.new("LIGHT_%s" % name, type="AREA")
        data.shape = "RECTANGLE"
        data.size = size
        data.size_y = size * 0.55
        data.energy = power
        data.color = color
        ob = bpy.data.objects.new("LIGHT_%s" % name, data)
        ob.location = loc
        link(ob, "LIGHTS")
        if name == "back":
            # Une lampe derriere un panneau TRANSMISSIF est vue a travers lui :
            # son emetteur rectangulaire formait un grand halo blanc au centre
            # de la façade, que j'ai pris trois passes de suite pour de la
            # laitance de matiere. Elle continue d'ECLAIRER l'interieur —
            # l'echantillonnage direct de la lumiere n'est pas affecte — mais
            # elle n'est plus VISIBLE a travers la coque.
            ob.visible_transmission = False
            ob.visible_camera = False
        con = ob.constraints.new("TRACK_TO")
        con.target = aim
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"

    # cyclorama gris chaud, derrière la façade
    # Plus clair et plus proche : c'est ce fond que la lumière transmise par le
    # pourtour de la coque capte. À 0.22 d'albédo et loin derrière, elle ne
    # captait que du noir.
    cyclo = mat("MAT_cyclo", lambda n: _plastic(n, (0.44, 0.425, 0.40), 0.60))
    back = create_box("BACKDROP_cyclo", (fw * 5.0, fh * 5.0, p(2.0)),
                      location=(0.0, 0.0, -p(BODY_D) - fw * 1.05),
                      collection="BACKDROP")
    assign(back, cyclo)

    # SOL. Le brief demande « soft contact shadow beneath the device » ; sans
    # plan d'appui le boîtier flottait, le cyclorama étant loin derrière. Le
    # plan affleure le bord bas de la façade : à 6 degrés de plongée on n'en
    # voit qu'un liseré, mais l'ombre de contact existe.
    # create_plane CENTRE le plan sur sa position : place a z = 0 il avancerait
    # de la moitie de sa taille VERS la camera et masquerait le bas du cadre
    # (constate). On le decale donc de la moitie de sa taille vers l'arriere,
    # pour qu'il parte de la face avant et file derriere le boitier.
    floor_size = fw * 4.0
    floor = create_plane("BACKDROP_floor", floor_size,
                         location=(0.0, -fh / 2.0 - p(1.0), -floor_size / 2.0),
                         rotation=(math.radians(90.0), 0.0, 0.0),
                         collection="BACKDROP")
    assign(floor, cyclo)

    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        # 0.055 laissait des ombres dures, 0.20 aplatissait tout le contraste
        # (bande PCB désaturée, blocs d'accords delaves). Valeur intermediaire :
        # les ombres se remplissent sans que la saturation tombe.
        bg.inputs["Color"].default_value = (0.095, 0.092, 0.088, 1.0)
        bg.inputs["Strength"].default_value = 1.0
    # Exposition globale, un seul levier plutot que de retoucher chaque albedo.
    # Les passes precedentes cramaient la coque : un trait de texte fin,
    # anti-aliase contre du blanc sature, ressort gris meme en encre a 0.045.
    # Ce n'etait donc pas l'encre le probleme, c'etait la coque.
    view = bpy.context.scene.view_settings
    # MESURE : a -1.4 EV la masse claire siegeait a p75 = 0.890 quand la
    # maquette de référence la place a 0.823, avec 31.9 % de pixels au-dessus de
    # 0.85 contre 5.9 %. Ce n'est pas l'albedo qui etait en cause — une surface
    # d'albedo 0.62 qui rend a 0.89 recoit trop de lumiere, point.
    # VALEUR MESUREE contre la VRAIE référence (e0e8c286-...png) :
    #   référence  médiane 0.619  p25 0.350  p75 0.753  >0.85 = 3.5 %
    #   a -3.3 EV  médiane 0.606  p25 0.455  p75 0.725  >0.85 = 0.0 %
    # Balayage -2.1 / -2.7 / -3.3 / -3.9. Deux cibles fausses l'ont precedee :
    # une heuristique generique, puis les mesures d'une image que j'avais prise
    # pour la maquette sans l'ouvrir. Ne pas retoucher sans re-mesurer.
    view.exposure = -3.3
    log("éclairage : 2 Area + 1 haute, cyclo gris chaud, exposition %.1f EV"
        % view.exposure)
    return aim


def build_camera(aim):
    """Élévation frontale : très légère plongée, distorsion minimale.

    Focale longue (135 mm) placée loin : c'est ce qui tient la promesse
    « minimal lens distortion » du brief. Pas de depth of field ici — sur une
    élévation technique, tout doit rester net.
    """
    fx0, fy0, fx1, fy1 = LAYOUT["faceplate"]
    _cx, _cy, fw, _fh = rect(fx0, fy0, fx1, fy1)

    data = bpy.data.cameras.new("CAM_front")
    data.lens = 135.0
    data.sensor_width = 36.0
    data.dof.use_dof = False

    dist = fw * (135.0 / 36.0) * 1.08          # cadre la largeur avec une marge
    elevation = math.radians(6.0)              # « very slight elevated perspective »
    cam = bpy.data.objects.new("CAM_front", data)
    cam.location = (0.0,
                    -dist * math.sin(elevation),
                    dist * math.cos(elevation))
    link(cam, "CAMERA")
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.context.scene.camera = cam

    frame_w = 36.0 / 135.0 * (dist * 1000.0)
    log("caméra : 135 mm à %.0f mm, plongée 6 deg, champ %.0f mm pour une façade de %.0f mm"
        % (dist * 1000, frame_w, fw * 1000))
    return cam


# ===========================================================================
# Assemblage
# ===========================================================================

def verify_layout():
    """Contrôles sur les nombres de LAYOUT, avant de construire.

    Ces erreurs sont silencieuses au rendu : une colonne manquante ou un
    libellé placé sur une rangée inexistante ne lève rien, ça produit juste une
    façade fausse.
    """
    cfg = LAYOUT["pads"]
    n = len(cfg["col_centers"])
    for field in ("degrees", "colors", "lit"):
        if len(cfg[field]) != n:
            raise RuntimeError(
                "pads.%s compte %d entrées pour %d colonnes"
                % (field, len(cfg[field]), n))
    for c, lit in enumerate(cfg["lit"]):
        for row in lit:
            if not 0 <= row < cfg["rows"]:
                raise RuntimeError(
                    "colonne %d : libellé %r sur la rangée %d, hors de [0, %d["
                    % (c, lit[row], row, cfg["rows"]))
    for name in cfg["colors"]:
        if name not in FAMILY:
            raise RuntimeError("famille harmonique %r absente de FAMILY" % name)
    for _x0, _x1, _c, _s, _v, tint, state in LAYOUT["blocks"]:
        if tint not in FAMILY:
            raise RuntimeError("bloc : teinte %r absente de FAMILY" % tint)
        if state not in ("pale", "hot", "warm"):
            raise RuntimeError("bloc : état %r inconnu" % state)

    fx0, fy0, fx1, fy1 = LAYOUT["faceplate"]
    _cx, _cy, w, h = rect(fx0, fy0, fx1, fy1)
    ratio = w / h
    log("layout vérifié : %d colonnes, façade %.1f x %.1f mm, ratio %.3f"
        % (n, w * 1000, h * 1000, ratio))


def build(plastic_only=False):
    """Construit la scene. `plastic_only` ne garde que la coque et son intérieur.

    A utiliser pour travailler la matiere : voir la note en tete du patch. Les
    puits ne sont pas creuses dans ce mode, puisque ce sont les constructeurs de
    panneaux qui declarent leurs cutters — la coque est donc nue, ce qui est
    exactement ce qu'on veut pour juger le plastique.
    """
    proto.clear_scene()
    proto.configure_units()
    # ces deux caches survivraient d'un run à l'autre dans la même session
    _PENDING_PLAQUE.clear()
    _MATS.clear()
    verify_layout()

    build_body()

    if plastic_only:
        log("MODE PLASTIQUE : panneaux, boutons, écrans et libellés ignorés")
    else:
        build_header()
        build_left_panel()
        build_pad_matrix()
        build_right_panel()
        build_progression()
    # APRÈS toute la géométrie : les plaques ont besoin de l'encombrement rendu
    # des textes, qui n'existe qu'une fois le depsgraph réévalué. En mode
    # plastique il n'y a aucun libellé, et finalize_plaques lève à juste titre.
    if not plastic_only:
        finalize_plaques()

    aim = build_lighting()
    build_camera(aim)

    bpy.context.view_layer.update()
    # Deux familles, deux booléens, de part et d'autre du Solidify : on les
    # compte séparément pour que l'ordre reste vérifiable dans le log.
    wells = [o for o in bpy.data.objects if o.name.startswith("CUT_")]
    if wells:
        log("découpe : %d puits (booléen avant Solidify)" % len(wells))
    else:
        # Légitime en mode plastique : ce sont les constructeurs de panneaux qui
        # déclarent les cutters, et ils ne tournent pas.
        log("découpe : aucun puits (coque nue)")
    log("objets : %d, collections : %s"
        % (len(bpy.data.objects),
           sorted(c.name for c in bpy.data.collections)))


def parse_args(argv):
    args = {"render": False, "engine": "CYCLES", "samples": None,
            "percent": None, "save_blend": None, "plastic": False}
    if "--" not in argv:
        return args
    rest = argv[argv.index("--") + 1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--render":
            args["render"] = True; i += 1
        elif tok == "--plastic":
            args["plastic"] = True; i += 1
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
                raise SystemExit("--engine attend cycles ou eevee, reçu %r" % rest[i + 1])
            args["engine"] = mapping[name]; i += 2
        else:
            raise SystemExit("argument inconnu : %r" % tok)
    return args


def main():
    args = parse_args(sys.argv)
    log("Blender %s" % bpy.app.version_string)
    build(plastic_only=args["plastic"])

    out = os.path.join(_HERE, "renders",
                       "plastic" if args["plastic"] else "faceplate")
    # le préfixe vit dans la CONFIG du module importé : le corriger AVANT
    # configure_render, sinon la ligne de log annonce "knob_" alors que le
    # fichier écrit s'appelle "faceplate_"
    proto.CONFIG["render"]["output_prefix"] = (
        "plastic_" if args["plastic"] else "faceplate_")
    proto.configure_render(samples=args["samples"], resolution_percent=args["percent"],
                           output_dir=out, engine=args["engine"])
    scene = bpy.context.scene
    scene.render.filepath = os.path.join(out, proto.CONFIG["render"]["output_prefix"])
    scene.frame_start = scene.frame_end = 1

    if args["save_blend"]:
        path = args["save_blend"]
        if not os.path.isabs(path):
            path = os.path.join(_HERE, path)
        bpy.ops.wm.save_as_mainfile(filepath=path)
        log(".blend écrit : %s" % path)

    if args["render"]:
        scene.render.filepath = os.path.join(out, proto.CONFIG["render"]["output_prefix"] + "0001")
        log("rendu...")
        bpy.ops.render.render(write_still=True)
        written = scene.render.filepath + ".png"
        log("écrit : %s (existe=%s)" % (written, os.path.exists(written)))
    else:
        log("façade construite, aucun rendu demandé (ajouter -- --render)")


if __name__ == "__main__":
    main()
