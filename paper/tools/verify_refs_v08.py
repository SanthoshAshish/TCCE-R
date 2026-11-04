"""Verify candidate references against Crossref (live query) and record the evidence.

  python paper/tools/verify_refs_v08.py            # verifies paper/references/refs_v2_recent.json -> refs_v08_verification.json
  python paper/tools/verify_refs_v08.py --search "query" [--rows 8] [--from 2022]   # print Crossref candidates for a topic

A reference counts as VERIFIED here only if Crossref returns a record for its DOI whose title (normalised) and year match
the entry. This checks existence and bibliographic metadata; it does NOT check that a paper supports any particular claim.
"""
import argparse
import datetime
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "tcce-r-reference-check (academic project; mailto not provided)"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def work(doi):
    return get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]


def year(m):
    for k in ("issued", "published-print", "published-online"):
        if m.get(k, {}).get("date-parts", [[None]])[0][0]:
            return m[k]["date-parts"][0][0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="paper/references/refs_v2_recent.json")
    ap.add_argument("--out", default="paper/references/refs_v08_verification.json")
    ap.add_argument("--search")
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--from", dest="since", type=int, default=2022)
    a = ap.parse_args()
    if a.search:
        q = urllib.parse.urlencode({"query.bibliographic": a.search, "rows": a.rows, "filter": f"from-pub-date:{a.since}-01-01,type:journal-article",
                                    "select": "DOI,title,issued,container-title,author,type"})
        for m in get("https://api.crossref.org/works?" + q)["message"]["items"]:
            au = ", ".join(x.get("family", "") for x in m.get("author", [])[:3])
            print(m["DOI"], "|", year(m), "|", (m.get("title") or [""])[0][:110], "|", (m.get("container-title") or [""])[0][:40], "|", au)
        return
    refs = json.load(open(a.inp, encoding="utf-8"))
    out = []
    for r in refs:
        rec = {"doi": r["doi"], "claimed_title": r["title"], "claimed_year": r["year"], "claimed_venue": r.get("venue")}
        try:
            m = work(r["doi"])
            t = (m.get("title") or [""])[0]
            rec.update({"crossref_title": t, "crossref_year": year(m), "crossref_venue": (m.get("container-title") or [""])[0],
                        "crossref_type": m.get("type"), "authors": [f"{x.get('given', '')} {x.get('family', '')}".strip() for x in m.get("author", [])],
                        "volume": m.get("volume"), "issue": m.get("issue"), "pages": m.get("page") or m.get("article-number"),
                        "has_abstract": bool(m.get("abstract")), "title_match": norm(t) == norm(r["title"]) or norm(r["title"]) in norm(t) or norm(t) in norm(r["title"]),
                        "year_match": year(m) == r["year"]})
            rec["verified"] = bool(rec["title_match"] and rec["year_match"])
            if not rec["verified"]:
                rec["note"] = "Crossref record exists but title or year differs from the entry"
        except Exception as e:  # noqa: BLE001
            rec.update({"verified": False, "note": f"Crossref lookup failed: {e}"})
        out.append(rec)
        print(("OK  " if rec["verified"] else "FAIL"), r["doi"], rec.get("crossref_year"), (rec.get("crossref_title") or "")[:80], flush=True)
    json.dump({"retrieved": datetime.date.today().isoformat(), "source": "api.crossref.org", "entries": out},
              open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(sum(r["verified"] for r in out), "of", len(out), "verified")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
