"""Final live re-check of every reference in paper/manuscript_v0.8.md against Crossref (no changes are made to any file but the report).

  python paper/tools/recheck_refs_final.py     -> paper/references/refs_final_recheck.json (+ printed summary)

For each numbered reference with a DOI: the Crossref record must exist and (a) the year equals the year in the entry, (b) the normalised
Crossref title is contained in the entry text, (c) the first author's family name appears in the entry, (d) the volume and first page of the
entry agree with Crossref when Crossref has them. Any failure is reported as a MISMATCH for human review; nothing is auto-corrected.
This checks bibliographic metadata only, not that a paper supports the sentence that cites it."""
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "tcce-r-final-reference-check (academic project)"}


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def crossref(doi):
    req = urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=40))["message"]


def main():
    text = open("paper/manuscript_v0.8.md", encoding="utf-8").read()
    refs = re.findall(r"^\[(\d+)\] (.+)$", text.split("## References")[1], flags=re.M)
    out, bad = [], 0
    for n, line in refs:
        m = re.search(r"https://doi\.org/(\S+)", line)
        rec = {"n": int(n), "entry": line[:120]}
        if not m:
            rec["status"] = "NO DOI (not machine-verified)"
            out.append(rec)
            continue
        doi = m.group(1).rstrip(".")
        try:
            w = crossref(doi)
        except Exception as e:  # noqa: BLE001
            rec["status"] = f"CROSSREF ERROR {e}"
            bad += 1
            out.append(rec)
            continue
        issues = []
        y = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
        yr = re.search(r"\b(1[89]\d\d|20\d\d)\b", line)
        if y and yr and int(yr.group(1)) != y:
            issues.append(f"year entry {yr.group(1)} vs Crossref {y}")
        ct = norm((w.get("title") or [""])[0])
        if ct and ct not in norm(line):
            issues.append(f"title differs: Crossref '{ct[:70]}'")
        fam = (w.get("author") or [{}])[0].get("family", "")
        if fam and norm(fam) not in norm(line):
            issues.append(f"first author '{fam}' not in entry")
        vol = w.get("volume")
        if vol and not re.search(rf"\b{re.escape(vol)}\b", line):
            issues.append(f"volume {vol} not in entry")
        page = (w.get("page") or "").split("-")[0]
        if page and page not in ("1",) and not re.search(rf"\b{re.escape(page)}\b", line):
            issues.append(f"first page {page} not in entry")
        rec.update(doi=doi, crossref_year=y, status="OK" if not issues else "MISMATCH", issues=issues)
        bad += bool(issues)
        out.append(rec)
    json.dump(out, open("paper/references/refs_final_recheck.json", "w", encoding="utf-8"), indent=1)
    ok = sum(r["status"] == "OK" for r in out)
    print(f"{len(out)} references: {ok} OK, {bad} need review, {sum(r['status'].startswith('NO DOI') for r in out)} without DOI")
    for r in out:
        if r["status"] != "OK":
            print(r["n"], r["status"], r.get("issues", ""), "|", r["entry"])


if __name__ == "__main__":
    main()
