"""Banc d'essai ISOLE pour la matiere de la coque.

POURQUOI IL EXISTE
    Toute la matiere du polycarbonate avait ete reglee en la regardant a
    travers la façade complete : 486 objets, une interface, une carte, deux
    plaques internes et quatre sources. Chaque essai bougeait donc plusieurs
    apparences a la fois, et aucun ne concluait. On ne regle pas une matiere
    dans une scene qui la cache.

    Ce banc ne contient que ce dont la matiere a besoin pour se juger :
    une plaque de polycarbonate avec son rebord, la carte derriere elle a la
    vraie distance, un fond, une lumiere. Rien d'autre. Il rend en quelques
    secondes en Eevee, contre 95 s pour la façade en Cycles.

USAGE
    blender --background --python-exit-code 1 --python shell_lab.py
    blender --background --python-exit-code 1 --python shell_lab.py -- --cycles
    blender --background --python-exit-code 1 --python shell_lab.py -- --only gba

    Un PNG par candidat sous renders/shell_lab/, plus une planche assemblee
    par assemble_lab.py.

CE QUE LE BANC NE DIT PAS
    Il juge la MATIERE, pas la façade. Un candidat qui gagne ici doit encore
    etre reporte sur la scene complete et re-juge : l'interface pose des
    ombres et des reflets que ce banc n'a pas.
"""

import math
import os
import sys

import bpy

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tuple_faceplate as fp                                       # noqa: E402
import tuple_vst_proto as proto                                    # noqa: E402


PLAQUE_W = 0.323          # m, largeur de la façade reelle
PLAQUE_H = 0.182
PLAQUE_D = 0.012          # 12 mm d'epaisseur de boitier
PCB_GAP = 0.0025          # 2,5 mm entre la face arriere de la plaque et la carte
LIP_W = 0.0068            # 34 px de maquette
LIP_D = 0.0052            # 26 px
WALL_EP = 0.0012          # 1,2 mm de paroi, comme WALL dans tuple_faceplate


def log(m):
    print("[shell-lab] %s" % m)


def vider():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def boite(nom, taille, position):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=position)
    ob = bpy.context.active_object
    ob.name = nom
    # `primitive_cube_add(size=1.0)` cree deja un cube de 1 x 1 x 1, pas de
    # 2 x 2 x 2 : diviser la taille par deux ici la divisait UNE FOIS DE TROP et
    # la plaque sortait a la moitie de sa cote. Elle apparaissait alors plus
    # petite que la carte censee etre derriere elle, ce qui rendait la planche
    # ininterpretable — on ne comparait pas des matieres mais des tailles.
    ob.scale = tuple(taille)
    bpy.ops.object.transform_apply(scale=True)
    return ob


def bevel(ob, largeur, segments=4):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.width = largeur
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(40.0)
    return m


# ===========================================================================
# Candidats de matiere. Un par fonction, meme signature.
# Chacun recoit un materiau neuf et le remplit ; aucun n'a le droit de
# dependre d'un autre.
# ===========================================================================

def cand_gba(m, nodes, links, bsdf):
    """Le node tree de cartouche Game Boy Advance transparente.

    Transmission 1,00, IOR 1,50, aucun subsurface, rugosite pilotee par un
    micro-grain tres dense, normale passee par un Bump. C'est la structure
    relevee sur la capture d'Antoine, transposee sans ses deux textures 4K
    (propres a sa cartouche) : le grain de moule les remplace.
    """
    fp.set_input(bsdf, "Base Color", (0.86, 0.87, 0.84, 1.0))
    fp.set_input(bsdf, "Metallic", 0.0)
    fp.set_input(bsdf, "IOR", 1.50)
    fp.set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)

    coord = nodes.new("ShaderNodeTexCoord")
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 7000.0
    grain.inputs["Detail"].default_value = 0.0
    grain.inputs["Distortion"].default_value = 0.2
    links.new(coord.outputs["Object"], grain.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].position = 0.35
    links.new(grain.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    links.new(ramp.outputs["Color"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    rough = nodes.new("ShaderNodeMapRange")
    rough.inputs[3].default_value = 0.06
    rough.inputs[4].default_value = 0.22
    links.new(ramp.outputs["Color"], rough.inputs[0])
    links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    return "gba"


def cand_nu(m, nodes, links, bsdf):
    """Le plus simple possible : transmission pure, rugosite uniforme.

    Sert de PLANCHER. Si un candidat elabore ne bat pas celui-ci, sa
    complexite ne se paie pas.
    """
    fp.set_input(bsdf, "Base Color", (0.88, 0.89, 0.86, 1.0))
    fp.set_input(bsdf, "Metallic", 0.0)
    fp.set_input(bsdf, "IOR", 1.585)
    fp.set_input(bsdf, "Roughness", 0.14)
    fp.set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)
    return "nu"


def cand_sss(m, nodes, links, bsdf):
    """Diffusion sous-surfacique DOMINANTE, transmission faible.

    L'hypothese opposee a `gba` : un polycarbonate laiteux n'est pas du verre
    rugueux, c'est un milieu ou la lumiere entre, diffuse et ressort ailleurs.
    """
    fp.set_input(bsdf, "Base Color", (0.90, 0.91, 0.88, 1.0))
    fp.set_input(bsdf, "Metallic", 0.0)
    fp.set_input(bsdf, "IOR", 1.585)
    fp.set_input(bsdf, "Roughness", 0.18)
    fp.set_input(bsdf, ["Transmission Weight", "Transmission"], 0.55)
    bsdf.subsurface_method = "BURLEY"
    fp.set_input(bsdf, ["Subsurface Weight", "Subsurface"], 0.55)
    fp.set_input(bsdf, "Subsurface Radius", (1.0, 0.88, 0.82))
    fp.set_input(bsdf, "Subsurface Scale", 0.004)
    return "sss"


def cand_poli(m, nodes, links, bsdf):
    """Verre optique : rugosite tres basse, aucune diffusion.

    Le cas limite haut. Il doit rendre la carte parfaitement nette et la
    matiere invisible — c'est le TEMOIN qui prouve que le banc separe bien
    « on voit a travers » de « on voit la matiere ».
    """
    fp.set_input(bsdf, "Base Color", (0.92, 0.93, 0.91, 1.0))
    fp.set_input(bsdf, "Metallic", 0.0)
    fp.set_input(bsdf, "IOR", 1.585)
    fp.set_input(bsdf, "Roughness", 0.02)
    fp.set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)
    return "poli"


def faire_gba(rmin, rmax, force=0.35):
    """Fabrique un candidat GBA a laitance donnee.

    La laitance de ce shader tient a UNE grandeur : la plage dans laquelle le
    micro-grain remappe la rugosite. Plus la borne haute monte, plus la surface
    disperse et moins on distingue ce qu'il y a derriere. La force du bump est
    laissee fixe — la faire varier en meme temps rendrait le balayage
    ininterpretable, puisque les deux agissent sur la meme apparence.
    """
    def candidat(m, nodes, links, bsdf):
        cand_gba(m, nodes, links, bsdf)
        for nd in nodes:
            if nd.type == "MAP_RANGE":
                nd.inputs[3].default_value = rmin
                nd.inputs[4].default_value = rmax
            elif nd.type == "BUMP":
                nd.inputs["Strength"].default_value = force
        return "gba"
    return candidat


def faire_plastique(transm, sss_w, sss_mm, rough, force=0.30):
    """Polycarbonate LAITEUX : transmission partielle PLUS diffusion interne.

    Antoine, sur le candidat gba : « on dirait un melange de metal et de verre,
    mais du plastique ». Le diagnostic est exact et il tient a une seule ligne du
    shader : a transmission 1,00 le Principled n'a plus AUCUNE composante
    diffuse, il ne renvoie que du speculaire — et une surface qui ne renvoie que
    du speculaire lit comme du verre ou du metal poli, quelle que soit sa
    rugosite.

    Un polycarbonate translucide n'est pas du verre rugueux : c'est un milieu
    diffusant. La lumiere y ENTRE, s'y disperse sur quelques dixiemes de
    millimetre et ressort ailleurs. C'est un BSSRDF.

    `sss_mm` est le rayon de diffusion EN MILLIMETRES. Il doit rester du meme
    ordre que la paroi (1,2 mm) : le premier candidat sss le posait a 4 mm, soit
    plus de trois fois l'epaisseur traversee, et la coque sortait blanche et
    opaque. C'est ce reglage qui l'avait fait ecarter, pas le principe.
    """
    def candidat(m, nodes, links, bsdf):
        cand_gba(m, nodes, links, bsdf)          # reprend le micro-grain
        fp.set_input(bsdf, ["Transmission Weight", "Transmission"], transm)
        bsdf.subsurface_method = "BURLEY"
        fp.set_input(bsdf, ["Subsurface Weight", "Subsurface"], sss_w)
        fp.set_input(bsdf, "Subsurface Radius", (1.0, 0.94, 0.90))
        fp.set_input(bsdf, "Subsurface Scale", sss_mm / 1000.0)
        for nd in nodes:
            if nd.type == "MAP_RANGE":
                nd.inputs[3].default_value = rough[0]
                nd.inputs[4].default_value = rough[1]
            elif nd.type == "BUMP":
                nd.inputs["Strength"].default_value = force
        return "plastique"
    return candidat


def cand_reddit(m, nodes, links, bsdf):
    """La recette la plus soutenue du fil r/blenderhelp, transposee.

    Subsurface a 0,30 avec un rayon NEUTRE sur les trois canaux — la reponse la
    plus votee le dit explicitement, et notre reglage teintait le rayon
    (1,0 / 0,94 / 0,90) sans que rien ne le justifie. Transmission volontairement
    MODEREE : « don't set transmission too high or it will kill all the
    subsurface », ce que la mesure d'hier avait montre sans que j'en tire la
    conclusion. Et du Coat, que plusieurs intervenants donnent comme ce qui fait
    la difference entre du verre et du plastique.
    """
    cand_gba(m, nodes, links, bsdf)
    fp.set_input(bsdf, ["Transmission Weight", "Transmission"], 0.55)
    bsdf.subsurface_method = "BURLEY"
    fp.set_input(bsdf, ["Subsurface Weight", "Subsurface"], 0.30)
    fp.set_input(bsdf, "Subsurface Radius", (1.0, 1.0, 1.0))
    # RAYON DIX FOIS PLUS COURT que le premier essai. La recette du fil precise
    # « make the surface really thin » ; notre paroi fait 1,2 mm, et un rayon de
    # 0,6 mm y noie tout — le rendu sortait en aplat blanc. Le dosage utile se
    # joue en centiemes de millimetre a cette epaisseur.
    fp.set_input(bsdf, "Subsurface Scale", SSS_MM / 1000.0)
    fp.set_input(bsdf, ["Coat Weight", "Clearcoat"], 0.35)
    fp.set_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.08)
    for nd in nodes:
        if nd.type == "MAP_RANGE":
            nd.inputs[3].default_value = 0.08
            nd.inputs[4].default_value = 0.22
    return "reddit"


def cand_blenderkit(m, nodes, links, bsdf):
    """« Procedural Translucent Plastic » de BlenderKit, royalty free.

    asset_base_id 6abfb12e-a102-47ac-8a4f-5859debd5801, verifie dans le fichier
    et non de memoire. Il etait DEJA telecharge, extrait et cable dans le projet
    sous USE_BK_PLASTIC — et debranche.

    CROYANCE REVISEE. Le motif ecrit pour l'ecarter etait : « ne peut pas
    exprimer ses rayures a Transmission Weight 0,88, faute de composante diffuse
    pour les porter ». C'est exact, et c'est exactement ce qu'un fil
    r/blenderhelp sur ce meme probleme resume par « don't set transmission too
    high or it will kill all the subsurface ». Le verdict portait donc sur un
    REGLAGE, pas sur le materiau — et ce reglage a change. On le rejuge a
    transmission moderee.
    """
    chemin = os.path.normpath(os.path.join(
        r"C:\dev\Tuple_3D", "05_textures", "blenderkit_translucent_plastic.blend"))
    nom = "Procedural Translucent Plastic"
    if nom not in bpy.data.materials:
        if not os.path.exists(chemin):
            raise RuntimeError("materiau BlenderKit absent : %s" % chemin)
        with bpy.data.libraries.load(chemin, link=False) as (src, dst):
            if nom not in src.materials:
                raise RuntimeError("materiau %r absent de %s ; presents : %s"
                                   % (nom, chemin, list(src.materials)))
            dst.materials = [nom]
    # COPIE de l'asset, jamais l'asset lui-meme : le banc corrige sa
    # transmission, et l'original doit rester intact pour rejouer la comparaison.
    copie = bpy.data.materials[nom].copy()
    copie.name = "MAT_lab_bk"
    # Sa structure n'est PAS un Principled expose : c'est un node group
    # « Procedural Plastic » a 10 entrees. Le garde precedent cherchait un
    # Principled et a bien bloque plutot que de laisser passer un reglage
    # applique nulle part.
    grp = next((n for n in copie.node_tree.nodes if n.type == "GROUP"), None)
    if grp is None:
        raise RuntimeError(
            "pas de node group dans %r — structure inattendue, le reglage de "
            "transmission ne s'appliquerait nulle part et le candidat serait "
            "juge sur ses valeurs d'origine sans que rien ne le signale." % nom)
    attendus = ("Transmission Weight", "Roughness")
    manquants = [k for k in attendus if k not in grp.inputs]
    if manquants:
        raise RuntimeError(
            "entrees %s absentes du groupe %r ; presentes : %s"
            % (manquants, grp.node_tree.name, [i.name for i in grp.inputs]))
    # L'asset est livre a Transmission Weight 1,0 — le reglage meme qui supprime
    # toute composante diffuse, et donc la raison pour laquelle il avait ete
    # juge « indiscernable du shader maison » puis debranche.
    grp.inputs["Transmission Weight"].default_value = BK_TRANSMISSION
    grp.inputs["Roughness"].default_value = BK_ROUGHNESS
    return copie


def faire_bk(transm, base=(0.86, 0.87, 0.85, 1.0)):
    """Le materiau BlenderKit a transmission donnee, base color NEUTRALISEE.

    Sa Base Color d'origine est rose (0,80 / 0,672 / 0,655). A transmission
    partielle cette teinte domine et la coque sort rosee opaque — la carte
    disparait derriere une matiere qui a pourtant un tres beau grain. On isole
    donc les deux effets : la teinte est ramenee au blanc casse du projet, seule
    la transmission varie.
    """
    def candidat(m, nodes, links, bsdf):
        copie = cand_blenderkit(m, nodes, links, bsdf)
        grp = next(n for n in copie.node_tree.nodes if n.type == "GROUP")
        grp.inputs["Transmission Weight"].default_value = transm
        grp.inputs["Base Color"].default_value = base
        return copie
    return candidat


CANDIDATS = {
    "gba": cand_gba,
    "reddit": cand_reddit,
    "bk": cand_blenderkit,
    "bk70": faire_bk(0.70), "bk85": faire_bk(0.85), "bk95": faire_bk(0.95),
    # Melanges transmission / diffusion interne, du plus vitreux au plus laiteux.
    # VALEURS BAISSEES apres un premier balayage a 0,18-0,62 de diffusion, ou
    # les quatre candidats sortaient blancs des le second. Le subsurface de
    # Blender sature tres vite quand son rayon approche l'epaisseur traversee :
    # sur 1,2 mm de paroi, un rayon de 0,6 mm noie deja tout. Le dosage utile se
    # joue en DIXIEMES de millimetre.
    "p1": faire_plastique(0.94, 0.05, 0.15, (0.06, 0.18)),
    "p2": faire_plastique(0.90, 0.09, 0.25, (0.06, 0.18)),
    "p3": faire_plastique(0.86, 0.14, 0.35, (0.08, 0.20)),
    "p4": faire_plastique(0.80, 0.20, 0.45, (0.08, 0.20)),
    "nu": cand_nu,
    "sss": cand_sss,
    "poli": cand_poli,
    # Balayage de laitance, du plus clair au plus depoli.
    "g1": faire_gba(0.03, 0.10),
    "g2": faire_gba(0.06, 0.18),
    "g3": faire_gba(0.10, 0.28),
    "g4": faire_gba(0.16, 0.40),
}


# Eclairage INTERNE. Piste venue d'un fil r/blenderhelp sur exactement ce
# probleme : la carte n'est pas seulement traversee par la lumiere du dehors,
# elle est ECLAIREE DE L'INTERIEUR. Un intervenant y branche sa PCB sur un
# shader emissif, un autre place des sources sous la coque. C'est ce qui fait
# ressortir les composants a travers un depoli qui, autrement, les mange.
# Positions RELEVEES sur la carte 4K, en coordonnees normalisees de la texture.
# Les trois encodeurs y sont serigraphies ENC1, ENC2, ENC3.
ENC_U = (0.076, 0.136, 0.200)
ENC_V = 0.342
ENC_RAYON_MM = 5.0          # percage de 10 mm, cote courante pour un potentiometre
BOSSAGE_MM = 2.2            # matiere en saillie autour de chaque percage
# Fenetres d'ecran, sur les deux nappes LCD du haut-gauche.
FENETRES = (
    (0.045, 0.055, 0.235, 0.115),
    (0.045, 0.135, 0.235, 0.195),
)

BK_TRANSMISSION = 0.55
BK_ROUGHNESS = 0.16
SSS_MM = 0.06
PCB_EMISSION = 0.35
LUMIERES_INTERNES = 3


def batir_scene(nom_mat, remplir, gap=None, emission=None, internes=None):
    """`gap` : distance entre la face INTERIEURE de la paroi et la carte.

    C'est le levier dominant du flou, et il l'emporte sur la rugosite. Une
    surface depolie ne floute pas ce qu'elle touche : elle floute en proportion
    de la distance qui l'en separe — un verre depoli pose sur un texte le laisse
    lire, a cinq millimetres il l'efface. Regler la rugosite sans regler cette
    distance revient a corriger un symptome.
    """
    vider()
    scene = bpy.context.scene

    # -- la carte, a la vraie distance ------------------------------------
    # LA CARTE EST DEDANS, pas derriere. Elle etait placee sous la face ARRIERE
    # du boitier, si bien que chaque rayon traversait la paroi avant, l'air,
    # PUIS la paroi arriere — deux lames au lieu d'une, et le decalage lateral
    # de la seconde deformait franchement l'image. Le temoin `poli` le montrait
    # en clair : la carte y sortait decalee vers la gauche avec une bande blanche
    # a droite.
    #
    # Dans un boitier reel la carte est a quelques millimetres SOUS la paroi
    # avant, du cote interieur. Le rayon ne traverse alors qu'une lame de
    # 1,2 mm, et une lame mince a faces paralleles ne deforme quasiment rien —
    # ce qu'Antoine a signale d'emblee : « le plastique ne fait pas ça ».
    bpy.ops.mesh.primitive_plane_add(size=1.0,
                                     location=(0.0, 0.0,
                                               PLAQUE_D / 2.0 - WALL_EP
                                               - (PCB_GAP if gap is None
                                                  else gap)))
    pcb = bpy.context.active_object
    pcb.name = "PCB"
    pcb.scale = (PLAQUE_W * 0.96, PLAQUE_H * 0.96, 1.0)
    bpy.ops.object.transform_apply(scale=True)

    mp = bpy.data.materials.new("MAT_pcb_lab")
    ntp = mp.node_tree
    bp = ntp.nodes.get("Principled BSDF")
    tex_dir = os.path.normpath(os.path.join(r"C:\dev\Tuple_3D", "05_textures"))
    for cle, socket, cs in (("color", "Base Color", "sRGB"),
                            ("rough", "Roughness", "Non-Color")):
        chemin = os.path.join(tex_dir, "pcb_%s.png" % cle)
        if not os.path.exists(chemin):
            raise RuntimeError(
                "carte de PCB absente : %s — sans elle le banc jugerait la "
                "matiere devant un plan uni, ou toute difference de "
                "transparence devient invisible." % chemin)
        t = ntp.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(chemin, check_existing=True)
        t.image.colorspace_settings.name = cs
        ntp.links.new(t.outputs["Color"], bp.inputs[socket])
        if cle == "color":
            em = PCB_EMISSION if emission is None else emission
            if em > 0.0:
                # La carte porte sa propre couleur en EMISSION, pas une teinte
                # inventee : c'est ce qui la fait lire a travers le depoli sans
                # la delaver, contrairement a une lumiere blanche posee derriere.
                ntp.links.new(t.outputs["Color"], bp.inputs["Emission Color"])
                bp.inputs["Emission Strength"].default_value = em
    pcb.data.materials.append(mp)

    # -- la plaque, avec son rebord ---------------------------------------
    plaque = boite("PLAQUE", (PLAQUE_W, PLAQUE_H, PLAQUE_D), (0.0, 0.0, 0.0))
    # CREUSE, pas pleine. Le premier jet donnait un bloc massif de 12 mm, et
    # Antoine l'a vu tout de suite : « pourquoi ça deforme autant la PCB
    # derriere ? Le plastique ne fait pas ça ». Il a raison — 12 mm de matiere a
    # IOR 1,585 decalent l'image d'environ 1,5 mm des qu'on regarde en biais, et
    # le chanfrein du pourtour agit en lentille. Un boitier reel n'est pas un
    # bloc : c'est une paroi de 1,2 mm avec de l'air derriere, et une lame mince
    # a faces paralleles ne deforme quasiment rien.
    #
    # La façade, elle, portait deja ce Solidify. Le banc etait donc MOINS juste
    # que la scene qu'il devait servir a regler — et il aurait fait choisir une
    # matiere sur une deformation qui n'existe pas.
    sol = plaque.modifiers.new("hollow", "SOLIDIFY")
    sol.thickness = WALL_EP
    sol.offset = -1.0
    sol.use_even_offset = True
    sol.use_rim = True
    bevel(plaque, 0.0026, segments=5)

    lip = boite("LIP", (PLAQUE_W, PLAQUE_H, LIP_D),
                (0.0, 0.0, PLAQUE_D / 2.0 - LIP_D / 2.0))
    trou = boite("LIP_CUT", (PLAQUE_W - LIP_W * 2.0, PLAQUE_H - LIP_W * 2.0,
                             LIP_D * 3.0),
                 (0.0, 0.0, PLAQUE_D / 2.0 - LIP_D / 2.0))
    trou.hide_render = True
    b = lip.modifiers.new("evide", "BOOLEAN")
    b.operation = "DIFFERENCE"
    b.object = trou
    b.solver = "EXACT"
    bevel(lip, 0.0016, segments=4)

    # ----- PERCAGES ET RELIEF -------------------------------------------
    # Une plaque lisse ne montre pas ce qu'une matiere translucide fait la ou
    # elle est PERCEE ou BOMBEE : c'est sur une arete de percage que l'epaisseur
    # se lit, et sur un bossage que la lumiere glisse. Les positions viennent de
    # la carte elle-meme — les trois encodeurs et les deux fenetres d'ecran sont
    # aux coordonnees ou la texture les dessine, pas a des endroits inventes.
    coupeurs = []

    def _perce_rond(nom_p, u, v, rayon_mm):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=64, radius=rayon_mm / 1000.0, depth=PLAQUE_D * 4.0,
            location=((u - 0.5) * PLAQUE_W, (0.5 - v) * PLAQUE_H, 0.0))
        c = bpy.context.active_object
        c.name = nom_p
        c.hide_render = True
        coupeurs.append(c)

    def _perce_rect(nom_p, u0, v0, u1, v1):
        c = boite(nom_p, ((u1 - u0) * PLAQUE_W, (v1 - v0) * PLAQUE_H,
                          PLAQUE_D * 4.0),
                  (((u0 + u1) / 2.0 - 0.5) * PLAQUE_W,
                   (0.5 - (v0 + v1) / 2.0) * PLAQUE_H, 0.0))
        c.hide_render = True
        coupeurs.append(c)

    for i, u in enumerate(ENC_U):
        _perce_rond("CUT_ENC%d" % i, u, ENC_V, ENC_RAYON_MM)
    for i, (u0, v0, u1, v1) in enumerate(FENETRES):
        _perce_rect("CUT_ECR%d" % i, u0, v0, u1, v1)

    # TROUS DE VIS, alignes sur ceux que la carte dessine. Antoine : « les trous
    # pour les vis alignees avec la pcb ». Les positions viennent de
    # pcb_screws.json, releve par Tuple_3D/pcb_screws.py sur la texture — pas de
    # cote inventee, donc pas de decalage entre le percage de la coque et la
    # couronne de la carte.
    chemin_vis = os.path.normpath(os.path.join(
        r"C:\dev\Tuple_3D", "05_textures", "pcb_screws.json"))
    if os.path.exists(chemin_vis):
        import json as _json
        with open(chemin_vis, encoding="utf-8") as _f:
            _v = _json.load(_f)
        tw = _v["texture"][0]
        for i, vis in enumerate(_v["vis"]):
            # Le percage de la coque passe la VIS, pas la couronne : il est plus
            # etroit que le disque dore de la carte, qui est la pastille de
            # cuivre autour du trou.
            rayon_mm = vis["diam_px"] / tw * PLAQUE_W * 1000.0 * 0.30
            _perce_rond("CUT_VIS%d" % i, vis["u"], vis["v"], rayon_mm)
        log("%d trous de vis perces, alignes sur la carte" % len(_v["vis"]))
    else:
        log("pcb_screws.json absent : aucun trou de vis")

    for i, c in enumerate(coupeurs):
        b = plaque.modifiers.new("perce_%d" % i, "BOOLEAN")
        b.operation = "DIFFERENCE"
        b.object = c
        b.solver = "EXACT"

    # BOSSAGES : de la matiere qui DEPASSE, pour voir la lumiere glisser dessus.
    # Une facade reelle en a autour de chaque commande.
    bossages = []
    for i, u in enumerate(ENC_U):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=64, radius=(ENC_RAYON_MM + 4.5) / 1000.0,
            depth=BOSSAGE_MM / 1000.0,
            location=((u - 0.5) * PLAQUE_W, (0.5 - ENC_V) * PLAQUE_H,
                      PLAQUE_D / 2.0 + BOSSAGE_MM / 2000.0))
        bo = bpy.context.active_object
        bo.name = "BOSS_ENC%d" % i
        bevel(bo, 0.0012, segments=4)
        bossages.append(bo)

    # CORPS DE POTENTIOMETRE. Antoine : « c'est quoi le truc noir au fond ? ».
    # C'etait le percage lui-meme : un trou traverse la coque et laisse voir
    # l'interieur du boitier, vide et qu'aucune lumiere n'atteint. Sur un
    # controleur reel le corps du potentiometre remplit le percage, et c'est lui
    # qu'on voit — jamais un trou beant.
    m_pot = bpy.data.materials.new("MAT_pot")
    bp_pot = m_pot.node_tree.nodes.get("Principled BSDF")
    bp_pot.inputs["Base Color"].default_value = (0.34, 0.345, 0.35, 1.0)
    bp_pot.inputs["Roughness"].default_value = 0.32
    bp_pot.inputs["Metallic"].default_value = 0.85
    for i, u in enumerate(ENC_U):
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=48, radius=(ENC_RAYON_MM - 1.2) / 1000.0,
            depth=0.010,
            location=((u - 0.5) * PLAQUE_W, (0.5 - ENC_V) * PLAQUE_H,
                      PLAQUE_D / 2.0 - 0.005))
        pot = bpy.context.active_object
        pot.name = "POT_%d" % i
        pot.data.materials.append(m_pot)

    m = bpy.data.materials.new(nom_mat)
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    # Un candidat peut soit REMPLIR le materiau qu'on lui donne, soit en RENDRE
    # un tout fait — c'est le cas de celui qui charge un asset BlenderKit, dont
    # on ne veut pas recopier les 60 noeuds a la main.
    rendu = remplir(m, nt.nodes, nt.links, bsdf)
    if isinstance(rendu, bpy.types.Material):
        bpy.data.materials.remove(m)
        m = rendu
    for ob in [plaque, lip] + bossages:
        ob.data.materials.append(m)

    # -- fond, lumiere, camera --------------------------------------------
    n_int = LUMIERES_INTERNES if internes is None else internes
    for i in range(n_int):
        d = bpy.data.lights.new("L_INT_%d" % i, type="POINT")
        d.energy = 0.020
        d.shadow_soft_size = 0.010
        d.color = (1.0, 0.96, 0.90)
        ob = bpy.data.objects.new("L_INT_%d" % i, d)
        # Reparties sur la largeur, JUSTE sous la paroi avant : une source
        # placee au fond du boitier n'eclairerait que le fond.
        ob.location = (PLAQUE_W * (i / max(1, n_int - 1) - 0.5) * 0.62, 0.0,
                       PLAQUE_D / 2.0 - WALL_EP - 0.004)
        bpy.context.collection.objects.link(ob)

    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0.0, 0.0, -0.20))
    fond = bpy.context.active_object
    fond.name = "FOND"
    mf = bpy.data.materials.new("MAT_fond")
    mf.node_tree.nodes.get("Principled BSDF").inputs["Base Color"] \
        .default_value = (0.42, 0.41, 0.39, 1.0)
    fond.data.materials.append(mf)

    for nom, loc, taille, watts in (
            # Puissances DIVISEES : a 60 et 22 W le banc sortait blanc sature
            # sur les quatre candidats, et une image ecretee ne distingue plus
            # rien — deux matieres tres differentes y rendent le meme blanc.
            # DIVISEES PAR TROIS. A 14 et 5 W, 28 a 52 % des pixels sortaient
            # ecretes a 1,0 selon le candidat — un banc dont la moitie de
            # l'image est saturee ne departage plus rien, puisque deux matieres
            # tres differentes y rendent le meme blanc. Le garde en fin de
            # rendu verifie desormais que ça ne revient pas.
            ("KEY", (-0.30, 0.26, 0.62), 0.34, 4.5),
            ("FILL", (0.34, 0.08, 0.52), 0.42, 1.6)):
        d = bpy.data.lights.new("L_" + nom, type="AREA")
        d.shape = "RECTANGLE"
        d.size, d.size_y, d.energy = taille, taille * 0.55, watts
        ob = bpy.data.objects.new("L_" + nom, d)
        ob.location = loc
        bpy.context.collection.objects.link(ob)
        c = ob.constraints.new("TRACK_TO")
        cible = bpy.data.objects.new("AIM", None)
        cible.location = (0.0, 0.0, 0.0)
        bpy.context.collection.objects.link(cible)
        c.target = cible
        c.track_axis = "TRACK_NEGATIVE_Z"

    # CADRAGE. La plaque fait 323 mm de large ; a 105 mm de focale et 0,42 m
    # elle debordait largement du cadre et le banc ne montrait qu'un aplat au
    # centre, sans ses bords — c'est-a-dire sans l'endroit meme ou l'epaisseur
    # se lit. Avec un capteur de 36 mm, la distance qui cadre 380 mm de large
    # a 50 mm de focale vaut 380 x 50 / 36 = 528 mm.
    bpy.ops.object.camera_add(location=(0.0, -0.02, 0.528),
                              rotation=(math.radians(3.0), 0.0, 0.0))
    cam = bpy.context.active_object
    cam.data.lens = 50.0
    scene.camera = cam

    monde = bpy.data.worlds.new("W")
    scene.world = monde
    bg = monde.node_tree.nodes.get("Background")
    hdri = os.path.normpath(os.path.join(r"C:\dev\Tuple_3D", "00_references",
                                          "hdri", "studio_small_09_4k.hdr"))
    if os.path.exists(hdri):
        env = monde.node_tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri, check_existing=True)
        monde.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.35
    else:
        raise RuntimeError(
            "HDRI absent : %s — sans lui les surfaces brillantes n'ont rien a "
            "refleter et tous les candidats se ressembleraient." % hdri)
    return scene


SEUIL_ECRETAGE = 0.08


def _garde_ecretage(chemin, etiquette):
    """Refuse une image dont trop de pixels touchent le blanc.

    Un banc de comparaison n'a de valeur que s'il rapporte des DIFFERENCES.
    Au-dela de quelques pour cent d'ecretage, les candidats les plus clairs se
    rejoignent tous sur 1,0 et la planche fait croire qu'ils se ressemblent
    alors que c'est le capteur qui est sature. Vecu ici a 28 puis 52 %.
    """
    # Lecture par bpy, PAS par PIL : le Python embarque de Blender porte numpy
    # mais pas Pillow, et le premier jet de ce garde s'est desactive tout seul
    # sur un ImportError — un garde qui se tait quand il ne peut pas mesurer ne
    # garde rien du tout.
    import numpy as np
    img = bpy.data.images.load(chemin, check_existing=False)
    try:
        buf = np.empty(len(img.pixels), dtype=np.float32)
        img.pixels.foreach_get(buf)
    finally:
        bpy.data.images.remove(img)
    rgba = buf.reshape(-1, 4)
    # Les pixels de bpy sont LINEAIRES ; le seuil vise l'image affichee, donc
    # on repasse en sRGB avant de comparer.
    lin = 0.2126 * rgba[:, 0] + 0.7152 * rgba[:, 1] + 0.0722 * rgba[:, 2]
    lum = np.where(lin <= 0.0031308, lin * 12.92,
                   1.055 * np.power(np.clip(lin, 1e-8, None), 1 / 2.4) - 0.055)
    part = float((lum > 0.98).mean())
    if part > SEUIL_ECRETAGE:
        log("!! %s : %.1f %% de pixels ecretes (seuil %.0f %%) — baisser les "
            "sources, cette image ne peut rien departager"
            % (etiquette, 100 * part, 100 * SEUIL_ECRETAGE))
    else:
        log("   %s : %.1f %% d'ecretage, mediane %.3f"
            % (etiquette, 100 * part, float(np.median(lum))))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    cycles = "--cycles" in argv
    seul = None
    if "--only" in argv:
        seul = argv[argv.index("--only") + 1]
    emission = None
    if "--emission" in argv:
        emission = float(argv[argv.index("--emission") + 1])
    gaps = None
    if "--gap" in argv:
        gaps = [float(v) / 1000.0 for v in argv[argv.index("--gap") + 1].split(",")]

    out = os.path.join(_HERE, "renders", "shell_lab")
    os.makedirs(out, exist_ok=True)

    noms = seul.split(",") if seul else list(CANDIDATS)
    inconnus = [n for n in noms if n not in CANDIDATS]
    if inconnus:
        raise SystemExit("candidat inconnu : %s ; connus : %s"
                         % (inconnus, list(CANDIDATS)))

    paires = ([(n, g) for n in noms for g in gaps] if gaps
              else [(n, None) for n in noms])
    for nom, gap in paires:
        scene = batir_scene("MAT_lab_" + nom, CANDIDATS[nom], gap=gap,
                            emission=emission)
        scene.render.resolution_x = 900
        scene.render.resolution_y = 560
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.view_settings.view_transform = "Standard"
        # CYCLES OBLIGATOIRE, et ce n'est pas un choix de qualite.
        #
        # Le premier jet de ce banc rendait en Eevee « pour aller vite », et son
        # temoin l'a pris en flagrant delit : le candidat `poli`, du verre
        # optique a rugosite 0,02, devait montrer la carte parfaitement nette et
        # rendait un aplat gris. Eevee ne calcule pas la transmission sans
        # refraction en espace ecran activee par materiau, donc AUCUN des quatre
        # candidats ne montrait ce qu'il y a derriere — c'est-a-dire la seule
        # chose que ce banc doit juger.
        #
        # Le gain de vitesse vient donc d'ailleurs : resolution reduite, peu de
        # samples, et surtout une scene a cinq objets au lieu de 486.
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 64 if not cycles else 256
        proto.pick_gpu()
        etiquette = nom if gap is None else "%s_g%03d" % (nom, round(gap * 1000 * 10))
        scene.render.filepath = os.path.join(out, "lab_%s" % etiquette)
        bpy.ops.render.render(write_still=True)
        ecrit = scene.render.filepath + ".png"
        log("%-10s -> %s (existe=%s)" % (etiquette, ecrit, os.path.exists(ecrit)))
        _garde_ecretage(ecrit, etiquette)


if __name__ == "__main__":
    main()
