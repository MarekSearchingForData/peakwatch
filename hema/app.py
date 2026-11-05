"""HEMA Tempo Lab -- Streamlit app.

    streamlit run hema/app.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from hemaviz.kinematics import WEAPONS
from hemaviz.sim import simulate
from hemaviz.techniques import SCENARIOS, TECHNIQUES
from hemaviz.timings import (STORE_PATH, beat_ms, durations, effective_ms,
                             frames_to_ms, is_measured, load_store,
                             merge_defaults, save_store, stats)
from hemaviz.viewer import render_html

JOURNAL_PATH = Path(__file__).resolve().parent / "records" / "journal.json"

st.set_page_config(page_title="HEMA Tempo Lab", page_icon="⚔️", layout="wide")


# ------------------------------------------------------------------ state
def store() -> dict:
    if "store" not in st.session_state:
        st.session_state.store = load_store()
    return st.session_state.store


def persist() -> None:
    try:
        save_store(st.session_state.store)
    except OSError as e:  # read-only deploys (e.g. Streamlit Cloud)
        st.warning(f"Could not save to {STORE_PATH.name}: {e}. "
                   "Use the download button to keep your data.")


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


@st.cache_data(show_spinner="Simulating the exchange…", max_entries=64)
def run_sim(a, b, dur_items, cue, reaction, distance, spd_a, spd_b, window):
    r = simulate(a, b, dict(dur_items), cue_phase=cue, reaction_ms=reaction,
                 distance=distance, speed_a=spd_a, speed_b=spd_b,
                 double_window_ms=window)
    return r.to_json(), [None if h is None else h.__dict__ for h in r.first_hit]


def viewer(res: dict, a: str, b: str, distance: float, height: int = 620):
    ta, tb = TECHNIQUES[a], TECHNIQUES[b]
    html = render_html(
        res, weapons=[WEAPONS[ta.weapon].as_dict(), WEAPONS[tb.weapon].as_dict()],
        labels=[ta.name, tb.name], beat_ms=beat_ms(store()), height=height,
        b_origin=distance)
    components.html(html, height=height + 8, scrolling=False)


def fmt_beats(ms: float) -> str:
    return f"{ms / beat_ms(store()):.2f}"


# ------------------------------------------------------------------ pages
def page_arena():
    st.title("Arena")
    st.caption("Two jointed fencers run techniques against each other on a "
               "1 ms clock, with phase lengths taken from your measured "
               "timings. Hits, binds and displacements are computed, not "
               "scripted, so if you slow a counter down it starts to fail.")

    names = {s.key: s.name for s in SCENARIOS}
    pick = st.selectbox("Matchup", ["custom"] + list(names),
                        format_func=lambda k: "Custom: pick any two"
                        if k == "custom" else names[k], index=1)
    scn = next((s for s in SCENARIOS if s.key == pick), None)

    real = [k for k, t in TECHNIQUES.items()]
    c1, c2 = st.columns(2)
    with c1:
        a = st.selectbox("A (attacks, starts at 0 ms)", real,
                         index=real.index(scn.a if scn else "ls_zornhau"),
                         format_func=lambda k: f"{TECHNIQUES[k].name} "
                         f"[{WEAPONS[TECHNIQUES[k].weapon].name}]",
                         disabled=scn is not None, key=f"a_{pick}")
    with c2:
        b = st.selectbox("B (responds)", real,
                         index=real.index(scn.b if scn else "m_zwerch"),
                         format_func=lambda k: f"{TECHNIQUES[k].name} "
                         f"[{WEAPONS[TECHNIQUES[k].weapon].name}]",
                         disabled=scn is not None, key=f"b_{pick}")
    if scn:
        st.info(scn.lesson)

    ta = TECHNIQUES[a]
    with st.expander("Tempo settings", expanded=scn is None):
        c1, c2, c3 = st.columns(3)
        phase_names = [f"{i + 1}. {p.name}" for i, p in enumerate(ta.phases)] \
            or ["(dummy has no phases)"]
        cue = c1.selectbox("B starts when A begins…", range(len(phase_names)),
                           index=min(scn.cue_phase if scn else 0,
                                     len(phase_names) - 1),
                           format_func=lambda i: phase_names[i],
                           key=f"cue_{pick}_{a}")
        reaction = c1.slider("…plus reaction delay (ms)", 0, 400,
                             int(scn.reaction_ms if scn else 150), 10,
                             key=f"rx_{pick}",
                             help="0 ms = B moves on the same instant (Indes). "
                                  "Simple visual reaction is ~180–250 ms.")
        distance = c2.slider("Start distance, pelvis to pelvis (m)", 1.6, 4.5,
                             float(scn.distance if scn else 2.6), 0.05,
                             key=f"d_{pick}")
        window = c2.slider("Double-hit window (ms)", 0, 400, 150, 10,
                           help="A second hit landing within this time of the "
                                "first counts as a double/afterblow.")
        spd_a = c3.slider("A speed (% of measured time)", 60, 160, 100, 5,
                          key=f"sa_{pick}",
                          help="Below 100 = faster than measured.") / 100
        spd_b = c3.slider("B speed (% of measured time)", 60, 160, 100, 5,
                          key=f"sb_{pick}") / 100

    dur = durations(store())
    res, first = run_sim(a, b, tuple(sorted(dur.items())), cue, float(reaction),
                         float(distance), spd_a, spd_b, float(window))

    verdict_col, info_col = st.columns([1, 2])
    with verdict_col:
        st.metric("Outcome", res["verdict"])
    with info_col:
        st.write(res["detail"])
        tl = []
        for i, h in enumerate(first):
            if h:
                tl.append(f"**{'AB'[i]}** first hit at {h['t'] * 1000:.0f} ms "
                          f"= **{fmt_beats(h['t'] * 1000)} beats**")
        if tl:
            st.markdown(" · ".join(tl))

    viewer(res, a, b, distance)
    st.caption("Drag to orbit, scroll to zoom. Click the timeline to jump. "
               "Bars: red = attacking, blue = covering, purple = both "
               "(covers and can hit). Grid lines are beats.")

    st.subheader("Tempo breakdown")
    rows = []
    for i, phases in enumerate(res["phases"]):
        tech = TECHNIQUES[[a, b][i]]
        for (name, t0, t1, action, kind), ph in zip(phases, tech.phases):
            ms = (t1 - t0) * 1000
            rows.append({
                "fencer": "AB"[i], "phase": name, "kind": kind,
                "starts (ms)": round(t0 * 1000), "ms": round(ms),
                "beats": round(ms / beat_ms(store()), 2),
                "new action?": "continuation" if ph.cont else "yes",
                "timing source": "measured" if is_measured(store(), action)
                else "placeholder",
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(f"1 beat = your *{store()['actions'][store()['beat_reference']]['label']}* "
               f"= {beat_ms(store()):.0f} ms. Change it in the Timing Lab.")


def page_catalog():
    st.title("Technique catalog")
    jr = journal()
    weapon = st.radio("Weapon", ["messer", "longsword"], horizontal=True,
                      format_func=lambda w: WEAPONS[w].name)
    techs = [t for t in TECHNIQUES.values()
             if t.weapon == weapon and "dummy" not in t.tags]
    key = st.selectbox("Technique", [t.key for t in techs],
                       format_func=lambda k: TECHNIQUES[k].name)
    t = TECHNIQUES[key]

    left, right = st.columns([3, 2])
    with left:
        dummy = "dummy_ls" if weapon == "messer" else "dummy_m"
        dist = st.slider("Distance to the dummy (m)", 1.4, 3.6,
                         2.4 if t.phases and t.phases[0].action.endswith("approach")
                         else 2.0, 0.05, key=f"cd_{key}")
        dur = durations(store())
        res, _ = run_sim(key, dummy, tuple(sorted(dur.items())), 0, 0.0,
                         float(dist), 1.0, 1.0, 150.0)
        viewer(res, key, dummy, dist, height=520)
        st.caption(f"{res['verdict']}: {res['detail']}")
    with right:
        st.markdown(f"**Guard:** {t.guard_name}  \n"
                    f"**Tempi:** {t.action_count} "
                    f"({t.blade_actions} blade, "
                    f"{t.action_count - t.blade_actions} footwork/wind-up)  \n"
                    f"**Tags:** {', '.join(t.tags)}")
        st.write(t.summary)
        st.caption(f"Source: {t.source}")
        total = 0.0
        rows = []
        for p in t.phases:
            ms = effective_ms(store(), p.action)
            total += ms
            rows.append({"phase": p.name, "ms": round(ms),
                         "beats": round(ms / beat_ms(store()), 2),
                         "attack": p.attack, "cover": p.cover,
                         "measured": is_measured(store(), p.action)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"Total {total:.0f} ms = {fmt_beats(total)} beats")

        entry = jr.setdefault(key, {"notes": "", "log": []})
        notes = st.text_area("My notes", entry["notes"], height=110,
                             key=f"notes_{key}",
                             placeholder="What to feel for, common mistakes, "
                                         "coach's cues…")
        if notes != entry["notes"]:
            entry["notes"] = notes
            persist_journal()
        with st.form(f"log_{key}", clear_on_submit=True):
            st.markdown("**Sparring log**")
            c1, c2 = st.columns(2)
            day = c1.date_input("Date", dt.date.today())
            outcome = c2.selectbox("Result", ["worked", "double hit",
                                              "failed", "didn't try"])
            vs = st.text_input("Against (opponent / weapon / their action)")
            what = st.text_input("What happened")
            if st.form_submit_button("Add to log"):
                entry["log"].append({"date": str(day), "result": outcome,
                                     "vs": vs, "note": what})
                persist_journal()
        if entry["log"]:
            df = pd.DataFrame(entry["log"])
            st.dataframe(df.iloc[::-1], hide_index=True, width="stretch")
            ok = (df["result"] == "worked").sum()
            tried = (df["result"] != "didn't try").sum()
            if tried:
                st.caption(f"Worked {ok}/{tried} times in sparring "
                           f"({ok / tried:.0%}).")


def page_timing():
    st.title("Timing Lab")
    s = store()
    st.markdown(
        "Every animated phase uses the **median of your trials** for its "
        "action, or a placeholder until you record one. Record each action "
        "on video at 60, 120 or 240 fps. Count frames from the first "
        "movement of the hands to the moment the blade arrives (or to the "
        "end position for steps and covers). Phones in slow-motion mode "
        "work well.")

    keys = list(s["actions"])
    lab = lambda k: f"{s['actions'][k]['label']}" + (
        "  ✓" if is_measured(s, k) else "")
    c1, c2 = st.columns([2, 1])
    key = c1.selectbox("Action", keys, format_func=lab)
    act = s["actions"][key]

    with c1:
        tab_v, tab_ms = st.tabs(["From video frames", "Type milliseconds"])
        with tab_v:
            v1, v2, v3 = st.columns(3)
            fps = v1.selectbox("Video fps", [30, 60, 120, 240], index=2)
            f0 = v2.number_input("First-movement frame", 0, 100000, 0)
            f1 = v3.number_input("Arrival frame", 0, 100000, 0)
            ms_v = frames_to_ms(int(f0), int(f1), fps) if f1 > f0 else 0.0
            st.caption(f"= {ms_v:.0f} ms (±{1000 / fps:.0f} ms frame resolution)")
            if st.button("Add trial", disabled=ms_v <= 0, key="add_v"):
                act["trials_ms"].append(round(ms_v, 1))
                persist()
                st.rerun()
        with tab_ms:
            raw = st.text_input("Trials in ms, comma separated",
                                placeholder="e.g. 342, 360, 351")
            if st.button("Add trials", key="add_ms"):
                try:
                    vals = [float(x) for x in raw.replace(";", ",").split(",")
                            if x.strip()]
                    act["trials_ms"].extend(v for v in vals if 30 < v < 3000)
                    persist()
                    st.rerun()
                except ValueError:
                    st.error("Use numbers separated by commas.")

    with c2:
        stt = stats(act["trials_ms"])
        st.metric("Used in simulations", f"{effective_ms(s, key):.0f} ms")
        st.markdown(f"**{effective_ms(s, key) / beat_ms(s):.2f} beats**")
        if stt["n"]:
            st.caption(f"n={stt['n']} · median {stt['median']:.0f} · "
                       f"sd {stt['sd']:.0f} · range {stt['min']:.0f}–{stt['max']:.0f} ms")
        else:
            st.caption(f"Placeholder {act['default_ms']} ms. Not measured yet.")
        new_default = st.number_input("Placeholder (ms)", 50, 3000,
                                      int(act["default_ms"]), 10)
        if new_default != act["default_ms"]:
            act["default_ms"] = int(new_default)
            persist()
            st.rerun()

    if act["trials_ms"]:
        df = pd.DataFrame({"trial": range(1, len(act["trials_ms"]) + 1),
                           "ms": act["trials_ms"]})
        edited = st.data_editor(df, hide_index=True, num_rows="dynamic",
                                key=f"ed_{key}", width="stretch")
        new = [float(x) for x in edited["ms"].dropna().tolist() if x > 0]
        if new != act["trials_ms"]:
            act["trials_ms"] = new
            persist()
            st.rerun()

    st.divider()
    st.subheader("Beat reference")
    ref = st.selectbox("One beat equals…", keys, index=keys.index(s["beat_reference"]),
                       format_func=lambda k: s["actions"][k]["label"])
    if ref != s["beat_reference"]:
        s["beat_reference"] = ref
        persist()
        st.rerun()
    st.caption("A good reference is your fastest clean one-action cut: "
               "\"one tempo\". Then a 2-beat technique against a 1-beat "
               "attack loses unless it starts a beat earlier.")

    rows = [{"action": v["label"], "weapon": v["weapon"],
             "ms used": round(effective_ms(s, k)),
             "beats": round(effective_ms(s, k) / beat_ms(s), 2),
             "trials": len(v["trials_ms"]),
             "source": "measured" if v["trials_ms"] else "placeholder"}
            for k, v in s["actions"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Backup")
    c1, c2 = st.columns(2)
    c1.download_button("Download timings.json", json.dumps(s, indent=2),
                       "timings.json", "application/json")
    up = c2.file_uploader("Restore from timings.json", type="json")
    if up is not None and st.session_state.get("_restored") != up.file_id:
        try:
            st.session_state.store = merge_defaults(json.load(up))
            st.session_state._restored = up.file_id
            persist()
            st.success("Restored.")
            st.rerun()
        except (json.JSONDecodeError, KeyError, TypeError):
            st.error("That file is not a timings export.")


def page_about():
    st.title("How it works")
    st.markdown("""
**Model.** Each fencer is a jointed gray figure: head, torso, upper arms,
forearms, hands, thighs and shins are capsule hitboxes. Elbows and knees are
solved with inverse kinematics from where the hands and feet need to be.
Techniques are written as guards plus timed phases with keyframes.

**Clock.** The exchange runs at 1 ms resolution. A phase lasts exactly as
long as your median measured time for that action, scaled by the speed
sliders. B starts when A begins a chosen phase, plus a reaction delay.

**Contact rules.**
* *Hit*: the cutting part of an attacking blade touches an opponent hitbox.
  That part turns red.
* *Bind*: blade or crossguard meets the other blade (yellow flash).
* *Displacement (Stärke vs Schwäche)*: if a covering blade meets the other
  blade nearer its own hilt than the other's contact point (crossguard =
  strongest), the weaker blade is knocked off line and that action can't
  score any more. Its follow-through is dead too.
* *Double hit*: both land within the double-hit window.

**What it is not.** The model has no mass, momentum or edge alignment, and
no reaction to being hit. The techniques are simplified study models of
the sources, not reconstructions. Use it to reason about **reach, line and
tempo**, and check your conclusions against the sources and your coach.

**Adding techniques.** See `hema/hemaviz/techniques.py`. A technique is a
guard and a list of `Phase(name, action_key, keys, attack, cover, cont)`.
New action keys go in `hema/hemaviz/timings.py` so they show up in the
Timing Lab.
""")


PAGES = {"Arena": page_arena, "Technique catalog": page_catalog,
         "Timing Lab": page_timing, "How it works": page_about}
with st.sidebar:
    st.markdown("### ⚔️ HEMA Tempo Lab")
    page = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    st.caption(f"Beat = {beat_ms(store()):.0f} ms "
               f"({store()['actions'][store()['beat_reference']]['label']})")
    measured = sum(1 for k in store()["actions"] if is_measured(store(), k))
    st.caption(f"{measured}/{len(store()['actions'])} actions measured")
PAGES[page]()
