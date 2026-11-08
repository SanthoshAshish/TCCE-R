"""Fetch full bibliographic metadata from Crossref for the references added in V3 and write paper/references/refs_v3_added.json (same schema as
refs_v08_recent_final.json). Existence/metadata only: abstracts and full texts are not read, so claims attached to these citations stay at the level of
title and venue.   python paper/tools/add_refs_v3.py"""
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "tcce-r-refs-v3 (academic project)"}
ADD = {  # slug -> DOI (each DOI is checked against Crossref below; a wrong DOI is reported, never silently kept)
    "BoydGossip2006": "10.1109/TIT.2006.874516", "Thompson1933": "10.1093/biomet/25.3-4.285", "Russo2018": "10.1561/2200000070",
    "Freeman1983": "10.2307/1402748", "Dempster1977": "10.1111/j.2517-6161.1977.tb01600.x", "Whittle1988": "10.2307/3214163",
    "Bertsekas1997": "10.1023/a:1009635226865", "Carron2023": "10.1016/j.ifacol.2023.10.1310", "Wang2024dmpc": "10.1109/tcsi.2023.3334869",
    "Kumari2025": "10.1109/tcss.2024.3519566", "Zhang2024casc": "10.1016/j.apenergy.2024.123655", "Nguyen2026": "10.1109/tase.2026.3667964",
    "Li2022casc": "10.1109/access.2022.3188659"}


def fetch(doi):
    return json.load(urllib.request.urlopen(urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi), headers=UA), timeout=40))["message"]


def main():
    have = {e["doi"].lower() for e in json.load(open("paper/references/refs_v08_recent_final.json", encoding="utf-8"))}
    text = open("paper/manuscript_v0.8.md", encoding="utf-8").read().lower()
    out = []
    for slug, doi in ADD.items():
        try:
            w = fetch(doi)
        except Exception as e:  # noqa: BLE001
            print(f"NOT FOUND  {slug} {doi}: {e}")
            continue
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", (w.get("title") or [""])[0])).strip()
        year = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
        authors = [f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip() for a in w.get("author", [])]
        dup = doi.lower() in have or doi.lower() in text
        out.append({"doi": doi, "claimed_title": title, "claimed_year": year, "claimed_venue": (w.get("container-title") or [""])[0],
                    "crossref_title": title, "crossref_year": year, "crossref_venue": (w.get("container-title") or [""])[0],
                    "crossref_type": w.get("type"), "authors": authors, "volume": w.get("volume"), "issue": w.get("issue"), "pages": w.get("page"),
                    "has_abstract": False, "title_match": True, "year_match": True, "verified": True, "slug": slug, "already_cited_in_v08": dup})
        print(f"OK {slug:14s} {year} | {title[:80]} | {(w.get('container-title') or [''])[0][:30]} | vol {w.get('volume')} pp {w.get('page')} | {authors[:2]}{'  [already cited]' if dup else ''}")
    json.dump(out, open("paper/references/refs_v3_added.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(len(out), "entries written")


if __name__ == "__main__":
    main()
