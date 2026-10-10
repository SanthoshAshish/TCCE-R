"""Simulation engine: one run = one (config, seed, policy). Implements the epoch loop.

Per epoch k:
  1. environment events (background, bursts, scripted events)     -> (1) Dynamic Network State
  2. T consensus rounds with transient failures, fresh x(0)        -> (2) Consensus Monitor
  3. resilience metrics (lambda2, components, bridges, volatility)
  4. policy.decide: debt / trigger / evaluator / gate / selector   -> (3)-(7), (9)
  5. apply mutation; takes effect from epoch k+1                   -> (8) Reconfigured Network
"""
import networkx as nx
import numpy as np

from tccer.consensus.algorithm import local_disagreement, run_epoch_state
from tccer.consensus.monitor import summarize
from tccer.core.counterfactual import ExogenousRecord
from tccer.core.debt import volatility
from tccer.core.selector import EMPTY_SELECTION, MutationPipeline
from tccer.metrics.resilience import lambda2, vulnerability
from tccer.network.events import FailureTrace
from tccer.network.generators import random_geometric
from tccer.network.scenario import load_scenario
from tccer.network.state import NetworkState
from tccer.policies import POLICIES


def simulate(cfg, seed: int, policy_name: str, log_rounds: bool = True, on_epoch=None):
    """on_epoch(k, state, mutation): optional read-only observer called at the end of every epoch
    (used by the network visualizer). It must not modify `state`."""
    if cfg.scenario_file:                     # v0.5: user-supplied topology / values / scripted events
        sc = load_scenario(cfg.scenario_file, cfg)
        pos, eu, ev, length, init_idx = sc.pos, sc.eu, sc.ev, sc.length, sc.init_idx
        scripted = sc.scripted_down
    else:                                     # seed-generated network (v0.1-v0.4 behaviour)
        sc = None
        pos, eu, ev, length, init_idx = random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, seed)
        scripted = np.zeros((cfg.epochs, len(eu)), dtype=bool)
    state = NetworkState(pos, eu, ev, length, init_idx)
    trace = FailureTrace(cfg, seed, state.P, edge_mid=(pos[eu] + pos[ev]) / 2)
    x0_all = np.random.default_rng([seed, 2]).random((cfg.epochs, state.n))
    if sc is not None and sc.initial_values is not None:
        x0_all = sc.initial_values
    pipeline = MutationPipeline(cfg, len(init_idx), state.P)
    policy = POLICIES[policy_name](cfg, pipeline, np.random.default_rng([seed, 3]))
    record = ExogenousRecord(cfg, state, trace, x0_all)     # what the controller has observed (read-only use)
    policy.attach_context(record)

    epoch_rows, round_rows, changes = [], [], []
    background_down = state.down.copy()          # background Markov state; bursts are layered on top
    for k in range(cfg.epochs):
        state.epoch = k
        # 1. environment
        background_down = trace.epoch_update(k, background_down)
        new_down = background_down | trace.burst[k] | scripted[k]
        changes.append(int(((new_down != state.down) & state.configured).sum()))
        state.down = new_down
        record.observe(k, state.down)

        # 2. consensus
        live = np.flatnonzero(state.live_mask())
        u, v = state.eu[live], state.ev[live]
        err, x_end = run_epoch_state(x0_all[k], u, v, lambda t: trace.transient_up(k, t)[live], cfg.rounds_per_epoch)
        delta = local_disagreement(x_end, u, v)       # (2) monitor: local disagreement at the end of the epoch
        rep = summarize(err, cfg.eps)

        # 3. resilience metrics
        g = state.graph()
        comps = nx.number_connected_components(g)
        obs = {
            "E_hat": rep.E_hat,
            "final_error": rep.final_error,
            "conv_round": rep.conv_round if rep.conv_round is not None else -1,
            "rate": rep.rate,
            "local_disagreement_total": float(delta.sum() / 2),   # = sum over live links of (x_i - x_j)^2
            "local_disagreement_max": float(delta.max()) if len(delta) else 0.0,
            "lambda2": lambda2(state.n, u, v) if comps == 1 else 0.0,
            "components": comps,
            "C": vulnerability(g),
            "V": volatility(changes, int(state.configured.sum()), cfg.vol_window),
            "live_edges": len(live),
            "configured_edges": int(state.configured.sum()),
            "pending_links": int((state.configured & (state.ready_at > k)).sum()),
            "n_down_potential": int(state.down.sum()),
            "n_burst_down": int(trace.burst[k].sum()),
            "n_scripted_down": int(scripted[k].sum()),
            "budget": pipeline.budget,
            # logging only: could the shared selector+gate reconnect the network this epoch?
            "reconnect_possible": pipeline.can_reconnect(state, k) if comps > 1 else True,
        }

        # 4. policy
        pipeline.last = dict(EMPTY_SELECTION)
        m = policy.decide(k, obs, state)

        # 5. apply
        if m is not None:
            state.apply(m, cfg.link_setup_epochs)
            pipeline.commit(m, k)
        if on_epoch is not None:
            on_epoch(k, state, m)

        epoch_rows.append({"seed": seed, "policy": policy_name, "epoch": k, **obs, **policy.info(),
                           "mutation": m.describe(state) if m else "", "mutation_kind": m.kind() if m else "",
                           "n_mutations": policy.n_mutations, "gate_rejections": pipeline.gate.rejections,
                           **pipeline.last})
        if log_rounds:
            round_rows.extend({"seed": seed, "policy": policy_name, "epoch": k, "round": t, "error": e}
                              for t, e in enumerate(err))
    return epoch_rows, round_rows
