# HEMA Studio

Choreograph and test **Kriegsmesser vs longsword** exchanges without
writing code. Pose two rigged mannequins by dragging their hands, sword
tips and feet, record a pose per beat, layer the opponent's action on a
second track, then **modulate each action by dragging its bar**: the end
for pace, the top for strength. Fight mode works out who gets displaced
in the bind and who gets hit, and paints the hit body part red.

```
pip install -r hema/requirements.txt
streamlit run hema/app.py          # or double-click hema/run_hema.bat on Windows
pytest hema/tests                  # engine tests need Node.js
```

## Workflow

1. **Exchange**: pick one of the examples or press *New*. Set each
   fencer's weapon, the start distance and the beat length.
2. **Pose**: choose A or B, start from a guard (Vom Tag, Ochs, Pflug,
   Alber, Langort / Zornhut, Stier, Eber, Luginsland, Wechsel), then drag:
   yellow = sword hand, orange = sword tip, cyan = pelvis, green = feet,
   ring = whole fencer. Arms and legs are IK on the mannequin's own bones,
   so they can't stretch, and the pelvis drops to keep the feet on the floor.
3. **Record** (`R`) at the playhead: e.g. guard on beat 0, end of the cut
   on beat 1. Add in-between keys for curved paths.
4. **Make action** from the key where a movement ends; name it and tick
   *attacks* / *covers* / *continuation* (follow-through).
5. **Modulate on the bar**: drag the bar's end to change pace (slow /
   medium / fast; everything after it moves with it). Drag its top to
   change strength (weak / medium / strong).
6. **Fight**: blade contact is judged by strength × leverage (nearer the
   hilt is stronger, crossguard strongest, covers get a bonus). Clearly
   stronger → the other blade is knocked off line and that action can't
   score. Equal → locked bind. The result panel lists hits, binds and
   displacements in ms and beats.
7. **Reuse**: *Save as move* → *Insert at playhead* in any exchange, for
   either fencer. Undo is `Ctrl+Z`.

**Library** page: all exchanges and moves, with notes and a sparring
log (worked / double hit / failed). **Reality check** page (optional):
film yourself and log frame counts. Actions linked to a measurement are
flagged when they're faster than you've actually done them. Every action
also gets automatic tip/hand-speed sanity checks.

## Examples included

| Exchange | What it shows |
|---|---|
| Mutual Zornhau, longsword vs messer | Same speed: the longsword's reach takes the head; the messer only gets an afterblow to the hands. |
| Zwerch against his Oberhau | Started on his cut, the Zwerch catches it on the cross and hits the head. Make it slow (drag its bar) or weak and it fails. |
| Nachreisen on a wind-up | A one-action cut to the rising hands beats a two-action attack. |
| Hanging cover + Einlaufen | Cover on the strong, then run in where the longsword can't follow. |
| Messer Zornhau vs longsword thrust | The point arrives first; how much faster would you need to be? |

*Restore the seed examples* in the sidebar brings back any you deleted.

## Files

* `hema/hemaviz/studio/`: the in-browser Studio: `engine.js` (IK,
  timeline, fight rules; also runs in Node for tests), `studio.js` (three.js
  UI), `index.html`, and the mannequin in `models/`.
* `hema/hemaviz/techniques.py` + `seeds.py`: the example techniques
  (Lichtenauer, Lecküchner, Meyer), written as poses and turned into
  Studio data.
* `hema/records/library.json`: your exchanges and moves (the Studio saves
  here). `timings.json`: measurements. `journal.json`: notes and sparring
  log. All plain JSON, so commit them to keep them. The sidebar has download
  and restore for hosted deployments.

## Credits and limits

Mannequin: **RiggedFigure** © 2017 Cesium, CC-BY 4.0, from the
[Khronos glTF Sample Assets](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/RiggedFigure)
(unmodified; scaled and posed at runtime). three.js r128 is loaded from a CDN.

No mass, momentum, edge alignment or reaction to being hit. The examples
are simplified study models of the sources, not reconstructions.
