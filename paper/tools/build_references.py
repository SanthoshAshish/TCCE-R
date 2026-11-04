"""Verify every cited reference against Crossref and write paper/references/references_verified.json + references.md.

Nothing is typed by hand except the DOI (or, for Holm 1979, a bibliographic search). All title/author/venue/volume/
issue/pages/year fields come from the Crossref record. Run: python -I paper/tools/build_references.py
Crossref is queried sequentially with a generic User-Agent (no personal data).
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request

REFS = [  # key, DOI
    ("OlfatiSaberMurray2004", "10.1109/TAC.2004.834113"),
    ("OlfatiSaberFaxMurray2007", "10.1109/JPROC.2006.887293"),
    ("Jadbabaie2003", "10.1109/TAC.2003.812781"),
    ("XiaoBoyd2004", "10.1016/j.sysconle.2004.02.022"),
    ("XiaoBoydLall2005", "10.1109/IPSN.2005.1440896"),
    ("KarMoura2008", "10.1109/TSP.2008.920143"),
    ("KarMoura2009", "10.1109/TSP.2008.2007111"),
    ("Fiedler1973", "10.21136/CMJ.1973.101168"),
    ("GhoshBoyd2006", "10.1109/CDC.2006.377282"),
    ("Sydney2013", "10.1016/j.amc.2012.11.002"),
    ("Zavlanos2011", "10.1109/JPROC.2011.2157884"),
    ("Santi2005", "10.1145/1089733.1089736"),
    ("GrossBlasius2008", "10.1098/rsif.2007.1229"),
    ("Sterbenz2010", "10.1016/j.comnet.2010.03.005"),
    ("Neumayer2011", "10.1109/TNET.2011.2128879"),
    ("LeBlanc2013", "10.1109/JSAC.2013.130413"),
    ("GencataMukherjee2003", "10.1109/TNET.2003.810319"),
    ("Dimarogonas2012", "10.1109/TAC.2011.2174666"),
    ("Tabuada2007", "10.1109/TAC.2007.904277"),
    ("Page1954", "10.1093/biomet/41.1-2.100"),
    ("Quattrociocchi2014", "10.1371/journal.pone.0087986"),
    ("ChanAkoglu2016", "10.1007/s10618-015-0447-5"),
    ("Wilcoxon1945", "10.2307/3001968"),
    ("Efron1979", "10.1214/aos/1176344552"),
    ("Lakens2017", "10.1177/1948550617697177"),
    ("Barnett2005", "10.1093/ije/dyh299"),
]
UA = {"User-Agent": "tccer-paper-reference-check/1.0 (research project)"}


def fetch(url):
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed {url}: {last}")


def split_name(a):
    """Crossref sometimes stores a whole name in one field ('Jie Lin'); split it as given = all but last token."""
    given, family = a.get("given", ""), a.get("family", "") or a.get("name", "")
    if not given and " " in family.strip():                       # whole name in one field: given = all but last token
        parts = family.split()
        given, family = " ".join(parts[:-1]), parts[-1]
    if family.isupper() and len(family) > 1:
        family = family.capitalize()                              # 'PAGE' -> 'Page'
    return {"given": given, "family": family}


def record(msg):
    year = None
    for k in ("published-print", "published-online", "issued", "published"):
        if msg.get(k, {}).get("date-parts", [[None]])[0][0]:
            year = msg[k]["date-parts"][0][0]
            break
    return {"doi": msg.get("DOI"), "title": html.unescape(re.sub(r"<[^>]+>", "", (msg.get("title") or [""])[0]).strip()),
            "authors": [split_name(a) for a in msg.get("author", [])],
            "venue": html.unescape((msg.get("container-title") or [""])[0]), "volume": msg.get("volume"), "issue": msg.get("issue"),
            "pages": msg.get("page"), "year": year, "type": msg.get("type"), "publisher": msg.get("publisher")}


def initials(given):
    parts = re.split(r"[\s.]+", given.strip())
    return "".join(p[0] for p in parts if p)


def fmt(r):
    au = ", ".join(f"{a['family']} {initials(a['given'])}".strip() for a in r["authors"])
    out = f"{au} ({r['year']}) {r['title']}. "
    if r["type"] == "proceedings-article":
        out += f"In: {r['venue']}"
        out += f", pp {r['pages'].replace('-', '–')}. " if r["pages"] else ". "
    elif r["type"] == "thesis":
        out += f"{r['venue']}. "
    else:
        out += r["venue"]
        if r["volume"]:
            out += f" {r['volume']}"
            if r["issue"]:
                out += f"({r['issue']})"
        if r["pages"]:
            out += f":{r['pages'].replace('-', '–')}"
        out += ". "
    if r.get("doi"):
        return out + f"https://doi.org/{r['doi']}"
    return out + f"{r.get('url', '')}" + ("  [DOI NOT VERIFIED]" if r.get("verification") == "PARTIAL" else "")


CACHE = "paper/references/crossref_cache.json"


def main():
    import os
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    data = {}
    for key, doi in REFS:
        if doi not in cache:                                      # raw Crossref record, kept so reruns need no network
            cache[doi] = fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(1.2)
        msg = cache[doi]
        data[key] = record(msg)
        assert data[key]["doi"].lower() == doi.lower(), (key, doi, data[key]["doi"])
        print(f"OK  {key:26s} {data[key]['year']}  {data[key]['title'][:70]}")
    for r in data.values():
        r["verification"] = "Crossref record matches the requested DOI"
        r["notes"] = []
        if r["title"].isupper():                                  # Crossref stores some old titles in capitals
            r["title"] = r["title"].capitalize()
            r["notes"].append("title converted from capitals to sentence case")
    # Documented overrides: each one states the independent source used. Nothing is filled in from memory.
    data["XiaoBoydLall2005"]["year"] = 2005
    data["XiaoBoydLall2005"]["notes"].append("Crossref has no date; year 2005 is taken from the venue name in the same record "
                                             "('IPSN 2005. Fourth International Symposium on Information Processing in Sensor Networks')")
    data["Barnett2005"]["year"] = 2005
    data["Barnett2005"]["notes"].append("Crossref gives the online date 2004-08-27; the issue is Int J Epidemiol 34(1), February 2005 "
                                        "(PubMed 15333621, Ovid listing). Cited by issue year.")
    data["Wilcoxon1945"]["pages"] = "80-83"
    data["Wilcoxon1945"]["notes"].append("Crossref gives only the start page (80); 80-83 confirmed by several index listings. "
                                         "Whether the 1945 paper fully develops the SIGNED-RANK test is hedged in the sources "
                                         "consulted: author to verify this attribution against the original.")
    data["GencataMukherjee2003"]["authors"][0]["family"] = "Gençata"
    data["GencataMukherjee2003"]["notes"].append("Crossref prints the ASCII spelling 'Gencata'; the first author's own thesis prints "
                                                 "'Gençata', used here.")
    data["Efron1979"]["pages"] = "1-26"
    data["Efron1979"]["notes"].append("Crossref record has no page range; pages 1-26 confirmed on the Project Euclid record "
                                      "(projecteuclid.org/euclid.aos/1176344552)")
    data["Holm1979"] = {"doi": None, "title": "A simple sequentially rejective multiple test procedure",
                        "authors": [{"given": "Sture", "family": "Holm"}], "venue": "Scandinavian Journal of Statistics",
                        "volume": "6", "issue": "2", "pages": "65-70", "year": 1979, "type": "journal-article",
                        "url": "https://www.jstor.org/stable/4615733", "verification": "PARTIAL",
                        "notes": ["Not found in Crossref (10.2307/4615733 returns 404). Volume, issue, pages and JSTOR id 4615733 are "
                                  "confirmed only by secondary indexes (GESIS ZIS record; Wikipedia Holm-Bonferroni article). "
                                  "TO VERIFY on the publisher/JSTOR page before submission."]}
    data["Gencata2003Thesis"] = {"doi": None, "title": "Topology and bandwidth adaptation in optical WDM backbone networks with dynamic traffic",
                                 "authors": [{"given": "Ayşegül", "family": "Gençata"}], "venue": "PhD thesis, Istanbul Technical University, Institute of Science and Technology",
                                 "volume": None, "issue": None, "pages": None, "year": 2003, "type": "thesis",
                                 "url": "https://web.itu.edu.tr/gencata/pubs/AGthesis.pdf", "verification": "author-hosted full text read (139 pages)",
                                 "notes": ["Cited for the watermark trigger (Sect. 3.3, p. 39) and the history-window variant (Sect. 4.4.5, pp. 64-65). "
                                           "The thesis prints the name 'Ayşegül GENÇATA'; the journal record in Crossref lists 'A. Gencata'. "
                                           "The thesis lists the ToN paper as 'to appear' in April 2003; which thesis parts appear in the journal paper is unverified."]}
    json.dump(data, open("paper/references/references_verified.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    with open("paper/references/references_formatted_authoryear.md", "w", encoding="utf-8") as f:
        for key in sorted(data, key=lambda k: (data[k]["authors"][0]["family"], data[k]["year"])):
            f.write(f"- [{key}] {fmt(data[key])}\n")
    print("wrote references_verified.json and references_formatted_authoryear.md;", len(data), "records")


if __name__ == "__main__":
    main()
