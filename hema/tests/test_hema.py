import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HEMA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HEMA))

from hemaviz.library import add_missing_seeds, load_library, save_library  # noqa: E402
from hemaviz.seeds import seed_guards, seed_library  # noqa: E402
from hemaviz.timings import (add_custom_action, default_store,  # noqa: E402
                             effective_ms, frames_to_ms, measured_map)


def test_seed_library_is_consistent():
    lib = seed_library()
    assert len(lib["exchanges"]) == 3 and lib["moves"]
    for ex in lib["exchanges"] + [dict(m, tracks=[{"keys": m["keys"]}]) for m in lib["moves"]]:
        ids = set()
        for tr in ex["tracks"]:
            ats = [k["at"] for k in tr["keys"]]
            assert ats == sorted(ats)
            ids |= {k["id"] for k in tr["keys"]}
            for k in tr["keys"]:
                assert set(k["pose"]) >= {"hip", "yaw", "lean", "lfoot", "rfoot", "grip", "blade"}
        for a in ex["actions"]:
            assert a["from"] in ids and a["to"] in ids
            assert 0 <= a["strength"] <= 1 and a["pace"] > 0
    assert set(seed_guards()) == {"longsword", "messer"}


def test_library_roundtrip_and_restore_seeds(tmp_path):
    p = tmp_path / "lib.json"
    lib = load_library(p)                      # missing file -> seeds
    lib["exchanges"] = lib["exchanges"][:1]
    save_library(lib, p)
    again = load_library(p)
    assert len(again["exchanges"]) == 1
    assert add_missing_seeds(again) == 2
    assert add_missing_seeds(again) == 0


def test_timings_are_only_a_reality_check():
    st = default_store()
    assert measured_map(st) == {}
    st["actions"]["messer.zwerch"]["trials_ms"] = [300, 500, 310]
    assert effective_ms(st, "messer.zwerch") == 310
    assert measured_map(st)["messer.zwerch"]["median"] == 310
    key = add_custom_action(st, "Messer Krumphau", "messer")
    assert key == "custom.messer-krumphau" and key in st["actions"]
    assert frames_to_ms(10, 52, 120) == pytest.approx(350)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_engine_in_node(tmp_path):
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps(seed_library()))
    r = subprocess.run(["node", "--test", str(HEMA / "tests" / "engine.test.js")],
                       capture_output=True, text=True,
                       env={**os.environ, "HEMA_SEEDS": str(seeds)})
    assert r.returncode == 0, r.stdout + r.stderr
