"""Policy interface: every strategy sees the same observations and uses the same MutationPipeline
(same candidate set, same safety gate, same edge budget). Only *when* and *how* it picks differ."""


class Policy:
    name = "base"

    def __init__(self, cfg, pipeline, rng):
        self.cfg, self.pipeline, self.rng = cfg, pipeline, rng
        self.n_mutations = 0
        self.last_mutation_epoch = None

    def capped(self) -> bool:
        cap = self.cfg.mutation_cap
        return cap is not None and self.n_mutations >= cap

    def decide(self, k: int, obs: dict, state):
        raise NotImplementedError

    def _mutate(self, k, state, mode="lexicographic"):
        if self.capped():
            self.pipeline.last["select_outcome"] = "capped"
            return None
        m = self.pipeline.select(state, k, mode=mode, rng=self.rng)
        if m is not None:
            self.n_mutations += 1
            self.last_mutation_epoch = k
        return m

    def info(self) -> dict:
        return {}
