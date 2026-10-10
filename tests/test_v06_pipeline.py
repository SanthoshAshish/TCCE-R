"""End-to-end v0.6 pipeline on a miniature setup in a temporary folder (calibrate -> freeze -> dry run -> analyze).
Never touches configs/v0.6/frozen or results/v0.6."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

import experiments.analyze_v06 as an
import experiments.calibrate_v06 as cal
import experiments.run_v06 as run
import experiments.v06_common as common
from tccer.config import load_config, replace


@pytest.fixture
def mini(tmp_path, monkeypatch):
    frozen = tmp_path / "frozen"
    manifest = str(frozen / "MANIFEST.sha256")

    def base(d):
        return replace(load_config(common.BASE_CONFIG), link_setup_epochs=d, mutation_cap=None, epochs=16,
                       rounds_per_epoch=10)
    grid = {a: np.array([0.0, 0.05, 0.3, 0.6, 2.0]) for a in common.CALIBRATED_ARMS}
    for mod in (common, cal):
        monkeypatch.setattr(mod, "FROZEN_DIR", str(frozen))
        monkeypatch.setattr(mod, "MANIFEST", manifest)
    monkeypatch.setattr(an, "FROZEN_DIR", str(frozen))
    monkeypatch.setattr(cal, "OUT", str(tmp_path / "calibration"))
    monkeypatch.setattr(cal, "TUNING_SEEDS", (100, 101))
    monkeypatch.setattr(cal, "GRID", grid)
    monkeypatch.setattr(cal, "base_config", base)
    monkeypatch.setattr(run, "TUNING_SEEDS", (100, 101))
    monkeypatch.setattr(run, "OUTS", {"dry": str(tmp_path / "dryrun"), "eval": str(tmp_path / "eval")})
    return tmp_path, frozen, manifest


def test_full_pipeline_mini(mini, monkeypatch):
    tmp, frozen, manifest = mini
    monkeypatch.setattr(sys, "argv", ["calibrate", "--workers", "1"])
    cal.main()
    assert os.path.exists(manifest)
    rep = pd.read_csv(frozen / "calibration_report.csv")
    assert set(rep.arm) == {"A1", "A2", "A3", "A4", "A5", "A6", "A7"}
    common.verify_manifest()
    with pytest.raises(SystemExit, match="already frozen"):           # no recalibration after freezing
        cal.main()

    monkeypatch.setattr(sys, "argv", ["run", "--mode", "dry", "--workers", "1"])
    run.main()
    dry = tmp / "dryrun"
    assert (dry / "COMPLETE").exists() and (dry / "A0_static" / "epochs.csv").exists()
    assert len(pd.read_csv(dry / "A0_static" / "epochs.csv").seed.unique()) == 2

    monkeypatch.setattr(sys, "argv", ["analyze", "--run", str(dry)])
    an.main()
    out = dry / "analysis"
    for f in ("per_seed_metrics.csv", "summary.csv", "primary_tests.csv", "secondary_tests.csv",
              "exploratory_diffs.csv", "sensitivity.csv", "REPORT.md"):
        assert (out / f).exists(), f
    ps = pd.read_csv(out / "per_seed_metrics.csv")
    assert {"A0", "A6", "A7"} <= set(ps.arm)
    assert len(pd.read_csv(out / "primary_tests.csv")) == 4

    # tampering with a frozen file blocks any further run
    p = next(f for f in frozen.iterdir() if f.name.startswith("A7"))
    p.write_text(p.read_text() + "\n# edited\n")
    monkeypatch.setattr(sys, "argv", ["run", "--mode", "dry", "--workers", "1"])
    with pytest.raises(RuntimeError, match="changed after freezing"):
        run.main()


def test_eval_mode_rejects_tuning_seeds(monkeypatch):
    monkeypatch.setattr(run, "EVAL_SEEDS", (100, 101))
    monkeypatch.setattr(sys, "argv", ["run", "--mode", "eval"])
    with pytest.raises(common.IsolationError):
        run.main()
