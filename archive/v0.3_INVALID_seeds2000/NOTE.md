# INVALID: do not use these results

First binding-budget run, evaluated on seeds 2000-2029, before two harness defects were found:
1. Under the strict budget, no rewire was generated while the graph was disconnected (the Fiedler vector was
   required to rank removals). No policy could reconnect the network.
2. The selector spent its 30 gate attempts on candidates violating d_max (TCCE-R: 1170 degree rejections on
   tuning seeds 100-109), so a fired trigger often produced no mutation.

Both affected all policies but hit TCCE-R hardest: 148 of its 214 trigger firings on seeds 100-109 came
while disconnected. After the fixes, the protocol was re-run from the sweep onward, on fresh seeds 3000-3029.
These files are kept for transparency only.
