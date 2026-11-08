**Table 1** Mechanism comparison of the controller families discussed (qualitative; no performance comparison is implied).

| Family | Decision addressed | Failure/objective model | Adaptation | Note |
|---|---|---|---|---|
| Consensus-law design (event-triggered, adaptive, fault-tolerant) | Protocol | Given or switching topology | No topology change | — |
| Connectivity-preserving control (MPC, barrier functions) | Motion or links, constraint-based | Known model, connectivity constraint | Continuous control | No hard rewiring cap |
| Budget-limited rewiring for information flow | Which links to add | Static objective | Offline or one-shot | No failure process |
| Reactive threshold (A1); front-loaded schedules (A7, A7M) | When to spend | State-blind or error threshold | Fixed rule | Earlier controllers of this study |
| Predictive and debt-based triggers (B8, C1) | When and which | Hand-built risk or debt scores | Calibrated thresholds | Earlier controllers of this study |
| COCRO-M (this paper) | Which link to swap | Fitted posterior failure model; scenario-averaged spectral gain | Timing fixed (front-loaded), selection by expected gain | Centralised; tested on random geometric graphs only |
