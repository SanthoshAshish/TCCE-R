# INVALID: do not use these results

Second binding-budget run (seeds 3000-3029), after the two fixes described in ../v0.3_INVALID_seeds2000/NOTE.md.
A third defect was then found; it dates back to v0.1:

3. The safety gate rejected a mutation if ANY node in the graph had degree > d_max, not just the endpoints of
   the new link. Some RGG nodes start above d_max = 10, so on those graphs every mutation was blocked until that
   node lost links. TCCE-R: 1500 degree rejections on tuning seeds 100-119, and 50 of its 91 trigger firings
   produced no mutation.

After the fix (flag `degree_fix`, which replaces `prefilter_degree`), the protocol was re-run from the sweep
onward, on fresh seeds 4000-4029. The config key `prefilter_degree` in these files no longer exists.
