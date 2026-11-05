# HEMA Tempo Lab

A Streamlit app for studying **Kriegsmesser vs longsword** exchanges: jointed
3D fencers perform techniques, hitboxes turn red when struck, and every
phase runs on **your own measured timings**, so you can see in beats who
lands first and why.

```
pip install -r hema/requirements.txt
streamlit run hema/app.py          # or double-click hema/run_hema.bat on Windows
pytest hema/tests
```

## Pages

* **Arena**: two techniques against each other. Pick a curated matchup
  or any two techniques; set when B reacts, the distance, and each side's
  speed. You get a 3D replay (slow-mo, scrub, orbit, A's/B's eyes views),
  a beat-gridded timeline, the verdict, and a per-phase tempo table.
* **Technique catalog**: each technique against a standing dummy, its
  source, tempo count, your notes and a sparring log (worked / failed).
* **Timing Lab**: record trials per action from video frames
  (start/arrival frame and fps) or as milliseconds. The median is used
  everywhere. Pick which action counts as one **beat**.

## Curated matchups

| Matchup | What it shows |
|---|---|
| Mutual Zornhau, longsword vs messer | Same speed, same habits: the longsword's ~15 cm extra reach takes the head; the messer gets an afterblow to the hands. |
| Zwerch against his Oberhau | Spring out with the Zwerch *Indes*: his blade lands on your cross, your short edge takes his head. Add 50+ ms reaction and it fails. |
| Nachreisen on a wind-up | A two-action attack (Pflug → Vom Tag → cut) loses to a one-action cut to the rising forearms. |
| Hanging cover + Einlaufen | Cover with your strong, then run in where his longer blade can't follow. |
| Messer Zornhau vs longsword thrust | The point is shorter-line and longer-reach. How much faster would you need to be? |

## How outcomes are decided (not scripted)

* 1 ms simulation clock; phase length = your median measured time × speed.
* **Hit**: the cutting part of an attacking blade touches a hitbox capsule
  (head, torso, upper arms, forearms, hands, thighs, shins). One hit per
  action; the blade stops in the target.
* **Bind / displacement (Stärke vs Schwäche)**: on blade contact, a
  *covering* blade meeting the other nearer its own hilt (crossguard =
  strongest) knocks the other off line. That action and its follow-through
  can no longer score.
* **Double hit**: second hit within the double-hit window (default 150 ms).

No mass, momentum, edge alignment or reaction to being hit. The
techniques are simplified study models of Lichtenauer, Lecküchner and
Meyer, not reconstructions. Check what you learn against the sources.

## Your data

`hema/records/timings.json` (measurements) and `hema/records/journal.json`
(notes, sparring log) are plain JSON in the repo. Commit them to keep them.
The Timing Lab has download/restore buttons for hosted deployments where
the disk is not persistent.

## Adding a technique

Write it in `hema/hemaviz/techniques.py` as a guard plus
`Phase(name, action_key, keys=[(u, P(grip, elev, az, hip=…, yaw=…, …))],
attack=…, cover=…, cont=…)`, in the fencer's own frame (x toward the
opponent, z to the fencer's right). Add any new `action_key` to
`DEFAULT_ACTIONS` in `hema/hemaviz/timings.py` so it appears in the Timing Lab.
Register it in `TECHNIQUES` (and optionally as a `Scenario`), then add a
test for the outcome you expect.
