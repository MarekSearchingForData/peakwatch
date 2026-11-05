"""Seed library: the hand-written techniques turned into Studio data.

The Studio stores everything as keyframes on a beat timeline. These seeds
give you editable starting points: five matchups and every technique as a
reusable move. After that, the library is yours; nothing here overwrites
saved work.
"""
from __future__ import annotations

from .techniques import GUARDS, SCENARIOS, TECHNIQUES, Technique
from .timings import DEFAULT_ACTIONS

SEED_BEAT_MS = 360.0

STRENGTH = {"ls.oberhau": 0.75, "messer.zornhau": 0.75, "ls.zwerch": 0.6,
            "messer.zwerch": 0.6, "messer.cover": 0.7, "ls.thrust": 0.45,
            "messer.nachreisen": 0.5, "messer.einlauf": 0.6}


def _ms(action: str) -> float:
    return float(DEFAULT_ACTIONS[action][2])


class _Ids:
    def __init__(self, prefix: str):
        self.prefix, self.n = prefix, 0

    def __call__(self) -> str:
        self.n += 1
        return f"{self.prefix}{self.n}"


def _track(tech: Technique, start_ms: float, kid: _Ids, aid: _Ids,
           fencer: int | None):
    """Keys and actions for one technique starting at start_ms."""
    keys = [{"id": kid(), "at": 0.0, "pose": tech.guard.to_dict()}]
    if start_ms > 0:
        keys.append({"id": kid(), "at": start_ms / SEED_BEAT_MS,
                     "pose": tech.guard.to_dict()})
    actions = []
    t = start_ms
    for ph in tech.phases:
        t += _ms(ph.action)
        prev = keys[-1]["id"]
        for u, pose in ph.keys[:-1]:   # intermediate keyframes
            frac = u  # the engine eases over the whole action
            keys.append({"id": kid(), "at": (t - _ms(ph.action) * (1 - frac))
                         / SEED_BEAT_MS, "pose": pose.to_dict()})
        keys.append({"id": kid(), "at": t / SEED_BEAT_MS,
                     "pose": ph.keys[-1][1].to_dict()})
        act = {"id": aid(), "from": prev, "to": keys[-1]["id"],
               "name": ph.name, "strength": STRENGTH.get(ph.action, 0.5),
               "pace": 1.0, "attack": ph.attack, "cover": ph.cover,
               "cont": ph.cont, "measure": ph.action}
        if fencer is not None:
            act["fencer"] = fencer
        actions.append(act)
    for k in keys:
        k["at"] = round(k["at"], 4)
    return keys, actions


def seed_exchanges() -> list:
    out = []
    for s in SCENARIOS:
        ta, tb = TECHNIQUES[s.a], TECHNIQUES[s.b]
        kid, aid = _Ids("k"), _Ids("a")
        ka, aa = _track(ta, 0.0, kid, aid, 0)
        cue = sum(_ms(p.action) for p in ta.phases[:s.cue_phase])
        kb, ab = _track(tb, cue + s.reaction_ms, kid, aid, 1)
        out.append({
            "id": f"seed-{s.key}", "name": s.name, "notes": s.lesson,
            "beat_ms": SEED_BEAT_MS, "distance": s.distance,
            "fencers": [{"weapon": ta.weapon, "label": "A"},
                        {"weapon": tb.weapon, "label": "B"}],
            "tracks": [{"keys": ka}, {"keys": kb}],
            "actions": aa + ab,
        })
    return out


def seed_moves() -> list:
    out = []
    for t in TECHNIQUES.values():
        if not t.phases:
            continue
        keys, actions = _track(t, 0.0, _Ids("k"), _Ids("a"), None)
        out.append({"id": f"seed-{t.key}", "name": t.name, "weapon": t.weapon,
                    "source": t.source, "summary": t.summary,
                    "keys": keys, "actions": actions})
    return out


def seed_guards() -> dict:
    return {w: {name: p.to_dict() for name, p in g.items()}
            for w, g in GUARDS.items()}


def seed_library() -> dict:
    return {"version": 1, "exchanges": seed_exchanges(),
            "moves": seed_moves()}
