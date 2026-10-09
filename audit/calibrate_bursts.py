"""Burst-model calibration: STATIC policy only, TUNING seeds 100-119 only. No strategy is evaluated here.
Target fixed in advance: the unmodified network is disconnected in roughly 15-35% of epochs."""
import itertools
import pandas as pd
from tccer.config import load_config, replace
from tccer.sim.engine import simulate

base = replace(load_config("configs/v0.3_binding_base.yaml"), degree_basis="configured",
               feedback_after_setup=True, failed_link_value="if_up")
rows = []
for rate, rad in itertools.product([0.0, 0.1, 0.2], [0.15, 0.2]):
    if rate == 0 and rad == 0.2:
        continue
    df = pd.concat([pd.DataFrame(simulate(replace(base, burst_rate=rate, burst_radius=rad), s, "static",
                                          log_rounds=False)[0]) for s in range(100, 120)])
    rows.append(dict(burst_rate=rate, burst_radius=rad, disconnected=(df.components > 1).mean(),
                     E=df.E_hat.mean(), links_down=df.n_down_potential.mean(), burst_down=df.n_burst_down.mean(),
                     C_connected=df[df.components == 1].C.mean(), V=df.V.mean(), V_p90=df.V.quantile(.9)))
print(pd.DataFrame(rows).round(3).to_string(index=False))
