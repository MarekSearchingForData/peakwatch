"""The Studio library on disk: exchanges (two-fencer timelines) and moves."""
from __future__ import annotations

import json
from pathlib import Path

from .seeds import seed_library

LIB_PATH = Path(__file__).resolve().parent.parent / "records" / "library.json"


def load_library(path: Path = LIB_PATH) -> dict:
    if path.exists():
        try:
            lib = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(lib, dict) and "exchanges" in lib:
                lib.setdefault("moves", [])
                return lib
        except (OSError, json.JSONDecodeError):
            pass
    return seed_library()


def save_library(lib: dict, path: Path = LIB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lib, indent=1), encoding="utf-8")


def add_missing_seeds(lib: dict) -> int:
    """Put back any seed example the user deleted. Returns how many."""
    seeds = seed_library()
    have_ex = {e["id"] for e in lib["exchanges"]}
    have_mv = {m["id"] for m in lib["moves"]}
    new_ex = [e for e in seeds["exchanges"] if e["id"] not in have_ex]
    new_mv = [m for m in seeds["moves"] if m["id"] not in have_mv]
    lib["exchanges"].extend(new_ex)
    lib["moves"].extend(new_mv)
    return len(new_ex) + len(new_mv)
