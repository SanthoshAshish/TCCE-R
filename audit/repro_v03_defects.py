"""Audit reproduction on the archived v0.3 configuration (held-out seeds 4000-4029). Read-only: no code is changed.
D1: degree constraint is checked on LIVE degree; failed/pending configured links later raise the live degree.
D2: feedback window ignores link setup delay (new link not usable during part/all of the 'after' window).
"""
import numpy as np
import pandas as pd

import tccer.core.selector as sel
import tccer.sim.engine as eng
from tccer.config import load_config, replace
from tccer.sim.engine import simulate

cfg = load_config("configs/v0.3_selected.yaml")
viol = {"mut_cfg_deg_over": 0, "mutations": 0, "epochs_live_deg_over_and_raised": 0}
orig_commit = sel.MutationPipeline.commit
STATE = {}

def commit(self, m, k):
    s = STATE["s"]
    cfgd = np.bincount(s.eu[s.configured], minlength=s.n) + np.bincount(s.ev[s.configured], minlength=s.n)
    viol["mutations"] += 1
    if m.add is not None and max(cfgd[s.eu[m.add]], cfgd[s.ev[m.add]]) > cfg.d_max:
        viol["mut_cfg_deg_over"] += 1
    return orig_commit(self, m, k)

orig_state = eng.NetworkState
class Spy(orig_state):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw); STATE["s"] = self
sel.MutationPipeline.commit = commit
eng.NetworkState = Spy

for seed in range(4000, 4030):
    for p in ["reactive", "tccer"]:
        simulate(cfg, seed, p, log_rounds=False)
print("D1: mutations whose new link pushed a node's CONFIGURED degree above d_max:",
      f'{viol["mut_cfg_deg_over"]}/{viol["mutations"]}')

# D2: with setup delay 2 and H=3, how much of the 'after' window precedes link activation?
H, d = cfg.feedback_horizon, cfg.link_setup_epochs
print(f"D2: H={H}, setup={d}: new link usable from epoch m+{1 + d}; 'after' window m+1..m+{H}; "
      f"epochs judged before activation = {min(H, d)}/{H} (delay 4 or 8 -> {H}/{H})")
