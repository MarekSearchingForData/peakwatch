"""Optional measurements: how fast you really do an action.

The Studio's timing comes from what you record and how you set each
action's pace. Measurements only act as a reality check: an action linked
to a measured key is flagged when it is faster than you have ever done it.
"""
from __future__ import annotations

import json
import statistics
from copy import deepcopy
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parent.parent / "records" / "timings.json"

# Placeholder defaults (ms) -- rough club-level numbers, NOT measurements.
# Replace them with your own trials in the Timing Lab.
DEFAULT_ACTIONS = {
    "ls.approach":   ("Longsword: step into distance (gathering step)", "longsword", 380),
    "ls.oberhau":    ("Longsword: Oberhau/Zornhau from Vom Tag, passing step", "longsword", 360),
    "ls.zwerch":     ("Longsword: Zwerchhau from Vom Tag", "longsword", 390),
    "ls.windup":     ("Longsword: lift from Pflug to Vom Tag (wind-up)", "longsword", 260),
    "ls.thrust":     ("Longsword: thrust from Pflug, passing step", "longsword", 300),
    "ls.follow":     ("Longsword: follow-through after the cut", "longsword", 220),
    "messer.approach": ("Messer: step into distance", "messer", 380),
    "messer.zornhau":  ("Messer: Zornhau from Zornhut, passing step", "messer", 360),
    "messer.zwerch":   ("Messer: Zwerch with step out to the right", "messer", 325),
    "messer.cover":    ("Messer: hanging cover (Versetzen) from Stier", "messer", 240),
    "messer.einlauf":  ("Messer: run in (Einlaufen) + short cut to head", "messer", 320),
    "messer.nachreisen": ("Messer: Nachreisen - cut to rising forearms", "messer", 300),
    "messer.follow":   ("Messer: follow-through / recover", "messer", 200),
}


def default_store() -> dict:
    return {
        "beat_reference": "ls.oberhau",
        "actions": {
            k: {"label": lab, "weapon": w, "default_ms": ms, "trials_ms": []}
            for k, (lab, w, ms) in DEFAULT_ACTIONS.items()
        },
    }


def merge_defaults(store: dict) -> dict:
    """Add any actions introduced in newer versions without losing trials."""
    out = deepcopy(store)
    base = default_store()
    out.setdefault("beat_reference", base["beat_reference"])
    acts = out.setdefault("actions", {})
    for k, v in base["actions"].items():
        acts.setdefault(k, v)
    return out


def load_store(path: Path = STORE_PATH) -> dict:
    if path.exists():
        try:
            return merge_defaults(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return default_store()


def save_store(store: dict, path: Path = STORE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


def effective_ms(store: dict, key: str) -> float:
    a = store["actions"].get(key)
    if a is None:
        raise KeyError(f"unknown action {key!r}")
    trials = [t for t in a.get("trials_ms", []) if t and t > 0]
    return float(statistics.median(trials)) if trials else float(a["default_ms"])


def is_measured(store: dict, key: str) -> bool:
    return bool(store["actions"].get(key, {}).get("trials_ms"))


def durations(store: dict) -> dict:
    """action key -> seconds."""
    return {k: effective_ms(store, k) / 1000.0 for k in store["actions"]}


def beat_ms(store: dict) -> float:
    return effective_ms(store, store["beat_reference"])


def measured_map(store: dict) -> dict:
    """{key: {median, label}} for actions that have trials (for the Studio)."""
    out = {}
    for k, a in store["actions"].items():
        t = [x for x in a.get("trials_ms", []) if x and x > 0]
        if t:
            out[k] = {"median": float(statistics.median(t)), "label": a["label"]}
    return out


def add_custom_action(store: dict, label: str, weapon: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-")
    key = f"custom.{slug or 'action'}"
    n, base = 2, key
    while key in store["actions"]:
        key, n = f"{base}-{n}", n + 1
    store["actions"][key] = {"label": label, "weapon": weapon,
                             "default_ms": 400, "trials_ms": []}
    return key


def stats(trials: list) -> dict:
    t = [x for x in trials if x and x > 0]
    if not t:
        return {"n": 0}
    return {
        "n": len(t),
        "median": statistics.median(t),
        "mean": statistics.fmean(t),
        "sd": statistics.stdev(t) if len(t) > 1 else 0.0,
        "min": min(t),
        "max": max(t),
    }


def frames_to_ms(start_frame: int, end_frame: int, fps: float) -> float:
    """Video timing: count frames from first movement to arrival."""
    if fps <= 0:
        raise ValueError("fps must be positive")
    return (end_frame - start_frame) * 1000.0 / fps
