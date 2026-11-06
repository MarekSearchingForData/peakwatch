"""Pose vocabulary shared with the Studio's JavaScript engine.

Fencer-local frame: x = toward the opponent, y = up, z = the fencer's
right. Metres and degrees. A Pose stores what an instructor would
describe (pelvis, torso turn/lean, feet, sword hand, blade direction);
the Studio solves elbows and knees with IK on the rigged figure's bones.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

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


LONGSWORD = Weapon("longsword", "Longsword (Feder)", blade=0.95, grip=0.29,
                   hand_sep=0.15, guard_half=0.135)
KRIEGSMESSER = Weapon("messer", "Kriegsmesser", blade=0.80, grip=0.28,
                      hand_sep=0.13, guard_half=0.10, nagel=True)
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
    roll: float = 0.0                    # edge turned about the blade (deg)

    def to_dict(self) -> dict:
        b = np.array(self.blade, float)
        b = b / np.linalg.norm(b)
        return {"hip": [round(v, 4) for v in self.hip], "yaw": self.yaw,
                "lean": self.lean, "lfoot": list(self.lfoot),
                "rfoot": list(self.rfoot), "grip": [round(v, 4) for v in self.grip],
                "blade": [round(float(v), 4) for v in b],
                "left_on": self.left_on, "roll": self.roll}

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
      lfoot=None, rfoot=None, left_on=True, roll=0.0) -> Pose:
    """Compact pose constructor used by the technique library."""
    hx = hip[0]
    lf = lfoot if lfoot is not None else (hx + 0.30, hip[2] - 0.13)
    rf = rfoot if rfoot is not None else (hx - 0.30, hip[2] + 0.13)
    return Pose(hip=tuple(hip), yaw=yaw, lean=lean, lfoot=tuple(lf),
                rfoot=tuple(rf), grip=tuple(grip),
                blade=tuple(blade_dir(elev, az)), left_on=left_on, roll=roll)
