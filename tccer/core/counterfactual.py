"""(9) Counterfactual feedback (v0.7): matched with/without-mutation replays for mutation attribution.

Problem with the before/after rule (core/feedback.py): the trigger fires on high-stress epochs, so mean E after a
mutation tends to be lower than before it even when the mutation does nothing (regression to the mean). On the
archived v0.6 held-out data the before/after rule declared "success" in 67-73% of Static runs, where no mutation
happened (audit, commit 95a1512).

Rule (feedback_rule = "counterfactual"):
  For a mutation decided at the end of epoch m, with setup delay d and horizon H, the evaluation window is
  W = {m+1, ..., m+d+H}. It starts at m+1, so the setup outage (removed link gone, new link not yet usable) counts
  against the mutation. At the end of epoch m+d+H, when every input in W has been observed, the controller replays
  W twice from the snapshot of the topology taken just before the mutation was applied:
      WITH    : snapshot + this mutation only (new link usable from m+1+d, removed link gone from m+1)
      WITHOUT : snapshot, no mutation
  Both replays use the identical observed exogenous record for every epoch in W: link failure states (background,
  bursts, scripted), per-round transient outages, and the epoch's initial values x(0). No other mutation is applied
  in either replay, so overlapping windows cannot attribute one mutation's effect to another.
      Delta = mean_{t in W} E_with(t) - mean_{t in W} E_without(t)
      success  if Delta < 0;   failure if Delta > 0;   neutral (no threshold update) if Delta == 0
  Delta == 0 occurs exactly when the two live graphs coincide in every epoch and round of W (the mutation had no
  effect), because both replays run the identical deterministic arithmetic.
  Invalid counterfactual: if m+d+H lies beyond the last epoch, the mutation is never evaluated (no update; logged as
  unevaluated).

Assumptions (stated, not hidden):
  * logically centralised controller (approved design) holding an exact model of the consensus dynamics;
  * it logs the link states it observed (per epoch and per round) and the epoch inputs x(0);
  * replays use only epochs <= the evaluation epoch: no future information is used.
"""
from dataclasses import dataclass

import numpy as np

from tccer.consensus.algorithm import run_epoch
from tccer.consensus.monitor import summarize


@dataclass
class Snapshot:
    epoch: int                 # m: the mutation was decided at the end of this epoch
    configured: np.ndarray     # configured links before the mutation
    ready_at: np.ndarray       # setup completion epochs before the mutation


class ExogenousRecord:
    """What the controller has observed so far: link failure state per epoch, per-round transient outages
    (pre-generated trace, read only for past epochs) and the epoch inputs x(0)."""

    def __init__(self, cfg, state, trace, x0_all):
        self.cfg, self.n, self.eu, self.ev = cfg, state.n, state.eu, state.ev
        self.trace, self.x0_all = trace, x0_all
        self.down = []                                 # down[t] appended by the engine at the start of epoch t

    def observe(self, k, down_mask):
        assert len(self.down) == k, "epochs must be observed in order"
        self.down.append(down_mask.copy())

    def replay(self, snap: Snapshot, mutation, epochs, now: int):
        """E per epoch for the given branch. Refuses to use any epoch not yet observed (t > now)."""
        if max(epochs) > now or max(epochs) >= len(self.down):
            raise ValueError("counterfactual replay would use unobserved (future) epochs")
        configured, ready = snap.configured.copy(), snap.ready_at.copy()
        if mutation is not None:
            if mutation.add is not None:
                configured[mutation.add] = True
                ready[mutation.add] = snap.epoch + 1 + self.cfg.link_setup_epochs
            if mutation.remove is not None:
                configured[mutation.remove] = False
        out = []
        for t in epochs:
            live = np.flatnonzero(configured & ~self.down[t] & (ready <= t))
            u, v = self.eu[live], self.ev[live]
            err = run_epoch(self.x0_all[t], u, v, lambda r, t=t, live=live: self.trace.transient_up(t, r)[live],
                            self.cfg.rounds_per_epoch)
            out.append(summarize(err, self.cfg.eps).E_hat)
        return np.array(out)


class CounterfactualFeedback:
    """Drop-in replacement for FeedbackEvaluator. register() needs the pre-mutation snapshot and the mutation."""

    def __init__(self, cfg, record: ExogenousRecord):
        self.H, self.d, self.record = cfg.feedback_horizon, cfg.link_setup_epochs, record
        self.pending = []                               # list of (Snapshot, mutation)
        self.last = []                                  # details of the latest evaluations, for logging

    def register(self, snap: Snapshot, mutation) -> None:
        self.pending.append((snap, mutation))

    def evaluate(self, k: int, E_history=None):
        """Return [(m, outcome, delta)] for mutations whose window ends at or before epoch k.
        outcome is 'S' (success), 'F' (failure) or 'N' (neutral: no effect, no threshold update)."""
        done, keep = [], []
        for item in self.pending:
            snap, mut = item
            end = snap.epoch + self.d + self.H
            if k >= end:
                window = list(range(snap.epoch + 1, end + 1))
                delta = float(self.record.replay(snap, mut, window, k).mean() -
                              self.record.replay(snap, None, window, k).mean())
                done.append((snap.epoch, "S" if delta < 0 else "F" if delta > 0 else "N", delta))
            else:
                keep.append(item)
        self.pending = keep
        self.last = done
        return done

    def unevaluated(self):
        return [snap.epoch for snap, _ in self.pending]
