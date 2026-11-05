"""Streamlit wrapper for the HEMA Studio (a no-build custom component).

The page in this folder (index.html + engine.js + studio.js + the rigged
model) does all the editing and simulation in the browser. It sends the
whole library back whenever something changes; the app saves it to disk.
"""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_DIR = Path(__file__).resolve().parent
_component = components.declare_component("hema_studio", path=str(_DIR))


def studio(*, library: dict, lib_version: int, guards: dict, measured: dict,
           timing_labels: dict, key: str = "studio"):
    """Render the Studio. Returns {"library": ..., "nonce": ...} after edits."""
    return _component(library=library, lib_version=lib_version, guards=guards,
                      measured=measured, timing_labels=timing_labels,
                      key=key, default=None)
