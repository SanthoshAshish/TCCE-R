"""One command to reproduce the v0.4 bursty-failure experiment end to end.

  python -m experiments.reproduce_v04            # all stages (about 15-25 min on a laptop)
  python -m experiments.reproduce_v04 --stage tune|eval|report

Stages (protocol: docs/PROTOCOL_v0.4.md):
  config : write configs/v0.4/base_d{D}.yaml from configs/v0.4/main.yaml, D in {0, 2, 4, 8}
  tune   : pre-specified sweep per delay on TUNING seeds 100-119 -> configs/v0.4/selected_d{D}.yaml
  eval   : held-out seeds 5000-5029, budget-matched -> results/v0.4/eval_d{D}/epochs.csv (raw, per epoch)
  report : results/v0.4/report/ (per-seed CSV, summary CSV, paired tests, figures)
"""
import argparse
import os
import shutil
import subprocess
import sys

from tccer.config import load_config, replace, save_config

DELAYS = [0, 2, 4, 8]
EVAL_SEEDS = (5000, 30)
POLICIES = ["static", "periodic", "reactive", "tccer", "tccer_fixed"]


def sh(*args):
    print(">", " ".join(args), flush=True)
    subprocess.run([sys.executable, "-m", *args], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "tune", "eval", "report"], default="all")
    a = ap.parse_args()
    os.makedirs("configs/v0.4", exist_ok=True)
    main_cfg = load_config("configs/v0.4/main.yaml")
    for d in DELAYS:
        save_config(replace(main_cfg, link_setup_epochs=d), f"configs/v0.4/base_d{d}.yaml")

    if a.stage in ("all", "tune"):
        for d in DELAYS:
            out = f"results/v0.4/sweep_d{d}"
            sh("experiments.sweep", "--config", f"configs/v0.4/base_d{d}.yaml", "--out", out)
            shutil.copy(f"{out}/selected_config.yaml", f"configs/v0.4/selected_d{d}.yaml")

    if a.stage in ("all", "eval"):
        for d in DELAYS:
            out = f"results/v0.4/eval_d{d}"
            sh("experiments.run", "--config", f"configs/v0.4/selected_d{d}.yaml", "--seed-start", str(EVAL_SEEDS[0]),
               "--seeds", str(EVAL_SEEDS[1]), "--no-rounds", "--policies", *POLICIES, "--out", out)
            sh("experiments.analyze", out)

    if a.stage in ("all", "report"):
        sh("experiments.report_v04", "--root", "results/v0.4")


if __name__ == "__main__":
    main()
