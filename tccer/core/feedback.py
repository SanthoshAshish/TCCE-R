"""(9) Feedback Loop: judge each mutation after it has had time to act.  [PROPOSED mechanism]

A mutation applied at the end of epoch m is a *success* if the mean consensus stress E over epochs
m+1..m+H is lower than over epochs m-H+1..m. Evaluated at epoch m+H.
Caveat (risk R7): the environment also changes in that window, so this signal is noisy.

v0.4 option feedback_after_setup: with a link setup delay d the new link is usable only from epoch
m+1+d, so the 'after' window becomes m+1+d .. m+d+H (evaluated at epoch m+d+H). Without it, a delay
d >= H means the mutation is judged entirely before its new link exists.
"""
import numpy as np


class FeedbackEvaluator:
    def __init__(self, cfg):
        self.H = cfg.feedback_horizon
        self.offset = cfg.link_setup_epochs if cfg.feedback_after_setup else 0
        self.pending = []

    def register(self, epoch: int) -> None:
        self.pending.append(epoch)

    def evaluate(self, k: int, E_history):
        """Return list of (mutation_epoch, success) whose horizon completes at epoch k."""
        done = []
        for m in list(self.pending):
            if k >= m + self.offset + self.H:
                before = np.mean(E_history[max(0, m - self.H + 1): m + 1])
                after = np.mean(E_history[m + self.offset + 1: m + self.offset + self.H + 1])
                done.append((m, bool(after < before)))
                self.pending.remove(m)
        return done
