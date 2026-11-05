"""HEMA Studio -- Streamlit app.

    streamlit run hema/app.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from hemaviz.library import add_missing_seeds, load_library, save_library
from hemaviz.seeds import seed_guards
from hemaviz.studio import studio
from hemaviz.timings import (add_custom_action, effective_ms, frames_to_ms,
                             load_store, measured_map,
                             save_store, stats)

JOURNAL_PATH = Path(__file__).resolve().parent / "records" / "journal.json"

st.set_page_config(page_title="HEMA Studio", page_icon="⚔️", layout="wide")


# ------------------------------------------------------------------ state
def library() -> dict:
    if "library" not in st.session_state:
        st.session_state.library = load_library()
        st.session_state.lib_version = 1
    return st.session_state.library


def replace_library(lib: dict) -> None:
    """Swap the whole library (restore/reset): the Studio reloads it."""
    st.session_state.library = lib
    st.session_state.lib_version = st.session_state.get("lib_version", 1) + 1
    persist_library()


def persist_library() -> None:
    try:
        save_library(st.session_state.library)
    except OSError as e:
        st.warning(f"Could not save the library ({e}). Use the download "
                   "button in the sidebar to keep your work.")


def timing_store() -> dict:
    if "store" not in st.session_state:
        st.session_state.store = load_store()
    return st.session_state.store


def persist_store() -> None:
    try:
        save_store(st.session_state.store)
    except OSError as e:
        st.warning(f"Could not save timings: {e}")


def journal() -> dict:
    if "journal" not in st.session_state:
        try:
            st.session_state.journal = json.loads(JOURNAL_PATH.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            st.session_state.journal = {}
    return st.session_state.journal


def persist_journal() -> None:
    try:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        JOURNAL_PATH.write_text(json.dumps(st.session_state.journal, indent=2),
                                encoding="utf-8")
    except OSError as e:
        st.warning(f"Could not save journal: {e}")


# ------------------------------------------------------------------ pages
def page_studio():
    st.markdown("<style>.block-container{padding-top:3.6rem;padding-bottom:0}"
                "</style>", unsafe_allow_html=True)
    store = timing_store()
    val = studio(library=library(), lib_version=st.session_state.lib_version,
                 guards=seed_guards(), measured=measured_map(store),
                 timing_labels={k: a["label"] for k, a in store["actions"].items()})
    if val and val.get("nonce") != st.session_state.get("last_nonce"):
        st.session_state.last_nonce = val["nonce"]
        st.session_state.library = val["library"]
        persist_library()
    with st.expander("How to use the Studio", expanded=False):
        st.markdown("""
1. **Pick or make an exchange** (top bar). Each one has two fencers, A and B,
   each with a weapon, a start distance and a beat length.
2. **Pose**: choose A or B, start from a guard button, then drag the handles:
   yellow = sword hand, orange = sword tip, cyan = pelvis, green = feet, ring =
   move the whole fencer. Turn/Lean/Crouch sliders do the torso. Arms and legs
   are inverse kinematics on the mannequin's bones, so they can't stretch.
   Feet stay on the ground (the pelvis drops if it has to).
3. **Record**: put the playhead on a beat (click the timeline, arrows step
   ⅛ beat) and press **● Record pose** (or `R`). Repeat: guard on beat 0,
   end of the cut on beat 1, and so on. Add in-between keys for curved paths.
4. **Make an action**: click the key where a movement ends, then
   **Make action**. Name it, say whether it attacks and/or covers.
5. **Modulate it on the bar**: the bar's **length** is its pace: drag the
   end to make it faster or slower (everything after it moves with it). Its
   **thickness** is its strength: make it
   fatter or thinner (drag its top or bottom edge) for strength. Short and
   fat = a fast, strong cut.
6. **Fight**: switch to *Fight*. Blades that meet are judged by strength and
   leverage (closer to the hilt = stronger, crossguard strongest). The loser
   is knocked off line and can't score with that action. Hits paint the body
   part red. The result panel lists everything with times in beats.
7. **Reuse**: *Save as move* stores an action (with its follow-through) in
   the moves library; *Insert at playhead* drops it into any exchange,
   for either fencer.
""")


def page_library():
    st.title("Library")
    lib, jr = library(), journal()
    st.caption("Everything recorded in the Studio. Open an exchange in the "
               "Studio to play or edit it. Keep notes and a sparring log here.")
    tab_ex, tab_mv = st.tabs([f"Exchanges ({len(lib['exchanges'])})",
                              f"Moves ({len(lib['moves'])})"])
    with tab_ex:
        if not lib["exchanges"]:
            st.info("No exchanges yet.")
        else:
            rows = [{"name": e["name"],
                     "A": e["fencers"][0]["weapon"], "B": e["fencers"][1]["weapon"],
                     "actions": len(e.get("actions", [])),
                     "keys": sum(len(t["keys"]) for t in e["tracks"]),
                     "beat (ms)": e["beat_ms"], "distance (m)": e["distance"]}
                    for e in lib["exchanges"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            ids = [e["id"] for e in lib["exchanges"]]
            pick = st.selectbox("Notes and sparring log for", ids,
                                format_func=lambda i: next(e["name"] for e in lib["exchanges"] if e["id"] == i))
            ex = next(e for e in lib["exchanges"] if e["id"] == pick)
            if ex.get("notes"):
                st.info(ex["notes"])
            acts = ex.get("actions", [])
            if acts:
                st.dataframe(pd.DataFrame([{
                    "fencer": "AB"[a["fencer"]], "action": a["name"],
                    "strength": round(a.get("strength", 0.5), 2),
                    "pace ×": round(a.get("pace", 1.0), 2),
                    "attacks": a.get("attack"), "covers": a.get("cover")} for a in acts]),
                    hide_index=True, width="stretch")
            journal_box(jr, pick)
    with tab_mv:
        if not lib["moves"]:
            st.info("No moves yet. Use *Save as move* on an action in the Studio.")
        for m in lib["moves"]:
            with st.expander(f"{m['name']}  ·  {m['weapon']}"):
                if m.get("summary"):
                    st.write(m["summary"])
                if m.get("source"):
                    st.caption(f"Source: {m['source']}")
                st.write(", ".join(f"**{a['name']}** ({'attack' if a.get('attack') else ''}"
                                   f"{'+' if a.get('attack') and a.get('cover') else ''}"
                                   f"{'cover' if a.get('cover') else ''})" for a in m["actions"]))
                journal_box(jr, m["id"])


def journal_box(jr: dict, key: str):
    entry = jr.setdefault(key, {"notes": "", "log": []})
    notes = st.text_area("My notes", entry["notes"], height=90, key=f"n_{key}",
                         placeholder="What to feel for, common mistakes, coach's cues…")
    if notes != entry["notes"]:
        entry["notes"] = notes
        persist_journal()
    with st.form(f"log_{key}", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 2])
        day = c1.date_input("Date", dt.date.today())
        outcome = c2.selectbox("In sparring it…", ["worked", "double hit", "failed"])
        what = c3.text_input("What happened")
        if st.form_submit_button("Add to sparring log"):
            entry["log"].append({"date": str(day), "result": outcome, "note": what})
            persist_journal()
    if entry["log"]:
        df = pd.DataFrame(entry["log"])
        st.dataframe(df.iloc[::-1], hide_index=True, width="stretch")
        ok = (df["result"] == "worked").sum()
        st.caption(f"Worked {ok}/{len(df)} times ({ok / len(df):.0%}).")


def page_timing():
    st.title("Reality check (optional)")
    s = timing_store()
    st.markdown(
        "The Studio's timing comes from what you record and the pace you give "
        "each bar. **You don't need to measure anything.** If you do film "
        "yourself, actions linked to a measurement (*Check vs* in the Studio) "
        "are flagged when they're faster than you've actually done them. "
        "Count frames from the first movement of the hands to the arrival of "
        "the blade, in slow-motion phone video.")
    keys = list(s["actions"])
    c1, c2 = st.columns([2, 1])
    key = c1.selectbox("Action", keys, format_func=lambda k: s["actions"][k]["label"]
                       + ("  ✓" if s["actions"][k]["trials_ms"] else ""))
    act = s["actions"][key]
    with c1:
        v1, v2, v3 = st.columns(3)
        fps = v1.selectbox("Video fps", [30, 60, 120, 240], index=2)
        f0 = v2.number_input("First-movement frame", 0, 100000, 0)
        f1 = v3.number_input("Arrival frame", 0, 100000, 0)
        ms_v = frames_to_ms(int(f0), int(f1), fps) if f1 > f0 else 0.0
        st.caption(f"= {ms_v:.0f} ms (±{1000 / fps:.0f} ms)")
        if st.button("Add trial", disabled=ms_v <= 0):
            act["trials_ms"].append(round(ms_v, 1))
            persist_store()
            st.rerun()
    with c2:
        stt = stats(act["trials_ms"])
        if stt["n"]:
            st.metric("Your median", f"{effective_ms(s, key):.0f} ms")
            st.caption(f"n={stt['n']} · sd {stt['sd']:.0f} · range "
                       f"{stt['min']:.0f}–{stt['max']:.0f} ms")
        else:
            st.caption("Not measured yet.")
    if act["trials_ms"]:
        df = pd.DataFrame({"ms": act["trials_ms"]})
        edited = st.data_editor(df, num_rows="dynamic", key=f"ed_{key}", width="stretch")
        new = [float(x) for x in edited["ms"].dropna().tolist() if x > 0]
        if new != act["trials_ms"]:
            act["trials_ms"] = new
            persist_store()
            st.rerun()
    with st.form("custom", clear_on_submit=True):
        st.markdown("**Measure something else**")
        a, b = st.columns([3, 1])
        label = a.text_input("Name", placeholder="e.g. Messer Krumphau from Zornhut")
        weapon = b.selectbox("Weapon", ["messer", "longsword"])
        if st.form_submit_button("Add action") and label.strip():
            add_custom_action(s, label.strip(), weapon)
            persist_store()
            st.rerun()
    measured = [{"action": v["label"], "trials": len(v["trials_ms"]),
                 "median ms": round(effective_ms(s, k))}
                for k, v in s["actions"].items() if v["trials_ms"]]
    if measured:
        st.dataframe(pd.DataFrame(measured), hide_index=True, width="stretch")


def page_about():
    st.title("How it works")
    st.markdown("""
**Figures.** The fencers are Quaternius's *Universal Base Characters*
(male and female, CC0 public domain) with their 65-bone humanoid skeleton.
You pose a few handles; elbows and knees come from inverse kinematics using
each character's real bone lengths, the bones are rotated to match and the
fingers are closed around the hilt. Pick the body per fencer in the top bar.

**Timeline.** Keys are recorded in beats. An action spans from one key to
a later one. Its **pace** stretches or squeezes that span, and everything
after it moves too. Its **strength** goes into the bind. Movements ease in
and out across the whole action.

**Fight rules** (1 ms clock):
* *Hit*: the cutting part of an attacking blade reaches a body part (head,
  torso, upper arm, forearm, hand, thigh, shin). One hit per action.
* *Bind*: blades or a crossguard meet. Each side's force = strength ×
  leverage (contact nearer your hilt is stronger; crossguard strongest),
  plus a bonus for an action marked as a cover. A blade that isn't doing an
  action is weak.
* *Displacement*: with clearly more force (×1.2), the other blade is knocked
  off line. That action and its follow-through can't score. Roughly equal
  forces lock the bind and nobody scores from it.
* *Double hit*: both land within 150 ms.

**Plausibility.** Each action shows its duration in beats, peak tip and
hand speeds, and flags tip speeds above ~25–30 m/s, hands above ~10 m/s,
very fast strong blows, and anything faster than your own measured time.

**Limits.** No mass, momentum, edge alignment or reaction to being hit,
and the seed techniques are simplified study models of Lichtenauer,
Lecküchner and Meyer. Use it to reason about reach, line and tempo.
""")


PAGES = {"Studio": page_studio, "Library": page_library,
         "Reality check": page_timing, "How it works": page_about}
with st.sidebar:
    st.markdown("### ⚔️ HEMA Studio")
    page = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    lib = library()
    st.caption(f"{len(lib['exchanges'])} exchanges · {len(lib['moves'])} moves")
    st.download_button("Download library", json.dumps(lib, indent=1),
                       "hema_library.json", "application/json")
    up = st.file_uploader("Restore library", type="json")
    if up is not None and st.session_state.get("_restored") != up.file_id:
        try:
            new = json.load(up)
            if "exchanges" not in new:
                raise KeyError("exchanges")
            new.setdefault("moves", [])
            st.session_state._restored = up.file_id
            replace_library(new)
            st.success("Library restored.")
        except (json.JSONDecodeError, KeyError, TypeError):
            st.error("That file is not a library export.")
    if st.button("Restore the seed examples",
                 help="Adds back any built-in example you deleted. Your own work is kept."):
        n = add_missing_seeds(lib)
        replace_library(lib)
        st.toast(f"Added {n} example(s)." if n else "All examples are already there.")
    st.caption("Fencers: Quaternius Universal Base Characters (CC0).")
PAGES[page]()
