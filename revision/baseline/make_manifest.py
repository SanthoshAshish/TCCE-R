"""Generate revision/baseline/baseline_manifest.json: SHA-256 of every baseline result/config/source file (read-only)."""
import hashlib, json, os, platform, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GROUPS = {"results_v0.7": "results/v0.7/eval", "results_v0.7_focused": "results/v0.7_focused/eval",
          "frozen_v0.7": "configs/v0.7/frozen", "frozen_v0.7_focused": "configs/v0.7_focused/frozen",
          "archive_v0.6": "archive/v0.6", "source_tccer": "tccer", "experiments": "experiments", "docs": "docs", "paper": "paper"}
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()
def git(*a): return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
out = {"git_head": git("rev-parse", "HEAD"), "git_branch": git("branch", "--show-current"),
       "git_dirty_files": git("status", "--short").splitlines(),
       "python": sys.version, "platform": platform.platform(), "packages": {}, "files": {}}
for m in ["numpy", "scipy", "pandas", "networkx", "matplotlib", "yaml", "pytest"]:
    try: out["packages"][m] = __import__(m).__version__
    except Exception as e: out["packages"][m] = f"unavailable: {e}"
for g, d in GROUPS.items():
    fs = {}
    for dp, dn, fn in os.walk(os.path.join(ROOT, d)):
        dn[:] = [x for x in dn if x != "__pycache__"]
        for f in sorted(fn):
            if f.endswith(".pyc") or f.endswith(".zip"): continue
            p = os.path.join(dp, f); fs[os.path.relpath(p, ROOT).replace("\\", "/")] = sha(p)
    out["files"][g] = fs
json.dump(out, open(os.path.join(ROOT, "revision/baseline/baseline_manifest.json"), "w"), indent=1)
print({g: len(v) for g, v in out["files"].items()}, out["git_head"])
