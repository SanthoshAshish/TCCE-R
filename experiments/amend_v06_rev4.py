"""Protocol revision 4 amendment (docs/PROTOCOL_v0.6.md, section 2.3a). Run once, before the held-out evaluation.

  python -m experiments.amend_v06_rev4

Builds, for every delay x budget cell, the empirical distribution of REALISED mutation counts of A1-A5 on the tuning
seeds (rev. 3 dry run, results/v0.6/dryrun, seeds 100-119) and writes it into the A6/A7 frozen configs as
`v06_count_pmf`. Only these 8 configs, the new control_count_pmf.csv and the manifest change; the script refuses to
finish if any other frozen file's checksum differs from the rev. 3 manifest. The rev. 3 manifest is kept as
MANIFEST_rev3.sha256.
"""
import os
import shutil

import pandas as pd

from experiments.v06_common import (CELLS, FROZEN_DIR, MANIFEST, TUNING_SEEDS, assert_seeds, cell_name, frozen_path,
                                    verify_manifest, write_manifest)
from tccer.config import load_config, replace, save_config

DRY = "results/v0.6/dryrun"
SOURCE_ARMS = ("A1", "A2", "A3", "A4", "A5")
CONTROLS = ("A6", "A7")


def empirical_pmf(counts, M):
    """counts: realised counts (ints in 0..M). Returns (list of probabilities for 0..M, per-count tallies)."""
    tally = [int((counts == n).sum()) for n in range(M + 1)]
    if sum(tally) != len(counts):
        raise ValueError("realised counts outside 0..M")
    return [t / len(counts) for t in tally], tally


def pmf_string(p):
    return ",".join(repr(float(x)) for x in p)


def main():
    if os.path.exists("results/v0.6/eval"):
        raise SystemExit("held-out evaluation output exists: amendment refused")
    old = verify_manifest()                                   # rev. 3 state must be intact
    if any(k.startswith("control_count_pmf") for k in old):
        raise SystemExit("rev. 4 amendment already applied")
    rows, new_files = [], []
    for d, M in CELLS:
        df = pd.read_csv(os.path.join(DRY, cell_name(d, M), "epochs.csv"))
        assert_seeds(df.seed.unique(), TUNING_SEEDS, "rev. 4 count distribution")
        last = df[df.epoch == df.epoch.max()]
        src = last[last.arm.isin(SOURCE_ARMS)]
        if len(src) != len(SOURCE_ARMS) * len(TUNING_SEEDS):
            raise SystemExit(f"{cell_name(d, M)}: expected {len(SOURCE_ARMS) * len(TUNING_SEEDS)} source runs")
        p, tally = empirical_pmf(src.n_mutations.to_numpy(), M)
        for n in range(M + 1):
            rows.append({"cell": cell_name(d, M), "delay": d, "M": M, "count": n, "n_runs": tally[n],
                         "probability": p[n]})
        for arm in CONTROLS:
            path = frozen_path(arm, d, M)
            cfg = load_config(path)
            save_config(replace(cfg, v06_count_pmf=pmf_string(p)), path)
            new_files.append(path)
    pmf_path = os.path.join(FROZEN_DIR, "control_count_pmf.csv")
    pd.DataFrame(rows).to_csv(pmf_path, index=False)
    shutil.copyfile(MANIFEST, os.path.join(FROZEN_DIR, "MANIFEST_rev3.sha256"))
    all_files = [os.path.join(FROZEN_DIR, rel) for rel in old] + [pmf_path]
    write_manifest(all_files)
    new = verify_manifest()
    changed = sorted(k for k in old if new[k] != old[k])
    expected = sorted(os.path.basename(f) for f in new_files)
    if changed != expected:
        raise SystemExit(f"unexpected checksum changes: {changed} (expected only {expected})")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nchanged: {changed}\nadded: control_count_pmf.csv\nunchanged: {len(old) - len(changed)} of {len(old)}"
          f" rev. 3 files (all thresholds, constants, A0-A5 configs, calibration report)")


if __name__ == "__main__":
    main()
