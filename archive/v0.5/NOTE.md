# v0.5 reference example run

Produced with the commands in SIMULATOR_GUIDE.md section 2 (tag v0.5):

    python -m experiments.run --config examples/grid_scenario_config.yaml --seeds 5 --policies static periodic reactive tccer --out results/grid_demo
    python -m experiments.analyze results/grid_demo
    python -m experiments.visualize --config examples/grid_scenario_config.yaml --seed 0 --epochs 0 8 17 25 --out results/grid_demo/network

This is a feature demonstration on a 16-node scripted scenario, not an evaluation.
