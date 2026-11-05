"""Exchange simulator.

Runs two techniques against each other on a 1 ms clock with phase lengths
taken from your measured timings, then reports:

* hits    -- an attacking blade's cutting part touching an opponent hitbox
* binds   -- blade-on-blade contact
* displacements -- at contact, a covering blade meeting the other blade
  with its strong (closer to the hilt) against the other's weak knocks the
  weaker blade off line; that action can no longer score.

Outcomes are therefore not scripted: slow a counter down in the Timing Lab
and the attacker's blade arrives before the cover is up.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .kinematics import (HITBOXES, Pose, Segment, Weapon, WEAPONS, seg_seg,
                         skeleton, to_world)
from .techniques import TECHNIQUES, Technique

JOINTS = ["pelvis", "neck", "head", "sh_l", "sh_r", "el_l", "el_r", "hand_l",
          "hand_r", "hp_l", "hp_r", "kn_l", "kn_r", "an_l", "an_r", "toe_l",
          "toe_r", "guard", "tip", "pommel"]
JOINT_INDEX = {j: i for i, j in enumerate(JOINTS)}

BLADE_HIT_FROM = 0.12     # cutting part starts this far up the blade
BLADE_HALF = 0.012        # blade half-thickness for hit tests
BIND_DIST = 0.03          # blade-on-blade contact distance
LEVERAGE_MARGIN = 0.08    # strong must beat weak by this fraction


@dataclass
class Event:
    t: float
    kind: str               # hit | bind | displace
    by: int                 # fencer index (0 = A, 1 = B)
    on: int | None = None
    part: str | None = None
    point: tuple | None = None
    note: str = ""


@dataclass
class Fencer:
    tech: Technique
    weapon: Weapon
    origin: float
    facing: int
    durations: dict
    speed: float = 1.0
    start: float | None = None
    phase: int = -1                     # -1 = waiting in guard
    seg: Segment | None = None
    suppressed: bool = False            # displaced -> no hits
    landed: bool = False                # this action already scored
    finished: bool = False
    phase_log: list = field(default_factory=list)   # (name, t0, t1, action)
    first_hit: Event | None = None

    def __post_init__(self):
        self.finished = not self.tech.phases   # a dummy just stands there

    def pose_at(self, t: float) -> tuple[Pose, dict]:
        if self.seg is None:
            return self.tech.guard, {"l": 0.0, "r": 0.0}
        return self.seg.at(t)

    def phase_obj(self):
        if 0 <= self.phase < len(self.tech.phases):
            return self.tech.phases[self.phase]
        return None

    def can_hit(self) -> bool:
        ph = self.phase_obj()
        return bool(ph and ph.attack and not self.suppressed
                    and not self.landed)

    def can_cover(self) -> bool:
        ph = self.phase_obj()
        return bool(ph and ph.cover and not self.suppressed)

    def duration_of(self, ph) -> float:
        return self.durations[ph.action] * self.speed

    def advance(self, t: float, current: Pose) -> bool:
        """Enter the next phase if due. Returns True if a phase started."""
        if self.finished or self.start is None or t + 1e-9 < self.start:
            return False
        if self.seg is not None and t + 1e-9 < self.seg.t1:
            return False
        nxt = self.phase + 1
        if nxt >= len(self.tech.phases):
            self.finished = True
            return False
        ph = self.tech.phases[nxt]
        t0 = self.start if self.seg is None else self.seg.t1
        dur = self.duration_of(ph)
        self.phase = nxt
        self.seg = Segment(t0, t0 + dur, current, list(ph.keys))
        if not ph.cont:
            self.suppressed = False
            self.landed = False
        kind = ("both" if ph.attack and ph.cover else "attack" if ph.attack
                else "cover" if ph.cover else "idle")
        self.phase_log.append([ph.name, t0, t0 + dur, ph.action, kind])
        return True

    def displace(self, t: float, current: Pose, push_local: np.ndarray,
                 hard: bool) -> None:
        """Knock this fencer's blade off line from time t."""
        end = self.seg.keys[-1][1]
        d = np.array(current.blade)
        if hard:
            d = d + push_local * 1.1 + np.array([0.0, -0.35, 0.0])
            grip = np.array(current.grip) + push_local * 0.10
        else:   # crossed in the bind: both stop where they meet
            grip = np.array(current.grip)
        d = d / np.linalg.norm(d)
        new_end = end.with_(grip=tuple(grip), blade=tuple(d))
        t1 = max(self.seg.t1, t + 0.15)
        self.seg = Segment(t, t1, current, [(1.0, new_end)])
        self.phase_log[-1][2] = t1
        self.suppressed = True


def cross_ends(guard: np.ndarray, tip: np.ndarray, half: float):
    """Crossguard bar endpoints (perpendicular to the blade, ~horizontal).
    The viewer draws the cross with the same rule."""
    d = tip - guard
    d = d / (np.linalg.norm(d) or 1.0)
    ax = np.cross(d, [0.0, 1.0, 0.0])
    if np.linalg.norm(ax) < 0.2:
        ax = np.array([0.0, 0.0, 1.0])
    ax = ax / np.linalg.norm(ax)
    return guard - ax * half, guard + ax * half


def _blade_contact(sk, F):
    """Closest weapon-on-weapon contact under BIND_DIST, or None.

    Returns (frac_a, frac_b, point_a, point_b); a contact on the crossguard
    counts as fraction 0 -- the strongest place to catch a blade."""
    a_g, a_t = sk[0]["guard"], sk[0]["tip"]
    b_g, b_t = sk[1]["guard"], sk[1]["tip"]
    best = None
    d, sa, sb = seg_seg(a_g, a_t, b_g, b_t)
    if d < BIND_DIST:
        best = (d, sa, sb, a_g + (a_t - a_g) * sa, b_g + (b_t - b_g) * sb)
    ca0, ca1 = cross_ends(a_g, a_t, F[0].weapon.guard_half)
    cb0, cb1 = cross_ends(b_g, b_t, F[1].weapon.guard_half)
    d, s, u = seg_seg(ca0, ca1, b_g, b_t)      # A's cross vs B's blade
    if d < BIND_DIST and (best is None or d < best[0]):
        best = (d, 0.0, u, ca0 + (ca1 - ca0) * s, b_g + (b_t - b_g) * u)
    d, s, u = seg_seg(a_g, a_t, cb0, cb1)      # A's blade vs B's cross
    if d < BIND_DIST and (best is None or d < best[0]):
        best = (d, s, 0.0, a_g + (a_t - a_g) * s, cb0 + (cb1 - cb0) * u)
    return None if best is None else best[1:]


def _local_vec(v: np.ndarray, facing: int) -> np.ndarray:
    return v.copy() if facing == 1 else np.array([-v[0], v[1], -v[2]])


@dataclass
class Result:
    frames: list
    events: list
    phases: list            # per fencer: [[name, t0, t1, action], ...]
    duration: float
    first_hit: list         # per fencer: Event | None
    verdict: str
    detail: str

    def to_json(self) -> dict:
        return {
            "joints": JOINTS,
            "frames": self.frames,
            "events": [e.__dict__ for e in self.events],
            "phases": self.phases,
            "duration": self.duration,
            "verdict": self.verdict,
            "detail": self.detail,
        }


def simulate(tech_a: str, tech_b: str, durations: dict, *, cue_phase: int = 0,
             reaction_ms: float = 150.0, distance: float = 2.4,
             speed_a: float = 1.0, speed_b: float = 1.0,
             weapons: dict | None = None, double_window_ms: float = 150.0,
             dt: float = 0.001, fps: int = 60, tail: float = 0.45,
             max_t: float = 4.0) -> Result:
    weapons = weapons or WEAPONS
    ta, tb = TECHNIQUES[tech_a], TECHNIQUES[tech_b]
    F = [
        Fencer(ta, weapons[ta.weapon], 0.0, 1, durations, speed_a, start=0.0),
        Fencer(tb, weapons[tb.weapon], distance, -1, durations, speed_b),
    ]
    cue_phase = min(max(cue_phase, 0), len(ta.phases) - 1)
    events: list[Event] = []
    frames: list = []
    hit_parts = [set(), set()]
    last_contact = -1.0
    frame_every = max(1, round(1.0 / (fps * dt)))
    end_t = None
    step = 0
    t = 0.0

    while t <= max_t:
        poses = []
        for f in F:
            pose, _ = f.pose_at(t)
            if f.advance(t, pose):
                pose, _ = f.pose_at(t)
            poses.append(pose)
        # B's cue: A entered the cue phase
        if F[1].start is None and F[0].phase >= cue_phase and F[0].seg:
            cue_t = F[0].phase_log[cue_phase][1]
            F[1].start = cue_t + reaction_ms / 1000.0
            if t + 1e-9 >= F[1].start:
                F[1].advance(t, poses[1])

        sk = []
        lifts = []
        for f in F:
            pose, lift = f.pose_at(t)
            lifts.append(lift)
            sk.append(to_world(skeleton(pose, f.weapon, lift), f.origin, f.facing))
        poses = [f.pose_at(t)[0] for f in F]

        # --- blade on blade -------------------------------------------
        contact = _blade_contact(sk, F) if t - last_contact > 0.25 else None
        if contact is not None:
            last_contact = t
            sa, sb, pa, pb = contact
            point = tuple(np.round((pa + pb) / 2, 3))
            cover = [F[0].can_cover(), F[1].can_cover()]
            frac = [sa, sb]
            winner = None
            for i, j in ((0, 1), (1, 0)):
                if cover[i] and frac[i] + LEVERAGE_MARGIN < frac[j]:
                    winner = i
            if winner is not None:
                loser = 1 - winner
                n = (pa - pb) if loser == 0 else (pb - pa)
                n = n / (np.linalg.norm(n) or 1.0)
                F[loser].displace(t, poses[loser],
                                  _local_vec(n, F[loser].facing), hard=True)
                events.append(Event(t, "displace", winner, loser, None, point,
                                    f"strong ({frac[winner]:.0%} up the blade) "
                                    f"on weak ({frac[loser]:.0%})"))
            elif cover[0] and cover[1]:
                for i in (0, 1):
                    F[i].displace(t, poses[i], np.zeros(3), hard=False)
                events.append(Event(t, "bind", 0, 1, None, point,
                                    f"crossed at {sa:.0%} / {sb:.0%} - "
                                    "neither has leverage"))
            else:
                events.append(Event(t, "bind", 0, 1, None, point,
                                    f"blades touch at {sa:.0%} / {sb:.0%}"))

        # --- hits ------------------------------------------------------
        for i in (0, 1):
            j = 1 - i
            f = F[i]
            if not f.can_hit():
                continue
            g, tip = sk[i]["guard"], sk[i]["tip"]
            cut_from = g + (tip - g) * BLADE_HIT_FROM
            mid = (cut_from + tip) / 2
            if np.linalg.norm(mid - sk[j]["pelvis"]) > f.weapon.blade + 1.3:
                continue
            for name, ja, jb, r in HITBOXES:
                if name in hit_parts[j]:
                    continue
                d, s, _ = seg_seg(cut_from, tip, sk[j][ja], sk[j][jb])
                if d < r + BLADE_HALF:
                    hit_parts[j].add(name)
                    p = cut_from + (tip - cut_from) * s
                    ev = Event(t, "hit", i, j, name, tuple(np.round(p, 3)))
                    events.append(ev)
                    if f.first_hit is None:
                        f.first_hit = ev
                    f.landed = True     # the blade stops in the target
                    break

        if step % frame_every == 0:
            frames.append({
                "t": round(t, 4),
                "p": [[[round(float(c), 3) for c in sk[k][jn]] for jn in JOINTS]
                      for k in (0, 1)],
                "ph": [f.phase_obj().name if f.phase_obj() and not f.finished
                       else ("guard" if f.phase < 0 else "done") for f in F],
            })

        if end_t is None and all(f.finished for f in F):
            end_t = t + tail
        if end_t is not None and t >= end_t:
            break
        step += 1
        t = step * dt

    verdict, detail = _verdict(F, double_window_ms)
    return Result(frames, events, [f.phase_log for f in F], t,
                  [f.first_hit for f in F], verdict, detail)


NAMES = ["A", "B"]


def _verdict(F, window_ms: float) -> tuple[str, str]:
    ha, hb = F[0].first_hit, F[1].first_hit
    if ha is None and hb is None:
        return "No hit", "Nobody landed. Look at the binds and displacements."
    if ha and hb:
        gap = (hb.t - ha.t) * 1000
        first, second = (0, 1) if gap >= 0 else (1, 0)
        h1 = F[first].first_hit
        if abs(gap) <= window_ms:
            return ("Double hit",
                    f"{NAMES[first]} hit {h1.part} first, but {NAMES[second]} "
                    f"answered {abs(gap):.0f} ms later -- inside the "
                    f"{window_ms:.0f} ms double-hit window.")
        return (f"{NAMES[first]} wins (afterblow too late)",
                f"{NAMES[first]} hit {h1.part} {abs(gap):.0f} ms before "
                f"{NAMES[second]}'s answer.")
    win = 0 if ha else 1
    h = F[win].first_hit
    return (f"{NAMES[win]} wins clean",
            f"{NAMES[win]} hit the {h.part} at {h.t * 1000:.0f} ms; "
            f"{NAMES[1 - win]} never landed.")
