from tccer.policies.baselines import PeriodicGreedyPolicy, RandomPolicy, ReactivePolicy, StaticPolicy
from tccer.policies.tccer import TCCERFixedThreshold, TCCERPolicy
from tccer.policies.v06 import V06_ARMS

POLICIES = {p.name: p for p in
            [TCCERPolicy, TCCERFixedThreshold, StaticPolicy, RandomPolicy, PeriodicGreedyPolicy, ReactivePolicy,
             *V06_ARMS.values()]}
