from tccer.policies.baselines import PeriodicGreedyPolicy, RandomPolicy, ReactivePolicy, StaticPolicy
from tccer.policies.tccer import TCCERFixedThreshold, TCCERPolicy

POLICIES = {p.name: p for p in
            [TCCERPolicy, TCCERFixedThreshold, StaticPolicy, RandomPolicy, PeriodicGreedyPolicy, ReactivePolicy]}
