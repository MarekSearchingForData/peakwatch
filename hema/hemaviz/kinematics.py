"""Jointed fencer model: poses, interpolation, inverse kinematics, hitboxes.

Coordinate frame (per fencer, "local"):
    x = forward (toward the opponent), y = up, z = the fencer's right.
    Units are metres and degrees.

A Pose only stores what a fencing instructor would describe -- where the
pelvis is, how the torso is turned/leaned, where the feet are, where the
sword hand is and which way the blade points. Elbows and knees are solved
with two-bone IK, so authored techniques stay short and readable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

# --- body dimensions (an average ~1.75 m adult) --------------------------
UPPER_ARM = 0.30
FOREARM = 0.29          # elbow -> hand centre
THIGH = 0.44
SHIN = 0.43
SPINE = 0.50            # pelvis -> base of neck
SHOULDER_HALF = 0.19
HIP_HALF = 0.10
NECK_TO_HEAD = 0.15
ANKLE_Y = 0.07

ARM_REACH = UPPER_ARM + FOREARM - 0.005


@dataclass(frozen=True)
class Weapon:
    key: str
    name: str
    blade: float        # crossguard -> tip (m)
    grip: float         # crossguard -> pommel (m)
    hand_sep: float     # distance between the two hands on the hilt (m)
    guard_half: float   # half width of the crossguard (m)
    nagel: bool = False  # Messer "nail" side-lug on the cross

    def as_dict(self) -> dict:
        return {"key": self.key, "name": self.name, "blade": self.blade,
                "grip": self.grip, "hand_sep": self.hand_sep,
                "guard_half": self.guard_half, "nagel": self.nagel}


LONGSWORD = Weapon("longsword", "Longsword", blade=0.95, grip=0.27,
                   hand_sep=0.15, guard_half=0.13)
KRIEGSMESSER = Weapon("messer", "Kriegsmesser", blade=0.80, grip=0.25,
                      hand_sep=0.12, guard_half=0.10, nagel=True)
WEAPONS = {w.key: w for w in (LONGSWORD, KRIEGSMESSER)}


def blade_dir(elev: float, az: float) -> np.ndarray:
    """Unit vector from elevation (deg above horizontal) and azimuth
    (deg; 0 = straight at the opponent, +90 = to the fencer's right)."""
    e, a = math.radians(elev), math.radians(az)
    return np.array([math.cos(e) * math.cos(a), math.sin(e),
                     math.cos(e) * math.sin(a)])


@dataclass(frozen=True)
class Pose:
    hip: tuple = (0.0, 0.90, 0.0)       # pelvis centre
    yaw: float = 0.0                     # + = right shoulder forward
    lean: float = 0.0                    # + = torso tilted forward
    lfoot: tuple = (0.30, -0.13)         # (x, z) on the ground
    rfoot: tuple = (-0.30, 0.13)
    grip: tuple = (0.45, 1.10, 0.10)     # front (sword) hand
    blade: tuple = (1.0, 0.3, 0.0)       # direction hand -> tip (any length)
    left_on: bool = True                 # second hand on the hilt

    def with_(self, **kw) -> "Pose":
        if "elev" in kw or "az" in kw:
            kw["blade"] = tuple(blade_dir(kw.pop("elev", 0.0), kw.pop("az", 0.0)))
        return replace(self, **kw)

    def shifted(self, dx: float = 0.0, dz: float = 0.0) -> "Pose":
        """Same pose translated along the ground (used to chain steps)."""
        h, g = self.hip, self.grip
        return replace(self,
                       hip=(h[0] + dx, h[1], h[2] + dz),
                       grip=(g[0] + dx, g[1], g[2] + dz),
                       lfoot=(self.lfoot[0] + dx, self.lfoot[1] + dz),
                       rfoot=(self.rfoot[0] + dx, self.rfoot[1] + dz))


def P(grip, elev, az, *, hip=(0.0, 0.90, 0.0), yaw=0.0, lean=0.0,
      lfoot=None, rfoot=None, left_on=True) -> Pose:
    """Compact pose constructor used by the technique library."""
    hx = hip[0]
    lf = lfoot if lfoot is not None else (hx + 0.30, hip[2] - 0.13)
    rf = rfoot if rfoot is not None else (hx - 0.30, hip[2] + 0.13)
    return Pose(hip=tuple(hip), yaw=yaw, lean=lean, lfoot=tuple(lf),
                rfoot=tuple(rf), grip=tuple(grip),
                blade=tuple(blade_dir(elev, az)), left_on=left_on)


# --- interpolation -------------------------------------------------------
def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def slerp(a: np.ndarray, b: np.ndarray, u: float) -> np.ndarray:
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    d = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if d > 0.9995:
        v = a + (b - a) * u
        return v / np.linalg.norm(v)
    if d < -0.9995:  # opposite: rotate through vertical
        mid = np.array([0.0, 1.0, 0.0])
        return slerp(a, mid, u * 2) if u < 0.5 else slerp(mid, b, u * 2 - 1)
    th = math.acos(d)
    s = math.sin(th)
    return (math.sin((1 - u) * th) * a + math.sin(u * th) * b) / s


def smooth(u: float) -> float:
    """Ease-in/out: actions accelerate then decelerate."""
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def lerp_pose(a: Pose, b: Pose, u: float) -> Pose:
    return Pose(
        hip=_lerp(a.hip, b.hip, u),
        yaw=a.yaw + (b.yaw - a.yaw) * u,
        lean=a.lean + (b.lean - a.lean) * u,
        lfoot=_lerp(a.lfoot, b.lfoot, u),
        rfoot=_lerp(a.rfoot, b.rfoot, u),
        grip=_lerp(a.grip, b.grip, u),
        blade=tuple(slerp(np.array(a.blade), np.array(b.blade), u)),
        left_on=b.left_on if u > 0.5 else a.left_on,
    )


@dataclass
class Segment:
    """Motion from a start pose through keyframes, over [t0, t1]."""
    t0: float
    t1: float
    start: Pose
    keys: list            # [(u, Pose)], u ascending, last u == 1
    ease: bool = True

    def at(self, t: float) -> tuple[Pose, dict]:
        span = max(self.t1 - self.t0, 1e-6)
        u = (t - self.t0) / span
        u = min(max(u, 0.0), 1.0)
        if self.ease:
            u = smooth(u)
        prev_u, prev = 0.0, self.start
        for ku, kp in self.keys:
            if u <= ku + 1e-9:
                local = 0.0 if ku - prev_u < 1e-9 else (u - prev_u) / (ku - prev_u)
                pose = lerp_pose(prev, kp, local)
                lift = {
                    "l": _foot_lift(prev.lfoot, kp.lfoot, local),
                    "r": _foot_lift(prev.rfoot, kp.rfoot, local),
                }
                return pose, lift
            prev_u, prev = ku, kp
        return self.keys[-1][1], {"l": 0.0, "r": 0.0}


def _foot_lift(a, b, u):
    travel = math.dist(a, b)
    if travel < 0.08:
        return 0.0
    return 0.10 * math.sin(math.pi * u) * min(1.0, travel / 0.3)


# --- skeleton -------------------------------------------------------------
def _rot_y(deg: float) -> np.ndarray:
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    # x' = x c + z s ; z' = -x s + z c   (+deg brings +z toward +x)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def two_bone(root, target, l1, l2, pole):
    root = np.asarray(root, float)
    target = np.asarray(target, float)
    d_vec = target - root
    d = float(np.linalg.norm(d_vec))
    d = min(max(d, abs(l1 - l2) + 1e-4), l1 + l2 - 1e-4)
    axis = d_vec / max(np.linalg.norm(d_vec), 1e-9)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    p = np.asarray(pole, float)
    p = p - axis * np.dot(p, axis)
    n = np.linalg.norm(p)
    if n < 1e-6:
        p = np.cross(axis, [0.0, 0.0, 1.0])
        n = np.linalg.norm(p) or 1.0
    p = p / n
    return root + axis * a + p * h


def _clamp_reach(shoulder, hand):
    v = hand - shoulder
    d = np.linalg.norm(v)
    if d > ARM_REACH:
        return shoulder + v * (ARM_REACH / d)
    return hand


def skeleton(pose: Pose, weapon: Weapon, lift: dict | None = None) -> dict:
    """Joint positions (local frame) + weapon points for one pose."""
    lift = lift or {"l": 0.0, "r": 0.0}
    hip = np.array(pose.hip, float)
    R = _rot_y(pose.yaw)
    Rp = _rot_y(pose.yaw * 0.5)
    fwd, right = R @ [1.0, 0, 0], R @ [0, 0, 1.0]
    lean = math.radians(pose.lean)
    up = math.cos(lean) * np.array([0.0, 1, 0]) + math.sin(lean) * fwd
    neck = hip + up * SPINE
    head = neck + up * NECK_TO_HEAD
    sh_r = neck - up * 0.03 + right * SHOULDER_HALF
    sh_l = neck - up * 0.03 - right * SHOULDER_HALF
    hp_r = hip + Rp @ [0, -0.03, HIP_HALF]
    hp_l = hip + Rp @ [0, -0.03, -HIP_HALF]

    d = np.array(pose.blade, float)
    d /= np.linalg.norm(d)
    hand_r = _clamp_reach(sh_r, np.array(pose.grip, float))
    if pose.left_on:
        hand_l = hand_r - d * weapon.hand_sep
        fixed = _clamp_reach(sh_l, hand_l)
        if not np.allclose(fixed, hand_l):
            shift = fixed - hand_l
            hand_r, hand_l = hand_r + shift, fixed
            hand_r = _clamp_reach(sh_r, hand_r)
            hand_l = hand_r - d * weapon.hand_sep
    else:
        hand_l = sh_l + np.array([0.05, -0.45, -0.10])

    pole_r = -up * 0.7 + right * 0.6 - fwd * 0.2
    pole_l = -up * 0.7 - right * 0.6 - fwd * 0.2
    el_r = two_bone(sh_r, hand_r, UPPER_ARM, FOREARM, pole_r)
    el_l = two_bone(sh_l, hand_l, UPPER_ARM, FOREARM, pole_l)

    an_l = np.array([pose.lfoot[0], ANKLE_Y + lift["l"], pose.lfoot[1]])
    an_r = np.array([pose.rfoot[0], ANKLE_Y + lift["r"], pose.rfoot[1]])
    leg_fwd = Rp @ [1.0, 0, 0]
    kn_l = two_bone(hp_l, an_l, THIGH, SHIN, leg_fwd - (Rp @ [0, 0, 0.3]))
    kn_r = two_bone(hp_r, an_r, THIGH, SHIN, leg_fwd + (Rp @ [0, 0, 0.3]))
    toe_l = an_l + np.array([leg_fwd[0] * 0.17, -0.05, leg_fwd[2] * 0.17])
    toe_r = an_r + np.array([leg_fwd[0] * 0.17, -0.05, leg_fwd[2] * 0.17])

    guard = hand_r + d * 0.055
    tip = guard + d * weapon.blade
    pommel = guard - d * weapon.grip

    return {
        "pelvis": hip, "neck": neck, "head": head,
        "sh_l": sh_l, "sh_r": sh_r, "el_l": el_l, "el_r": el_r,
        "hand_l": hand_l, "hand_r": hand_r,
        "hp_l": hp_l, "hp_r": hp_r, "kn_l": kn_l, "kn_r": kn_r,
        "an_l": an_l, "an_r": an_r, "toe_l": toe_l, "toe_r": toe_r,
        "guard": guard, "tip": tip, "pommel": pommel,
    }


# Hitboxes: (name, joint a, joint b, radius). a == b -> sphere.
HITBOXES = [
    ("head", "head", "head", 0.115),
    ("torso", "pelvis", "neck", 0.155),
    ("upper arm R", "sh_r", "el_r", 0.050),
    ("upper arm L", "sh_l", "el_l", 0.050),
    ("forearm R", "el_r", "hand_r", 0.045),
    ("forearm L", "el_l", "hand_l", 0.045),
    ("hand R", "hand_r", "hand_r", 0.050),
    ("hand L", "hand_l", "hand_l", 0.050),
    ("thigh R", "hp_r", "kn_r", 0.075),
    ("thigh L", "hp_l", "kn_l", 0.075),
    ("shin R", "kn_r", "an_r", 0.055),
    ("shin L", "kn_l", "an_l", 0.055),
]
HITBOX_NAMES = [h[0] for h in HITBOXES]


def to_world(local: dict, origin_x: float, facing: int) -> dict:
    """Place a local skeleton in the arena. facing=+1 looks down +x,
    facing=-1 is rotated 180 deg about the vertical axis."""
    out = {}
    for k, v in local.items():
        if facing == 1:
            out[k] = np.array([origin_x + v[0], v[1], v[2]])
        else:
            out[k] = np.array([origin_x - v[0], v[1], -v[2]])
    return out


def seg_seg(p1, q1, p2, q2):
    """Closest distance between segments p1q1 and p2q2.
    Returns (distance, s, t) with s, t the fractions along each segment."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = float(d1 @ d1), float(d2 @ d2), float(d2 @ r)
    eps = 1e-12
    if a <= eps and e <= eps:
        return float(np.linalg.norm(r)), 0.0, 0.0
    if a <= eps:
        s, t = 0.0, min(max(f / e, 0.0), 1.0)
    else:
        c = float(d1 @ r)
        if e <= eps:
            t, s = 0.0, min(max(-c / a, 0.0), 1.0)
        else:
            b = float(d1 @ d2)
            den = a * e - b * b
            s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > eps else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, min(max(-c / a, 0.0), 1.0)
            elif t > 1.0:
                t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    c1, c2 = p1 + d1 * s, p2 + d2 * t
    return float(np.linalg.norm(c1 - c2)), s, t
