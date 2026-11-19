"""Costruisce un personaggio completo in Blender: materiali, armatura, mesh con pesi e shape keys, driver del viso.

    from cartoon_character.character.builder import build
    ch = build('Ciuffo', 'default', collection)          # ch['rig'] = oggetto armatura, ch['meshes'] = dict di oggetti

Si possono costruire piu' personaggi nella stessa scena (nomi diversi, varianti di colore diverse): non condividono dati.
"""
import math
import bpy

from .. import config as C
from . import model as M
from . import facial as F
from . import rig as R


def srgb_to_lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def _principled(m):
    m.use_nodes = True
    return m.node_tree.nodes.get('Principled BSDF')


def _set(b, **kv):
    for k, v in kv.items():
        if k in b.inputs:
            b.inputs[k].default_value = v


def make_materials(prefix, variant):
    pal = {k: srgb_to_lin(C.hexrgb(v)) for k, v in C.VARIANTS[variant].items()}
    mats = {}

    def mat(key, col, rough=0.5, **kv):
        m = bpy.data.materials.new('%s_%s' % (prefix, key))
        b = _principled(m)
        _set(b, **{'Base Color': (*col, 1.0), 'Roughness': rough})
        _set(b, **kv)
        m.diffuse_color = (*col, 1.0)
        mats[key] = m
        return m

    mat('skin', pal['skin'], 0.52, **{'Specular IOR Level': 0.35, 'Coat Weight': 0.08, 'Coat Roughness': 0.4})
    mat('lid', pal['skin'], 0.52, **{'Specular IOR Level': 0.35})
    mat('nose', pal['skin_dark'], 0.42, **{'Specular IOR Level': 0.45})
    mat('curl', pal['curl'], 0.48, **{'Specular IOR Level': 0.4, 'Coat Weight': 0.15})
    mat('shirt', pal['shirt'], 0.78, **{'Specular IOR Level': 0.2, 'Sheen Weight': 0.35})
    mat('shorts', pal['shorts'], 0.82, **{'Specular IOR Level': 0.2, 'Sheen Weight': 0.3})
    mat('shoe', pal['shoe'], 0.5, **{'Coat Weight': 0.25, 'Coat Roughness': 0.3})
    mat('sole', pal['sole'], 0.6)
    mat('sclera', srgb_to_lin((0.98, 0.97, 0.95)), 0.12, **{'Coat Weight': 0.7, 'Coat Roughness': 0.05})
    mat('pupil', (0.004, 0.004, 0.006), 0.08, **{'Coat Weight': 1.0, 'Coat Roughness': 0.02})
    mat('brow', pal['brow'], 0.62)
    mat('lash', pal['brow'], 0.5)
    mat('mouth', srgb_to_lin(C.hexrgb('#3D0F17')), 0.6, **{'Specular IOR Level': 0.2})
    mat('tongue', srgb_to_lin(C.hexrgb('#FF6F86')), 0.4)
    mat('teeth', srgb_to_lin(C.hexrgb('#FFFCF2')), 0.28, **{'Coat Weight': 0.4})
    # iride: anello scuro al bordo, centro piu' chiaro (UV x = distanza dal centro)
    m = mat('iris', pal['iris'], 0.1, **{'Coat Weight': 1.0, 'Coat Roughness': 0.02})
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeUVMap'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(uv.outputs['UV'], sep.inputs[0]); nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    base = pal['iris']; light = tuple(min(1.0, c * 3.2 + 0.03) for c in base)
    ramp.color_ramp.elements[0].position = 0.35; ramp.color_ramp.elements[0].color = (*light, 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (base[0] * 0.25, base[1] * 0.25, base[2] * 0.25, 1)
    mid = ramp.color_ramp.elements.new(0.78); mid.color = (*base, 1)
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    # riflessi
    m = mat('shine', (1, 1, 1), 0.2)
    _set(m.node_tree.nodes['Principled BSDF'], **{'Emission Color': (1, 1, 1, 1), 'Emission Strength': 6.0})
    # rossore: trasparente sul bordo
    m = mat('blush', pal['blush'], 0.6)
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeUVMap'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(uv.outputs['UV'], sep.inputs[0]); nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.62, 0.62, 0.62, 1)
    ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
    nt.links.new(ramp.outputs['Color'], b.inputs['Alpha'])
    m.surface_render_method = 'DITHERED'
    return mats


def _mesh_object(name, data, mats, collection, arm_ob, preserve_volume=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in data['verts']], [], [tuple(f) for f in data['faces']])
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    # materiali per faccia
    keys = []
    for k in data.get('mat', []):
        if k not in keys:
            keys.append(k)
    for k in keys:
        me.materials.append(mats[k])
    if data.get('mat'):
        idx = [keys.index(k) for k in data['mat']]
        if len(idx) == len(me.polygons):
            me.polygons.foreach_set('material_index', idx)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    # UV (solo per iride, pupilla e rossore: frazione radiale)
    if 'uv' in data and len(data['uv']) == len(me.vertices):
        uvl = me.uv_layers.new(name='UVMap')
        loops_v = [0] * len(me.loops)
        me.loops.foreach_get('vertex_index', loops_v)
        flat = []
        for vi in loops_v:
            flat += list(data['uv'][vi])
        uvl.data.foreach_set('uv', flat)
    # normali verso l'esterno
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if data.get('ref') is not None:                 # superfici aperte: normali verso fuori rispetto al centro di riferimento
        from mathutils import Vector
        ref = Vector(data['ref'])
        tot = sum(f.normal.dot(f.calc_center_median() - ref) for f in bm.faces)
        if tot < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    # pesi
    groups = {}
    for i, w in enumerate(data['weights']):
        for bone, val in w.items():
            groups.setdefault(bone, []).append((i, val))
    for bone, lst in groups.items():
        vg = ob.vertex_groups.new(name=bone)
        for i, val in lst:
            vg.add([i], val, 'REPLACE')
    # shape keys
    if data.get('keys'):
        ob.shape_key_add(name='Basis', from_mix=False)
        for kname, kverts in data['keys'].items():
            sk = ob.shape_key_add(name=kname, from_mix=False)
            flat = []
            for v in kverts:
                flat += list(v)
            sk.data.foreach_set('co', flat)
    ob.parent = arm_ob
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm_ob
    mod.use_deform_preserve_volume = preserve_volume
    return ob


def build(name=C.NAME, variant='default', collection=None):
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    mats = make_materials(name, variant)
    arm = R.build_armature(name, collection)
    arm['cc_character'] = name
    arm['cc_variant'] = variant
    parts = M.body_parts()
    parts.update(F.face_parts())
    meshes = {}
    for pname, data in parts.items():
        pv = pname.split('.')[0] in ('arm', 'leg', 'curl')
        meshes[pname] = _mesh_object('%s_%s' % (name, pname), data, mats, collection, arm, preserve_volume=pv)
    # driver: proprieta' dell'osso «face» -> shape keys
    for pname, ob in meshes.items():
        sk = ob.data.shape_keys
        if not sk:
            continue
        for kb in sk.key_blocks[1:]:
            R._driver(sk, 'key_blocks["%s"].value' % kb.name, arm, 'pose.bones["face"]["%s"]' % kb.name)
    poles = R.calibrate_poles(arm)
    curl = R.curl_poses(arm)
    return dict(name=name, variant=variant, rig=arm, meshes=meshes, materials=mats, collection=collection, poles=poles,
                curl_poses=curl)
