# Literature review for TCCE-R (first pass)

**Status:** first-pass review, written 2026-10-10. No simulator code or results were changed.

> **Update:** P6, P7 and P12 were checked further in [`KEY_PAPERS_VERIFICATION.md`](KEY_PAPERS_VERIFICATION.md).
> - **P6:** full text read.
> - **P12:** method verified from the first author's thesis. The thesis also studies a history-window (averaged) trigger, so P12's "accumulated signal" cell below should read "✔ (variant, thesis §4.4.5)".
> - **P7:** still unverifiable beyond its metadata.
>
> Where they conflict, that document takes precedence over the abstract-based notes here.

**How the papers were verified**
- **Bibliographic data:** title, authors, venue, volume/pages, year and DOI were checked against Crossref (`api.crossref.org`) or OpenAlex. In two cases the venue was confirmed through a publisher or repository page.
- **Contribution summaries** are based on each paper's abstract, retrieved from OpenAlex, Semantic Scholar, the authors' page or a repository record.
- **Full texts were not read in this pass.** Anything an abstract does not state is marked **unknown (not in abstract)**. Items I recall but did not verify here are marked **[unverified]**.
- **Facts vs interpretation:** sections 2 and 3 report what the sources state. Sections 4–6 contain **my interpretations**, labelled as such.

---

## 1. Selected papers

| # | Paper | Venue, DOI | Topic group |
|---|---|---|---|
| P1 | R. Olfati-Saber, R. M. Murray, *Consensus Problems in Networks of Agents With Switching Topology and Time-Delays*, 2004 | IEEE Trans. Automatic Control 49(9):1520–1533, [10.1109/TAC.2004.834113](https://doi.org/10.1109/TAC.2004.834113) | consensus, changing topology |
| P2 | A. Jadbabaie, J. Lin, A. S. Morse, *Coordination of groups of mobile autonomous agents using nearest neighbor rules*, 2003 | IEEE Trans. Automatic Control 48(6):988–1001, [10.1109/TAC.2003.812781](https://doi.org/10.1109/TAC.2003.812781) | consensus, changing topology |
| P3 | L. Xiao, S. Boyd, *Fast linear iterations for distributed averaging*, 2004 | Systems & Control Letters 53(1):65–78, [10.1016/j.sysconle.2004.02.022](https://doi.org/10.1016/j.sysconle.2004.02.022) | consensus speed (weights) |
| P4 | S. Kar, J. M. F. Moura, *Distributed Consensus Algorithms in Sensor Networks With Imperfect Communication: Link Failures and Channel Noise*, 2009 | IEEE Trans. Signal Processing 57(1):355–369, [10.1109/TSP.2008.2007111](https://doi.org/10.1109/TSP.2008.2007111) | consensus under link failures |
| P5 | S. Kar, J. M. F. Moura, *Sensor Networks With Random Links: Topology Design for Distributed Consensus*, 2008 | IEEE Trans. Signal Processing 56(7):3315–3326, [10.1109/TSP.2008.920143](https://doi.org/10.1109/TSP.2008.920143) | topology design, failures, cost budget |
| P6 | A. Ghosh, S. Boyd, *Growing Well-connected Graphs*, 2006 | Proc. 45th IEEE Conf. Decision and Control, pp. 6605–6611, [10.1109/CDC.2006.377282](https://doi.org/10.1109/CDC.2006.377282) | connectivity optimisation (adding edges) |
| P7 | A. Sydney, C. Scoglio, D. Gruenbacher, *Optimizing algebraic connectivity by edge rewiring*, 2013 | Applied Mathematics and Computation 219(10):5465–5479, [10.1016/j.amc.2012.11.002](https://doi.org/10.1016/j.amc.2012.11.002) | connectivity optimisation (rewiring) |
| P8 | M. M. Zavlanos, M. B. Egerstedt, G. J. Pappas, *Graph-theoretic connectivity control of mobile robot networks*, 2011 | Proceedings of the IEEE 99(9):1525–1540, [10.1109/JPROC.2011.2157884](https://doi.org/10.1109/JPROC.2011.2157884) | adaptive topology / connectivity control |
| P9 | J. P. G. Sterbenz, D. Hutchison, E. K. Çetinkaya, A. Jabbar, J. P. Rohrer, M. Schöller, P. Smith, *Resilience and survivability in communication networks: Strategies, principles, and survey of disciplines*, 2010 | Computer Networks 54(8):1245–1265, [10.1016/j.comnet.2010.03.005](https://doi.org/10.1016/j.comnet.2010.03.005) | network resilience framework |
| P10 | S. Neumayer, G. Zussman, R. Cohen, E. Modiano, *Assessing the Vulnerability of the Fiber Infrastructure to Disasters*, 2011 | IEEE/ACM Trans. Networking 19(6):1610–1623, [10.1109/TNET.2011.2128879](https://doi.org/10.1109/TNET.2011.2128879) | geographically correlated failures |
| P11 | H. J. LeBlanc, H. Zhang, X. Koutsoukos, S. Sundaram, *Resilient Asymptotic Consensus in Robust Networks*, 2013 | IEEE J. Selected Areas in Communications 31(4):766–781, [10.1109/JSAC.2013.130413](https://doi.org/10.1109/JSAC.2013.130413) | resilient / fault-tolerant consensus |
| P12 | A. Gençata, B. Mukherjee, *Virtual-topology adaptation for WDM mesh networks under dynamic traffic*, 2003 | IEEE/ACM Trans. Networking 11(2):236–247, [10.1109/TNET.2003.810319](https://doi.org/10.1109/TNET.2003.810319) | threshold-triggered topology reconfiguration |
| P13 | D. V. Dimarogonas, E. Frazzoli, K. H. Johansson, *Distributed Event-Triggered Control for Multi-Agent Systems*, 2012 | IEEE Trans. Automatic Control 57(5):1291–1297, [10.1109/TAC.2011.2174666](https://doi.org/10.1109/TAC.2011.2174666) | event-triggered adaptation |
| P14 | E. S. Page, *Continuous Inspection Schemes*, 1954 | Biometrika 41(1–2):100–115, [10.1093/biomet/41.1-2.100](https://doi.org/10.1093/biomet/41.1-2.100) | accumulated-evidence (CUSUM) detection |
| P15 | T. Gross, B. Blasius, *Adaptive coevolutionary networks: a review*, 2008 | J. Royal Society Interface 5(20):259–271, [10.1098/rsif.2007.1229](https://doi.org/10.1098/rsif.2007.1229) | topology–state co-evolution |

**Additional candidates** (bibliographic data verified; not yet analysed):
- P. Santi, *Topology control in wireless ad hoc and sensor networks*, ACM Computing Surveys 37(2):164–194, 2005, [10.1145/1089733.1089736](https://doi.org/10.1145/1089733.1089736).
- W. Quattrociocchi, G. Caldarelli, A. Scala, *Self-Healing Networks: Redundancy and Structure*, PLoS ONE 9(2):e87986, 2014, [10.1371/journal.pone.0087986](https://doi.org/10.1371/journal.pone.0087986).
- H. Chan, L. Akoglu, *Optimizing network robustness by edge rewiring: a general framework*, Data Mining and Knowledge Discovery 30(5):1395–1425, 2016, [10.1007/s10618-015-0447-5](https://doi.org/10.1007/s10618-015-0447-5). Bibliographic data from OpenAlex only.

## 2. Per-paper extraction (verified facts; "unknown" = not stated in the abstract)

### P1 Olfati-Saber & Murray 2004
- **Problem:** consensus for networks of dynamic agents with fixed and switching topologies.
- **Method:** two consensus protocols (with and without time delays), analysed with disagreement functions (Lyapunov functions); algebraic graph theory.
- **Assumptions:** three cases:
  - directed graphs with fixed topology;
  - directed graphs with switching topology;
  - undirected graphs with communication time delays and fixed topology.
- **Metrics:** convergence / "negotiation speed".
- **Baselines:** unknown (not in abstract).
- **Findings:** a direct connection between algebraic connectivity (Fiedler eigenvalue) and the speed of linear consensus; balanced digraphs are key for average consensus; a common Lyapunov function for directed switching topologies.
- **Evaluation:** theory, illustrated by simulations.
- **Limitations:** unknown (not in abstract).

### P2 Jadbabaie, Lin & Morse 2003
- **Problem:** why agents updating headings by nearest-neighbour averaging (Vicsek model) align, even though neighbour sets change over time.
- **Method:** analysis as a switched linear system; convergence results for related models.
- **Assumptions:** n agents moving in the plane at equal speed, with time-varying neighbour sets.
- **Metrics:** convergence of headings.
- **Baselines:** unknown.
- **Findings:** a theoretical explanation of the observed alignment. The system is stable, yet no common quadratic Lyapunov function exists.
- **Limitations:** unknown (not in abstract).

### P3 Xiao & Boyd 2004
- **Problem:** find the linear iteration (weights) that converges fastest to the network average.
- **Method:** for symmetric weights, a semidefinite program solved globally; structure-exploiting interior-point methods (about 1,000 edges) and a subgradient method (up to about 100,000 edges).
- **Assumptions:** fixed graph; symmetric weights for the convex formulation.
- **Metric:** asymptotic convergence rate of the averaging iteration.
- **Baselines:** "common Laplacian-based heuristics", which the optimal weights often beat by a wide margin.
- **Limitations:** unknown (not in abstract).
- **Not verified here:** whether this paper is the right citation for the Metropolis–Hastings weights used in our simulator. **[unverified — check the full text]**

### P4 Kar & Moura 2009
- **Problem:** average consensus with random topologies (intermittent links) and noisy channels.
- **Method:** two algorithms:
  - **A-ND:** weights decaying under a persistence condition;
  - **A-NC:** constant weights, repeated restarts and Monte Carlo averaging.

  Analysed with controlled Markov processes and stochastic approximation.
- **Assumptions:** "fairly general" random link failures and communication noise.
- **Metrics:** bias, variance / mean-square error of the consensus limit, convergence rate, iterations to (ε, δ)-consensus.
- **Baselines:** unknown.
- **Findings:**
  - A-ND gives almost-sure convergence with zero bias and low variance, but converges slowly.
  - A-NC converges fast, with a different bias–variance trade-off.
- **Limitations:** unknown (not in abstract).

### P5 Kar & Moura 2008
- **Problem:** design the topology, i.e. the link-reliability probabilities, to maximise the convergence rate of average consensus, given link communication costs and an overall communication budget.
- **Method:** a Bernoulli random-topology model, formulated as a constrained convex optimisation and solved by semidefinite programming.
- **Assumptions:** random link failures; per-link costs; a budget constraint.
- **Metrics:** mean-square and almost-sure convergence; convergence speed; communication cost.
- **Baselines:** unknown.
- **Findings:**
  - Consensus converges (in mean square / almost surely) if and only if the mean graph's algebraic connectivity is positive.
  - The optimised design converges significantly faster and matches a non-random network at a fraction of the cost (simulations).
- **Limitations:** unknown. The design appears to be offline, for known failure statistics (my reading of the abstract).

### P6 Ghosh & Boyd 2006
- **Problem:** add edges from a candidate set to maximise algebraic connectivity, a difficult combinatorial problem.
- **Method:**
  - an SDP convex relaxation, which gives an upper bound and a heuristic;
  - a new greedy heuristic based on the Fiedler vector, scalable to very large graphs.
- **Assumptions:** a static graph and a candidate edge set.
- **Metric:** algebraic connectivity.
- **Baselines:** unknown (not in abstract).
- **Limitations:** unknown.
- **Relevance to TCCE-R:** TCCE-R's selector scores an addition (i, j) by the first-order estimate (f_i − f_j)², with f the Fiedler vector. This is the same kind of Fiedler-based greedy heuristic, so **P6 should be cited for it**. Whether the exact formula matches P6 needs checking against the full text.

### P7 Sydney, Scoglio & Gruenbacher 2013
- **Problem:** which edge to rewire to obtain the largest increase in algebraic connectivity, extended to rewiring multiple edges.
- **Method:** unknown in detail (the abstract was available only as a paraphrase on an index page).
- **Assumptions:** unknown.
- **Metric:** algebraic connectivity as a robustness measure.
- **Findings (per the indexed abstract):** guidance on how many edges to rewire and where.
- **Baselines, limitations:** unknown.
- **Relevance:** rewiring at a constant edge count is exactly the operation TCCE-R performs under its strict budget (v0.3/v0.4). **The full text must be read before using P7.**

### P8 Zavlanos, Egerstedt & Pappas 2011
- **Problem:** controlling graph connectivity in mobile robot networks.
- **Method:** a framework spanning:
  - convex optimisation and subgradient methods to maximise algebraic connectivity;
  - potential fields and hybrid systems that maintain links or control topology "in a least restrictive manner".

  Both centralised and distributed algorithms are discussed.
- **Assumptions:** proximity-based links (disk-based or uniformly fading signal strength); topology is controlled through **mobility**.
- **Metrics:** connectivity, algebraic connectivity.
- **Baselines:** unknown.
- **Findings:** connectivity control applied to rendezvous, flocking and formation control.
- **Limitations:** unknown. Mobility-based control does not map onto static node positions (my reading).

### P9 Sterbenz et al. 2010
- **Problem:** the growing consequences of network disruption.
- **Method:**
  - an architectural framework for resilience and survivability;
  - a strategy to defend against, detect and remediate challenges (the ResiliNets D²R² + DR loop);
  - design principles;
  - techniques to analyse resilience.

  The paper is a survey and framework.
- **Assumptions, metrics, baselines, limitations:** unknown (not in the abstract text retrieved).

### P10 Neumayer, Zussman, Cohen & Modiano 2011
- **Problem:** the vulnerability of geographical networks to disasters and physical attacks that hit specific locations.
- **Method:** polynomial-time algorithms for worst-case line-segment cuts and circular (disk) cuts; nodes and links are located in the plane.
- **Metrics:** disruption of capacity and connectivity.
- **Evaluation:** numerical results on a specific backbone network.
- **Baselines, limitations:** unknown.
- **Relevance:** TCCE-R v0.4's burst model (all links within a disk fail together) is a geographically correlated failure model of this kind, though ours is random and temporary rather than worst-case.

### P11 LeBlanc, Zhang, Koutsoukos & Sundaram 2013
- **Problem:** resilient consensus despite misbehaving or compromised nodes, using only local information.
- **Method:** a local consensus protocol resilient to worst-case attackers with full knowledge.
- **Assumptions:** misbehaving nodes under several threat models.
- **Findings:**
  - necessary and sufficient conditions for consensus among the normal nodes;
  - traditional connectivity measures are inadequate for this purpose;
  - a new graph property, "network robustness", is introduced.
- **Metrics, baselines, limitations:** unknown.
- **Relevance:** a different threat model (adversarial nodes vs our benign link failures), but an important counterpoint. The resilience of consensus may need properties beyond connectivity or λ₂.

### P12 Gençata & Mukherjee 2003
- **Problem:** reconfigure the virtual topology of a WDM optical mesh network under dynamic traffic, without knowing future traffic.
- **Method:**
  - measure lightpath load every measurement period;
  - **high and low watermark thresholds** on load trigger an adaptation step;
  - at each step, add or delete **one lightpath at a time**;
  - choose the step by solving a mixed-integer linear program.
- **Assumptions:** measured, realistic backbone traffic.
- **Metrics:** unknown in detail (traffic adaptation quality).
- **Baselines:** the abstract contrasts the approach with prior work that redesigns the topology for an expected traffic pattern.
- **Findings:** the method "adapts very well" to traffic changes; the effects of the watermarks and the measurement period are studied.
- **Limitations:** unknown.
- **Relevance:** a peer-reviewed precedent for **threshold-triggered, incremental topology reconfiguration**, which is close in spirit to our *reactive* baseline.

### P13 Dimarogonas, Frazzoli & Johansson 2012
- **Problem:** event-driven controller updates for multi-agent agreement on resource-limited embedded hardware.
- **Method:** an agent updates when the ratio of a measurement error to a state-dependent norm crosses a threshold; centralised and distributed versions; a self-triggered extension.
- **Assumptions:** first-order agreement dynamics; agents know their neighbours' states.
- **Evaluation:** simulation examples.
- **Metrics, baselines, limitations:** unknown.
- **Relevance:** event triggering decides *when to communicate or actuate*, not when to change topology. It is a conceptual relative of TCCE-R's trigger.

### P14 Page 1954
- **Contribution:** introduced the cumulative-sum (CUSUM) scheme for detecting a change in a distribution parameter (a "quality number", e.g. a mean), with a criterion for when to take corrective action. Confirmed via the [CUSUM encyclopedia entry](https://en.wikipedia.org/wiki/CUSUM); the paper itself has no abstract.
- **Relevance:** TCCE-R's debt D_k = max(0, D_{k−1} + s_k − κ) is the one-sided CUSUM recursion. **P14 is the citation for it, so the debt accumulation is an established statistic, not a new invention.**

### P15 Gross & Blasius 2008
- **Problem:** reviews adaptive networks, which combine topological evolution with node dynamics, across fields from genomics to game theory.
- **Findings:** common themes are complex dynamics and robust topological self-organisation from simple local rules.
- **Metrics, baselines:** not applicable (review).
- **Relevance:** "topology–state co-evolution" is an established research field. TCCE-R's "co-evolution" wording must be positioned relative to it.

## 3. Comparison matrix (verified facts only)

✔ = addressed according to the abstract · ✘ = not addressed according to the abstract · ? = unknown from the abstract

| Paper | Consensus dynamics | Time-varying / failing links | Controller changes topology | Edge or cost budget | Reconfiguration cost or delay | Explicit trigger (*when*) rule | Accumulated (integrated) signal | Evaluation |
|---|---|---|---|---|---|---|---|---|
| P1 Olfati-Saber & Murray | ✔ | ✔ switching | ✘ | ✘ | ✔ communication delays only | ✘ | ✘ | theory + simulation |
| P2 Jadbabaie et al. | ✔ (headings) | ✔ neighbour sets change | ✘ | ✘ | ✘ | ✘ | ✘ | theory |
| P3 Xiao & Boyd | ✔ | ✘ fixed graph | ✘ (weights only) | ✘ | ✘ | ✘ | ✘ | optimisation + numerical |
| P4 Kar & Moura 2009 | ✔ | ✔ random link failures | ✘ | ✘ | ✘ | ✘ | ✘ | theory |
| P5 Kar & Moura 2008 | ✔ | ✔ random links | ✔ offline design | ✔ communication budget | ? | ✘ | ✘ | SDP + simulation |
| P6 Ghosh & Boyd | (λ₂ only) | ✘ | ✔ add edges | ✔ edge count | ✘ | ✘ | ✘ | heuristic + SDP bound |
| P7 Sydney et al. | (λ₂ only) | ? | ✔ rewire | ✔ constant edge count | ? | ? | ? | analytical + numerical |
| P8 Zavlanos et al. | applications | ✔ mobility | ✔ via mobility | ? | ? | ? | ? | framework / survey |
| P9 Sterbenz et al. | ✘ | ✔ challenges | framework | ? | ? | detect/remediate loop | ? | framework / survey |
| P10 Neumayer et al. | ✘ | ✔ geographic disasters | ✘ (assessment) | ✘ | ✘ | ✘ | ✘ | algorithms + backbone case |
| P11 LeBlanc et al. | ✔ resilient | adversarial nodes | ✘ | ✘ | ✘ | ✘ | ✘ | theory |
| P12 Gençata & Mukherjee | ✘ (traffic) | ✔ traffic changes | ✔ add/remove lightpaths | ? | ✔ one change per step | ✔ high/low watermarks | ✘ (per-period load) | MILP + simulation |
| P13 Dimarogonas et al. | ✔ agreement | ✘ | ✘ | ✘ | ✘ | ✔ event-triggered updates | ✘ | theory + simulation |
| P14 Page | ✘ | — | ✘ | ✘ | ✘ | ✔ alarm rule | ✔ CUSUM | statistics |
| P15 Gross & Blasius | node dynamics | ✔ | ✔ adaptive rules | ? | ? | ? | ? | review |
| **TCCE-R (ours, for reference)** | ✔ Metropolis averaging | ✔ transient, background, bursts, scripted | ✔ add/rewire | ✔ strict edge budget | ✔ break-before-make delay | ✔ D > Θ, adaptive Θ | ✔ CUSUM debt | simulation only |

### Which component of TCCE-R each paper informs

| TCCE-R component | Directly related papers |
|---|---|
| (1) Dynamic network state, failures | P4, P5 (random links); P10 (geographic failures) |
| (2) Consensus monitor (E, λ₂ ↔ speed) | P1, P2, P3, P4 |
| (3) Resilience debt (CUSUM) | P14; resilience framing P9 |
| (4) Trigger and threshold | P12 (watermarks), P13 (event-triggering), P14 (alarm rule) |
| (5) Coupling evaluator (Δλ₂ estimate) | P6, P7 |
| (6) Safety gate (λ₂ floor, connectivity) | P1 (λ₂ ↔ speed); P11 cautions that connectivity may not suffice |
| (7) Mutation selector (add / rewire) | P6 (add), P7 (rewire), P12 (incremental changes) |
| (8) Reconfigured network | P5, P8 |
| (9) Feedback loop | P9 (D²R² + DR control loop); P15 (co-evolution) |

## 4. Research gaps (my interpretation)

### 4a. Gaps observed within this set of 15 papers
These hold **for these papers only**. They are not claims about the whole literature.

1. **Fixed edge count and reconfiguration delay together.** None of the 15 abstracts combines a controller that changes the topology of a *consensus* network during operation, under a fixed edge count, with an explicit reconfiguration delay. P5–P7 optimise topology offline or for a static graph. P12 adapts online, but for traffic in optical networks, not consensus.
2. **When versus what.** None of the abstracts studies *when* to reconfigure as a question separate from *what* to change. P6, P7 and P5 address *what*; P12 and P13 use instantaneous thresholds for *when*.
3. **CUSUM-driven topology changes.** No abstract in this set uses an accumulated-evidence statistic (P14) to trigger topology changes.

### 4b. Hypotheses that still need a wider literature review
Each needs further searching before it can be stated as a gap:
- **H1: Online topology adaptation for consensus or gossip networks.** Search terms: "online algebraic connectivity maintenance", "dynamic topology control consensus", "rewiring under link failures". A preliminary web search found offline rewiring (P7, Chan & Akoglu 2016) but no online/failure-driven variant. **One search is not a review.**
- **H2: CUSUM / change detection used to trigger network reconfiguration.** CUSUM is widely used for traffic anomaly detection, so reconfiguration triggered by it may already exist in SDN or optical networking. Search before claiming novelty.
- **H3: Break-before-make reconfiguration cost in topology-control models.** Literature on SDN updates, optical reconfiguration and hitless switching likely models this. Not yet searched.
- **H4: Accumulated vs instantaneous triggering.** Whether it has been compared for *topology* adaptation; event-triggered control has comparisons for control updates.
- **H5: Resilience beyond λ₂.** P11 shows connectivity can be the wrong measure for adversarial settings. Whether this matters for benign failures is open in our reading.
- **Self-healing network literature** (e.g. Quattrociocchi et al. 2014; distributed self-healing data structures) has not been reviewed. It may overlap with TCCE-R's goal.

### 4c. Context for our negative result (interpretation, not evidence)
- P12 is a peer-reviewed precedent for **instantaneous, threshold-triggered incremental reconfiguration**, essentially our reactive baseline. So the baseline that beats TCCE-R is a recognised design, not a straw man.
- P14's CUSUM is designed to **delay action until evidence accumulates**. This trades detection delay for fewer false alarms. Our v0.4 finding fits that trade-off: reactive acted earlier and won when rewiring was cheap and beneficial. **This explanation is a hypothesis, not a demonstrated finding.**

## 5. Candidate baselines for the existing simulator (proposals; nothing implemented)

| Candidate | What it would test | Required changes / assumptions | Fairness notes |
|---|---|---|---|
| **B-P6 Fiedler greedy, periodic** (Ghosh & Boyd) | *what* heuristic without a trigger | Already effectively present: our selector uses the Fiedler-based Δλ₂ estimate, and the `periodic` policy applies it on a schedule. Needs only a citation and a check of the formula against P6. | Same gate, budget and failures |
| **B-P7 rewiring rule** (Sydney et al.) | a published rewiring heuristic in place of our removal rule (min first-order loss) | A new selector mode implementing P7's rule. **Needs the full text**; the rule is currently unknown. Keep the gate, budget and delay identical. | Compare with the same trigger so only *what* changes |
| **B-P12 watermark hysteresis** (Gençata & Mukherjee) | instantaneous trigger with separate high/low thresholds | A reactive variant: act when E > high; optionally a "release" rule when E < low. P12's objective is traffic load, so this is an **analogue**, not a reproduction. | Tune both thresholds on tuning seeds with equal effort |
| **B-P5 offline optimised static topology** (Kar & Moura 2008) | whether a well-designed static network makes adaptation unnecessary | Solve P5's SDP for the initial topology given failure probabilities and a budget. Needs an SDP solver (e.g. cvxpy, a new dependency) and **assumes known failure statistics**, which is more information than the online policies have. | Report as an oracle-informed baseline |
| **B-P13-style trigger** | ratio-based event trigger | Trigger when error ÷ state-norm exceeds σ. P13 triggers control updates, not topology changes, so the mapping is loose. | Low priority |
| P3 optimal weights | sensitivity check, not a baseline | Replace Metropolis weights with SDP-optimised weights for **all** policies. | Changes the consensus layer for every policy alike |
| P11 W-MSR resilient consensus | — | **Not applicable** without an adversarial-node model. Out of scope for benign failures. | — |
| P8 mobility-based control | — | **Not applicable**: node positions are fixed in our model. | — |

**Recommended first step:** read the full texts of P6, P7 and P12. Then decide whether to add B-P7 (rewiring rule) and B-P12 (watermark trigger). Both fit the existing policy interface and shared gate, and they would let the paper separate *what* from *when* using published designs.

## 6. Verified facts vs interpretation

**Verified in this pass:**
- the bibliographic data of the 15 core papers and 3 additional candidates;
- the content of each abstract as summarised in section 2.

**Interpretation (mine):**
- the relevance notes in section 2;
- the ✔/✘ cells where the abstract is indirect (e.g. "offline", "one change per step");
- everything in sections 4 and 5.

**Not claimed:** that TCCE-R is novel or superior. Our own held-out results (RESULTS_SUMMARY.md) show it losing to the reactive baseline, and novelty cannot be judged until the hypotheses in 4b have been searched.

### Sources used for verification
- Crossref REST API records for every DOI listed above.
- OpenAlex works API (abstracts for P1, P2, P6, P8, P10, P11, P12, P13, P15; Quattrociocchi et al.; Chan & Akoglu).
- Semantic Scholar Graph API (abstracts for P4, P5).
- [Boyd's paper page for P3](https://web.stanford.edu/~boyd/papers/fastavg.html).
- [Scholars' Mine record for P9](https://scholarsmine.mst.edu/ele_comeng_facwork/25).
- [MIT DSpace record for P10](https://dspace.mit.edu/handle/1721.1/58792).
- [ITU record for P12](https://avesis.itu.edu.tr/yayin/d4870e0f-8988-4d9b-8e24-235115c27abc/virtual-topology-adaptation-for-wdm-mesh-networks-under-dynamic-traffic).
- [DataLearner record for P7](https://datalearner.com/academic/journal-papers/0096-3003/volumes-and-issues/583/paper-detail/65149).
- [CUSUM entry for P14](https://en.wikipedia.org/wiki/CUSUM).
