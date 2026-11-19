"""Risorse comuni ai test: un solo personaggio costruito in una scena pulita, utilita' per le pose."""
import bpy
from mathutils import Quaternion

from .. import config as C

_CH = None
REPORT = {}


def character():
    global _CH
    if _CH is None:
        from ..automation import scene as S
        from ..automation.controller import Character
        S.reset()
        _CH = Character(C.NAME, 'default')
    return _CH


def reset_pose(rig):
    if rig.animation_data:
        rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    for k in C.FACE_PROPS:
        rig.pose.bones['face'][k] = 0.55 if k == 'pupil' else 0.0
    for k in ('ik_arm.L', 'ik_arm.R', 'ik_leg.L', 'ik_leg.R', 'eyes_track'):
        rig.pose.bones['root'][k] = 0.0
    bpy.context.view_layer.update()


def apply(rig, pose, props=None):
    for pb in rig.pose.bones:
        bp = pose.get(pb.name)
        if bp is None:
            pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
        else:
            pb.location = bp.loc; pb.rotation_quaternion = bp.rot; pb.scale = bp.scl
    if props:
        for k, v in props.items():
            rig.pose.bones['face'][k] = v
    bpy.context.view_layer.update()


def evaluated(rig):
    rig.update_tag()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return rig.evaluated_get(dg)
