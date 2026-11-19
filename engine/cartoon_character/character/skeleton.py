"""Scheletro in Python puro (mathutils): cinematica diretta identica a quella di Blender e IK analitico a due ossa.

Serve alla pipeline per calcolare pose, appoggi dei piedi, mira della testa e collisioni senza passare dal depsgraph:
e' veloce, deterministico e verificabile (tests/test_rig.py confronta la cinematica con quella di Blender).
"""
import math
from mathutils import Vector, Matrix, Quaternion, Euler

I4 = Matrix.Identity(4)


class BonePose:
    __slots__ = ('loc', 'rot', 'scl')

    def __init__(self, loc=None, rot=None, scl=None):
        self.loc = Vector(loc) if loc is not None else Vector((0.0, 0.0, 0.0))
        self.rot = Quaternion(rot) if rot is not None else Quaternion()
        self.scl = Vector(scl) if scl is not None else Vector((1.0, 1.0, 1.0))

    def copy(self):
        return BonePose(self.loc.copy(), self.rot.copy(), self.scl.copy())

    def matrix(self):
        S = Matrix.Diagonal((*self.scl, 1.0))
        return Matrix.Translation(self.loc) @ self.rot.to_matrix().to_4x4() @ S

    def is_identity(self, eps=1e-6):
        return (self.loc.length < eps and abs(abs(self.rot.w) - 1.0) < eps and (self.scl - Vector((1, 1, 1))).length < eps)


def euler_q(deg, order='XYZ'):
    return Euler([math.radians(a) for a in deg], order).to_quaternion()


def mirror_euler(deg):
    """valori scritti «come se fossero il lato sinistro» -> valori per il lato destro."""
    return (deg[0], -deg[1], -deg[2])


def mirror_name(n):
    if n.endswith('.L'):
        return n[:-2] + '.R'
    if n.endswith('.R'):
        return n[:-2] + '.L'
    return n


def mirror_quat(q):
    """specchia una rotazione locale tra ossa simmetriche costruite come in rig.py: (w, x, y, z) -> (w, x, -y, -z)."""
    return Quaternion((q.w, q.x, -q.y, -q.z))


def slerp(a, b, t):
    if a.dot(b) < 0:
        b = -b
    return a.slerp(b, t)


class Skeleton:
    def __init__(self, names, parent, rest, length, inherit):
        self.names = list(names)
        self.parent = dict(parent)
        self.rest = {n: Matrix(rest[n]) for n in names}
        self.length = dict(length)
        self.inherit = dict(inherit)
        self.rest_inv = {n: self.rest[n].inverted() for n in names}
        self.offs = {}
        for n in names:
            p = self.parent[n]
            self.offs[n] = self.rest_inv[p] @ self.rest[n] if p else self.rest[n].copy()
        self.children = {n: [] for n in names}
        for n in names:
            if self.parent[n]:
                self.children[self.parent[n]].append(n)
        self._hinge = {}

    # ---------------------------------------------------------------- creazione e salvataggio
    @classmethod
    def from_armature(cls, ob):
        bones = ob.data.bones
        order = []

        def visit(b):
            order.append(b.name)
            for c in b.children:
                visit(c)
        for b in bones:
            if b.parent is None:
                visit(b)
        return cls(order, {b.name: (b.parent.name if b.parent else None) for b in bones},
                   {b.name: b.matrix_local.copy() for b in bones}, {b.name: b.length for b in bones},
                   {b.name: b.inherit_scale for b in bones})

    def to_dict(self):
        return dict(names=self.names, parent=self.parent, length=self.length, inherit=self.inherit,
                    rest={n: [list(r) for r in self.rest[n]] for n in self.names})

    @classmethod
    def from_dict(cls, d):
        return cls(d['names'], d['parent'], {n: Matrix(d['rest'][n]) for n in d['names']}, d['length'], d['inherit'])

    # ---------------------------------------------------------------- cinematica diretta
    def base_matrix(self, n, mats):
        p = self.parent[n]
        if p is None:
            return self.rest[n]
        Mp = mats[p]
        if self.inherit[n] in ('NONE', 'NONE_LEGACY'):
            full = Mp @ self.offs[n]
            rot = Mp.to_3x3().normalized() @ self.offs[n].to_3x3()
            M = rot.to_4x4(); M.translation = full.translation
            return M
        return Mp @ self.offs[n]

    def fk(self, pose, names=None):
        mats = {}
        for n in self.names:
            bp = pose.get(n)
            base = self.base_matrix(n, mats)
            mats[n] = base @ bp.matrix() if bp is not None else base.copy()
        return mats

    def head(self, mats, n):
        return mats[n].translation.copy()

    def tail(self, mats, n):
        return mats[n] @ Vector((0.0, self.length[n], 0.0))

    def axis(self, mats, n, k=1):
        return (mats[n].to_3x3() @ Vector([1.0 if i == k else 0.0 for i in range(3)])).normalized()

    # ---------------------------------------------------------------- orientamenti nel mondo
    def set_world_rotation(self, pose, n, R3, mats):
        """imposta la rotazione locale di n perche' il suo orientamento (spazio armatura) sia R3. Aggiorna mats[n]."""
        base = self.base_matrix(n, mats)
        brot = base.to_3x3().normalized()
        q = (brot.inverted() @ R3.normalized()).to_quaternion()
        bp = pose.get(n)
        if bp is None:
            bp = pose[n] = BonePose()
        bp.rot = q
        mats[n] = base @ bp.matrix()
        return q

    def update_subtree(self, pose, n, mats):
        stack = list(self.children[n])
        while stack:
            c = stack.pop()
            bp = pose.get(c)
            base = self.base_matrix(c, mats)
            mats[c] = base @ bp.matrix() if bp is not None else base.copy()
            stack.extend(self.children[c])

    # ---------------------------------------------------------------- IK analitico a due ossa
    def hinge_sign(self, upper, lower):
        key = (upper, lower)
        if key not in self._hinge:
            R1, R2 = self.rest[upper], self.rest[lower]
            y1 = (R1.to_3x3() @ Vector((0, 1, 0))).normalized()
            y2 = (R2.to_3x3() @ Vector((0, 1, 0))).normalized()
            n = y1.cross(y2)
            x1 = (R1.to_3x3() @ Vector((1, 0, 0))).normalized()
            self._hinge[key] = 1.0 if (n.length < 1e-9 or x1.dot(n) >= 0) else -1.0
        return self._hinge[key]

    def two_bone(self, pose, upper, lower, target, pole, mats, end=None, end_rot=None, soft=0.012):
        """porta la coda di `lower` su `target` piegando verso `pole` (punto). Scrive le rotazioni locali in pose.
        soft: avvicinamento morbido al limite di estensione (evita lo scatto del ginocchio tutto dritto)."""
        S = mats[upper].translation.copy()
        L1, L2 = self.length[upper], self.length[lower]
        sc1 = mats[upper].to_3x3().col[1].length            # scala lungo l'osso (squash & stretch)
        sc2 = mats[lower].to_3x3().col[1].length
        L1 *= sc1; L2 *= sc2
        T = Vector(target)
        d = T - S
        dist = max(1e-6, d.length)
        reach = L1 + L2
        lo = abs(L1 - L2) + 1e-4
        # estensione morbida: la distanza efficace non supera mai (reach - piccolo margine)
        if soft > 1e-9 and dist > reach - soft:
            x = dist - (reach - soft)
            dist_c = (reach - soft) + soft * (1 - math.exp(-x / soft))
        elif dist > reach * 0.9995:
            dist_c = reach * 0.9995
        else:
            dist_c = max(lo, dist)
        u = d / dist
        v = Vector(pole) - S
        v = v - u * v.dot(u)
        if v.length < 1e-6:
            v = self.tail(mats, upper) - S
            v = v - u * v.dot(u)
            if v.length < 1e-6:
                v = u.orthogonal()
        v.normalize()
        ca = (L1 * L1 + dist_c * dist_c - L2 * L2) / (2 * L1 * dist_c)
        a = math.acos(max(-1.0, min(1.0, ca)))
        E = S + (u * math.cos(a) + v * math.sin(a)) * L1
        T2 = S + u * dist_c
        y1 = (E - S).normalized(); y2 = (T2 - E).normalized()
        # normale del piano di piegatura dal polo (y1 x y2 = -s*d*(u x v)): stabile anche a gamba quasi tesa
        n = v.cross(u).normalized()
        sg = self.hinge_sign(upper, lower)
        x1 = n * sg
        z1 = x1.cross(y1).normalized(); x1 = y1.cross(z1).normalized()
        self.set_world_rotation(pose, upper, Matrix((x1, y1, z1)).transposed(), mats)
        z2 = x1.cross(y2).normalized(); x2 = y2.cross(z2).normalized()
        self.set_world_rotation(pose, lower, Matrix((x2, y2, z2)).transposed(), mats)
        if end:
            if end_rot is not None:
                self.set_world_rotation(pose, end, end_rot, mats)
            else:
                b = self.base_matrix(end, mats)
                bp = pose.get(end)
                mats[end] = b @ bp.matrix() if bp is not None else b.copy()
            self.update_subtree(pose, end, mats)
        return dist - dist_c          # quanto manca per arrivare (0 se raggiunto)

    def aim_bone(self, pose, n, direction, mats, up=None):
        """ruota n perche' il suo asse Y punti verso `direction` (spazio armatura), con rotazione minima."""
        base = self.base_matrix(n, mats)
        bp = pose.get(n) or BonePose()
        cur = (base @ bp.matrix()).to_3x3()
        y = (cur @ Vector((0, 1, 0))).normalized()
        q = y.rotation_difference(Vector(direction).normalized())
        R = q.to_matrix() @ cur
        return self.set_world_rotation(pose, n, R, mats)
