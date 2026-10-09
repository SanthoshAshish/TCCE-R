"""(9) Feedback Loop: judge each mutation after it has had time to act.  [PROPOSED mechanism]

A mutation applied at the end of epoch m is a *success* if the mean consensus stress E over epochs
m+1..m+H is lower than over epochs m-H+1..m. Evaluated at epoch m+H.
Caveat (risk R7): the environment also changes in that window, so this signal is noisy.
"""
import numpy as np


class FeedbackEvaluator:
    def __init__(self, cfg):
        self.H = cfg.feedback_horizon
        self.pending = []

    def register(self, epoch: int) -> None:
        self.pending.append(epoch)

    def evaluate(self, k: int, E_history):
        """Return list of (mutation_epoch, success) whose horizon completes at epoch k."""
        done = []
        for m in list(self.pending):
            if k >= m + self.H:
                before = np.mean(E_history[max(0, m - self.H + 1): m + 1])
                after = np.mean(E_history[m + 1: m + self.H + 1])
                done.append((m, bool(after < before)))
                self.pending.remove(m)
        return done
