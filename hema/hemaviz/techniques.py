"""Technique library: guards, phased techniques and matchups.

Each technique is a guard plus a list of phases. A phase is one action
you can time on its own (it names an action key from the timing store),
with one or more keyframes. Flags per phase:

    attack   the blade can score hits during this phase
    cover    the blade can displace an incoming blade (if it meets it
             with its strong against the other's weak -- Stärke/Schwäche)
    cont     continuation of the previous action (a displaced action stays
             "dead" through its continuations)

Poses are written in the fencer's own frame (x toward the opponent,
z to the fencer's right), with the opponent's pelvis ~2.4 m away.

The interpretations here are simplified study models, not reconstructions;
the source notes say where each idea comes from so you can go back to it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .kinematics import P, Pose


@dataclass
class Phase:
    name: str
    action: str                 # timing-store key
    keys: list                  # [(u, Pose)]
    attack: bool = False
    cover: bool = False
    cont: bool = False


@dataclass
class Technique:
    key: str
    name: str
    weapon: str                 # "longsword" | "messer"
    guard_name: str
    guard: Pose
    phases: list
    source: str
    summary: str
    tags: list = field(default_factory=list)

    @property
    def action_count(self) -> int:
        """Independent actions (continuations don't count as a new tempo)."""
        return sum(1 for p in self.phases if not p.cont)

    @property
    def blade_actions(self) -> int:
        """Independent actions that use the blade (cut, thrust, cover)."""
        return sum(1 for p in self.phases
                   if not p.cont and (p.attack or p.cover))


# ---------------------------------------------------------------- stances
def lf_fwd(hx, hz=0.0):
    """Left foot forward, right foot back."""
    return {"lfoot": (hx + 0.30, hz - 0.13), "rfoot": (hx - 0.30, hz + 0.15)}


def rf_fwd(hx, hz=0.0):
    """Right foot forward (after a passing step)."""
    return {"lfoot": (hx - 0.32, hz - 0.15), "rfoot": (hx + 0.30, hz + 0.13)}


# ------------------------------------------------------------------ guards
# Longsword (Lichtenauer / Meyer names)
VOM_TAG = P((0.05, 1.30, 0.24), 72, 165, yaw=-30, **lf_fwd(0.0))
PFLUG = P((0.30, 1.00, 0.14), 28, -6, yaw=-20, **lf_fwd(0.0))

# Messer (Lecküchner / Meyer dussack names)
ZORNHUT = P((0.02, 1.32, 0.25), 30, 170, yaw=-35, **lf_fwd(0.0))
STIER = P((0.25, 1.55, 0.22), 10, -12, yaw=-25, **lf_fwd(0.0))
EBER = P((0.30, 1.00, 0.14), 25, -6, yaw=-20, **lf_fwd(0.0))


def _stance(pose: Pose, hx: float) -> Pose:
    return pose.shifted(dx=hx)


# ============================================================ LONGSWORD
def _ls_oberhau_phases(start_hip: float) -> list:
    h0 = start_hip
    mid = P((h0 + 0.45, 1.62, 0.24), 72, 30, hip=(h0 + 0.30, 0.90, 0.02),
            yaw=-10, lfoot=(h0 + 0.30, -0.13), rfoot=(h0 + 0.20, 0.14), roll=-3)
    hit = P((h0 + 1.15, 1.36, 0.06), 8, 2, hip=(h0 + 0.65, 0.86, 0.0),
            yaw=20, lean=10, **rf_fwd(h0 + 0.65), roll=-52)
    follow = P((h0 + 1.00, 1.00, -0.18), -30, -35, hip=(h0 + 0.70, 0.85, 0.0),
               yaw=30, lean=12, **rf_fwd(h0 + 0.65), roll=-7)
    return [
        Phase("Oberhau", "ls.oberhau", [(0.45, mid), (1.0, hit)],
              attack=True, cover=True),
        Phase("follow-through", "ls.follow", [(1.0, follow)],
              attack=True, cont=True),
    ]


def _ls_approach(guard: Pose, dx=0.35, action="ls.approach") -> Phase:
    return Phase("step into distance", action, [(1.0, _stance(guard, dx))])


LS_ZORNHAU = Technique(
    key="ls_zornhau", name="Zornhau (Oberhau) from Vom Tag",
    weapon="longsword", guard_name="Vom Tag", guard=VOM_TAG,
    phases=[_ls_approach(VOM_TAG)] + _ls_oberhau_phases(0.35),
    source="Lichtenauer Zettel (Zornhau); Ringeck / Döbringer glosses; "
           "Meyer 1570 longsword cuts.",
    summary="The reference cut: a diagonal Oberhau from the right with a "
            "passing step, ending in Alber/Wechsel. One action. Its measured "
            "time is the default beat.",
    tags=["oberhau", "one action", "reference"],
)


def _ls_zwerch_phases(h0: float) -> list:
    mid = P((h0 + 0.30, 1.80, 0.25), 20, 110, hip=(h0 + 0.30, 0.89, 0.08),
            yaw=0, lfoot=(h0 + 0.30, -0.10), rfoot=(h0 + 0.20, 0.25), roll=71)
    hit = P((h0 + 0.95, 1.74, 0.18), -12, -15, hip=(h0 + 0.60, 0.87, 0.15),
            yaw=15, lean=6, **rf_fwd(h0 + 0.60, 0.15), roll=88)
    follow = P((h0 + 0.85, 1.55, -0.15), -15, -55, hip=(h0 + 0.62, 0.87, 0.15),
               yaw=25, lean=6, **rf_fwd(h0 + 0.60, 0.15), roll=88)
    return [
        Phase("Zwerchhau", "ls.zwerch", [(0.5, mid), (1.0, hit)],
              attack=True, cover=True),
        Phase("follow-through", "ls.follow", [(1.0, follow)],
              attack=True, cont=True),
    ]


LS_ZWERCH = Technique(
    key="ls_zwerch", name="Zwerchhau from Vom Tag",
    weapon="longsword", guard_name="Vom Tag", guard=VOM_TAG,
    phases=[_ls_approach(VOM_TAG)] + _ls_zwerch_phases(0.35),
    source="Lichtenauer: 'Zwerch benimmt, was vom Tag herkommt'; "
           "Ringeck gloss on the Zwerchhau.",
    summary="Horizontal cut with the hilt high over the head: the hilt and "
            "strong cover the head while the short edge strikes the left ear.",
    tags=["zwerch", "one action", "cover+strike"],
)


def _ls_thrust_phases(h0: float) -> list:
    hit = P((h0 + 1.10, 1.30, 0.02), 6, -2, hip=(h0 + 0.62, 0.85, 0.0),
            yaw=15, lean=14, **rf_fwd(h0 + 0.62), roll=-25)
    back = P((h0 + 0.80, 1.05, 0.12), 25, -6, hip=(h0 + 0.50, 0.88, 0.0),
             yaw=0, lean=5, **rf_fwd(h0 + 0.55), roll=-25)
    return [
        Phase("thrust", "ls.thrust", [(1.0, hit)], attack=True),
        Phase("recover to Pflug", "ls.follow", [(1.0, back)], cont=True),
    ]


LS_THRUST = Technique(
    key="ls_thrust", name="Thrust from Pflug",
    weapon="longsword", guard_name="Pflug", guard=PFLUG,
    phases=[_ls_approach(PFLUG)] + _ls_thrust_phases(0.35),
    source="Lichtenauer: Pflug as a thrusting guard; Meyer 1570 Langort.",
    summary="Point-first attack with a passing step. Fast and long, but the "
            "point is the weak of the blade -- it can be cut aside from above.",
    tags=["thrust", "one action", "reach"],
)

LS_WINDUP = Technique(
    key="ls_windup", name="Wind-up Oberhau (Pflug -> Vom Tag -> cut)",
    weapon="longsword", guard_name="Pflug", guard=PFLUG,
    phases=[
        _ls_approach(PFLUG),
        Phase("wind up to Vom Tag", "ls.windup",
              # lift forward and up, away from the belly, then back to the shoulder
              [(0.5, P((0.80, 1.30, 0.16), 62, 15, yaw=-25, **lf_fwd(0.35))),
               (1.0, _stance(VOM_TAG, 0.35))]),
    ] + _ls_oberhau_phases(0.35),
    source="Teaching counter-example: the 'two-tempo' cut that Nachreisen "
           "is built to punish (Ringeck gloss on Nachreisen).",
    summary="Same Oberhau, but started from a low guard so it needs a "
            "separate wind-up first. Two actions -- watch what that costs.",
    tags=["oberhau", "two actions", "telegraphed"],
)

# ================================================================ MESSER


def _messer_zornhau_phases(h0: float) -> list:
    mid = P((h0 + 0.40, 1.62, 0.26), 70, 40, hip=(h0 + 0.30, 0.90, 0.02),
            yaw=-12, lfoot=(h0 + 0.30, -0.13), rfoot=(h0 + 0.20, 0.14), roll=4)
    hit = P((h0 + 1.15, 1.40, 0.05), 6, 2, hip=(h0 + 0.68, 0.86, 0.0),
            yaw=22, lean=12, **rf_fwd(h0 + 0.68), roll=-69)
    follow = P((h0 + 1.00, 1.00, -0.18), -30, -35, hip=(h0 + 0.72, 0.85, 0.0),
               yaw=30, lean=12, **rf_fwd(h0 + 0.68), roll=-9)
    return [
        Phase("Zornhau", "messer.zornhau", [(0.45, mid), (1.0, hit)],
              attack=True, cover=True),
        Phase("follow-through", "messer.follow", [(1.0, follow)],
              attack=True, cont=True),
    ]


M_ZORNHAU = Technique(
    key="m_zornhau", name="Zornhau from Zornhut",
    weapon="messer", guard_name="Zornhut", guard=ZORNHUT,
    phases=[_ls_approach(ZORNHUT, action="messer.approach")]
    + _messer_zornhau_phases(0.35),
    source="Lecküchner, Kunst des Messerfechtens (1478/1482): Zornhau; "
           "Meyer 1570 dussack: Zornhut / Zornhau.",
    summary="Fighting the messer exactly like a longsword: same cut, same "
            "distance, ~15 cm less blade. Use it to see the reach gap.",
    tags=["oberhau", "one action", "longsword habits"],
)

_ZW_MID = P((0.18, 1.82, -0.05), 20, 95, hip=(0.20, 0.89, 0.09), yaw=-5,
            lfoot=(0.30, -0.08), rfoot=(0.18, 0.25), roll=113)
# hilt high in front of the head (catch his blade on the cross), short edge
# to his left ear, having sprung out to the right
_ZW_HIT = P((0.87, 1.74, -0.15), -10, 3, hip=(0.45, 0.87, 0.15), yaw=15,
            lean=10, **rf_fwd(0.45, 0.15), roll=119)
_ZW_FOLLOW = P((0.85, 1.45, -0.16), -15, -55, hip=(0.48, 0.87, 0.15), yaw=25,
               lean=10, **rf_fwd(0.45, 0.15), roll=119)

M_ZWERCH = Technique(
    key="m_zwerch", name="Zwerch against the Oberhau",
    weapon="messer", guard_name="Zornhut", guard=ZORNHUT,
    phases=[
        Phase("Zwerch (step out right)", "messer.zwerch",
              [(0.45, _ZW_MID), (1.0, _ZW_HIT)], attack=True, cover=True),
        Phase("follow-through", "messer.follow", [(1.0, _ZW_FOLLOW)],
              attack=True, cont=True),
    ],
    source="Lecküchner: Zwerchhau / Twerhau; same principle as Lichtenauer's "
           "Zwerch breaking Vom Tag.",
    summary="Hilt high, strong over your own head, strike the ear with the "
            "short edge while stepping off the line. One action that covers "
            "and hits -- if you start it in time.",
    tags=["zwerch", "one action", "cover+strike", "vs oberhau"],
)

_NR_HIT = P((1.32, 1.42, -0.04), -18, -16, hip=(0.82, 0.86, 0.0), yaw=22,
            lean=14, **rf_fwd(0.82), roll=30)
_NR_BACK = P((0.75, 1.20, 0.10), 10, -8, hip=(0.55, 0.88, 0.0), yaw=5,
             lean=5, **rf_fwd(0.55), roll=30)

M_NACHREISEN = Technique(
    key="m_nachreisen", name="Nachreisen to the hands",
    weapon="messer", guard_name="Eber", guard=EBER,
    phases=[
        Phase("chase the hands", "messer.nachreisen", [(1.0, _NR_HIT)],
              attack=True),
        Phase("get out / recover", "messer.follow", [(1.0, _NR_BACK)],
              cont=True),
    ],
    source="Lichtenauer: Nachreisen (traveling after); Meyer 1570 on "
           "cutting the hands as the nearest target with a short weapon.",
    summary="When he lifts his sword to wind up, cut his forearms -- the "
            "nearest target. Your short blade only has to reach his hands, "
            "not his head.",
    tags=["nachreisen", "one action", "hands", "vs wind-up"],
)

_CV_HANG = P((0.35, 1.70, -0.02), 35, -55, hip=(0.12, 0.89, 0.0), yaw=-10,
             lean=4, **lf_fwd(0.12))
_EL_MID = P((0.70, 1.75, 0.10), 30, -10, hip=(0.45, 0.88, 0.10), yaw=5,
            lean=8, lfoot=(0.42, -0.10), rfoot=(0.40, 0.25), roll=157)
_EL_HIT = P((1.05, 1.55, 0.05), -24, -8, hip=(0.80, 0.86, 0.10), yaw=20,
            lean=12, **rf_fwd(0.80, 0.10), roll=219)

M_HENGEN_EINLAUF = Technique(
    key="m_hengen_einlauf", name="Hanging cover, then run in (Einlaufen)",
    weapon="messer", guard_name="Stier", guard=STIER,
    phases=[
        Phase("hanging cover", "messer.cover", [(1.0, _CV_HANG)], cover=True),
        Phase("run in + short cut", "messer.einlauf",
              [(0.4, _EL_MID), (1.0, _EL_HIT)], attack=True),
    ],
    source="Lecküchner: Versetzen and Einlaufen; Meyer 1570 dussack: "
           "close in after the parry, where the longer weapon is a liability.",
    summary="Take his Oberhau on your strong in a hanging cover, then step "
            "in past his point. Two actions -- it only works if the cover is "
            "already up when his blade arrives.",
    tags=["versetzen", "two actions", "close range", "vs oberhau"],
)

DUMMY_LS = Technique(
    key="dummy_ls", name="Target dummy (longsword, Pflug)", weapon="longsword",
    guard_name="Pflug", guard=PFLUG, phases=[], source="-",
    summary="Stands still in Pflug. Use it to see what a technique reaches.",
    tags=["dummy"])
DUMMY_M = Technique(
    key="dummy_m", name="Target dummy (messer, Stier)", weapon="messer",
    guard_name="Stier", guard=STIER, phases=[], source="-",
    summary="Stands still in Stier. Use it to see what a technique reaches.",
    tags=["dummy"])

TECHNIQUES = {t.key: t for t in (DUMMY_LS, DUMMY_M, LS_ZORNHAU, LS_ZWERCH, LS_THRUST, LS_WINDUP,
                                 M_ZORNHAU, M_ZWERCH, M_NACHREISEN,
                                 M_HENGEN_EINLAUF)}


@dataclass
class Scenario:
    key: str
    name: str
    a: str                  # attacker technique key (starts at t = 0)
    b: str                  # responder technique key
    cue_phase: int          # B starts when A begins this phase ...
    reaction_ms: float      # ... plus this delay
    lesson: str
    distance: float = 2.4   # pelvis to pelvis at the start (m)


SCENARIOS = [
    Scenario("mutual", "Mutual Zornhau: longsword vs messer", "ls_zornhau",
             "m_zornhau", 0, 0,
             "Both fencers cut on the same tempo with the same speed. The "
             "longsword's extra ~15 cm lands on the head first; the best the "
             "messer gets is an afterblow to the hands. This is fighting the "
             "messer like a longsword.", distance=3.6),
    Scenario("zwerch", "Zwerch against his Oberhau", "ls_zornhau", "m_zwerch",
             1, 0,
             "Spring out with the Zwerch the instant he cuts (Indes): his blade "
             "lands on your cross while your short edge takes his head. One "
             "action that covers and hits. Add even 50 ms of reaction and it "
             "fails -- you have to read the cut, not answer it.",
             distance=2.6),
    Scenario("nachreisen", "Nachreisen on a wind-up", "ls_windup",
             "m_nachreisen", 1, 120,
             "He winds up from Pflug (two actions). You go on his wind-up "
             "and cut the hands. A one-action answer to a two-action attack."),
    Scenario("einlauf", "Hanging cover + Einlaufen", "ls_zornhau",
             "m_hengen_einlauf", 1, 60,
             "Cover his Oberhau with your strong, then run in where his "
             "longer blade can't follow. Cover must be up before his "
             "blade arrives."),
    Scenario("thrust", "Messer Zornhau vs longsword thrust", "ls_thrust",
             "m_zornhau", 0, 0,
             "Both go at once. His point travels the shortest line and has "
             "more reach, so it lands first. The Zornhau only breaks a thrust "
             "when your strong meets his weak -- try the speed sliders to "
             "find out how much faster you would need to be.",
             distance=3.0),
]
SCENARIO_BY_KEY = {s.key: s for s in SCENARIOS}


# ---------------------------------------------------------- guard presets
OCHS = P((0.22, 1.58, 0.22), 12, -14, yaw=-25, **lf_fwd(0.0))
ALBER = P((0.35, 0.85, 0.05), -35, -2, yaw=-15, **lf_fwd(0.0))
LANGORT = P((0.62, 1.30, 0.02), 4, -2, yaw=10, lean=6, **lf_fwd(0.0))
LUGINSLAND = P((0.10, 1.78, 0.18), 78, 170, yaw=-25, **lf_fwd(0.0))
WECHSEL = P((0.12, 0.92, 0.26), -35, 150, yaw=-35, **lf_fwd(0.0))

GUARDS = {
    "longsword": {"Vom Tag": VOM_TAG, "Ochs": OCHS, "Pflug": PFLUG,
                  "Alber": ALBER, "Langort": LANGORT},
    "messer": {"Zornhut": ZORNHUT, "Stier": STIER, "Eber": EBER,
               "Luginsland": LUGINSLAND, "Wechsel": WECHSEL},
}
